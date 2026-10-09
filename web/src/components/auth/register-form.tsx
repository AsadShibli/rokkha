"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export function RegisterForm() {
  const { t } = useI18n();
  const { login } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", phone: "", email: "", password: "" });
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(false);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api.post(
        "/auth/register",
        { ...form, phone: form.phone.trim(), email: form.email.trim() || null },
        false,
      );
      const me = await login(form.phone.trim(), form.password);
      router.replace(homeFor(me.role));
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "UNKNOWN", t.errors.generic));
      setPending(false);
    }
  }

  const fieldError = (field: string) => error?.fieldError(field);
  const general = error && error.details.length === 0 ? error.message : null;

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">{t.register.title}</h1>
      <p className="mt-2 text-muted">{t.register.subtitle}</p>

      <form className="mt-8 flex flex-col gap-4" onSubmit={submit} noValidate>
        <Field
          label={t.register.name}
          autoComplete="name"
          value={form.name}
          onChange={set("name")}
          error={fieldError("name")}
          required
        />
        <Field
          label={t.login.phone}
          type="tel"
          autoComplete="tel"
          placeholder="+8801XXXXXXXXX"
          hint="+8801XXXXXXXXX"
          value={form.phone}
          onChange={set("phone")}
          error={fieldError("phone")}
          required
        />
        <Field
          label={t.register.email}
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={set("email")}
          error={fieldError("email")}
        />
        <Field
          label={t.login.password}
          type="password"
          autoComplete="new-password"
          value={form.password}
          onChange={set("password")}
          error={fieldError("password")}
          hint="8+"
          required
        />
        {general && (
          <p role="alert" className="rounded-xl bg-sos-soft px-3.5 py-2.5 text-sm text-sos-strong">
            {general}
          </p>
        )}
        <Button type="submit" size="lg" disabled={pending}>
          {pending && <Loader2 className="h-4 w-4 animate-spin" />}
          {pending ? t.register.submitting : t.register.submit}
        </Button>
      </form>

      <p className="mt-5 text-sm text-muted">
        {t.register.haveAccount}{" "}
        <Link href="/login" className="font-medium text-accent-strong hover:underline">
          {t.register.signIn}
        </Link>
      </p>
    </div>
  );
}
