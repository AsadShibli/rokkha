"use client";

import { Crosshair, Hand, LocateFixed, LocateOff, MapPinOff, RotateCw, Satellite } from "lucide-react";
import { useState } from "react";

import { IncidentMap } from "@/components/map/incident-map";
import { DEMO_POINT, type GeoState, type Point, retryLocation, setManualPoint } from "@/lib/geo";
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
    case "manual":
      return t.location.manual;
    case "outside":
      return t.location.outside;
    case "denied":
      return t.location.denied;
    case "unavailable":
      return t.location.unavailable;
    case "unsupported":
      return t.location.unsupported;
    default:
      return geo.slow ? t.location.slow : t.location.locating;
  }
}

/**
 * Small map + status line. Shows the real position when there is one; otherwise the point that
 * will actually be used (`fallback`), so what you see is what gets sent. Without a real fix the
 * map can be tapped to set where you are, which works on any device.
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
  const [outsidePick, setOutsidePick] = useState(false);
  const real = geo.status === "ready";
  const manual = geo.status === "manual";
  const point = real || manual ? geo.point : geo.status === "locating" && !geo.slow ? null : fallback;
  const Icon = real
    ? Satellite
    : manual
      ? Hand
      : geo.status === "locating"
        ? Crosshair
        : geo.status === "denied"
          ? LocateOff
          : MapPinOff;
  const canRetry = !real && geo.status !== "unsupported" && !(geo.status === "locating" && !geo.slow);

  const pick = real ? undefined : (p: Point) => setOutsidePick(!setManualPoint(p));

  return (
    <section className="overflow-hidden rounded-3xl border border-line bg-white">
      <div className="relative h-44">
        <IncidentMap
          pins={point ? [{ id: "me", lat: point.lat, lng: point.lng, kind }] : []}
          zoom={15}
          follow
          onPick={pick}
        />
        {!point && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center text-muted">
            <Crosshair className="h-6 w-6 animate-pulse" />
          </div>
        )}
      </div>
      <div className="flex items-start gap-3 p-4">
        <span
          className={cn(
            "mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl",
            real || manual
              ? "bg-resolved-soft text-resolved"
              : geo.status === "locating"
                ? "bg-cream text-muted"
                : "bg-pending-soft text-pending",
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">{title ?? t.location.title}</p>
          <p className="mt-0.5 text-sm text-muted" aria-live="polite">
            {text}
          </p>
          {!real && (
            <p className={cn("mt-1 text-xs", outsidePick ? "font-medium text-pending" : "text-ink-soft")}>
              {outsidePick ? t.location.pickOutside : manual ? t.location.pickMove : t.location.pickHint}
            </p>
          )}
          {geo.status === "unavailable" && (
            <p className="mt-1 font-mono text-[11px] text-muted">
              {t.location.browserSaid} {geo.detail}
            </p>
          )}
          {(canRetry || manual) && (
            <div className="mt-2 flex flex-wrap gap-2">
              {manual ? (
                <button
                  type="button"
                  onClick={() => {
                    setManualPoint(null);
                    retryLocation();
                  }}
                  className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-xs font-semibold hover:bg-cream"
                >
                  <LocateFixed className="h-3.5 w-3.5" />
                  {t.location.useDevice}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={retryLocation}
                  className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-xs font-semibold hover:bg-cream"
                >
                  <RotateCw className="h-3.5 w-3.5" />
                  {t.location.retry}
                </button>
              )}
            </div>
          )}
          {footer}
        </div>
      </div>
    </section>
  );
}
