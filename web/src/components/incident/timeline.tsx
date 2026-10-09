"use client";

import { type IncidentEvent, statusDot } from "@/lib/incidents";
import { useI18n } from "@/lib/i18n";
import { formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Status history, newest last, from the incident's append-only event log. */
export function Timeline({ events }: { events: IncidentEvent[] }) {
  const { t, locale } = useI18n();
  return (
    <ol className="relative flex flex-col gap-5 pl-6">
      <span className="absolute top-1.5 bottom-1.5 left-[7px] w-px bg-line" aria-hidden="true" />
      {events.map((event, i) => {
        const reassigned = event.from_status && event.from_status !== "pending" && event.to_status === "assigned";
        return (
          <li key={event.id} className="relative">
            <span
              className={cn(
                "absolute top-1 -left-6 h-3.5 w-3.5 rounded-full border-[3px] border-white ring-1 ring-line",
                statusDot[event.to_status],
                i === events.length - 1 && "ring-2 ring-accent",
              )}
            />
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <p className="text-sm font-semibold">
                {reassigned ? `${t.incident.events.assigned} ↻` : t.incident.events[event.to_status]}
              </p>
              <time className="text-xs text-muted" dateTime={event.created_at}>
                {formatTime(event.created_at, locale)}
              </time>
            </div>
            {(event.note || event.actor_id === null) && (
              <p className="mt-0.5 text-sm text-muted">{event.note ?? t.incident.bySystem}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
