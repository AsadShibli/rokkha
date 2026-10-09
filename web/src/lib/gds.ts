"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "./api";
import type { Page } from "./incidents";

export type GdCategory = "lost_item" | "lost_document" | "missing_person" | "threat" | "harassment" | "other";
export type GdStatus = "submitted" | "under_review" | "approved" | "rejected";

export const GD_CATEGORIES: GdCategory[] = [
  "lost_item",
  "lost_document",
  "missing_person",
  "threat",
  "harassment",
  "other",
];

export type Gd = {
  id: number;
  gd_number: string;
  citizen_id: number;
  station_id: number;
  category: GdCategory;
  title: string;
  details: string;
  incident_date: string;
  status: GdStatus;
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
};

export type GdDraft = Pick<Gd, "category" | "title" | "details"> & { incident_date: string | null };

export type Station = { id: number; name: string; code: string; city: string; city_code: string; lat: number; lng: number };

export function useGds(query = "page_size=50") {
  return useQuery({
    queryKey: ["gds", query],
    queryFn: ({ signal }) => api.get<Page<Gd>>(`/gds?${query}`, signal),
  });
}

export function useStations() {
  return useQuery({
    queryKey: ["stations"],
    queryFn: ({ signal }) => api.get<Page<Station>>("/stations?page_size=100", signal),
    staleTime: 5 * 60_000,
  });
}

export const gdTone: Record<GdStatus, string> = {
  submitted: "bg-pending-soft text-pending",
  under_review: "bg-assigned-soft text-assigned",
  approved: "bg-resolved-soft text-resolved",
  rejected: "bg-sos-soft text-sos-strong",
};

/** Today in Dhaka as YYYY-MM-DD (the API checks "not in the future" in local time). */
export function todayInDhaka(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka" }).format(new Date());
}
