"use client";

import { Building2, BellRing, Loader2, Shield, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { ApiError } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/demo";
import { useI18n } from "@/lib/i18n";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

const roleIcons: Record<Role, typeof Shield> = {
  citizen: UserRound,
  officer: Shield,
  station_admin: Building2,
  super_admin: BellRing,
};

// Free hosting sleeps when idle; if sign-in takes this long, say why.
const SLOW_MS = 4000;

export function LoginForm() {
  const { t } = useI18n();
  const { login, status, user } = useAuth();
  const router = useRouter();
  const params = useSearchParams();

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState<Role | "form" | null>(null);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoDemo = useRef(false);

  const goHome = useCallback(
    (role: Role) => {
      const next = params.get("next");
      router.replace(next?.startsWith("/") ? next : homeFor(role));
    },
    [params, router],
  );

  const signIn = useCallback(
    async (asPhone: string, asPassword: string, source: Role | "form") => {
      setPending(source);
      setError(null);
      const timer = setTimeout(() => setSlow(true), SLOW_MS);
      try {
        const me = await login(asPhone, asPassword);
        goHome(me.role);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t.errors.generic);
        setPending(null);
      } finally {
        clearTimeout(timer);
        setSlow(false);
      }
    },
    [goHome, login, t.errors.generic],
  );

  // Already signed in: go straight to your home.
  useEffect(() => {
    if (status === "authenticated" && user && !pending) goHome(user.role);
  }, [status, user, pending, goHome]);

  // /login?demo=officer (from the landing page role cards) signs in with one click.
  useEffect(() => {
    const demo = DEMO_ACCOUNTS.find((d) => d.role === params.get("demo"));
    if (demo && status === "anonymous" && !autoDemo.current) {
      autoDemo.current = true;
      void signIn(demo.phone, DEMO_PASSWORD, demo.role);
    }
  }, [params, status, signIn]);

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">{t.login.title}</h1>
      <p className="mt-2 text-muted">{t.login.subtitle}</p>

      <form
        className="mt-8 flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void signIn(phone.trim(), password, "form");
        }}
      >
        <Field
          label={t.login.phone}
          type="tel"
          autoComplete="username"
          placeholder="+8801XXXXXXXXX"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          required
        />
        <Field
          label={t.login.password}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && (
          <p role="alert" className="rounded-xl bg-sos-soft px-3.5 py-2.5 text-sm text-sos-strong">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={pending !== null}>
          {pending === "form" && <Loader2 className="h-4 w-4 animate-spin" />}
          {pending === "form" ? t.login.submitting : t.login.submit}
        </Button>
        {slow && <p className="text-center text-sm text-muted">{t.login.coldStart}</p>}
      </form>

      <p className="mt-5 text-sm text-muted">
        {t.login.noAccount}{" "}
        <Link href="/register" className="font-medium text-accent-strong hover:underline">
          {t.login.register}
        </Link>
      </p>

      <div className="mt-10">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-semibold">{t.login.demoTitle}</h2>
          <span className="text-xs text-muted">{t.login.demoHint}</span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2.5">
          {DEMO_ACCOUNTS.map(({ role, phone: demoPhone }) => {
            const Icon = roleIcons[role];
            const busy = pending === role;
            return (
              <button
                key={role}
                type="button"
                disabled={pending !== null}
                onClick={() => void signIn(demoPhone, DEMO_PASSWORD, role)}
                className={cn(
                  "flex items-center gap-3 rounded-2xl border border-line bg-white p-3 text-left transition",
                  "hover:border-accent hover:shadow-card disabled:opacity-60",
                  busy && "border-accent",
                )}
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-strong">
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
                </span>
                <span className="text-sm font-medium">{t.app.roleLabels[role]}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
