"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "./api";

export type IncidentStatus = "pending" | "assigned" | "en_route" | "resolved" | "cancelled";
export type IncidentType = "sos" | "report";

export type OfficerBrief = {
  id: number;
  name: string;
  rank: string;
  phone: string;
  last_lat: number | null;
  last_lng: number | null;
};

export type IncidentEvent = {
  id: number;
  from_status: IncidentStatus | null;
  to_status: IncidentStatus;
  actor_id: number | null;
  officer_id: number | null;
  note: string | null;
  created_at: string;
};

export type Incident = {
  id: number;
  type: IncidentType;
  status: IncidentStatus;
  lat: number;
  lng: number;
  description: string | null;
  station_id: number;
  citizen_id: number;
  officer: OfficerBrief | null;
  created_at: string;
  assigned_at: string | null;
  accepted_at: string | null;
  resolved_at: string | null;
  cancelled_at: string | null;
};

export type IncidentDetail = Incident & { events: IncidentEvent[] };

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export const OPEN_STATUSES: IncidentStatus[] = ["pending", "assigned", "en_route"];

export const incidentKeys = {
  all: ["incidents"] as const,
  list: (query: string) => ["incidents", "list", query] as const,
  detail: (id: number) => ["incidents", "detail", id] as const,
};

export function useIncident(id: number) {
  return useQuery({
    queryKey: incidentKeys.detail(id),
    queryFn: ({ signal }) => api.get<IncidentDetail>(`/incidents/${id}`, signal),
    enabled: Number.isFinite(id),
  });
}

export function useIncidents(query = "page_size=20", refetchInterval?: number, inBackground = false) {
  return useQuery({
    queryKey: incidentKeys.list(query),
    queryFn: ({ signal }) => api.get<Page<Incident>>(`/incidents?${query}`, signal),
    refetchInterval,
    // Officers must hear about a new SOS even with the tab in the background.
    refetchIntervalInBackground: inBackground,
  });
}

/** Tailwind classes per status, from the design tokens. */
export const statusTone: Record<IncidentStatus, string> = {
  pending: "bg-pending-soft text-pending",
  assigned: "bg-assigned-soft text-assigned",
  en_route: "bg-en-route-soft text-en-route",
  resolved: "bg-resolved-soft text-resolved",
  cancelled: "bg-cancelled-soft text-cancelled",
};

export const statusDot: Record<IncidentStatus, string> = {
  pending: "bg-pending",
  assigned: "bg-assigned",
  en_route: "bg-en-route",
  resolved: "bg-resolved",
  cancelled: "bg-cancelled",
};
