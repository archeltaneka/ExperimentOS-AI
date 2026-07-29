"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { navigationItems } from "@/lib/navigation";
import { cn } from "@/lib/utils";

export function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary navigation" className="space-y-1">
      {navigationItems.map(({ href, icon: Icon, label, description }) => {
        const active = pathname === href;
        return <Link aria-current={active ? "page" : undefined} className={cn("flex min-h-11 items-center gap-3 rounded-md px-3 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", active && "bg-accent text-accent-foreground")} href={href} key={href} onClick={onNavigate} title={description}><Icon aria-hidden="true" className="size-4 shrink-0" />{label}</Link>;
      })}
    </nav>
  );
}
