"use client";

import { type IncidentStatus, statusDot, statusTone } from "@/lib/incidents";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function StatusBadge({ status, className }: { status: IncidentStatus; className?: string }) {
  const { t } = useI18n();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
        statusTone[status],
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", statusDot[status])} />
      {t.incident.statusShort[status]}
    </span>
  );
}
