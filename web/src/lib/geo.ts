"use client";

import { useEffect, useRef, useState } from "react";

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
 * - unavailable: allowed, but no fix yet after trying (no GPS/Wi-Fi signal)
 * - unsupported: the browser has no geolocation
 */
export type GeoState =
  | { status: "locating" }
  | { status: "ready"; point: Point; accuracy: number }
  | { status: "outside"; point: Point; accuracy: number }
  | { status: "denied" }
  | { status: "unavailable" }
  | { status: "unsupported" };

const PERMISSION_DENIED = 1;

/**
 * Watch the device position while `enabled`.
 *
 * A quick low-accuracy fix first (network/Wi-Fi, cached up to a minute) so something shows
 * within a second or two, then a high-accuracy watch with no timeout that keeps refining.
 * The old one-shot high-accuracy request with an 8 s timeout often failed on laptops without
 * GPS, which is why location used to fall back to the demo point.
 * If permission is granted later (site settings), the watch restarts on its own.
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
      if (error.code === PERMISSION_DENIED) setState({ status: "denied" });
      // Keep a position we already have; only report "unavailable" if we never got one.
      else setState((s) => (s.status === "ready" || s.status === "outside" ? s : { status: "unavailable" }));
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
      permission?.removeEventListener("change", onPermissionChange);
    };
  }, [enabled, attempt]);

  return enabled ? state : { status: "locating" };
}

export type ResolvedPoint = Point & { source: "device" | "outside" | "denied" | "unavailable" };

/**
 * The point to send with an SOS or report: the device position when it is in Bangladesh,
 * otherwise the demo point together with the reason (so the UI can say exactly why).
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
    if (s.status === "outside") return { ...DEMO_POINT, source: "outside" };
    if (s.status === "denied") return { ...DEMO_POINT, source: "denied" };
    return { ...DEMO_POINT, source: "unavailable" };
  };
}
