"use client";

import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LanguageToggle({ className }: { className?: string }) {
  const { locale, setLocale } = useI18n();
  return (
    <div
      role="group"
      aria-label="Language"
      className={cn("inline-flex rounded-xl border border-line bg-white p-0.5 text-sm", className)}
    >
      {(["en", "bn"] as const).map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => setLocale(option)}
          aria-pressed={locale === option}
          className={cn(
            "rounded-[10px] px-2.5 py-1 font-medium transition",
            locale === option ? "bg-ink text-white" : "text-muted hover:text-ink",
          )}
        >
          {option === "en" ? "EN" : "বাং"}
        </button>
      ))}
    </div>
  );
}
