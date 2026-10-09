import { cn } from "@/lib/utils";

/** Rokkha mark: a rounded shield holding a location pin with a pulse line. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("h-9 w-9", className)} aria-hidden="true">
      <defs>
        <linearGradient id="rokkha-shield" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f8aa60" />
          <stop offset="1" stopColor="#e5484d" />
        </linearGradient>
      </defs>
      <path
        d="M20 2.5 34.5 8v11.2c0 9.3-6.1 15.8-14.5 18.3C11.6 35 5.5 28.5 5.5 19.2V8L20 2.5Z"
        fill="url(#rokkha-shield)"
      />
      <path
        d="M20 10.5a6.6 6.6 0 0 0-6.6 6.6c0 4.8 6.6 11.4 6.6 11.4s6.6-6.6 6.6-11.4a6.6 6.6 0 0 0-6.6-6.6Z"
        fill="#fff"
      />
      <path
        d="M15.4 17.3h2.3l1.2-2.4 2 4.6 1.3-2.2h2.4"
        fill="none"
        stroke="#e5484d"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="text-lg font-bold tracking-tight text-ink">Rokkha</span>
          <span className="mt-0.5 text-[11px] font-medium text-muted">রক্ষা</span>
        </span>
      )}
    </span>
  );
}
