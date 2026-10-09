"use client";

import { useStations } from "@/lib/gds";
import { useI18n } from "@/lib/i18n";

/** Super admin only: narrow every panel to one station (or see the whole city). */
export function StationFilter({ value, onChange }: { value: number | null; onChange: (id: number | null) => void }) {
  const { t } = useI18n();
  const stations = useStations();
  return (
    <select
      aria-label={t.gd.station}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      className="h-10 rounded-xl border border-line bg-white px-3 text-sm outline-none focus:border-accent-strong"
    >
      <option value="">{t.admin.allStations}</option>
      {stations.data?.items.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name}
        </option>
      ))}
    </select>
  );
}
