import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowUpRight, ExternalLink, GitBranch, Layers, BookOpen } from "lucide-react";
import { MobileNavigation } from "@/components/mobile-navigation";
import { Navigation } from "@/components/navigation";

export function ApplicationShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      <a className="sr-only fixed left-4 top-4 z-[60] rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only focus:outline-none focus:ring-2 focus:ring-ring" href="#main-content">Skip to main content</a>
      <aside className="atlas-rail sticky top-0 hidden h-screen flex-col px-4 py-7 lg:flex">
        <div className="mb-10 px-2">
          <div className="atlas-brand"><span className="atlas-brand-mark"><Layers aria-hidden="true" className="size-5" /></span><p className="text-lg font-semibold tracking-tight">ExperimentOS <span className="text-primary">AI</span></p></div>
          <p className="mt-5 text-sm leading-6 text-muted-foreground">Experiment analysis evidence and decision support.</p>
        </div>
        <Navigation />
        <div className="mt-auto pt-10">
          <div className="mb-5 border-y border-border px-2 py-5"><BookOpen aria-hidden="true" className="mb-3 size-5 text-primary" /><p className="text-sm font-medium">Every answer has a source.</p><p className="mt-2 text-xs leading-5 text-muted-foreground">Follow the evidence from experiment to decision.</p></div>
          <Link className="flex min-h-11 items-center gap-3 rounded-md px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground" href="/"><ExternalLink aria-hidden="true" className="size-4" />Product overview</Link>
          <a className="flex min-h-11 items-center gap-3 rounded-md px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground" href="https://github.com/archeltaneka/ExperimentOS-AI" rel="noreferrer" target="_blank"><GitBranch aria-hidden="true" className="size-4" />GitHub <ArrowUpRight aria-hidden="true" className="ml-auto size-4" /><span className="sr-only">(opens in a new tab)</span></a>
        </div>
      </aside>
      <div className="min-w-0">
        <div className="atlas-topbar"><p><Layers aria-hidden="true" className="size-4" />Experiment intelligence / Workspace</p><p>Evidence. Context. Decisions.</p></div>
        <header className="atlas-rail flex min-h-18 items-center justify-between gap-3 px-5 py-3 lg:hidden"><span className="font-semibold">ExperimentOS AI</span><MobileNavigation /></header>
        <main id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
