"use client";

import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { LanguageToggle } from "@/components/language-toggle";
import { useI18n } from "@/lib/i18n";

/** Split screen: warm brand panel on large screens, form on the right. */
export function AuthLayout({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="bg-warm relative hidden flex-col justify-between overflow-hidden p-12 lg:flex">
        <Link href="/" aria-label="Rokkha home">
          <Logo />
        </Link>
        <div className="max-w-md">
          <h2 className="text-4xl leading-tight font-bold tracking-tight">{t.login.panelTitle}</h2>
          <p className="mt-4 text-lg text-muted">{t.login.panelBody}</p>
        </div>
        <div className="absolute -right-24 -bottom-24 h-80 w-80 rounded-full bg-sos/10 blur-2xl" />
        <p className="text-sm text-muted">{t.brand.tagline}</p>
      </aside>

      <main className="flex flex-col">
        <div className="flex items-center justify-between p-4 sm:p-6">
          <Link href="/" className="lg:invisible" aria-label="Rokkha home">
            <Logo />
          </Link>
          <LanguageToggle />
        </div>
        <div className="flex flex-1 items-center justify-center px-4 pb-12 sm:px-6">
          <div className="w-full max-w-md">{children}</div>
        </div>
      </main>
    </div>
  );
}
