import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { analysisAvailability, analysisGuideUrl } from "@/lib/analysis-capabilities";
import { capabilityStatuses } from "@/lib/capability-status";
import {
  architectureStages,
  capabilityStatusGroups,
  demoUrl,
  githubUrl,
} from "@/lib/landing-content";
import type { CapabilityStatus, RoadmapPhase } from "@/types/domain";

const textLink = "inline-flex min-h-11 items-center gap-2 rounded-sm text-sm text-primary underline underline-offset-4 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const disclosure = "cursor-pointer rounded-sm py-4 font-medium marker:text-muted-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function StatusBadge({ status }: { status: CapabilityStatus }) {
  const definition = capabilityStatuses[status];
  return <Badge className={definition.className}>{definition.label}</Badge>;
}

function PublicHeader() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-8 gap-y-2 px-5 py-4 sm:px-8">
        <Link className="rounded-sm font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="/">
          ExperimentOS <span className="text-primary">AI</span>
        </Link>
        <nav aria-label="Landing page navigation" className="flex flex-wrap items-center gap-x-5 text-sm text-muted-foreground">
          <a className={textLink} href="#architecture">Workflow</a>
          <a className={textLink} href="#status">Status</a>
          <a aria-label="View ExperimentOS AI on GitHub" className={textLink} href={githubUrl} rel="noreferrer" target="_blank">
            GitHub <ExternalLink aria-hidden="true" className="size-4" />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        </nav>
      </div>
    </header>
  );
}

function ArchitectureFlow() {
  return (
    <ol aria-label="ExperimentOS system architecture" className="mt-8 grid gap-x-10 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
      {architectureStages.map((stage, index) => (
        <li className="flex min-w-0 gap-4 border-t pt-5" key={stage.title}>
          <span aria-hidden="true" className="text-sm tabular-nums text-muted-foreground">{index + 1}</span>
          <div>
            <h3 className="text-base font-medium">{stage.title}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{stage.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function RoadmapSummary({ phases }: { phases: readonly RoadmapPhase[] }) {
  return (
    <ol className="grid gap-x-10 gap-y-6 pb-6 sm:grid-cols-2">
      {phases.map((phase) => (
        <li key={phase.id}>
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-medium">{phase.title}</h3>
            <StatusBadge status={phase.status === "in_progress" ? "in-progress" : phase.status === "future" || phase.status === "research" ? "future-research" : phase.status} />
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{phase.description}</p>
        </li>
      ))}
    </ol>
  );
}

export function LandingPage({ roadmap }: { roadmap: readonly RoadmapPhase[] }) {
  return (
    <div className="min-h-screen bg-background selection:bg-primary selection:text-primary-foreground">
      <a className="sr-only fixed left-4 top-4 z-[60] rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only focus:outline-none focus:ring-2 focus:ring-ring" href="#main-content">
        Skip to main content
      </a>
      <PublicHeader />
      <main id="main-content" tabIndex={-1} className="mx-auto max-w-6xl px-5 sm:px-8">
        <section className="py-16 sm:py-24">
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
            Evidence-backed answers for product experiments.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
            Find the evidence behind an experiment decision. Ask a question, inspect its answer and citations, and trace the source reports.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
            <Link className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={demoUrl}>
              Launch Demo <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
            <a className={textLink} href={githubUrl} rel="noreferrer" target="_blank">
              View GitHub <ExternalLink aria-hidden="true" className="size-4" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </div>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
            The demo uses saved records and answers. Try a saved question to inspect its citations; free-form questions require a local backend.
          </p>
        </section>

        <section aria-label="Product availability" className="border-t py-10 sm:py-12">
          <h2 className="text-2xl font-semibold tracking-tight">What you can use today</h2>
          <dl className="mt-6 grid gap-6 md:grid-cols-3 md:gap-10">
            <div>
              <dt className="font-medium">Backend analysis</dt>
              <dd className="mt-2 text-sm leading-6 text-muted-foreground">{analysisAvailability.backend}</dd>
            </div>
            <div>
              <dt className="font-medium">Web interface</dt>
              <dd className="mt-2 text-sm leading-6 text-muted-foreground">{analysisAvailability.interface} Local live mode supports free-form questions about an experiment’s report.</dd>
            </div>
            <div>
              <dt className="font-medium">Deployment</dt>
              <dd className="mt-2 text-sm leading-6 text-muted-foreground">{analysisAvailability.deployment}</dd>
            </div>
          </dl>
          <a className={`${textLink} mt-4`} href={analysisGuideUrl}>Read supported backend methods and examples</a>
        </section>

        <section className="scroll-mt-8 border-t py-12 sm:py-16" id="architecture">
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">From stored reports to reviewed decisions.</h2>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
            These stages describe the implemented backend. Analysis requires explicit method selection and validated inputs; web forms do not execute structured analyses.
          </p>
          <ArchitectureFlow />
          <p className="mt-8 max-w-2xl text-sm leading-6 text-muted-foreground">
            Uncertainty, limitations, and human approval stay attached to the evidence. Positive effects do not authorize autonomous rollout.
          </p>
          <details className="mt-8 border-y" id="engineering">
            <summary className={disclosure}>Engineering and reliability</summary>
            <dl className="grid gap-x-10 gap-y-6 pb-6 sm:grid-cols-2">
              <div>
                <dt className="font-medium">Typed services</dt>
                <dd className="mt-2 text-sm leading-6 text-muted-foreground">Next.js and TypeScript use strict frontend service contracts. FastAPI, Pydantic, and SQLAlchemy keep backend boundaries explicit; PostgreSQL and pgvector store and retrieve evidence.</dd>
              </div>
              <div>
                <dt className="font-medium">Reliable workflows</dt>
                <dd className="mt-2 text-sm leading-6 text-muted-foreground">LangGraph state, human approval, and prompt versioning keep orchestration explicit.</dd>
              </div>
              <div>
                <dt className="font-medium">Evaluated changes</dt>
                <dd className="mt-2 text-sm leading-6 text-muted-foreground">Deterministic evaluation, RAGAS, DeepEval, prompt regression, and CI quality gates test reliability. Alembic, Docker Compose, and GitHub Actions support repeatable development.</dd>
              </div>
              <div>
                <dt className="font-medium">Observable execution</dt>
                <dd className="mt-2 text-sm leading-6 text-muted-foreground">Phoenix, LangSmith, and OpenTelemetry integrations are available as optional, disabled-by-default sinks.</dd>
              </div>
            </dl>
          </details>
        </section>

        <section className="scroll-mt-8 border-t py-12 sm:py-16" id="status">
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Backend capabilities and their limits.</h2>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
            Completed means implemented within the documented scope. Optional dependencies, method assumptions, and UI availability still determine how a capability can be used.
          </p>
          <div className="mt-8 grid gap-8 lg:grid-cols-3 lg:gap-10">
            {capabilityStatusGroups.map((group) => (
              <section aria-label={group.title} key={group.title}>
                <StatusBadge status={group.status} />
                <h3 className="mt-3 font-medium">{group.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{group.description}</p>
                <details className="mt-2">
                  <summary className={`${disclosure} text-sm`}>View {group.status === "future-research" ? "future scope" : group.title === "Optional backend adapters" ? "adapters" : "capabilities"}</summary>
                  <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
                    {group.items.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </details>
              </section>
            ))}
          </div>
          <div className="mt-10 border-t pt-6">
            <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
              <h3 className="text-base font-medium">Roadmap</h3>
              <Link className={textLink} href="/roadmap">View full roadmap <ArrowRight aria-hidden="true" className="size-4" /></Link>
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Four phases have implementations within their documented scope. Open the roadmap for method limits and future work.</p>
            <details className="mt-2">
              <summary className={disclosure}>Phase summary</summary>
              <RoadmapSummary phases={roadmap} />
            </details>
          </div>
        </section>
      </main>
      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 text-sm text-muted-foreground sm:px-8 md:flex-row md:items-center md:justify-between">
          <p className="max-w-lg leading-6">ExperimentOS AI — a portfolio project for traceable experiment evidence, grounded answers, and decision support.</p>
          <Link className={textLink} href={demoUrl}>Explore the demo <ArrowRight aria-hidden="true" className="size-4" /></Link>
        </div>
      </footer>
    </div>
  );
}
