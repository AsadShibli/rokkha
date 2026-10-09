"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ChevronRight, FileText, Info, MessageSquareWarning, Radio } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/app/app-shell";
import { SosButton } from "@/components/citizen/sos-button";
import { StatusBadge } from "@/components/incident/status-badge";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { LocationCard } from "@/components/location/location-card";
import { useGeolocation, useResolvePoint } from "@/lib/geo";
import { useI18n } from "@/lib/i18n";
import { type IncidentDetail, OPEN_STATUSES, useIncidents } from "@/lib/incidents";

export function CitizenHome() {
  return <AppShell roles={["citizen"]}>{(user) => <Home firstName={user.name.split(" ")[0]} />}</AppShell>;
}

function Home({ firstName }: { firstName: string }) {
  const { t, locale } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const incidents = useIncidents("page_size=20");
  const geo = useGeolocation();
  const resolvePoint = useResolvePoint(geo);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openSos = incidents.data?.items.find(
    (i) => i.type === "sos" && OPEN_STATUSES.includes(i.status),
  );

  async function raiseSos() {
    setBusy(true);
    setError(null);
    setNotice(t.citizen.locating);
    try {
      const where = await resolvePoint();
      setNotice(where.source === "device" ? null : t.location.usedDemo[where.source]);
      const incident = await api.post<IncidentDetail>("/incidents/sos", { lat: where.lat, lng: where.lng });
      queryClient.setQueryData(["incidents", "detail", incident.id], incident);
      void queryClient.invalidateQueries({ queryKey: ["incidents", "list"] });
      router.push(`/citizen/incidents/${incident.id}`);
    } catch (err) {
      setBusy(false);
      if (err instanceof ApiError && err.code === "ACTIVE_SOS_EXISTS" && openSos) {
        router.push(`/citizen/incidents/${openSos.id}`);
        return;
      }
      if (err instanceof ApiError && err.code === "RATE_LIMITED") {
        setError(t.citizen.rateLimited.replace("{s}", "600"));
        return;
      }
      setError(err instanceof ApiError ? err.message : t.errors.generic);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
      <section className="bg-warm flex flex-col items-center rounded-[32px] px-6 py-10 text-center sm:py-14">
        <p className="text-sm font-medium text-accent-strong">{t.citizen.greeting}, {firstName}</p>

        {openSos ? (
          <Link
            href={`/citizen/incidents/${openSos.id}`}
            className="mt-8 flex w-full max-w-md items-center gap-4 rounded-3xl bg-white p-5 text-left shadow-card transition hover:-translate-y-0.5"
          >
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-sos text-white">
              <Radio className="h-5 w-5" />
            </span>
            <span className="flex-1">
              <span className="block font-semibold">{t.citizen.activeTitle}</span>
              <span className="mt-1 block text-sm text-muted">{t.incident.status[openSos.status]}</span>
            </span>
            <ArrowRight className="h-5 w-5 text-muted" />
          </Link>
        ) : (
          <div className="mt-8">
            <SosButton busy={busy} onTrigger={() => void raiseSos()} />
          </div>
        )}

        {notice && (
          <p className="mt-6 inline-flex max-w-md items-start gap-2 rounded-2xl bg-white/80 px-4 py-2.5 text-left text-sm text-ink-soft">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong" />
            {notice}
          </p>
        )}
        {error && (
          <p role="alert" className="mt-6 max-w-md rounded-2xl bg-sos-soft px-4 py-2.5 text-sm text-sos-strong">
            {error}
          </p>
        )}
      </section>

      <aside className="flex flex-col gap-4">
        <LocationCard geo={geo} />

        <Link
          href="/citizen/report"
          className="flex items-center gap-4 rounded-3xl border border-line bg-white p-5 transition hover:border-accent hover:shadow-card"
        >
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-pending-soft text-pending">
            <MessageSquareWarning className="h-5 w-5" />
          </span>
          <span className="flex-1">
            <span className="block font-semibold">{t.citizen.report}</span>
            <span className="mt-0.5 block text-sm text-muted">{t.citizen.reportBody}</span>
          </span>
          <ChevronRight className="h-5 w-5 text-muted" />
        </Link>

        <Link
          href="/citizen/gd"
          className="flex items-center gap-4 rounded-3xl border border-line bg-white p-5 transition hover:border-accent hover:shadow-card"
        >
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent-strong">
            <FileText className="h-5 w-5" />
          </span>
          <span className="flex-1">
            <span className="block font-semibold">{t.gd.navCard}</span>
            <span className="mt-0.5 block text-sm text-muted">{t.gd.navCardBody}</span>
          </span>
          <ChevronRight className="h-5 w-5 text-muted" />
        </Link>

        <div className="rounded-3xl border border-line bg-white p-5">
          <h2 className="font-semibold">{t.citizen.myIncidents}</h2>
          {incidents.isLoading ? (
            <div className="mt-4 flex flex-col gap-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-2xl bg-cream" />
              ))}
            </div>
          ) : incidents.data?.items.length ? (
            <ul className="mt-3 flex flex-col">
              {incidents.data.items.map((incident) => (
                <li key={incident.id}>
                  <Link
                    href={`/citizen/incidents/${incident.id}`}
                    className="-mx-2 flex items-center justify-between gap-3 rounded-2xl px-2 py-3 hover:bg-cream/70"
                  >
                    <span>
                      <span className="block text-sm font-medium">
                        {t.incident.types[incident.type]} #{incident.id}
                      </span>
                      <span className="text-xs text-muted">
                        {formatDateTime(incident.created_at, locale)}
                      </span>
                    </span>
                    <StatusBadge status={incident.status} />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-muted">{t.citizen.noIncidents}</p>
          )}
        </div>
      </aside>
    </div>
  );
}
