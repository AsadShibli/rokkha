"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Phone, Wifi, WifiOff } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/app/app-shell";
import { StatusBadge } from "@/components/incident/status-badge";
import { Timeline } from "@/components/incident/timeline";
import { IncidentMap, type MapPin } from "@/components/map/incident-map";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { distanceKm } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { type IncidentDetail, incidentKeys, OPEN_STATUSES, useIncident } from "@/lib/incidents";
import { useIncidentFeed } from "@/lib/realtime";
import { cn } from "@/lib/utils";

export function CitizenIncidentView() {
  return <AppShell roles={["citizen"]}>{() => <View />}</AppShell>;
}

function View() {
  const { t, locale } = useI18n();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const queryClient = useQueryClient();
  const incident = useIncident(id);
  const data = incident.data;
  const live = useIncidentFeed(id, !!data && OPEN_STATUSES.includes(data.status));
  const [confirming, setConfirming] = useState(false);

  const cancel = useMutation({
    mutationFn: () => api.post<IncidentDetail>(`/incidents/${id}/cancel`),
    onSuccess: (updated) => {
      queryClient.setQueryData(incidentKeys.detail(id), updated);
      void queryClient.invalidateQueries({ queryKey: ["incidents", "list"] });
      setConfirming(false);
    },
  });

  const pins = useMemo<MapPin[]>(() => {
    if (!data) return [];
    const list: MapPin[] = [{ id: "me", lat: data.lat, lng: data.lng, kind: data.type === "sos" ? "sos" : "report" }];
    const o = data.officer;
    if (o?.last_lat != null && o.last_lng != null && OPEN_STATUSES.includes(data.status)) {
      list.push({ id: "officer", lat: o.last_lat, lng: o.last_lng, kind: "officer", label: o.name });
    }
    return list;
  }, [data]);

  if (incident.isLoading) {
    return <div className="h-[70vh] animate-pulse rounded-[28px] bg-cream" />;
  }
  if (!data) {
    return (
      <div className="rounded-3xl bg-white p-8 text-center shadow-card">
        <p className="text-muted">
          {incident.error instanceof ApiError && incident.error.status === 404 ? t.incident.notFound : t.errors.generic}
        </p>
        <Link href="/citizen" className="mt-4 inline-block font-medium text-accent-strong">
          {t.citizen.back}
        </Link>
      </div>
    );
  }

  const open = OPEN_STATUSES.includes(data.status);
  const officer = data.officer;
  const km =
    officer?.last_lat != null && officer.last_lng != null
      ? distanceKm({ lat: data.lat, lng: data.lng }, { lat: officer.last_lat, lng: officer.last_lng })
      : null;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <Link href="/citizen" className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink">
          <ArrowLeft className="h-4 w-4" /> {t.citizen.back}
        </Link>
        {open && (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
              live === "live" ? "bg-resolved-soft text-resolved" : "bg-cancelled-soft text-cancelled",
            )}
          >
            {live === "live" ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
            {live === "live" ? t.incident.live : t.incident.reconnecting}
          </span>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <div className="relative h-[52vh] min-h-[340px] overflow-hidden rounded-[28px] border border-line shadow-card lg:h-[70vh]">
          <IncidentMap pins={pins} />
          <div className="absolute inset-x-3 top-3 rounded-2xl bg-white/95 p-4 shadow-card backdrop-blur sm:right-auto sm:max-w-sm">
            <div className="flex items-center gap-2">
              <StatusBadge status={data.status} />
              <span className="text-xs text-muted">
                {t.incident.types[data.type]} #{data.id}
              </span>
            </div>
            <p className="mt-2 text-lg font-semibold">{t.incident.status[data.status]}</p>
            <p className="mt-0.5 text-sm text-muted">{t.incident.statusBody[data.status]}</p>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          {officer && open && (
            <section className="rounded-3xl bg-white p-5 shadow-card">
              <h2 className="text-xs font-semibold tracking-wide text-muted uppercase">{t.incident.officer}</h2>
              <div className="mt-3 flex items-center gap-3">
                <span className="grid h-12 w-12 place-items-center rounded-full bg-en-route-soft font-bold text-en-route">
                  {officer.name
                    .split(" ")
                    .map((w) => w[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <div className="flex-1">
                  <p className="font-semibold">{officer.name}</p>
                  <p className="text-sm text-muted">
                    {officer.rank}
                    {km !== null && ` · ${km.toLocaleString(locale === "bn" ? "bn-BD" : "en", { maximumFractionDigits: 1 })} km`}
                  </p>
                </div>
                <a
                  href={`tel:${officer.phone}`}
                  className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink px-3.5 text-sm font-medium text-white"
                >
                  <Phone className="h-4 w-4" /> {t.incident.call}
                </a>
              </div>
            </section>
          )}

          <section className="rounded-3xl bg-white p-5 shadow-card">
            <h2 className="mb-4 text-xs font-semibold tracking-wide text-muted uppercase">{t.incident.timeline}</h2>
            <Timeline events={data.events} />
          </section>

          {(data.status === "pending" || data.status === "assigned") && (
            <section className="rounded-3xl border border-line bg-white p-5">
              {confirming ? (
                <>
                  <p className="text-sm text-ink-soft">{t.incident.cancelConfirm}</p>
                  <div className="mt-4 flex gap-2">
                    <Button variant="sos" size="sm" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
                      {cancel.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                      {t.incident.cancel}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setConfirming(false)}>
                      {t.incident.cancelKeep}
                    </Button>
                  </div>
                  {cancel.error && (
                    <p className="mt-3 text-sm text-sos-strong">
                      {cancel.error instanceof ApiError ? cancel.error.message : t.errors.generic}
                    </p>
                  )}
                </>
              ) : (
                <Button variant="outline" size="sm" className="w-full" onClick={() => setConfirming(true)}>
                  {t.incident.cancel}
                </Button>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
