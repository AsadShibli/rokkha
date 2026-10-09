"use client";

import {
  ArrowRight,
  BellRing,
  Building2,
  FileText,
  LayoutDashboard,
  MapPinned,
  Radio,
  Shield,
  Sparkles,
  TimerReset,
  UserRound,
} from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { LanguageToggle } from "@/components/language-toggle";
import { ButtonLink } from "@/components/ui/button";
import { API_DOCS_URL, SOURCE_URL } from "@/lib/demo";
import { useI18n } from "@/lib/i18n";
import type { Role } from "@/lib/types";

import { HeroVisual } from "./hero-visual";

const featureIcons = [Radio, MapPinned, TimerReset, FileText, Sparkles, LayoutDashboard];
const roleIcons: Record<Role, typeof Shield> = {
  citizen: UserRound,
  officer: Shield,
  station_admin: Building2,
  super_admin: BellRing,
};

export function Landing() {
  const { t } = useI18n();

  return (
    <div className="flex min-h-screen flex-col">
      {/* nav */}
      <header className="sticky top-0 z-30 border-b border-line/60 bg-canvas/80 backdrop-blur">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" aria-label="Rokkha home">
            <Logo />
          </Link>
          <div className="hidden items-center gap-7 text-sm text-ink-soft md:flex">
            <a href="#how" className="hover:text-ink">{t.nav.how}</a>
            <a href="#features" className="hover:text-ink">{t.nav.features}</a>
            <a href="#roles" className="hover:text-ink">{t.nav.roles}</a>
            <a href={API_DOCS_URL} target="_blank" rel="noreferrer" className="hover:text-ink">
              {t.nav.apiDocs}
            </a>
          </div>
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ButtonLink href="/login" size="sm" className="hidden sm:inline-flex">
              {t.nav.tryDemo}
            </ButtonLink>
          </div>
        </nav>
      </header>

      <main className="flex-1">
        {/* hero */}
        <section className="bg-warm overflow-hidden">
          <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:py-24">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-accent/40 bg-white/70 px-3 py-1 text-xs font-medium text-accent-strong">
                <span className="h-1.5 w-1.5 rounded-full bg-sos" />
                {t.hero.eyebrow}
              </span>
              <h1 className="mt-5 text-4xl leading-[1.08] font-bold tracking-tight text-balance sm:text-5xl lg:text-6xl">
                {t.hero.titleStart} <span className="text-accent">{t.hero.titleAccent}</span>
              </h1>
              <p className="mt-5 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
                {t.hero.body}
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <ButtonLink href="/login" size="lg">
                  {t.hero.primary}
                  <ArrowRight className="h-4 w-4" />
                </ButtonLink>
                <ButtonLink href={API_DOCS_URL} target="_blank" rel="noreferrer" size="lg" variant="outline">
                  {t.hero.secondary}
                </ButtonLink>
              </div>
            </div>
            <HeroVisual />
          </div>
        </section>

        {/* stats */}
        <section className="border-y border-line bg-white">
          <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-px bg-line px-0 sm:px-6 lg:grid-cols-4">
            {t.stats.map((stat) => (
              <div key={stat.label} className="bg-white px-5 py-7">
                <dt className="sr-only">{stat.label}</dt>
                <dd className="text-3xl font-bold tracking-tight">{stat.value}</dd>
                <dd className="mt-1 text-sm text-muted">{stat.label}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* how it works */}
        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6">
          <h2 className="max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">{t.how.title}</h2>
          <ol className="mt-10 grid gap-5 md:grid-cols-3">
            {t.how.steps.map((step, i) => (
              <li key={step.title} className="rounded-3xl border border-line bg-white p-6 shadow-card">
                <span className="grid h-10 w-10 place-items-center rounded-full bg-accent-soft text-sm font-bold text-accent-strong">
                  0{i + 1}
                </span>
                <h3 className="mt-5 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* features */}
        <section id="features" className="scroll-mt-20 bg-cream/60 py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
              {t.features.title}
            </h2>
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {t.features.items.map((feature, i) => {
                const Icon = featureIcons[i];
                return (
                  <div key={feature.title} className="rounded-3xl bg-white p-6 shadow-card">
                    <span className="grid h-11 w-11 place-items-center rounded-2xl bg-ink text-white">
                      <Icon className="h-5 w-5" />
                    </span>
                    <h3 className="mt-5 font-semibold">{feature.title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-muted">{feature.body}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* roles */}
        <section id="roles" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t.roles.title}</h2>
          <p className="mt-3 max-w-xl text-muted">{t.roles.body}</p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {(Object.keys(roleIcons) as Role[]).map((role) => {
              const Icon = roleIcons[role];
              const item = t.roles.items[role];
              return (
                <Link
                  key={role}
                  href={`/login?demo=${role}`}
                  className="group rounded-3xl border border-line bg-white p-6 transition hover:-translate-y-0.5 hover:border-accent hover:shadow-card"
                >
                  <Icon className="h-6 w-6 text-accent-strong" />
                  <h3 className="mt-4 font-semibold">{item.name}</h3>
                  <p className="mt-1.5 text-sm text-muted">{item.body}</p>
                  <ArrowRight className="mt-4 h-4 w-4 text-muted transition group-hover:translate-x-1 group-hover:text-ink" />
                </Link>
              );
            })}
          </div>
        </section>

        {/* CTA */}
        <section className="px-4 pb-20 sm:px-6">
          <div className="bg-warm mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 rounded-[32px] p-8 sm:flex-row sm:items-center sm:p-12">
            <div>
              <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t.cta.title}</h2>
              <p className="mt-2 text-muted">{t.cta.body}</p>
            </div>
            <ButtonLink href="/login" size="lg">
              {t.cta.button}
              <ArrowRight className="h-4 w-4" />
            </ButtonLink>
          </div>
        </section>
      </main>

      <footer className="border-t border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex items-center gap-3">
            <Logo compact />
            <span>{t.footer.note}</span>
          </div>
          <a href={SOURCE_URL} target="_blank" rel="noreferrer" className="font-medium text-ink hover:text-accent-strong">
            {t.footer.source}
          </a>
        </div>
      </footer>
    </div>
  );
}
