"use client";

import { type GdStatus, gdTone } from "@/lib/gds";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function GdStatusBadge({ status }: { status: GdStatus }) {
  const { t } = useI18n();
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold", gdTone[status])}>
      {t.gd.status[status]}
    </span>
  );
}
