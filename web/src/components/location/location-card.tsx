"use client";

import { Crosshair, LocateOff, MapPinOff, Satellite } from "lucide-react";

import { IncidentMap } from "@/components/map/incident-map";
import { DEMO_POINT, type GeoState, type Point } from "@/lib/geo";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/** One line that says exactly what the location situation is. */
export function useLocationText(geo: GeoState): string {
  const { t, locale } = useI18n();
  switch (geo.status) {
    case "ready":
      return t.location.ready.replace(
        "{m}",
        Math.max(1, Math.round(geo.accuracy)).toLocaleString(locale === "bn" ? "bn-BD" : "en"),
      );
    case "outside":
      return t.location.outside;
    case "denied":
      return t.location.denied;
    case "unavailable":
      return t.location.unavailable;
    case "unsupported":
      return t.location.unsupported;
    default:
      return t.location.locating;
  }
}

/**
 * Small map + status line. Shows the real position when there is one; otherwise the point that
 * will actually be used (`fallback`), so what you see is what gets sent.
 */
export function LocationCard({
  geo,
  title,
  fallback = DEMO_POINT,
  kind = "me",
  footer,
}: {
  geo: GeoState;
  title?: string;
  fallback?: Point;
  kind?: "me" | "officer";
  footer?: React.ReactNode;
}) {
  const { t } = useI18n();
  const text = useLocationText(geo);
  const real = geo.status === "ready";
  const point = real ? geo.point : geo.status === "locating" ? null : fallback;
  const Icon = real ? Satellite : geo.status === "locating" ? Crosshair : geo.status === "denied" ? LocateOff : MapPinOff;

  return (
    <section className="overflow-hidden rounded-3xl border border-line bg-white">
      <div className="relative h-40 bg-[#f6f1ea]">
        {point ? (
          <IncidentMap pins={[{ id: "me", lat: point.lat, lng: point.lng, kind }]} zoom={15} follow />
        ) : (
          <div className="grid h-full place-items-center text-muted">
            <Crosshair className="h-6 w-6 animate-pulse" />
          </div>
        )}
      </div>
      <div className="flex items-start gap-3 p-4">
        <span
          className={cn(
            "mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl",
            real ? "bg-resolved-soft text-resolved" : geo.status === "locating" ? "bg-cream text-muted" : "bg-pending-soft text-pending",
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">{title ?? t.location.title}</p>
          <p className="mt-0.5 text-sm text-muted" aria-live="polite">
            {text}
          </p>
          {footer}
        </div>
      </div>
    </section>
  );
}
