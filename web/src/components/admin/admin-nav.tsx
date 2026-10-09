"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useI18n } from "@/lib/i18n";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

export function AdminNav({ role }: { role: Role }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const items = [
    { href: "/admin", label: t.admin.nav.overview },
    { href: "/admin/officers", label: t.admin.nav.officers },
    { href: "/admin/gds", label: t.admin.nav.gds },
    ...(role === "super_admin" ? [{ href: "/admin/stations", label: t.admin.nav.stations }] : []),
  ];
  return (
    <nav className="mb-6 -mt-2 flex gap-1 overflow-x-auto border-b border-line" aria-label="Admin">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "border-b-2 px-3.5 py-2.5 text-sm font-medium whitespace-nowrap transition",
              active ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
