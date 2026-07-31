"use client";

import Link from "next/link";
import { AlertCircle, ArrowDown, CheckCircle2, CircleDot, ExternalLink, FlaskConical, MapPinned, RotateCw } from "lucide-react";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Section } from "@/components/layout/section";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRoadmapDataSource, useRoadmapQuery } from "@/hooks/use-services";
import { roadmapPhaseStatuses } from "@/lib/capability-status";
import type { Capability, DataSource, RoadmapPhase, RoadmapPhaseStatus } from "@/types/domain";

const expectedPhaseIds = ["foundation", "agent-workflow", "llmops", "product-intelligence", "enterprise", "research"];

function PhaseStatusBadge({ status }: { status: RoadmapPhaseStatus }) {
  const definition = roadmapPhaseStatuses[status];
  return <span className={`inline-flex min-h-6 items-center rounded-full border px-2 text-xs font-medium ${definition.className}`}>{definition.label}</span>;
}

function CapabilityGroup({ title, description, capabilities }: RoadmapPhase["capabilityGroups"][number]) {
  if (capabilities.length === 0) return null;
  return <div className="rounded-lg border bg-background/50 p-4"><h3 className="font-medium">{title}</h3>{description ? <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p> : null}<ul className="mt-4 space-y-3">{capabilities.map((capability) => <CapabilityItem capability={capability} key={capability.name} />)}</ul></div>;
}

function CapabilityItem({ capability }: { capability: Capability }) {
  return <li className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-sm font-medium">{capability.name}</p><p className="mt-1 text-sm leading-5 text-muted-foreground">{capability.detail}</p></div><StatusBadge status={capability.status} /></li>;
}

function RoadmapTimeline({ phases }: { phases: readonly RoadmapPhase[] }) {
  const columns = [
    { title: "Completed", phases: phases.filter((phase) => phase.status === "completed"), accent: "bg-status-completed" },
    { title: "In progress", phases: phases.filter((phase) => phase.status === "in_progress"), accent: "bg-status-progress" },
    { title: "Future and research", phases: phases.filter((phase) => phase.status === "future" || phase.status === "research"), accent: "bg-status-research" },
  ];

  return <nav aria-label="Roadmap phases"><div className="grid gap-5 xl:grid-cols-3">{columns.map((column) => <section className="overflow-hidden rounded-xl border bg-card/35" key={column.title}><header className="flex items-center gap-3 border-b px-5 py-4"><span aria-hidden="true" className={`size-2.5 rounded-full ${column.accent}`} /><h3 className="font-semibold">{column.title}</h3><span className="ml-auto font-mono text-xs text-muted-foreground">{column.phases.length}</span></header><ol className="space-y-3 p-3">{column.phases.map((phase) => <li key={phase.id}><a aria-label={`Jump to ${phase.title}`} className={`block rounded-lg border p-4 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${phase.status === "in_progress" ? "border-status-progress/60 bg-status-progress/10" : "bg-background/60"}`} href={`#${phase.id}`}><div className="flex items-start justify-between gap-3"><span className="font-mono text-xs text-muted-foreground">PHASE {phase.number}</span><PhaseStatusBadge status={phase.status} /></div><p className="mt-4 font-medium">{phase.title}</p><p className="mt-2 text-sm leading-5 text-muted-foreground">{phase.description}</p></a></li>)}</ol></section>)}</div></nav>;
}

function PhaseSection({ phase }: { phase: RoadmapPhase }) {
  const isCurrent = phase.status === "in_progress";
  return <article aria-labelledby={`${phase.id}-heading`} className={`scroll-mt-6 rounded-xl border p-5 sm:p-6 ${isCurrent ? "border-status-progress/60 bg-status-progress/5" : "bg-card/30"}`} id={phase.id}><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-mono text-xs tracking-[0.14em] text-muted-foreground uppercase">Phase {phase.number}</p><h2 className="mt-2 text-2xl font-semibold tracking-tight" id={`${phase.id}-heading`}>{phase.title}</h2></div><PhaseStatusBadge status={phase.status} /></div>{isCurrent ? <p className="mt-5 flex items-center gap-2 rounded-md border border-status-progress/40 bg-status-progress/10 px-3 py-2 text-sm font-medium"><CircleDot aria-hidden="true" className="size-4" />Current active phase</p> : null}<div className="mt-6 grid gap-5 lg:grid-cols-3"><div><h3 className="text-sm font-medium">Objective</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{phase.objective}</p></div><div><h3 className="text-sm font-medium">Why it matters</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{phase.technicalSignificance}</p></div><div><h3 className="text-sm font-medium">Capability boundary</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{phase.limitations}</p></div></div><div className="mt-6 grid gap-4 lg:grid-cols-2">{phase.capabilityGroups.map((group) => <CapabilityGroup {...group} key={group.title} />)}</div>{phase.relatedRoutes?.length ? <div className="mt-6 flex flex-wrap gap-3">{phase.relatedRoutes.map((route) => <Link className="inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={route.href} key={route.href}>{route.label}<ExternalLink aria-hidden="true" className="size-3.5" /></Link>)}</div> : null}</article>;
}

function LoadingState() {
  return <PageContainer><Section><PageHeader description="Follow the progression from experiment infrastructure and grounded AI to causal analysis and decision intelligence." title="Roadmap" /><div aria-live="polite" className="mt-8 space-y-4"><p className="text-sm text-muted-foreground">Loading repository-backed roadmap…</p><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <Skeleton className="h-40" key={index} />)}</div></div></Section></PageContainer>;
}

function EmptyState() {
  return <Card className="mt-8 p-6" role="status"><h2 className="text-lg font-semibold">Roadmap information is unavailable</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">The configured roadmap source returned no phases. This page does not infer missing status information.</p></Card>;
}

function ErrorState({ onRetry, message }: { onRetry: () => void; message: string }) {
  return <Card aria-live="assertive" className="mt-8 p-6" role="alert"><div className="flex gap-3"><AlertCircle aria-hidden="true" className="mt-0.5 size-5 text-status-unavailable" /><div><h2 className="font-semibold">Roadmap information could not be loaded</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{message}</p><Button className="mt-4" onClick={onRetry} variant="outline"><RotateCw aria-hidden="true" className="size-4" />Retry</Button></div></div></Card>;
}

function RoadmapContent({ phases, source }: { phases: readonly RoadmapPhase[]; source: DataSource }) {
  const completed = phases.filter((phase) => phase.status === "completed").length;
  const current = phases.find((phase) => phase.status === "in_progress");
  const future = phases.filter((phase) => phase.status === "future" || phase.status === "research").length;
  const missingPhases = expectedPhaseIds.filter((id) => !phases.some((phase) => phase.id === id));
  const duplicateNumbers = new Set(phases.map((phase) => phase.number)).size !== phases.length;
  const invalidActivePhase = phases.filter((phase) => phase.status === "in_progress").length !== 1;
  const hasPartialData = missingPhases.length > 0 || duplicateNumbers || invalidActivePhase;

  return <PageContainer><Section><PageHeader actions={current ? <PhaseStatusBadge status={current.status} /> : undefined} description="Follow the progression from experiment infrastructure and grounded AI to causal analysis and decision intelligence." title="Roadmap" /><div className="mt-4 flex items-start gap-2 text-sm text-muted-foreground"><MapPinned aria-hidden="true" className="mt-0.5 size-4 shrink-0" /><p><span className="font-medium text-foreground">{source.label}.</span> {source.detail} Status is based on repository implementation and versioned project planning, not a live project-management integration.</p></div>{hasPartialData ? <div className="mt-6 rounded-lg border border-status-planned/40 bg-status-planned/10 p-4 text-sm" role="status"><p className="font-medium">Partial roadmap data</p><p className="mt-1 text-muted-foreground">{missingPhases.length ? `Missing phase metadata: ${missingPhases.join(", ")}. ` : ""}{duplicateNumbers ? "Duplicate phase numbers were returned. " : ""}{invalidActivePhase ? "The source must define exactly one active phase." : ""}</p></div> : null}<section aria-labelledby="current-state" className="mt-8 rounded-xl border border-status-progress/50 bg-status-progress/10 p-5 sm:p-6"><p className="font-mono text-xs tracking-[0.14em] uppercase">Current state</p><h2 className="mt-3 text-2xl font-semibold tracking-tight" id="current-state">{current ? `${current.title} is in progress` : "Current phase unavailable"}</h2><div className="mt-5 grid gap-4 sm:grid-cols-3"><div><p className="text-2xl font-semibold">{completed}</p><p className="text-sm text-muted-foreground">phases completed</p></div><div><p className="text-2xl font-semibold">{future}</p><p className="text-sm text-muted-foreground">future phases</p></div><div><p className="text-sm font-medium">Next meaningful milestone</p><p className="mt-1 text-sm leading-5 text-muted-foreground">Strengthen statistical analysis from validated foundations without treating planned estimators as available.</p></div></div></section><section className="mt-10" aria-labelledby="roadmap-overview"><div className="flex items-center gap-2"><FlaskConical aria-hidden="true" className="size-4 text-primary" /><h2 className="text-xl font-semibold" id="roadmap-overview">Six-phase progression</h2></div><p className="mt-2 text-sm text-muted-foreground">Select a phase to jump to its evidence, technical role, and capability boundary.</p><div className="mt-5"><RoadmapTimeline phases={phases} /></div></section><section className="mt-10 space-y-5" aria-label="Detailed roadmap phases">{phases.map((phase) => <PhaseSection key={phase.id} phase={phase} />)}</section><section className="mt-10 grid gap-6 lg:grid-cols-2"><Card className="p-5"><h2 className="text-lg font-semibold">Status legend</h2><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="font-medium">Completed</dt><dd className="mt-1 text-muted-foreground">Repository-verified implementation.</dd></div><div><dt className="font-medium">In progress</dt><dd className="mt-1 text-muted-foreground">Active development focus, not a completed method.</dd></div><div><dt className="font-medium">Planned</dt><dd className="mt-1 text-muted-foreground">Named direction with no operational product result.</dd></div><div><dt className="font-medium">Future research</dt><dd className="mt-1 text-muted-foreground">Exploratory or future scope, not committed delivery.</dd></div></dl></Card><Card className="p-5"><h2 className="text-lg font-semibold">Portfolio relevance</h2><p className="mt-3 text-sm leading-6 text-muted-foreground">Foundation demonstrates backend and data engineering; agent workflow demonstrates agentic architecture; LLMOps demonstrates reliability engineering; Product Intelligence develops experimentation and causal-inference foundations; enterprise and research phases indicate the next system-design and decision-science directions.</p></Card></section><section className="mt-10 rounded-xl border bg-card/35 p-5 sm:p-6" aria-labelledby="technical-progression"><h2 className="text-lg font-semibold" id="technical-progression">Technical progression</h2><ol className="mt-5 space-y-2 text-sm"><li>Store experiment knowledge <ArrowDown aria-hidden="true" className="mx-2 inline size-3.5" /> Retrieve evidence <ArrowDown aria-hidden="true" className="mx-2 inline size-3.5" /> Generate grounded answers</li><li>Coordinate agent workflows <ArrowDown aria-hidden="true" className="mx-2 inline size-3.5" /> Evaluate AI reliability <ArrowDown aria-hidden="true" className="mx-2 inline size-3.5" /> Apply statistical analysis</li><li>Support decisions <ArrowDown aria-hidden="true" className="mx-2 inline size-3.5" /> Scale toward enterprise and research use</li></ol><p className="mt-5 flex gap-2 text-sm leading-6 text-muted-foreground"><CheckCircle2 aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-status-completed" />The completed stages establish evidence and reliability. Statistical analysis is the active transition; enterprise and research use remain future direction.</p></section><p className="mt-10 max-w-3xl text-sm leading-6 text-muted-foreground">ExperimentOS AI evolves from experiment infrastructure into decision intelligence by keeping evidence, workflow controls, evaluation, and statistical claims explicit at every stage.</p></Section></PageContainer>;
}

export function RoadmapPage() {
  const source = useRoadmapDataSource();
  const { data, error, isError, isLoading, refetch } = useRoadmapQuery();
  if (isLoading) return <LoadingState />;
  if (isError) return <PageContainer><Section><PageHeader description="Follow the progression from experiment infrastructure and grounded AI to causal analysis and decision intelligence." title="Roadmap" /><ErrorState message={error.userMessage} onRetry={() => void refetch()} /></Section></PageContainer>;
  if (!data?.length) return <PageContainer><Section><PageHeader description="Follow the progression from experiment infrastructure and grounded AI to causal analysis and decision intelligence." title="Roadmap" /><EmptyState /></Section></PageContainer>;
  return <RoadmapContent phases={data} source={source} />;
}
