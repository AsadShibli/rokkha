"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Info, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { AppShell } from "@/components/app/app-shell";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { LocationCard } from "@/components/location/location-card";
import { useGeolocation, useResolvePoint } from "@/lib/geo";
import { useI18n } from "@/lib/i18n";
import type { IncidentDetail } from "@/lib/incidents";

export function CitizenReport() {
  return <AppShell roles={["citizen"]}>{() => <ReportForm />}</AppShell>;
}

function ReportForm() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const textId = useId();
  const geo = useGeolocation();
  const resolvePoint = useResolvePoint(geo);
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const where = await resolvePoint();
      if (where.source !== "device") setNotice(t.location.usedDemo[where.source]);
      const incident = await api.post<IncidentDetail>("/incidents/report", {
        lat: where.lat,
        lng: where.lng,
        description: text.trim(),
      });
      queryClient.setQueryData(["incidents", "detail", incident.id], incident);
      void queryClient.invalidateQueries({ queryKey: ["incidents", "list"] });
      router.push(`/citizen/incidents/${incident.id}`);
    } catch (err) {
      setPending(false);
      setError(err instanceof ApiError ? (err.fieldError("description") ?? err.message) : t.errors.generic);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <Link href="/citizen" className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink">
        <ArrowLeft className="h-4 w-4" /> {t.citizen.back}
      </Link>
      <h1 className="mt-5 text-3xl font-bold tracking-tight">{t.citizen.reportTitle}</h1>
      <p className="mt-2 text-muted">{t.citizen.reportSubtitle}</p>

      <div className="mt-8">
        <LocationCard geo={geo} />
      </div>

      <form onSubmit={submit} className="mt-4 flex flex-col gap-4 rounded-3xl bg-white p-6 shadow-card">
        <label htmlFor={textId} className="text-sm font-medium text-ink-soft">
          {t.citizen.reportLabel}
        </label>
        <textarea
          id={textId}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t.citizen.reportPlaceholder}
          rows={5}
          minLength={10}
          maxLength={1000}
          required
          className="rounded-2xl border border-line bg-white p-3.5 text-[15px] outline-none focus:border-accent-strong focus:ring-4 focus:ring-accent/20"
        />
        {notice && (
          <p className="inline-flex items-start gap-2 text-sm text-ink-soft">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong" /> {notice}
          </p>
        )}
        {error && (
          <p role="alert" className="rounded-xl bg-sos-soft px-3.5 py-2.5 text-sm text-sos-strong">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={pending || text.trim().length < 10}>
          {pending && <Loader2 className="h-4 w-4 animate-spin" />}
          {t.citizen.reportSubmit}
        </Button>
      </form>
    </div>
  );
}
