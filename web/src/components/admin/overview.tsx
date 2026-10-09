"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, Clock3, FileText, Loader2, Radio, ShieldCheck, Siren, UserCheck, X } from "lucide-react";
import { useMemo, useState } from "react";

import { AdminNav } from "@/components/admin/admin-nav";
import { StationFilter } from "@/components/admin/station-filter";
import { AppShell } from "@/components/app/app-shell";
import { StatusBadge } from "@/components/incident/status-badge";
import { IncidentMap, type MapPin } from "@/components/map/incident-map";
import { Button } from "@/components/ui/button";
import { formatDuration, minutesSince, POLL_MS, useOfficers, useStats, withStation } from "@/lib/admin";
import { api, ApiError } from "@/lib/api";
import { formatTime } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { type Incident, type IncidentDetail, OPEN_STATUSES, useIncidents } from "@/lib/incidents";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";

export function AdminOverview() {
  return (
    <AppShell roles={["station_admin", "super_admin"]}>
      {(user) => (
        <>
          <AdminNav role={user.role} />
          <Overview user={user} />
        </>
      )}
    </AppShell>
  );
}

function Overview({ user }: { user: User }) {
  const { t, locale } = useI18n();
  const isSuper = user.role === "super_admin";
  const [stationId, setStationId] = useState<number | null>(null);
  const [assigning, setAssigning] = useState<Incident | null>(null);

  const stats = useStats(stationId);
  const officers = useOfficers(stationId, "", POLL_MS);
  const incidents = useIncidents(withStation("page_size=50", stationId), POLL_MS);
  const open = useMemo(
    () => (incidents.data?.items ?? []).filter((i) => OPEN_STATUSES.includes(i.status)),
    [incidents.data],
  );

  const pins = useMemo<MapPin[]>(() => {
    const list: MapPin[] = open.map((i) => ({
      id: `i${i.id}`,
      lat: i.lat,
      lng: i.lng,
      kind: i.type === "sos" ? "sos" : "report",
      label: `${i.type.toUpperCase()} #${i.id}`,
    }));
    for (const o of officers.data?.items ?? []) {
      if (o.duty_status !== "off_duty" && o.last_lat != null && o.last_lng != null) {
        list.push({ id: `o${o.id}`, lat: o.last_lat, lng: o.last_lng, kind: "officer", label: o.user.name });
      }
    }
    return list;
  }, [open, officers.data]);

  const s = stats.data;
  const tiles = [
    { icon: Siren, label: t.admin.tiles.openSos, value: s?.open_sos, tone: "text-sos-strong bg-sos-soft" },
    { icon: Clock3, label: t.admin.tiles.pending, value: s?.incidents.pending, tone: "text-pending bg-pending-soft" },
    { icon: Activity, label: t.admin.tiles.active, value: s?.officers.busy, tone: "text-en-route bg-en-route-soft" },
    { icon: UserCheck, label: t.admin.tiles.available, value: s?.officers.available, tone: "text-resolved bg-resolved-soft" },
    {
      icon: ShieldCheck,
      label: t.admin.tiles.response,
      value: s ? (s.avg_response_seconds_7d === null ? t.admin.noData : formatDuration(s.avg_response_seconds_7d)) : undefined,
      tone: "text-accent-strong bg-accent-soft",
    },
    {
      icon: FileText,
      label: t.admin.tiles.gds,
      value: s ? (s.gds.submitted ?? 0) + (s.gds.under_review ?? 0) : undefined,
      tone: "text-assigned bg-assigned-soft",
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{isSuper && !stationId ? t.admin.cityTitle : t.admin.overviewTitle}</h1>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted">
            <span className="h-2 w-2 animate-pulse rounded-full bg-resolved" /> {t.admin.refreshed}
          </p>
        </div>
        {isSuper && <StationFilter value={stationId} onChange={setStationId} />}
      </div>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {tiles.map(({ icon: Icon, label, value, tone }) => (
          <div key={label} className="rounded-3xl bg-white p-4 shadow-card">
            <span className={cn("grid h-9 w-9 place-items-center rounded-xl", tone)}>
              <Icon className="h-4 w-4" />
            </span>
            <p className="mt-3 text-2xl font-bold tracking-tight">
              {value === undefined ? <span className="inline-block h-7 w-10 animate-pulse rounded bg-cream" /> : value}
            </p>
            <p className="mt-0.5 text-xs text-muted">{label}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-5 lg:grid-cols-[1fr_400px]">
        <section className="relative h-[420px] overflow-hidden rounded-[28px] border border-line shadow-card lg:h-[560px]">
          <IncidentMap pins={pins} zoom={13} />
          <span className="absolute top-3 left-3 rounded-full bg-white/95 px-3 py-1 text-xs font-semibold shadow-card">
            {t.admin.mapTitle}
          </span>
        </section>

        <section className="flex max-h-[560px] flex-col rounded-[28px] bg-white shadow-card">
          <h2 className="border-b border-line px-5 py-4 font-semibold">
            {t.admin.queueTitle} <span className="text-muted">({open.length})</span>
          </h2>
          <ul className="flex-1 divide-y divide-line overflow-y-auto">
            {open.length === 0 && (
              <li className="flex flex-col items-center gap-2 px-5 py-12 text-center text-sm text-muted">
                <Radio className="h-5 w-5" /> {t.admin.queueEmpty}
              </li>
            )}
            {open.map((incident) => (
              <li key={incident.id} className="px-5 py-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold">
                    {t.incident.types[incident.type]} #{incident.id}
                  </span>
                  <StatusBadge status={incident.status} />
                </div>
                <p className="mt-1 text-xs text-muted">
                  {formatTime(incident.created_at, locale)}
                  {incident.officer &&
                    ` · ${incident.officer.name}${incident.officer.badge_no ? ` (${incident.officer.badge_no})` : ""}`}
                </p>
                {incident.description && <p className="mt-1.5 line-clamp-2 text-sm text-ink-soft">{incident.description}</p>}
                {user.role === "station_admin" && (
                  <Button size="sm" variant={incident.status === "pending" ? "primary" : "outline"} className="mt-3" onClick={() => setAssigning(incident)}>
                    {t.admin.reassign}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>
      </div>

      {assigning && <AssignDialog incident={assigning} onClose={() => setAssigning(null)} />}
    </div>
  );
}

function AssignDialog({ incident, onClose }: { incident: Incident; onClose: () => void }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  // The station admin's officer list is already scoped to their station by the API.
  const officers = useOfficers(null, "&duty_status=available");
  const candidates = (officers.data?.items ?? []).filter((o) => o.id !== incident.officer?.id);

  const assign = useMutation({
    mutationFn: (officerId: number) => api.post<IncidentDetail>(`/incidents/${incident.id}/reassign`, { officer_id: officerId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["incidents"] });
      void queryClient.invalidateQueries({ queryKey: ["officers"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-4 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="assign-title">
      <div className="w-full max-w-md rounded-[28px] bg-white p-6 shadow-float">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="assign-title" className="text-lg font-semibold">
              {t.admin.reassignTitle}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {t.incident.types[incident.type]} #{incident.id} · {t.admin.reassignHint}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-muted hover:bg-cream hover:text-ink">
            <X className="h-5 w-5" />
          </button>
        </div>
        <ul className="mt-4 flex max-h-80 flex-col gap-2 overflow-y-auto">
          {officers.isLoading && <li className="h-14 animate-pulse rounded-2xl bg-cream" />}
          {officers.data && candidates.length === 0 && <li className="py-6 text-center text-sm text-muted">{t.admin.noOfficers}</li>}
          {candidates.map((o) => {
            const mins = minutesSince(o.last_seen_at);
            return (
              <li key={o.id} className="flex items-center justify-between gap-3 rounded-2xl border border-line p-3">
                <div>
                  <p className="text-sm font-semibold">{o.user.name}</p>
                  <p className="text-xs text-muted">
                    {o.rank} · {mins === null ? t.admin.seenNever : t.admin.seen.replace("{m}", String(mins))}
                  </p>
                </div>
                <Button size="sm" disabled={assign.isPending} onClick={() => assign.mutate(o.id)}>
                  {assign.isPending && assign.variables === o.id && <Loader2 className="h-4 w-4 animate-spin" />}
                  {t.admin.assignTo}
                </Button>
              </li>
            );
          })}
        </ul>
        {assign.error && (
          <p role="alert" className="mt-3 text-sm text-sos-strong">
            {assign.error instanceof ApiError ? assign.error.message : t.errors.generic}
          </p>
        )}
      </div>
    </div>
  );
}
