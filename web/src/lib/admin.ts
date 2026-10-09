"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "./api";
import type { Page } from "./incidents";
import type { OfficerProfile } from "./officer";

export type DashboardStats = {
  station_id: number | null;
  incidents: Record<string, number>;
  open_sos: number;
  gds: Record<string, number>;
  officers: Record<string, number>;
  avg_response_seconds_7d: number | null;
};

const POLL_MS = 10_000;

const withStation = (query: string, stationId: number | null) =>
  stationId ? `${query}${query ? "&" : ""}station_id=${stationId}` : query;

export function useStats(stationId: number | null) {
  return useQuery({
    queryKey: ["dashboard", stationId],
    queryFn: ({ signal }) => api.get<DashboardStats>(`/dashboard/stats?${withStation("", stationId)}`, signal),
    refetchInterval: POLL_MS,
  });
}

export function useOfficers(stationId: number | null, extra = "", refetchInterval?: number) {
  const query = withStation(`page_size=100${extra}`, stationId);
  return useQuery({
    queryKey: ["officers", query],
    queryFn: ({ signal }) => api.get<Page<OfficerProfile>>(`/officers?${query}`, signal),
    refetchInterval,
  });
}

export { POLL_MS, withStation };

/** "4m 12s" from seconds. */
export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m ? `${m}m ${s}s` : `${s}s`;
}

export function minutesSince(iso: string | null): number | null {
  return iso ? Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000)) : null;
}
