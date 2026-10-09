"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api } from "./api";
import { DEMO_POINT, inBangladesh, type Point } from "./geo";
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

const SEND_EVERY_MS = 10_000;
const DEMO_SEND_EVERY_MS = 30_000;

/**
 * While `enabled`, stream the device position to PATCH /officers/me/location (at most every
 * 10 s). If the browser can't give a Bangladeshi position (desktop demo), re-send the last known
 * point every 30 s instead, so the officer stays "reachable" (seen in the last 10 minutes).
 */
export function useLocationSharing(enabled: boolean, lastLat: number | null, lastLng: number | null) {
  const [lastSent, setLastSent] = useState<Date | null>(null);
  const [demo, setDemo] = useState(false);
  const lastAt = useRef(0);
  const fallback = useRef<Point>(DEMO_POINT);

  useEffect(() => {
    if (lastLat !== null && lastLng !== null) fallback.current = { lat: lastLat, lng: lastLng };
  }, [lastLat, lastLng]);

  useEffect(() => {
    if (!enabled) return;
    let stopped = false;

    const send = async (point: Point, isDemo: boolean) => {
      lastAt.current = Date.now();
      try {
        await api.patch("/officers/me/location", point);
        if (stopped) return;
        setLastSent(new Date());
        setDemo(isDemo);
      } catch {
        /* next tick retries */
      }
    };

    let watchId: number | null = null;
    let demoTimer: ReturnType<typeof setInterval> | null = null;
    const startDemo = () => {
      if (demoTimer) return;
      void send(fallback.current, true);
      demoTimer = setInterval(() => void send(fallback.current, true), DEMO_SEND_EVERY_MS);
    };

    if (typeof navigator !== "undefined" && navigator.geolocation) {
      watchId = navigator.geolocation.watchPosition(
        ({ coords }) => {
          const point = { lat: coords.latitude, lng: coords.longitude };
          if (!inBangladesh(point)) return startDemo();
          if (demoTimer) {
            clearInterval(demoTimer);
            demoTimer = null;
          }
          if (Date.now() - lastAt.current >= SEND_EVERY_MS) void send(point, false);
        },
        () => startDemo(),
        { enableHighAccuracy: true, maximumAge: 5_000, timeout: 10_000 },
      );
    } else {
      startDemo();
    }

    return () => {
      stopped = true;
      if (watchId !== null) navigator.geolocation.clearWatch(watchId);
      if (demoTimer) clearInterval(demoTimer);
    };
  }, [enabled]);

  return { lastSent, demo };
}
