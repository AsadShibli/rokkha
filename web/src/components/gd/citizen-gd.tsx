"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Info, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useId, useState } from "react";

import { AppShell } from "@/components/app/app-shell";
import { GdStatusBadge } from "@/components/gd/gd-status";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { GD_CATEGORIES, type Gd, type GdCategory, type GdDraft, todayInDhaka, useGds, useStations } from "@/lib/gds";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function CitizenGd() {
  return <AppShell roles={["citizen"]}>{() => <GdPage />}</AppShell>;
}

type Form = { station_id: string; category: GdCategory | ""; title: string; details: string; incident_date: string };

const inputClass =
  "w-full rounded-xl border border-line bg-white px-3.5 text-[15px] text-ink outline-none transition focus:border-accent-strong focus:ring-4 focus:ring-accent/20";

function GdPage() {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const stations = useStations();
  const gds = useGds();
  const ids = { text: useId(), station: useId(), category: useId(), title: useId(), details: useId(), date: useId() };

  const [story, setStory] = useState("");
  const [aiNote, setAiNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [form, setForm] = useState<Form>({ station_id: "", category: "", title: "", details: "", incident_date: "" });
  const [done, setDone] = useState<string | null>(null);
  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const draft = useMutation({
    mutationFn: () => api.post<GdDraft>("/gds/ai-draft", { text: story.trim() }),
    onSuccess: (d) => {
      setForm((f) => ({
        ...f,
        category: d.category,
        title: d.title,
        details: d.details,
        incident_date: d.incident_date ?? f.incident_date,
      }));
      setAiNote({ ok: true, text: t.gd.aiDone });
    },
    onError: (err) =>
      setAiNote({
        ok: false,
        text: err instanceof ApiError && err.code === "RATE_LIMITED" ? err.message : t.gd.aiUnavailable,
      }),
  });

  const submit = useMutation({
    mutationFn: () =>
      api.post<Gd>("/gds", {
        station_id: Number(form.station_id || stations.data?.items[0]?.id),
        category: form.category,
        title: form.title.trim(),
        details: form.details.trim(),
        incident_date: form.incident_date,
      }),
    onSuccess: (gd) => {
      setDone(gd.gd_number);
      setStory("");
      setAiNote(null);
      setForm((f) => ({ ...f, category: "", title: "", details: "", incident_date: "" }));
      void queryClient.invalidateQueries({ queryKey: ["gds"] });
    },
  });
  const fieldError = (field: string) => (submit.error instanceof ApiError ? submit.error.fieldError(field) : undefined);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <div>
        <Link href="/citizen" className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink">
          <ArrowLeft className="h-4 w-4" /> {t.citizen.back}
        </Link>
        <h1 className="mt-4 text-3xl font-bold tracking-tight">{t.gd.title}</h1>
        <p className="mt-2 max-w-xl text-muted">{t.gd.subtitle}</p>

        {done && (
          <p className="mt-6 flex items-center gap-2 rounded-2xl bg-resolved-soft px-4 py-3 text-sm font-medium text-resolved">
            <CheckCircle2 className="h-5 w-5" /> {t.gd.submitted.replace("{n}", done)}
          </p>
        )}

        {/* AI helper */}
        <section className="bg-warm mt-6 rounded-3xl p-5 sm:p-6">
          <label htmlFor={ids.text} className="text-sm font-semibold">
            {t.gd.aiLabel}
          </label>
          <textarea
            id={ids.text}
            value={story}
            onChange={(e) => setStory(e.target.value)}
            placeholder={t.gd.aiPlaceholder}
            rows={3}
            maxLength={2000}
            className={cn(inputClass, "mt-2 py-3")}
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button variant="accent" disabled={story.trim().length < 10 || draft.isPending} onClick={() => draft.mutate()}>
              {draft.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {draft.isPending ? t.gd.aiDrafting : t.gd.aiButton}
            </Button>
            {aiNote && (
              <span className={cn("inline-flex items-center gap-1.5 text-sm", aiNote.ok ? "text-resolved" : "text-ink-soft")}>
                <Info className="h-4 w-4" /> {aiNote.text}
              </span>
            )}
          </div>
        </section>

        {/* form */}
        <form
          className="mt-5 grid gap-4 rounded-3xl bg-white p-5 shadow-card sm:grid-cols-2 sm:p-6"
          onSubmit={(e) => {
            e.preventDefault();
            setDone(null);
            submit.mutate();
          }}
        >
          <label htmlFor={ids.station} className="flex flex-col gap-1.5 text-sm font-medium text-ink-soft">
            {t.gd.station}
            <select id={ids.station} value={form.station_id} onChange={set("station_id")} className={cn(inputClass, "h-11")}>
              {stations.data?.items.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.city}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor={ids.category} className="flex flex-col gap-1.5 text-sm font-medium text-ink-soft">
            {t.gd.category}
            <select id={ids.category} value={form.category} onChange={set("category")} required className={cn(inputClass, "h-11")}>
              <option value="" disabled>
                —
              </option>
              {GD_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {t.gd.categories[c]}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor={ids.title} className="flex flex-col gap-1.5 text-sm font-medium text-ink-soft sm:col-span-2">
            {t.gd.gdTitle}
            <input id={ids.title} value={form.title} onChange={set("title")} required minLength={5} maxLength={150} className={cn(inputClass, "h-11")} />
            {fieldError("title") && <span className="text-sos-strong">{fieldError("title")}</span>}
          </label>
          <label htmlFor={ids.details} className="flex flex-col gap-1.5 text-sm font-medium text-ink-soft sm:col-span-2">
            {t.gd.details}
            <textarea id={ids.details} value={form.details} onChange={set("details")} required minLength={20} maxLength={5000} rows={5} className={cn(inputClass, "py-3")} />
            {fieldError("details") && <span className="text-sos-strong">{fieldError("details")}</span>}
          </label>
          <label htmlFor={ids.date} className="flex flex-col gap-1.5 text-sm font-medium text-ink-soft">
            {t.gd.incidentDate}
            <input id={ids.date} type="date" value={form.incident_date} onChange={set("incident_date")} max={todayInDhaka()} required className={cn(inputClass, "h-11")} />
            {fieldError("incident_date") && <span className="text-sos-strong">{fieldError("incident_date")}</span>}
          </label>
          <div className="flex items-end">
            <Button type="submit" size="lg" className="w-full" disabled={submit.isPending}>
              {submit.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              {submit.isPending ? t.gd.submitting : t.gd.submit}
            </Button>
          </div>
          {submit.error && !(submit.error instanceof ApiError && submit.error.details.length) && (
            <p role="alert" className="text-sm text-sos-strong sm:col-span-2">
              {submit.error instanceof ApiError ? submit.error.message : t.errors.generic}
            </p>
          )}
        </form>
      </div>

      <aside className="h-fit rounded-3xl border border-line bg-white p-5 lg:sticky lg:top-24">
        <h2 className="font-semibold">{t.gd.mine}</h2>
        {gds.data?.items.length ? (
          <ul className="mt-3 flex flex-col divide-y divide-line">
            {gds.data.items.map((gd) => (
              <li key={gd.id} className="py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold">{gd.gd_number}</span>
                  <GdStatusBadge status={gd.status} />
                </div>
                <p className="mt-1 text-sm font-medium">{gd.title}</p>
                <p className="text-xs text-muted">{formatDateTime(gd.created_at, locale)}</p>
                {gd.review_note && (
                  <p className="mt-1.5 rounded-xl bg-cream/70 px-3 py-2 text-xs text-ink-soft">
                    {t.gd.reviewNote}: {gd.review_note}
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-muted">{gds.isLoading ? t.app.loading : t.gd.none}</p>
        )}
      </aside>
    </div>
  );
}
