"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, UserPlus } from "lucide-react";
import { useState } from "react";

import { AdminNav } from "@/components/admin/admin-nav";
import { StationFilter } from "@/components/admin/station-filter";
import { AppShell } from "@/components/app/app-shell";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { minutesSince, POLL_MS, useOfficers } from "@/lib/admin";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { DutyStatus, OfficerProfile } from "@/lib/officer";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";

const dutyTone: Record<DutyStatus, string> = {
  off_duty: "bg-cancelled-soft text-cancelled",
  available: "bg-resolved-soft text-resolved",
  busy: "bg-en-route-soft text-en-route",
};

export function AdminOfficers() {
  return (
    <AppShell roles={["station_admin", "super_admin"]}>
      {(user) => (
        <>
          <AdminNav role={user.role} />
          <Officers user={user} />
        </>
      )}
    </AppShell>
  );
}

function Officers({ user }: { user: User }) {
  const { t } = useI18n();
  const [stationId, setStationId] = useState<number | null>(null);
  const officers = useOfficers(stationId, "", POLL_MS);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="text-3xl font-bold tracking-tight">{t.admin.officersTitle}</h1>
          {user.role === "super_admin" && <StationFilter value={stationId} onChange={setStationId} />}
        </div>
        <div className="mt-5 overflow-hidden rounded-3xl bg-white shadow-card">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line bg-cream/50 text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3 font-semibold">{t.register.name}</th>
                <th className="hidden px-4 py-3 font-semibold sm:table-cell">{t.admin.badgeNo}</th>
                <th className="px-4 py-3 font-semibold">{t.officer.onDuty}</th>
                <th className="hidden px-4 py-3 font-semibold md:table-cell">{t.officer.sharing}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {officers.isLoading &&
                [0, 1, 2].map((i) => (
                  <tr key={i}>
                    <td colSpan={4} className="px-4 py-3">
                      <div className="h-8 animate-pulse rounded bg-cream" />
                    </td>
                  </tr>
                ))}
              {officers.data?.items.map((o: OfficerProfile) => {
                const mins = minutesSince(o.last_seen_at);
                return (
                  <tr key={o.id}>
                    <td className="px-4 py-3">
                      <p className="font-medium">{o.user.name}</p>
                      <p className="text-xs text-muted">
                        {o.rank} · {o.user.phone}
                      </p>
                    </td>
                    <td className="hidden px-4 py-3 font-mono text-xs sm:table-cell">{o.badge_no}</td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-semibold", dutyTone[o.duty_status])}>
                        {t.admin.duty[o.duty_status]}
                      </span>
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-muted md:table-cell">
                      {mins === null ? t.admin.seenNever : t.admin.seen.replace("{m}", String(mins))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="h-fit lg:sticky lg:top-24">
        {user.role === "station_admin" ? (
          <AddOfficer />
        ) : (
          <p className="rounded-3xl border border-dashed border-line p-6 text-sm text-muted">{t.admin.readOnlyOfficers}</p>
        )}
      </aside>
    </div>
  );
}

function AddOfficer() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const empty = { name: "", phone: "", email: "", password: "", badge_no: "", rank: "" };
  const [form, setForm] = useState(empty);
  const [done, setDone] = useState<string | null>(null);
  const set = (key: keyof typeof empty) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const create = useMutation({
    mutationFn: () => api.post<OfficerProfile>("/officers", { ...form, email: form.email.trim() || null }),
    onSuccess: (officer) => {
      setDone(officer.user.name);
      setForm(empty);
      void queryClient.invalidateQueries({ queryKey: ["officers"] });
    },
  });
  const err = (field: string) => (create.error instanceof ApiError ? create.error.fieldError(field) : undefined);

  return (
    <form
      className="flex flex-col gap-3.5 rounded-3xl bg-white p-5 shadow-card"
      onSubmit={(e) => {
        e.preventDefault();
        setDone(null);
        create.mutate();
      }}
    >
      <h2 className="flex items-center gap-2 font-semibold">
        <UserPlus className="h-4 w-4 text-accent-strong" /> {t.admin.addOfficer}
      </h2>
      <Field label={t.register.name} value={form.name} onChange={set("name")} error={err("name")} required />
      <Field label={t.login.phone} type="tel" placeholder="+8801XXXXXXXXX" value={form.phone} onChange={set("phone")} error={err("phone")} required />
      <div className="grid grid-cols-2 gap-3">
        <Field label={t.admin.badgeNo} value={form.badge_no} onChange={set("badge_no")} error={err("badge_no")} required />
        <Field label={t.admin.rank} value={form.rank} onChange={set("rank")} error={err("rank")} required />
      </div>
      <Field label={t.login.password} type="password" autoComplete="new-password" value={form.password} onChange={set("password")} error={err("password")} required />
      {done && (
        <p className="flex items-start gap-2 text-sm text-resolved">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {t.admin.created.replace("{name}", done)}
        </p>
      )}
      {create.error && !(create.error instanceof ApiError && create.error.details.length) && (
        <p role="alert" className="text-sm text-sos-strong">
          {create.error instanceof ApiError ? create.error.message : t.errors.generic}
        </p>
      )}
      <Button type="submit" disabled={create.isPending}>
        {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />} {t.admin.save}
      </Button>
    </form>
  );
}
