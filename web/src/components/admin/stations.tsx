"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, CheckCircle2, Loader2, UserPlus } from "lucide-react";
import { useState } from "react";

import { AdminNav } from "@/components/admin/admin-nav";
import { AppShell } from "@/components/app/app-shell";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api";
import { type Station, useStations } from "@/lib/gds";
import { useI18n } from "@/lib/i18n";
import type { User } from "@/lib/types";

export function AdminStations() {
  return (
    <AppShell roles={["super_admin"]}>
      {(user) => (
        <>
          <AdminNav role={user.role} />
          <Stations />
        </>
      )}
    </AppShell>
  );
}

function Stations() {
  const { t } = useI18n();
  const stations = useStations();
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">{t.admin.stationsTitle}</h1>
        <ul className="mt-5 grid gap-3 sm:grid-cols-2">
          {stations.data?.items.map((s) => (
            <li key={s.id} className="rounded-3xl bg-white p-5 shadow-card">
              <div className="flex items-center justify-between">
                <span className="grid h-10 w-10 place-items-center rounded-2xl bg-accent-soft text-accent-strong">
                  <Building2 className="h-5 w-5" />
                </span>
                <span className="font-mono text-xs font-semibold text-muted">
                  {s.city_code}-{s.code}
                </span>
              </div>
              <p className="mt-3 font-semibold">{s.name}</p>
              <p className="text-sm text-muted">
                {s.city} · {s.lat.toFixed(4)}, {s.lng.toFixed(4)}
              </p>
            </li>
          ))}
        </ul>
      </section>
      <aside className="flex h-fit flex-col gap-5 lg:sticky lg:top-24">
        <AddStation />
        <AddStationAdmin stations={stations.data?.items ?? []} />
      </aside>
    </div>
  );
}

function AddStation() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const empty = { name: "", code: "", city: "Dhaka", city_code: "DHA", lat: "", lng: "" };
  const [form, setForm] = useState(empty);
  const [done, setDone] = useState<string | null>(null);
  const set = (key: keyof typeof empty) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const create = useMutation({
    mutationFn: () =>
      api.post<Station>("/stations", {
        ...form,
        code: form.code.trim().toUpperCase(),
        city_code: form.city_code.trim().toUpperCase(),
        lat: Number(form.lat),
        lng: Number(form.lng),
      }),
    onSuccess: (station) => {
      setDone(station.name);
      setForm(empty);
      void queryClient.invalidateQueries({ queryKey: ["stations"] });
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
        <Building2 className="h-4 w-4 text-accent-strong" /> {t.admin.addStation}
      </h2>
      <Field label={t.admin.stationName} value={form.name} onChange={set("name")} error={err("name")} required />
      <div className="grid grid-cols-2 gap-3">
        <Field label={t.admin.stationCode} value={form.code} onChange={set("code")} error={err("code")} required />
        <Field label={t.admin.cityCode} value={form.city_code} onChange={set("city_code")} error={err("city_code")} required />
      </div>
      <Field label={t.admin.city} value={form.city} onChange={set("city")} error={err("city")} required />
      <div className="grid grid-cols-2 gap-3">
        <Field label={t.admin.lat} inputMode="decimal" value={form.lat} onChange={set("lat")} error={err("lat")} required />
        <Field label={t.admin.lng} inputMode="decimal" value={form.lng} onChange={set("lng")} error={err("lng")} required />
      </div>
      {done && (
        <p className="flex items-center gap-2 text-sm text-resolved">
          <CheckCircle2 className="h-4 w-4" /> {t.admin.stationCreated.replace("{name}", done)}
        </p>
      )}
      <Button type="submit" disabled={create.isPending}>
        {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />} {t.admin.save}
      </Button>
    </form>
  );
}

function AddStationAdmin({ stations }: { stations: Station[] }) {
  const { t } = useI18n();
  const empty = { station_id: "", name: "", phone: "", password: "" };
  const [form, setForm] = useState(empty);
  const [done, setDone] = useState<string | null>(null);
  const set = (key: keyof typeof empty) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  const stationId = form.station_id || String(stations[0]?.id ?? "");

  const create = useMutation({
    mutationFn: () =>
      api.post<User>(`/stations/${stationId}/admins`, { name: form.name, phone: form.phone.trim(), password: form.password }),
    onSuccess: (admin) => {
      setDone(admin.name);
      setForm(empty);
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
        <UserPlus className="h-4 w-4 text-accent-strong" /> {t.admin.addAdmin}
      </h2>
      <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-soft">
        {t.admin.adminFor}
        <select value={stationId} onChange={set("station_id")} className="h-11 rounded-xl border border-line bg-white px-3 text-[15px] text-ink outline-none focus:border-accent-strong">
          {stations.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <Field label={t.register.name} value={form.name} onChange={set("name")} error={err("name")} required />
      <Field label={t.login.phone} type="tel" placeholder="+8801XXXXXXXXX" value={form.phone} onChange={set("phone")} error={err("phone")} required />
      <Field label={t.login.password} type="password" autoComplete="new-password" value={form.password} onChange={set("password")} error={err("password")} required />
      {done && (
        <p className="flex items-center gap-2 text-sm text-resolved">
          <CheckCircle2 className="h-4 w-4" /> {t.admin.adminCreated.replace("{name}", done)}
        </p>
      )}
      {create.error && !(create.error instanceof ApiError && create.error.details.length) && (
        <p role="alert" className="text-sm text-sos-strong">
          {create.error instanceof ApiError ? create.error.message : t.errors.generic}
        </p>
      )}
      <Button type="submit" disabled={create.isPending || !stationId}>
        {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />} {t.admin.save}
      </Button>
    </form>
  );
}
