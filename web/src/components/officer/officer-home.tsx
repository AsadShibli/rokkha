"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Loader2, MapPin, Navigation, Power, Radio, Timer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app/app-shell";
import { LocationCard } from "@/components/location/location-card";
import { StatusBadge } from "@/components/incident/status-badge";
import { IncidentMap, type MapPin as Pin } from "@/components/map/incident-map";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { distanceKm, formatDateTime, formatTime } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { type Incident, type IncidentDetail, incidentKeys, useIncident, useIncidents } from "@/lib/incidents";
import { type OfficerProfile, useLocationSharing, useMe, useSetDuty } from "@/lib/officer";
import type { GeoState, Point } from "@/lib/geo";
import { useIncidentFeed } from "@/lib/realtime";
import { cn } from "@/lib/utils";

const ACTIVE = new Set(["assigned", "en_route"]);

export function OfficerHome() {
  return <AppShell roles={["officer"]}>{() => <Home />}</AppShell>;
}

function Home() {
  const { t, locale } = useI18n();
  const me = useMe();
  const officer = me.data?.officer ?? null;
  // Poll for new assignments; the open incident itself streams over the WebSocket.
  const incidents = useIncidents("page_size=10", 5_000, true);
  const active = incidents.data?.items.find((i) => ACTIVE.has(i.status) && i.officer?.id === officer?.id);
  const history = incidents.data?.items.filter((i) => i !== active) ?? [];
  const queryClient = useQueryClient();
  const activeId = active?.id;

  // A new assignment (or one ending) changes duty_status on the server: refresh the profile so
  // the "busy" pill and the disabled off-duty button follow it.
  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: ["me"] });
  }, [activeId, queryClient]);

  const onDuty = !!officer && officer.duty_status !== "off_duty";
  const sharing = useLocationSharing(onDuty, officer?.last_lat ?? null, officer?.last_lng ?? null);

  if (me.isLoading || !officer) return <div className="h-64 animate-pulse rounded-[28px] bg-cream" />;

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <div className="flex flex-col gap-4">
        <DutyCard officer={officer} sharing={sharing} />
        <section className="rounded-3xl border border-line bg-white p-5">
          <h2 className="font-semibold">{t.officer.history}</h2>
          {history.length ? (
            <ul className="mt-3 flex flex-col">
              {history.map((incident) => (
                <li key={incident.id} className="flex items-center justify-between gap-3 py-2.5">
                  <span>
                    <span className="block text-sm font-medium">
                      {t.incident.types[incident.type]} #{incident.id}
                    </span>
                    <span className="text-xs text-muted">{formatDateTime(incident.created_at, locale)}</span>
                  </span>
                  <StatusBadge status={incident.status} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">{t.officer.noHistory}</p>
          )}
        </section>
      </div>

      {active ? (
        <ActiveIncident incident={active} officer={officer} />
      ) : (
        <section className="bg-warm grid min-h-[360px] place-items-center rounded-[28px] p-8 text-center">
          <div>
            <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-white text-accent-strong shadow-card">
              <Radio className="h-7 w-7" />
            </span>
            <h2 className="mt-5 text-xl font-semibold">{t.officer.waiting}</h2>
            <p className="mt-1.5 text-muted">{onDuty ? t.officer.waitingBody : t.officer.offDutyBody}</p>
          </div>
        </section>
      )}
    </div>
  );
}

function DutyCard({
  officer,
  sharing,
}: {
  officer: OfficerProfile;
  sharing: { geo: GeoState; lastSent: { at: Date; point: Point } | null; demo: boolean };
}) {
  const { t, locale } = useI18n();
  const setDuty = useSetDuty();
  const busy = officer.duty_status === "busy";
  const onDuty = officer.duty_status !== "off_duty";

  return (
    <section className="rounded-3xl bg-white p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold">{officer.user.name}</p>
          <p className="text-sm text-muted">
            {officer.rank} · {t.officer.badge} {officer.badge_no}
          </p>
        </div>
        <span
          className={cn(
            "rounded-full px-2.5 py-1 text-xs font-semibold",
            busy ? "bg-en-route-soft text-en-route" : onDuty ? "bg-resolved-soft text-resolved" : "bg-cancelled-soft text-cancelled",
          )}
        >
          {busy ? t.officer.busy : onDuty ? t.officer.onDuty : t.officer.offDuty}
        </span>
      </div>

      <Button
        className="mt-5 w-full"
        variant={onDuty ? "outline" : "primary"}
        disabled={busy || setDuty.isPending}
        onClick={() => setDuty.mutate(onDuty ? "off_duty" : "available")}
      >
        {setDuty.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Power className="h-4 w-4" />}
        {onDuty ? t.officer.goOffDuty : t.officer.goOnDuty}
      </Button>
      <p className="mt-3 text-xs text-muted">{t.officer.dutyHint}</p>

      {onDuty && (
        <div className="mt-4">
          <LocationCard
            geo={sharing.geo}
            title={t.location.officerTitle}
            kind="officer"
            fallback={
              sharing.lastSent?.point ??
              (officer.last_lat != null && officer.last_lng != null
                ? { lat: officer.last_lat, lng: officer.last_lng }
                : undefined)
            }
            footer={
              <p className="mt-1.5 text-xs font-medium text-ink-soft">
                {sharing.demo ? t.location.keepingFresh : t.location.sharingLive}
                {sharing.lastSent &&
                  ` · ${t.location.lastSent.replace("{t}", formatTime(sharing.lastSent.at.toISOString(), locale))}`}
              </p>
            }
          />
        </div>
      )}
    </section>
  );
}

function ActiveIncident({ incident, officer }: { incident: Incident; officer: OfficerProfile }) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const detail = useIncident(incident.id);
  useIncidentFeed(incident.id); // a citizen cancel or admin reassign shows up immediately
  const data: Incident = detail.data ?? incident;
  const [note, setNote] = useState("");

  const act = useMutation({
    mutationFn: (action: "accept" | "resolve") =>
      api.post<IncidentDetail>(`/incidents/${incident.id}/${action}`, note.trim() ? { note: note.trim() } : undefined),
    onSuccess: (updated) => {
      queryClient.setQueryData(incidentKeys.detail(incident.id), updated);
      setNote("");
      void queryClient.invalidateQueries({ queryKey: ["incidents", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });

  const me = data.officer ?? officer;
  const pins = useMemo<Pin[]>(() => {
    const list: Pin[] = [{ id: "target", lat: data.lat, lng: data.lng, kind: data.type === "sos" ? "sos" : "report" }];
    if (me.last_lat != null && me.last_lng != null) list.push({ id: "me", lat: me.last_lat, lng: me.last_lng, kind: "officer" });
    return list;
  }, [data.lat, data.lng, data.type, me.last_lat, me.last_lng]);

  const km =
    me.last_lat != null && me.last_lng != null
      ? distanceKm({ lat: data.lat, lng: data.lng }, { lat: me.last_lat, lng: me.last_lng })
      : null;
  const assigned = data.status === "assigned";
  const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${data.lat},${data.lng}`;

  return (
    <section className="overflow-hidden rounded-[28px] border border-line bg-white shadow-card">
      <div className="relative h-[42vh] min-h-[280px]">
        <IncidentMap pins={pins} />
      </div>
      <div className="p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={data.status} />
          <span className="text-xs text-muted">
            {t.incident.types[data.type]} #{data.id} · {formatTime(data.created_at, locale)}
          </span>
        </div>
        <h2 className="mt-3 text-2xl font-bold tracking-tight">
          {assigned ? t.officer.assignedTitle : t.officer.enRouteTitle}
        </h2>
        <p className="mt-1 flex items-center gap-1.5 text-muted">
          <MapPin className="h-4 w-4" />
          {km !== null
            ? t.officer.away.replace("{km}", km.toLocaleString(locale === "bn" ? "bn-BD" : "en", { maximumFractionDigits: 1 }))
            : `${data.lat.toFixed(4)}, ${data.lng.toFixed(4)}`}
        </p>
        {data.station && (
          <p className="mt-1 text-sm text-muted">{t.incident.handledBy.replace("{name}", data.station.name)}</p>
        )}
        {data.description && <p className="mt-4 rounded-2xl bg-cream/70 p-3.5 text-sm">{data.description}</p>}
        {assigned && (
          <p className="mt-4 flex items-center gap-2 text-sm text-pending">
            <Timer className="h-4 w-4" /> {t.officer.acceptSoon}
          </p>
        )}

        {!assigned && (
          <label className="mt-5 flex flex-col gap-1.5 text-sm font-medium text-ink-soft">
            {t.officer.noteLabel}
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t.officer.notePlaceholder}
              maxLength={500}
              className="h-11 rounded-xl border border-line px-3.5 font-normal text-ink outline-none focus:border-accent-strong focus:ring-4 focus:ring-accent/20"
            />
          </label>
        )}

        <div className="mt-5 flex flex-wrap gap-2.5">
          <Button
            size="lg"
            variant={assigned ? "sos" : "primary"}
            disabled={act.isPending}
            onClick={() => act.mutate(assigned ? "accept" : "resolve")}
            className="flex-1"
          >
            {act.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : assigned ? (
              <Navigation className="h-4 w-4" />
            ) : (
              <BadgeCheck className="h-4 w-4" />
            )}
            {assigned ? t.officer.accept : t.officer.resolve}
          </Button>
          <a
            href={mapsUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-13 items-center gap-2 rounded-xl border border-line px-5 font-medium hover:border-ink/30"
          >
            <Navigation className="h-4 w-4" /> {t.officer.navigate}
          </a>
        </div>
        {act.error && (
          <p role="alert" className="mt-3 text-sm text-sos-strong">
            {act.error instanceof ApiError ? act.error.message : t.errors.generic}
          </p>
        )}
      </div>
    </section>
  );
}
