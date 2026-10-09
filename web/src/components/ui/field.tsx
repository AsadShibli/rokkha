import { useId } from "react";

import { cn } from "@/lib/utils";

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: string;
};

/** Labelled input with inline error, wired up for screen readers. */
export function Field({ label, error, hint, className, ...props }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium text-ink-soft">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(
          "h-11 rounded-xl border bg-white px-3.5 text-[15px] text-ink outline-none transition",
          "placeholder:text-muted/70 focus:border-accent-strong focus:ring-4 focus:ring-accent/20",
          error ? "border-sos" : "border-line",
        )}
        {...props}
      />
      {error ? (
        <p id={`${id}-error`} className="text-sm text-sos-strong">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
