"use client";

import { BadgeCheck, Navigation, ShieldAlert, Timer } from "lucide-react";

import { useI18n } from "@/lib/i18n";

/** Phone mock: a map with the citizen, the assigned officer en route, and a status card. */
export function HeroVisual() {
  const { t } = useI18n();
  return (
    <div className="relative mx-auto w-full max-w-[380px]" aria-hidden="true">
      <div className="absolute -inset-8 -z-10 rounded-[48px] bg-accent/25 blur-3xl" />

      <div className="relative overflow-hidden rounded-[36px] border-[10px] border-ink bg-white shadow-float">
        <div className="bg-streets relative h-[460px]">
          {/* route */}
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 360 460" fill="none">
            <path
              d="M268 92 C 240 150, 250 190, 200 220 S 150 270, 158 300"
              stroke="#4338ca"
              strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray="2 12"
            />
          </svg>

          {/* officer */}
          <div className="absolute top-[70px] left-[248px] flex flex-col items-center">
            <span className="grid h-10 w-10 place-items-center rounded-full border-4 border-white bg-en-route text-white shadow-card">
              <Navigation className="h-4 w-4 rotate-[200deg]" />
            </span>
          </div>

          {/* citizen with SOS pulse */}
          <div className="absolute top-[284px] left-[138px]">
            <span className="absolute inset-0 animate-pulse-ring rounded-full bg-sos" />
            <span className="absolute inset-0 animate-pulse-ring rounded-full bg-sos [animation-delay:1.1s]" />
            <span className="relative grid h-10 w-10 place-items-center rounded-full border-4 border-white bg-sos text-white shadow-card">
              <ShieldAlert className="h-4 w-4" />
            </span>
          </div>

          {/* status card */}
          <div className="absolute inset-x-3 bottom-3 rounded-2xl bg-white p-4 shadow-card">
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-en-route-soft px-2.5 py-0.5 text-xs font-semibold text-en-route">
                {t.hero.cardStatus}
              </span>
              <span className="text-xs text-muted">{t.hero.cardDistance}</span>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-full bg-cream text-sm font-bold text-accent-strong">
                TH
              </span>
              <div>
                <p className="text-sm font-semibold">{t.hero.cardOfficer}</p>
                <div className="mt-1.5 h-1.5 w-40 overflow-hidden rounded-full bg-line">
                  <div className="h-full w-2/3 rounded-full bg-en-route" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* floating chips */}
      <div className="absolute top-16 -left-6 hidden max-w-[210px] items-start gap-2 rounded-2xl bg-white p-3 text-xs shadow-card sm:flex">
        <Timer className="mt-0.5 h-4 w-4 shrink-0 text-accent-strong" />
        <span className="text-ink-soft">{t.hero.chipEscalation}</span>
      </div>
      <div className="absolute -right-8 bottom-40 hidden max-w-[220px] items-start gap-2 rounded-2xl bg-white p-3 text-xs shadow-card sm:flex">
        <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-resolved" />
        <span className="text-ink-soft">{t.hero.chipGd}</span>
      </div>
    </div>
  );
}
