"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "./api";
import { distanceKm } from "./format";
import { DEMO_POINT, type Point, useGeolocation } from "./geo";
import type { User } from "./types";

export type DutyStatus = "off_duty" | "available" | "busy";

export type OfficerProfile = {
  id: number;
  user: { id: number; name: string; phone: string };
  station_id: number;
  badge_no: string;
  rank: string;
  duty_status: DutyStatus;
  last_lat: number | null;
  last_lng: number | null;
  last_seen_at: string | null;
};

export type Me = User & { officer: OfficerProfile | null };

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: ({ signal }) => api.get<Me>("/users/me", signal) });
}

export function useSetDuty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (duty_status: "available" | "off_duty") =>
      api.patch<OfficerProfile>("/officers/me/status", { duty_status }),
    onSuccess: (officer) =>
      queryClient.setQueryData<Me>(["me"], (me) => (me ? { ...me, officer } : me)),
  });
}

const SEND_EVERY_MS = 10_000; // while moving: at most this often...
const MOVED_KM = 0.025; // ...or immediately after moving 25 m
const KEEPALIVE_MS = 30_000; // standing still: re-send so the officer stays "reachable"

/**
 * While `enabled` (on duty), share the device position with PATCH /officers/me/location,
 * automatically, with nothing to click: right away, after every 25 m moved (at most every
 * 10 s), and every 30 s while standing still, which keeps the officer inside the 10-minute
 * "reachable" window.
 *
 * Without a usable Bangladeshi fix (blocked, no signal, or a reviewer abroad) it shares the spot
 * the officer set on the map, or else keeps the last known position fresh, and `geo.status` says
 * which, so the screen can tell the officer.
 */
export function useLocationSharing(enabled: boolean, lastLat: number | null, lastLng: number | null) {
  const geo = useGeolocation(enabled);
  const [lastSent, setLastSent] = useState<{ at: Date; point: Point } | null>(null);
  const sentRef = useRef<{ at: number; point: Point } | null>(null);
  const geoRef = useRef(geo);
  const fallback = useRef<Point>(DEMO_POINT);

  useEffect(() => {
    geoRef.current = geo;
  }, [geo]);
  useEffect(() => {
    if (lastLat !== null && lastLng !== null) fallback.current = { lat: lastLat, lng: lastLng };
  }, [lastLat, lastLng]);

  const send = useCallback(async (point: Point) => {
    sentRef.current = { at: Date.now(), point };
    try {
      await api.patch("/officers/me/location", point);
      setLastSent({ at: new Date(), point });
    } catch {
      /* the next tick retries */
    }
  }, []);

  // A fresh device fix (or a newly set map spot): send if we moved 25 m or 10 s have passed.
  useEffect(() => {
    if (!enabled || (geo.status !== "ready" && geo.status !== "manual")) return;
    const prev = sentRef.current;
    if (!prev || Date.now() - prev.at >= SEND_EVERY_MS || distanceKm(prev.point, geo.point) > MOVED_KM) {
      void send(geo.point);
    }
  }, [enabled, geo, send]);

  // No usable fix or map spot (blocked / no signal / abroad): keep the last known position fresh.
  const noFix = geo.status !== "ready" && geo.status !== "manual" && geo.status !== "locating";
  useEffect(() => {
    if (enabled && noFix && !sentRef.current) void send(fallback.current);
  }, [enabled, noFix, send]);

  // Standing still or no fix: re-send every 30 s.
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => {
      const g = geoRef.current;
      void send(g.status === "ready" || g.status === "manual" ? g.point : fallback.current);
    }, KEEPALIVE_MS);
    return () => clearInterval(id);
  }, [enabled, send]);

  useEffect(() => {
    if (!enabled) sentRef.current = null;
  }, [enabled]);

  return { geo, lastSent, demo: enabled && noFix };
}
