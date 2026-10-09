"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, FileSearch, Loader2, X } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/app/app-shell";
import { GdStatusBadge } from "@/components/gd/gd-status";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { type Gd, type GdStatus, useGds } from "@/lib/gds";
import { useI18n } from "@/lib/i18n";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";

const TABS: GdStatus[] = ["submitted", "under_review", "approved", "rejected"];

export function GdReview() {
  return <AppShell roles={["station_admin", "super_admin"]}>{(user) => <Queue user={user} />}</AppShell>;
}

function Queue({ user }: { user: User }) {
  const { t, locale } = useI18n();
  const [tab, setTab] = useState<GdStatus>("submitted");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const gds = useGds(`status=${tab}&page_size=50`);
  const selected = gds.data?.items.find((g) => g.id === selectedId) ?? null;

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">{t.gd.queueTitle}</h1>
      <p className="mt-2 text-muted">{t.gd.queueSubtitle}</p>

      <div role="tablist" className="mt-6 inline-flex flex-wrap gap-1 rounded-2xl border border-line bg-white p-1">
        {TABS.map((status) => (
          <button
            key={status}
            role="tab"
            aria-selected={tab === status}
            onClick={() => {
              setTab(status);
              setSelectedId(null);
            }}
            className={cn(
              "rounded-xl px-3.5 py-1.5 text-sm font-medium transition",
              tab === status ? "bg-ink text-white" : "text-muted hover:text-ink",
            )}
          >
            {t.gd.status[status]}
          </button>
        ))}
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_420px]">
        <ul className="flex flex-col gap-2.5">
          {gds.isLoading &&
            [0, 1, 2].map((i) => <li key={i} className="h-20 animate-pulse rounded-2xl bg-cream" />)}
          {gds.data?.items.length === 0 && (
            <li className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">{t.gd.empty}</li>
          )}
          {gds.data?.items.map((gd) => (
            <li key={gd.id}>
              <button
                onClick={() => setSelectedId(gd.id)}
                className={cn(
                  "w-full rounded-2xl border bg-white p-4 text-left transition hover:shadow-card",
                  selectedId === gd.id ? "border-accent shadow-card" : "border-line",
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-xs font-semibold">{gd.gd_number}</span>
                  <span className="text-xs text-muted">{t.gd.categories[gd.category]}</span>
                </div>
                <p className="mt-1.5 font-medium">{gd.title}</p>
                <p className="mt-0.5 text-xs text-muted">{t.gd.filedOn.replace("{d}", formatDateTime(gd.created_at, locale))}</p>
              </button>
            </li>
          ))}
        </ul>

        <aside className="h-fit lg:sticky lg:top-24">
          {selected ? (
            <Detail key={selected.id} gd={selected} canReview={user.role === "station_admin"} onDone={() => setSelectedId(null)} />
          ) : (
            <div className="grid h-48 place-items-center rounded-3xl border border-dashed border-line text-sm text-muted">
              <span className="flex items-center gap-2">
                <FileSearch className="h-4 w-4" /> {t.gd.select}
              </span>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function Detail({ gd, canReview, onDone }: { gd: Gd; canReview: boolean; onDone: () => void }) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [needNote, setNeedNote] = useState(false);

  const review = useMutation({
    mutationFn: (action: "start_review" | "approve" | "reject") =>
      api.patch<Gd>(`/gds/${gd.gd_number}/review`, { action, note: note.trim() || undefined }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["gds"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onDone();
    },
  });

  const reject = () => {
    if (!note.trim()) {
      setNeedNote(true);
      return;
    }
    review.mutate("reject");
  };

  return (
    <article className="rounded-3xl bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-sm font-semibold">{gd.gd_number}</span>
        <GdStatusBadge status={gd.status} />
      </div>
      <h2 className="mt-3 text-xl font-semibold">{gd.title}</h2>
      <p className="mt-1 text-sm text-muted">
        {t.gd.categories[gd.category]} · {t.gd.incidentOn.replace("{d}", gd.incident_date)}
      </p>
      <p className="mt-4 rounded-2xl bg-cream/70 p-4 text-sm leading-relaxed whitespace-pre-wrap">{gd.details}</p>
      <p className="mt-2 text-xs text-muted">{t.gd.filedOn.replace("{d}", formatDateTime(gd.created_at, locale))}</p>
      {gd.review_note && (
        <p className="mt-3 text-sm">
          <span className="font-medium">{t.gd.reviewNote}:</span> {gd.review_note}
        </p>
      )}

      {canReview && (gd.status === "submitted" || gd.status === "under_review") && (
        <div className="mt-5 border-t border-line pt-5">
          {gd.status === "submitted" ? (
            <Button className="w-full" disabled={review.isPending} onClick={() => review.mutate("start_review")}>
              {review.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              {t.gd.startReview}
            </Button>
          ) : (
            <>
              <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-soft">
                {t.gd.noteLabel}
                <textarea
                  value={note}
                  onChange={(e) => {
                    setNote(e.target.value);
                    setNeedNote(false);
                  }}
                  rows={3}
                  maxLength={1000}
                  className={cn(
                    "rounded-xl border bg-white p-3 text-[15px] font-normal text-ink outline-none focus:border-accent-strong focus:ring-4 focus:ring-accent/20",
                    needNote ? "border-sos" : "border-line",
                  )}
                />
                {needNote && <span className="text-sos-strong">{t.gd.noteRequired}</span>}
              </label>
              <div className="mt-3 grid grid-cols-2 gap-2.5">
                <Button disabled={review.isPending} onClick={() => review.mutate("approve")}>
                  <Check className="h-4 w-4" /> {t.gd.approve}
                </Button>
                <Button variant="outline" disabled={review.isPending} onClick={reject}>
                  <X className="h-4 w-4" /> {t.gd.reject}
                </Button>
              </div>
            </>
          )}
          {review.error && (
            <p role="alert" className="mt-3 text-sm text-sos-strong">
              {review.error instanceof ApiError ? review.error.message : t.errors.generic}
            </p>
          )}
        </div>
      )}
      {!canReview && <p className="mt-5 text-xs text-muted">{t.gd.readOnly}</p>}
    </article>
  );
}
