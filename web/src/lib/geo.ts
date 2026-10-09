"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

/** The API only accepts points inside Bangladesh (BR Locations 1). */
const BD = { minLat: 20.5, maxLat: 26.7, minLng: 88.0, maxLng: 92.7 };

/** Gulshan 1, Dhaka: the labelled fallback when no Bangladeshi position is available (demo). */
export const DEMO_POINT = { lat: 23.781, lng: 90.414 };

export type Point = { lat: number; lng: number };

export function inBangladesh({ lat, lng }: Point): boolean {
  return lat >= BD.minLat && lat <= BD.maxLat && lng >= BD.minLng && lng <= BD.maxLng;
}

/**
 * Where the device is, and why not when it isn't known:
 * - ready: a usable position in Bangladesh
 * - outside: a real position, but outside Bangladesh (e.g. a reviewer abroad)
 * - denied: the user or browser blocked location for this site
 * - locating: still searching; `slow` once the quick fix timed out (GPS indoors can take a while)
 * - unavailable: the device said it has no position (location off in the OS, no signal);
 *   `detail` is the browser's own reason, shown small so a user can report it
 * - unsupported: the browser has no geolocation
 * - manual: no usable fix, so the spot the user tapped on the map is used instead
 */
export type GeoState =
  | { status: "locating"; slow?: boolean }
  | { status: "ready"; point: Point; accuracy: number }
  | { status: "outside"; point: Point; accuracy: number }
  | { status: "denied" }
  | { status: "unavailable"; detail: string }
  | { status: "unsupported" }
  | { status: "manual"; point: Point };

const PERMISSION_DENIED = 1;
const TIMEOUT = 3;
const RETRY_MS = 20_000; // no fix yet: ask the device again this often

/*
 * The spot set by tapping the map, for devices that can't give a position (e.g. Windows with
 * Location turned off, or a desktop with no Wi-Fi). Kept in this browser only, shared by every
 * screen through useSyncExternalStore.
 */
const MANUAL_KEY = "rokkha.manualPoint";
const manualListeners = new Set<() => void>();
let manualCache: { raw: string | null; point: Point | null } = { raw: null, point: null };

function readManual(): Point | null {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(MANUAL_KEY);
  } catch {
    /* storage blocked: nothing saved */
  }
  if (raw !== manualCache.raw) {
    let point: Point | null = null;
    try {
      const parsed = raw ? (JSON.parse(raw) as Point) : null;
      point = parsed && inBangladesh(parsed) ? parsed : null;
    } catch {
      point = null;
    }
    manualCache = { raw, point };
  }
  return manualCache.point;
}

/** Ask every location watcher on the page to start again now (the "Try again" button). */
const retryListeners = new Set<() => void>();
export function retryLocation() {
  retryListeners.forEach((fn) => fn());
}

/** Set (or clear, with null) the map-picked spot. Points outside Bangladesh are ignored. */
export function setManualPoint(point: Point | null) {
  if (point && !inBangladesh(point)) return false;
  try {
    if (point) localStorage.setItem(MANUAL_KEY, JSON.stringify(point));
    else localStorage.removeItem(MANUAL_KEY);
  } catch {
    /* storage blocked: the spot can't be kept */
  }
  manualListeners.forEach((fn) => fn());
  return true;
}

function subscribeManual(fn: () => void) {
  manualListeners.add(fn);
  return () => manualListeners.delete(fn);
}

export function useManualPoint(): Point | null {
  return useSyncExternalStore(subscribeManual, readManual, () => null);
}

/**
 * Watch the device position while `enabled`.
 *
 * A quick low-accuracy fix first (network/Wi-Fi, cached up to a minute) so something shows
 * within a second or two, then a high-accuracy watch with no timeout that keeps refining.
 * The old one-shot high-accuracy request with an 8 s timeout often failed on laptops without
 * GPS, which is why location used to fall back to the demo point.
 * A timeout of the quick fix is not a failure: the precise watch keeps searching. If permission is
 * granted later (site settings) the watch restarts on its own, and while the device reports no
 * position it asks again every 20 s. A real fix always wins over a spot set on the map.
 */
export function useGeolocation(enabled = true): GeoState {
  const [state, setState] = useState<GeoState>({ status: "locating" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      queueMicrotask(() => setState({ status: "unsupported" }));
      return;
    }
    let stopped = false;

    const onPosition = ({ coords }: GeolocationPosition) => {
      if (stopped) return;
      const point = { lat: coords.latitude, lng: coords.longitude };
      setState({ status: inBangladesh(point) ? "ready" : "outside", point, accuracy: coords.accuracy });
    };
    const onError = (error: GeolocationPositionError) => {
      if (stopped) return;
      // Keep a position we already have; otherwise say exactly what happened.
      setState((s) => {
        if (error.code === PERMISSION_DENIED) return { status: "denied" };
        if (s.status === "ready" || s.status === "outside") return s;
        if (error.code === TIMEOUT) return { status: "locating", slow: true };
        return { status: "unavailable", detail: `${error.code}: ${error.message || "position unavailable"}` };
      });
    };

    navigator.geolocation.getCurrentPosition(onPosition, onError, {
      enableHighAccuracy: false,
      maximumAge: 60_000,
      timeout: 15_000,
    });
    const watchId = navigator.geolocation.watchPosition(onPosition, onError, {
      enableHighAccuracy: true,
      maximumAge: 10_000,
    });

    const onRetry = () => {
      setState({ status: "locating" });
      setAttempt((n) => n + 1);
    };
    retryListeners.add(onRetry);

    // If the user allows location in site settings, start again without a reload.
    let permission: PermissionStatus | null = null;
    const onPermissionChange = () => {
      if (permission?.state === "granted") setAttempt((n) => n + 1);
    };
    navigator.permissions
      ?.query({ name: "geolocation" })
      .then((status) => {
        if (stopped) return;
        permission = status;
        status.addEventListener("change", onPermissionChange);
      })
      .catch(() => {});

    return () => {
      stopped = true;
      navigator.geolocation.clearWatch(watchId);
      retryListeners.delete(onRetry);
      permission?.removeEventListener("change", onPermissionChange);
    };
  }, [enabled, attempt]);

  // No fix (no signal / OS location off): try again periodically instead of giving up.
  const failed = state.status === "unavailable";
  useEffect(() => {
    if (!enabled || !failed) return;
    const id = setTimeout(() => setAttempt((n) => n + 1), RETRY_MS);
    return () => clearTimeout(id);
  }, [enabled, failed, attempt]);

  const manual = useManualPoint();
  if (!enabled) return { status: "locating" };
  if (state.status !== "ready" && manual) return { status: "manual", point: manual };
  return state;
}

export type ResolvedPoint = Point & { source: "device" | "manual" | "outside" | "denied" | "unavailable" };

/**
 * The point to send with an SOS or report: the device position when it is in Bangladesh, else
 * the spot set on the map, else the demo point together with the reason (so the UI can say why).
 * Waits up to `waitMs` for a first fix if location is still being found.
 */
export function useResolvePoint(geo: GeoState) {
  const latest = useRef(geo);
  useEffect(() => {
    latest.current = geo;
  }, [geo]);

  return async (waitMs = 10_000): Promise<ResolvedPoint> => {
    const deadline = Date.now() + waitMs;
    while (latest.current.status === "locating" && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 200));
    }
    const s = latest.current;
    if (s.status === "ready") return { ...s.point, source: "device" };
    if (s.status === "manual") return { ...s.point, source: "manual" };
    if (s.status === "outside") return { ...DEMO_POINT, source: "outside" };
    if (s.status === "denied") return { ...DEMO_POINT, source: "denied" };
    return { ...DEMO_POINT, source: "unavailable" };
  };
}
