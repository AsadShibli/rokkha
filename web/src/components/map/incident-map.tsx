"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

const STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

type MapLibre = typeof import("maplibre-gl");

export type MapPin = {
  id: string;
  lat: number;
  lng: number;
  kind: "sos" | "report" | "officer" | "station" | "me";
  label?: string;
};

const COLOURS: Record<MapPin["kind"], string> = {
  sos: "#e5484d",
  report: "#b45309",
  officer: "#4338ca",
  station: "#131313",
  me: "#2563eb",
};

function pinElement(pin: MapPin): HTMLElement {
  const el = document.createElement("div");
  el.setAttribute("aria-label", pin.label ?? pin.kind);
  el.title = pin.label ?? "";
  const colour = COLOURS[pin.kind];
  const size = pin.kind === "officer" ? 30 : 22;
  const dot = `<span style="position:relative;display:block;width:${size}px;height:${size}px;border-radius:9999px;background:${colour};border:4px solid #fff;box-shadow:0 4px 12px rgb(0 0 0/.25)"></span>`;
  el.innerHTML =
    pin.kind === "sos"
      ? `<span style="position:relative;display:grid;place-items:center;width:40px;height:40px">
           <span class="animate-pulse-ring" style="position:absolute;inset:0;border-radius:9999px;background:${colour}"></span>${dot}
         </span>`
      : dot;
  return el;
}

/** Add, move or remove DOM markers so the map shows exactly `pins`. */
function syncPins(lib: MapLibre, map: MapLibreMap, markers: Map<string, Marker>, pins: MapPin[]) {
  const seen = new Set<string>();
  for (const pin of pins) {
    seen.add(pin.id);
    const existing = markers.get(pin.id);
    if (existing) existing.setLngLat([pin.lng, pin.lat]);
    else markers.set(pin.id, new lib.Marker({ element: pinElement(pin) }).setLngLat([pin.lng, pin.lat]).addTo(map));
  }
  for (const [id, marker] of markers) {
    if (!seen.has(id)) {
      marker.remove();
      markers.delete(id);
    }
  }
}

/**
 * MapLibre map with OpenFreeMap tiles (free, no key). Pins are DOM markers styled with the
 * design tokens; positions update in place as props change. Fits all pins on first load.
 */
export function IncidentMap({
  pins,
  className,
  zoom = 14,
  follow = false,
  onPick,
}: {
  pins: MapPin[];
  className?: string;
  zoom?: number;
  /** Keep the first pin centred as it moves (your own live position). */
  follow?: boolean;
  /** Called with the tapped spot; the map shows a crosshair cursor while this is set. */
  onPick?: (point: { lat: number; lng: number }) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState<{ lib: MapLibre; map: MapLibreMap } | null>(null);
  const markers = useRef(new Map<string, Marker>());
  const fitted = useRef(false);
  const pick = useRef(onPick);
  useEffect(() => {
    pick.current = onPick;
  }, [onPick]);

  // Create the map once; MapLibre needs the browser, so it's loaded lazily.
  useEffect(() => {
    let cancelled = false;
    let created: MapLibreMap | null = null;
    const pinsOnScreen = markers.current;
    void import("maplibre-gl").then((lib) => {
      if (cancelled || !container.current) return;
      created = new lib.Map({
        container: container.current,
        style: STYLE_URL,
        center: [90.414, 23.781],
        zoom,
        attributionControl: { compact: true },
      });
      created.addControl(new lib.NavigationControl({ showCompass: false }), "top-right");
      created.on("click", (e) => pick.current?.({ lat: e.lngLat.lat, lng: e.lngLat.lng }));
      setReady({ lib, map: created });
    });
    return () => {
      cancelled = true;
      created?.remove();
      pinsOnScreen.clear();
    };
  }, [zoom]);

  useEffect(() => {
    if (!ready) return;
    syncPins(ready.lib, ready.map, markers.current, pins);
    if (follow && fitted.current && pins[0]) {
      ready.map.easeTo({ center: [pins[0].lng, pins[0].lat], duration: 600 });
    }
    if (!fitted.current && pins.length > 0) {
      fitted.current = true;
      if (pins.length === 1) {
        ready.map.jumpTo({ center: [pins[0].lng, pins[0].lat] });
      } else {
        const bounds = new ready.lib.LngLatBounds();
        pins.forEach((p) => bounds.extend([p.lng, p.lat]));
        ready.map.fitBounds(bounds, { padding: 80, maxZoom: 15, duration: 0 });
      }
    }
  }, [ready, pins, follow]);

  return (
    <div
      ref={container}
      className={cn("h-full w-full bg-[#f6f1ea]", onPick && "[&_canvas]:!cursor-crosshair", className)}
    />
  );
}
