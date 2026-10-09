"use client";

import { AppShell } from "@/components/app/app-shell";
import { useI18n } from "@/lib/i18n";
import type { Role } from "@/lib/types";

/** Placeholder home for each role until its screens land (citizen: Day 2, officer: Day 3, …). */
export function RoleHome({ roles }: { roles: Role[] }) {
  const { t } = useI18n();
  return (
    <AppShell roles={roles}>
      {(user) => (
        <section className="bg-warm rounded-[28px] p-8 sm:p-10">
          <p className="text-sm font-medium text-accent-strong">{t.app.roleLabels[user.role]}</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">
            {t.app.welcome}, {user.name.split(" ")[0]}
          </h1>
          <p className="mt-2 text-muted">{user.phone}</p>
        </section>
      )}
    </AppShell>
  );
}
