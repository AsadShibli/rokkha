"use client";

import { Loader2, ShieldAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const HOLD_MS = 2000;
const RING = 2 * Math.PI * 92;

/** Read only from event handlers and timers, never during render. */
const clock = () => performance.now();

/**
 * Press-and-hold SOS: letting go before 2 seconds cancels, so an accidental tap never fires.
 * Works with mouse, touch and keyboard (hold Space/Enter).
 *
 * The SOS fires from a timer, and animation frames only draw the ring, so a throttled or
 * backgrounded page still sends it. Releasing also checks the elapsed time: on a busy page the
 * timer callback can run late, and letting go once the ring is full must send, not cancel.
 */
export function SosButton({ busy, onTrigger }: { busy: boolean; onTrigger: () => void }) {
  const { t } = useI18n();
  const [progress, setProgress] = useState(0);
  const startedAt = useRef<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frame = useRef<number | null>(null);

  const stop = () => {
    if (timer.current) clearTimeout(timer.current);
    if (frame.current) cancelAnimationFrame(frame.current);
    timer.current = null;
    frame.current = null;
    startedAt.current = null;
    setProgress(0);
  };

  const draw = () => {
    if (startedAt.current === null) return;
    setProgress(Math.min((clock() - startedAt.current) / HOLD_MS, 1));
    frame.current = requestAnimationFrame(draw);
  };

  const fire = () => {
    stop();
    if (navigator.vibrate) navigator.vibrate(200);
    onTrigger();
  };

  const begin = () => {
    if (busy || timer.current) return;
    startedAt.current = clock();
    timer.current = setTimeout(fire, HOLD_MS);
    frame.current = requestAnimationFrame(draw);
  };

  /** Let go: send if the full 2 seconds have passed (even if the timer hasn't run yet). */
  const release = () => {
    if (startedAt.current !== null && clock() - startedAt.current >= HOLD_MS) fire();
    else stop();
  };

  useEffect(() => () => stop(), []);

  const holding = progress > 0;
  return (
    <div className="flex flex-col items-center">
      <button
        type="button"
        disabled={busy}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          begin();
        }}
        onPointerUp={release}
        onPointerCancel={stop}
        onKeyDown={(e) => {
          if ((e.key === " " || e.key === "Enter") && !e.repeat) {
            e.preventDefault();
            begin();
          }
        }}
        onKeyUp={release}
        onContextMenu={(e) => e.preventDefault()}
        aria-label={t.citizen.sosHold}
        className="relative grid h-56 w-56 touch-none place-items-center rounded-full select-none disabled:cursor-wait"
      >
        <span className="absolute inset-4 animate-pulse-ring rounded-full bg-sos/40" aria-hidden="true" />
        <svg className="absolute inset-0 -rotate-90" viewBox="0 0 200 200" aria-hidden="true">
          <circle cx="100" cy="100" r="92" fill="none" stroke="var(--color-sos-soft)" strokeWidth="8" />
          <circle
            cx="100"
            cy="100"
            r="92"
            fill="none"
            stroke="var(--color-sos-strong)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={RING}
            strokeDashoffset={RING * (1 - progress)}
          />
        </svg>
        <span
          className={cn(
            "relative grid h-44 w-44 place-items-center rounded-full bg-sos text-white shadow-[0_20px_50px_-12px_rgb(229_72_77/0.7)] transition",
            holding && "scale-95 bg-sos-strong",
          )}
        >
          <span className="flex flex-col items-center gap-1.5">
            {busy ? <Loader2 className="h-9 w-9 animate-spin" /> : <ShieldAlert className="h-10 w-10" />}
            <span className="text-2xl font-bold tracking-wide">SOS</span>
          </span>
        </span>
      </button>
      <p className="mt-4 text-sm font-medium text-ink-soft" aria-live="polite">
        {busy ? t.citizen.sosSending : holding ? t.citizen.sosHolding : t.citizen.sosHold}
      </p>
      <p className="mt-1 max-w-xs text-center text-xs text-muted">{t.citizen.sosHint}</p>
    </div>
  );
}
