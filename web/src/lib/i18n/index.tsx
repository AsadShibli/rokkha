"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { bn } from "./bn";
import { type Dictionary, en } from "./en";

export type Locale = "en" | "bn";

const dictionaries: Record<Locale, Dictionary> = { en, bn };
const STORAGE_KEY = "rokkha.locale";

type I18nValue = { locale: Locale; t: Dictionary; setLocale: (locale: Locale) => void };

const I18nContext = createContext<I18nValue | null>(null);

/*
 * Client-side locale: pages prerender in English (fast static shell), then switch to the
 * saved choice. Keeping it out of cookies/URLs keeps every public page fully static.
 */
export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from storage
      if (saved === "bn" || saved === "en") setLocaleState(saved);
    } catch {
      /* storage blocked: stay on English */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ locale, t: dictionaries[locale], setLocale }),
    [locale, setLocale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside <I18nProvider>");
  return value;
}
