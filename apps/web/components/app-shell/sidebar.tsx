"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS } from "./nav-items";

export function Sidebar() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="w-52 shrink-0 border-r border-border bg-surface px-3 py-5">
      <p className="mb-4 px-2 text-sm font-semibold tracking-tight">RoleRadarAI</p>
      <ul className="space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`block rounded px-2 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-accent ${
                  active ? "bg-background font-medium" : "text-muted hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
