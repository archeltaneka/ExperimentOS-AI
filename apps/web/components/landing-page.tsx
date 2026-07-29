import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  Bot,
  CheckCircle2,
  Database,
  ExternalLink,
  GitBranch,
  GitPullRequest,
  Network,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { capabilityStatuses } from "@/lib/capability-status";
import {
  architectureStages,
  capabilityGroups,
  capabilityStatusGroups,
  demoUrl,
  githubUrl,
  roadmapSummary,
} from "@/lib/landing-content";
import type { CapabilityStatus, RoadmapPhase } from "@/types/domain";

function StatusBadge({ status }: { status: CapabilityStatus }) {
  const definition = capabilityStatuses[status];
  return <Badge className={definition.className}>{definition.label}</Badge>;
}

function CtaGroup() {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <Link className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={demoUrl}>
        Launch Demo <ArrowRight aria-hidden="true" className="size-4" />
      </Link>
      <a className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-input px-4 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={githubUrl} rel="noreferrer" target="_blank">
        View GitHub <ExternalLink aria-hidden="true" className="size-4" />
      </a>
    </div>
  );
}

function SectionHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return <header className="max-w-2xl"><p className="text-xs font-semibold tracking-[0.18em] text-primary uppercase">{eyebrow}</p><h2 className="mt-3 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">{title}</h2><div className="mt-4 text-sm leading-6 text-muted-foreground sm:text-base">{children}</div></header>;
}

function PublicHeader() {
  return <header className="border-b border-border bg-background/95"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-4 sm:px-8"><Link className="rounded-sm font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="/">ExperimentOS <span className="text-primary">AI</span></Link><nav aria-label="Landing page navigation" className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground"><a className="rounded-sm hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="#architecture">Architecture</a><a className="rounded-sm hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="#engineering">Engineering</a><a className="rounded-sm hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="#status">Status</a><a aria-label="View ExperimentOS AI on GitHub" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-input px-3 text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={githubUrl} rel="noreferrer" target="_blank"><GitBranch aria-hidden="true" className="size-4" />GitHub</a><Link className="inline-flex min-h-10 items-center rounded-md bg-primary px-3 font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={demoUrl}>Launch Demo</Link></nav></div></header>;
}

function ArchitectureFlow() {
  return <div aria-label="ExperimentOS system architecture" className="mt-10 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{architectureStages.map((stage, index) => <article className="relative min-w-0 rounded-lg border bg-card/60 p-4" key={stage.title}><p className="text-xs font-semibold text-muted-foreground">0{index + 1}</p><div className="mt-2 flex items-start justify-between gap-2"><p className="text-sm font-semibold">{stage.title}</p><StatusBadge status={stage.status} /></div><p className="mt-3 text-sm leading-5 text-muted-foreground">{stage.detail}</p>{index < architectureStages.length - 1 ? <ArrowRight aria-hidden="true" className="absolute -bottom-5 left-1/2 z-10 size-4 -translate-x-1/2 bg-card text-muted-foreground sm:hidden" /> : null}</article>)}</div>;
}

function RoadmapSummary({ phases }: { phases: readonly RoadmapPhase[] }) {
  return <ol className="mt-9 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{roadmapSummary(phases).map((phase) => <li className="rounded-lg border bg-card/40 p-4" key={phase.id}><div className="flex items-center justify-between gap-3"><h3 className="font-medium">{phase.title}</h3><StatusBadge status={phase.status === "in_progress" ? "in-progress" : phase.status === "future" ? "future-research" : phase.status} /></div><p className="mt-2 text-sm leading-5 text-muted-foreground">{phase.description}</p></li>)}</ol>;
}

export function LandingPage({ roadmap }: { roadmap: readonly RoadmapPhase[] }) {
  return <div className="min-h-screen bg-background"><PublicHeader /><main><section className="mx-auto grid max-w-7xl gap-10 px-5 py-16 sm:px-8 sm:py-24 lg:grid-cols-[minmax(0,1fr)_25rem] lg:items-center"><div><p className="text-xs font-semibold tracking-[0.18em] text-primary uppercase">Agentic product experimentation</p><h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">Evidence-backed answers for product experiments.</h1><p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">ExperimentOS turns fragmented reports, metrics, and decisions into retrievable evidence for grounded questions, coordinated analysis, and more reliable product decisions.</p><div className="mt-8"><CtaGroup /></div><p className="mt-5 inline-flex items-center gap-2 text-sm text-muted-foreground"><CheckCircle2 aria-hidden="true" className="size-4 text-status-completed" />Core retrieval, RAG, agents, and evaluation workflows are implemented.</p></div><aside className="rounded-xl border bg-card/70 p-5"><p className="font-mono text-xs text-primary">evidence → answer → decision</p><div className="mt-5 space-y-4"><div className="border-l-2 border-status-completed pl-4"><p className="text-sm font-medium">Grounded by retrieval</p><p className="mt-1 text-sm text-muted-foreground">Citations and retrieved chunks preserve the evidence trail.</p></div><div className="border-l-2 border-status-completed pl-4"><p className="text-sm font-medium">Coordinated by agents</p><p className="mt-1 text-sm text-muted-foreground">LangGraph runs a structured workflow with human approval.</p></div><div className="border-l-2 border-status-progress pl-4"><p className="text-sm font-medium">Extending into analysis</p><p className="mt-1 text-sm text-muted-foreground">Statistical eligibility and descriptive summaries are in place; causal estimators are not.</p></div></div></aside></section>

  <section className="border-y bg-card/25"><div className="mx-auto grid max-w-7xl gap-10 px-5 py-16 sm:px-8 lg:grid-cols-2"><SectionHeading eyebrow="The problem" title="Experiment knowledge is hard to reconstruct.">Product Data Scientists and teams often need to piece together records, metric outputs, reports, statistical results, decisions, and documentation before they can answer a basic experiment question with confidence.</SectionHeading><div className="grid gap-3 sm:grid-cols-2">{["Experiment records", "Metric outputs", "Reports and evidence", "Decisions and caveats"].map((item) => <div className="rounded-lg border bg-background/60 p-4 text-sm" key={item}>{item}</div>)}</div></div></section>

  <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-24"><SectionHeading eyebrow="The solution" title="A traceable route from evidence to better decisions.">ExperimentOS retrieves the right context first, then makes the answer, workflow, and reliability signals inspectable rather than opaque.</SectionHeading><div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-5">{capabilityGroups.map((capability) => <article className="rounded-lg border bg-card/40 p-4" key={capability.title}><StatusBadge status={capability.status} /><h3 className="mt-5 font-medium">{capability.title}</h3><p className="mt-2 text-sm leading-5 text-muted-foreground">{capability.detail}</p></article>)}</div></section>

  <section className="border-y bg-card/25" id="architecture"><div className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-24"><SectionHeading eyebrow="Architecture" title="Designed as a system, not a chat surface.">The core evidence path is implemented through Agent Workflow. Statistical Analysis is partially implemented; Decision Intelligence is deliberately marked planned.</SectionHeading><ArchitectureFlow /><p className="mt-6 text-sm text-muted-foreground">Infrastructure: PostgreSQL and pgvector store evidence; FastAPI serves typed backend contracts; LangGraph coordinates workflow state; evaluation, observability, and CI guard reliability.</p></div></section>

  <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-24"><SectionHeading eyebrow="How it works" title="Specific steps, explicit boundaries.">The workflow keeps data provenance and reliability visible as the system moves from raw experiment context to a decision-supporting answer.</SectionHeading><ol className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[[Database,"Store experiment context","Load structured metadata, metrics, and report documents."],[ScanSearch,"Retrieve relevant evidence","Search semantic report chunks scoped to the experiment."],[Sparkles,"Generate a grounded answer","Use retrieved context and return citations instead of unsupported claims."],[Network,"Coordinate analysis through agents","Route deterministic workflow state through retrieval, analysis, risk, decision, approval, and summary steps."],[ShieldCheck,"Evaluate reliability","Measure outputs with offline evaluators, regressions, and quality policy."],[ArrowDown,"Support better decisions","Preserve what is complete today while keeping advanced methods explicitly planned."]].map(([Icon,title,detail], index) => { const StepIcon = Icon as typeof Database; return <li className="flex gap-4 rounded-lg border p-4" key={title as string}><StepIcon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-primary" /><div><p className="text-xs font-semibold text-muted-foreground">0{index + 1}</p><h3 className="mt-1 font-medium">{title as string}</h3><p className="mt-2 text-sm leading-5 text-muted-foreground">{detail as string}</p></div></li>})}</ol></section>

  <section className="border-y bg-card/25" id="engineering"><div className="mx-auto grid max-w-7xl gap-10 px-5 py-16 sm:px-8 sm:py-24 lg:grid-cols-[0.9fr_1.1fr]"><SectionHeading eyebrow="Technical depth" title="Engineering constraints are part of the product.">This is a backend-first system with typed boundaries and deterministic development paths, built to make AI behaviour inspectable and repeatable.</SectionHeading><div className="grid gap-3 sm:grid-cols-2">{[[Bot,"Typed services","FastAPI and strict frontend service contracts keep transport details out of UI code."],[Workflow,"Reliable workflows","LangGraph state, human approval, and prompt versioning keep orchestration explicit."],[GitPullRequest,"Evaluated changes","Deterministic evaluation, RAGAS, DeepEval, prompt regression, and CI quality gates test reliability."],[ShieldCheck,"Observable execution","Phoenix, LangSmith, and OpenTelemetry integrations are available as optional, disabled-by-default sinks."]].map(([Icon,title,detail]) => { const ItemIcon = Icon as typeof Bot; return <article className="rounded-lg border bg-background/60 p-4" key={title as string}><ItemIcon aria-hidden="true" className="size-5 text-primary" /><h3 className="mt-4 font-medium">{title as string}</h3><p className="mt-2 text-sm leading-5 text-muted-foreground">{detail as string}</p></article>})}</div></div></section>

  <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-24"><SectionHeading eyebrow="Technology stack" title="Tools selected for clear system boundaries.">No logo wall—each layer has a defined job in the evidence and reliability workflow.</SectionHeading><dl className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[["Frontend","Next.js App Router, TypeScript, Tailwind"],["Backend","FastAPI, Pydantic, SQLAlchemy"],["Retrieval and AI","PostgreSQL, pgvector, embedding and LLM adapters"],["Agent orchestration","LangGraph, structured agent state, approval workflow"],["Evaluation and observability","Deterministic evaluators, RAGAS, DeepEval, Phoenix, LangSmith, OpenTelemetry"],["Infrastructure and quality","Alembic, Docker Compose, GitHub Actions, CI quality gates"]].map(([term,description]) => <div className="rounded-lg border bg-card/40 p-4" key={term}><dt className="font-medium">{term}</dt><dd className="mt-2 text-sm leading-5 text-muted-foreground">{description}</dd></div>)}</dl></section>

  <section className="border-y bg-card/25" id="status"><div className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-24"><SectionHeading eyebrow="Current implementation status" title="What is real today, and what is not.">The capability boundary is intentionally explicit. Planned causal and business-impact methods do not produce operational results in this project.</SectionHeading><div className="mt-10 grid gap-4 lg:grid-cols-3">{capabilityStatusGroups.map((group) => <article className="rounded-lg border bg-background/60 p-5" key={group.title}><div className="flex items-center justify-between gap-3"><h3 className="font-medium">{group.title}</h3><StatusBadge status={group.status} /></div><ul className="mt-4 space-y-2 text-sm text-muted-foreground">{group.items.map((item) => { const status = item === "Double Machine Learning" ? "future-research" : group.status; return <li className="flex items-center gap-2" key={item}><span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-current" />{item}<span className="ml-auto"><StatusBadge status={status} /></span></li>; })}</ul></article>)}</div></div></section>

  <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-24"><SectionHeading eyebrow="Roadmap summary" title="A focused path from foundation to research.">This summary uses the shared local roadmap service. The dedicated Roadmap view remains a placeholder for its own issue.</SectionHeading><RoadmapSummary phases={roadmap} /><Link className="mt-7 inline-flex min-h-11 items-center gap-2 rounded-md border border-input px-4 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="/roadmap">View full roadmap <ArrowRight aria-hidden="true" className="size-4" /></Link></section>

  <section className="border-t bg-card/25"><div className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-20"><h2 className="max-w-xl text-3xl font-semibold tracking-tight">Explore the evidence workflow behind ExperimentOS AI.</h2><p className="mt-4 max-w-2xl text-muted-foreground">The demo route is an intentionally scoped application placeholder until the Ask Experiment interface is implemented.</p><div className="mt-7"><CtaGroup /></div></div></section>
  </main><footer className="border-t"><div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-8 text-sm text-muted-foreground sm:px-8 md:flex-row md:items-end md:justify-between"><div><p className="font-medium text-foreground">ExperimentOS AI</p><p className="mt-1 max-w-md">A portfolio project for traceable experiment evidence, grounded answers, and decision support.</p></div><div className="flex flex-wrap gap-x-4 gap-y-2"><Link className="hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="/ask-experiment">Demo</Link><Link className="hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="/roadmap">Roadmap</Link><a className="hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={githubUrl} rel="noreferrer" target="_blank">GitHub</a><span>© 2026</span></div></div></footer></div>;
}
