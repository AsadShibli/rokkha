"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

import { bn } from "./bn";
import { type Dictionary, en } from "./en";

export type Locale = "en" | "bn";

const dictionaries: Record<Locale, Dictionary> = { en, bn };
const STORAGE_KEY = "rokkha.locale";
const CHANGE_EVENT = "rokkha:locale";

/*
 * The saved locale lives in localStorage and every useI18n() call reads it through
 * useSyncExternalStore. While a component is hydrating, React uses the server snapshot ("en",
 * matching the prerendered HTML) and re-renders with the saved choice right after. Because each
 * consumer subscribes itself, parts that hydrate late (inside Suspense) never mismatch either.
 * Keeping the locale out of cookies and URLs keeps every public page fully static.
 */
let memoryLocale: Locale | null = null; // used when storage is blocked

function readLocale(): Locale {
  try {
    return localStorage.getItem(STORAGE_KEY) === "bn" ? "bn" : "en";
  } catch {
    return memoryLocale ?? "en";
  }
}

const serverLocale = (): Locale => "en";

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange); // other tabs
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function writeLocale(next: Locale) {
  memoryLocale = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* storage blocked: keep it for this page view only */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function useI18n(): { locale: Locale; t: Dictionary; setLocale: (locale: Locale) => void } {
  const locale = useSyncExternalStore(subscribe, readLocale, serverLocale);
  const setLocale = useCallback((next: Locale) => writeLocale(next), []);
  return { locale, t: dictionaries[locale], setLocale };
}

/** Keeps <html lang> in step with the chosen language (screen readers, Bangla hyphenation). */
export function I18nProvider({ children }: { children: React.ReactNode }) {
  const { locale } = useI18n();
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  return children;
}
