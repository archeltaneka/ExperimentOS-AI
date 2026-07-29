import type { ReactNode } from "react";
import Link from "next/link";
import { ExternalLink, GitBranch } from "lucide-react";
import { MobileNavigation } from "@/components/mobile-navigation";
import { Navigation } from "@/components/navigation";

export function ApplicationShell({ children }: { children: ReactNode }) {
  return <div className="min-h-screen lg:grid lg:grid-cols-[17rem_minmax(0,1fr)]"><aside className="sticky top-0 hidden h-screen border-r bg-card/35 px-4 py-6 lg:flex lg:flex-col"><div className="mb-9 px-3"><p className="font-semibold tracking-tight">ExperimentOS AI</p><p className="mt-2 text-xs leading-5 text-muted-foreground">Experiment analysis evidence and decision support.</p></div><Navigation /><div className="mt-auto space-y-1"><Link className="flex min-h-11 items-center gap-3 rounded-md px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="/"><ExternalLink aria-hidden="true" className="size-4" />View demo</Link><a className="flex min-h-11 items-center gap-3 rounded-md px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="https://github.com/archeltaneka/ExperimentOS-AI"><GitBranch aria-hidden="true" className="size-4" />GitHub</a></div></aside><div className="min-w-0"><header className="flex h-16 items-center justify-between border-b px-5 sm:px-8 lg:hidden"><span className="font-semibold">ExperimentOS AI</span><MobileNavigation /></header><main>{children}</main></div></div>;
}
