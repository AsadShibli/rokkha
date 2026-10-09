import type { Locale } from "./i18n";

const tag = (locale: Locale) => (locale === "bn" ? "bn-BD" : "en-GB");

export function formatTime(iso: string, locale: Locale): string {
  return new Intl.DateTimeFormat(tag(locale), { hour: "numeric", minute: "2-digit" }).format(
    new Date(iso),
  );
}

export function formatDateTime(iso: string, locale: Locale): string {
  return new Intl.DateTimeFormat(tag(locale), {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

/** Great-circle distance in km (same formula the API uses for dispatch). */
export function distanceKm(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const h =
    Math.sin(rad(b.lat - a.lat) / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}
