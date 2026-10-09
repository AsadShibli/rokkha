"use client";

import { Loader2, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Logo } from "@/components/brand/logo";
import { LanguageToggle } from "@/components/language-toggle";
import { Button } from "@/components/ui/button";
import { homeFor, useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Role, User } from "@/lib/types";

/**
 * Signed-in frame. Redirects anonymous visitors to /login (remembering where they were) and
 * sends users of another role to their own home. The API still enforces every permission;
 * this only keeps people on screens that make sense for them.
 */
export function AppShell({
  roles,
  children,
}: {
  roles: Role[];
  children: (user: User) => React.ReactNode;
}) {
  const { status, user, logout } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();

  const allowed = status === "authenticated" && user && roles.includes(user.role);

  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    if (status === "authenticated" && user && !roles.includes(user.role)) {
      router.replace(homeFor(user.role));
    }
  }, [status, user, roles, router, pathname]);

  if (!allowed) {
    return (
      <div className="grid min-h-screen place-items-center text-muted">
        <span className="inline-flex items-center gap-2 text-sm">
          <Loader2 className="h-4 w-4 animate-spin" /> {t.app.loading}
        </span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-30 border-b border-line bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link href={homeFor(user.role)} aria-label="Rokkha home">
            <Logo />
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <span className="hidden rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent-strong sm:inline">
              {t.app.roleLabels[user.role]}
            </span>
            <LanguageToggle />
            <Button variant="ghost" size="sm" onClick={() => void logout()} aria-label={t.nav.signOut}>
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">{t.nav.signOut}</span>
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children(user)}</main>
    </div>
  );
}
