"use client";

import Link from "next/link";
import { ArrowLeft, Database, FileText, FlaskConical, ListChecks } from "lucide-react";

import { ContentCard } from "@/components/layout/content-card";
import { PageHeader } from "@/components/layout/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  businessImpactLabels,
  decisionStatusLabels,
  experimentStatusLabels,
} from "@/features/experiment-explorer/explorer-model";
import { useExperimentDataSource, useExperimentDetailQuery } from "@/hooks/use-services";
import type {
  AnalysisReadiness,
  Capability,
  ExperimentDetail as ExperimentDetailRecord,
  ExperimentMetric,
  ReadinessCheckStatus,
} from "@/types/domain";

const dateFormatter = new Intl.DateTimeFormat("en-AU", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

function isExperimentIdentifier(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function formatDate(value?: string): string | undefined {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? undefined : dateFormatter.format(date);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-AU", { maximumFractionDigits: 2 }).format(value);
}

function formatMetricValue(metric: ExperimentMetric): string {
  if (!Number.isFinite(metric.value)) return "Unavailable";
  const value = formatNumber(metric.value);
  return metric.unit.startsWith("%") ? `${value}${metric.unit}` : `${value} ${metric.unit}`;
}

function metadataItems(experiment: ExperimentDetailRecord): readonly { label: string; value: string }[] {
  const items = [
    { label: "Owner", value: experiment.owner.name },
    { label: "Team", value: experiment.owner.team },
    ...(formatDate(experiment.startedAt) ? [{ label: "Started", value: formatDate(experiment.startedAt)! }] : []),
    ...(formatDate(experiment.overview?.endedAt) ? [{ label: "Ended", value: formatDate(experiment.overview?.endedAt)! }] : []),
    ...(experiment.overview?.platform ? [{ label: "Surface", value: experiment.overview.platform }] : []),
    ...(experiment.overview?.experimentType ? [{ label: "Experiment type", value: experiment.overview.experimentType }] : []),
  ];
  return items.filter((item) => Boolean(item.value));
}

function BackToExplorer({ explorerSearch = "" }: { explorerSearch?: string }) {
  const href = explorerSearch ? `/experiment-explorer?${explorerSearch}` : "/experiment-explorer";
  return <Link className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={href}><ArrowLeft aria-hidden="true" className="size-4" />Back to Experiment Explorer</Link>;
}

function DataSourceDisclosure() {
  const source = useExperimentDataSource();
  return <div className="flex items-start gap-3 rounded-lg border bg-card/35 p-4 text-sm"><Database aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" /><div><p className="font-medium text-foreground">{source.label}</p><p className="mt-1 text-muted-foreground">{source.detail}</p></div></div>;
}

function Header({ experiment }: { experiment: ExperimentDetailRecord }) {
  return <PageHeader title={experiment.name} description={experiment.summary} actions={<div className="flex max-w-full flex-col items-start gap-2"><div className="flex flex-wrap items-center gap-2"><Badge className="border-border bg-muted/60">{experimentStatusLabels[experiment.status]}</Badge><Badge className="border-primary/35 bg-primary/10 text-primary">{decisionStatusLabels[experiment.decision.status]}</Badge></div><p className="max-w-full break-all font-mono text-xs text-muted-foreground">{experiment.id}</p></div>} />;
}

function Overview({ experiment }: { experiment: ExperimentDetailRecord }) {
  const overview = experiment.overview;
  const metadata = metadataItems(experiment);
  return <section aria-labelledby="experiment-overview"><div className="mb-3 flex items-center gap-2"><FlaskConical aria-hidden="true" className="size-4 text-primary" /><h2 className="text-xl font-semibold" id="experiment-overview">Experiment overview</h2></div><ContentCard><div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(16rem,0.65fr)]"><div className="space-y-5"><Field label="Hypothesis" value={overview?.hypothesis} /><Field label="Problem" value={overview?.problemStatement} /><Field label="Description" value={overview?.description} /><Field label="Target audience" value={overview?.targetAudience} />{overview?.tags?.length ? <div><p className="text-sm font-medium">Tags</p><div className="mt-2 flex flex-wrap gap-2">{overview.tags.map((tag) => <Badge className="border-border bg-muted/60" key={tag}>{tag}</Badge>)}</div></div> : null}</div><dl className="grid content-start gap-4 sm:grid-cols-2 lg:grid-cols-1">{metadata.map((item) => <Metadata key={item.label} label={item.label} value={item.value} />)}</dl></div></ContentCard></section>;
}

function Field({ label, value }: { label: string; value?: string }) {
  return value ? <div><p className="text-sm font-medium">{label}</p><p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">{value}</p></div> : null;
}

function Metadata({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</dt><dd className="mt-1 text-sm">{value}</dd></div>;
}

function DecisionSummary({ experiment }: { experiment: ExperimentDetailRecord }) {
  const decision = experiment.decision;
  const decidedAt = formatDate(decision.decidedAt);
  return <section aria-labelledby="decision-summary"><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold" id="decision-summary">Decision summary</h2><Badge className="border-primary/35 bg-primary/10 text-primary">{decisionStatusLabels[decision.status]}</Badge></div><ContentCard><div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]"><div><p className="text-sm font-medium">Recorded recommendation</p><p className="mt-1 text-lg font-medium">{decision.recommendation || "No recorded recommendation"}</p><p className="mt-4 text-sm font-medium">Recorded rationale</p><p className="mt-1 text-sm leading-6 text-muted-foreground">{decision.rationale || "No recorded rationale is available."}</p>{decision.nextAction ? <><p className="mt-4 text-sm font-medium">Next action</p><p className="mt-1 text-sm leading-6 text-muted-foreground">{decision.nextAction}</p></> : null}<p className="mt-5 text-xs leading-5 text-muted-foreground">This is fixture record metadata, not an AI recommendation or live organisational approval.</p></div><dl className="grid content-start gap-4 sm:grid-cols-2 lg:grid-cols-1">{decidedAt ? <Metadata label="Decision date" value={decidedAt} /> : null}{decision.decidedBy ? <Metadata label="Recorded by" value={decision.decidedBy} /> : null}<Metadata label="Evidence summary" value="Recorded metrics and report excerpts" /></dl></div></ContentCard></section>;
}

function MetricCard({ metric, primary = false }: { metric: ExperimentMetric; primary?: boolean }) {
  return <article className="rounded-md border bg-background/35 p-4"><p className="text-sm font-medium">{metric.name}</p><p className="mt-3 text-2xl font-semibold tracking-tight">{formatMetricValue(metric)}</p><p className="mt-1 text-sm text-muted-foreground">{primary ? "Primary metric · observed difference" : "Supporting metric · observed difference"}</p>{metric.baseline !== undefined || metric.treatment !== undefined || metric.absoluteChange !== undefined || metric.relativeChange !== undefined ? <dl className="mt-4 grid gap-2 border-t pt-3 text-sm">{metric.baseline !== undefined ? <Metadata label="Baseline" value={formatNumber(metric.baseline)} /> : null}{metric.treatment !== undefined ? <Metadata label="Treatment" value={formatNumber(metric.treatment)} /> : null}{metric.absoluteChange !== undefined ? <Metadata label="Absolute change" value={formatNumber(metric.absoluteChange)} /> : null}{metric.relativeChange !== undefined ? <Metadata label="Relative change" value={`${formatNumber(metric.relativeChange)}%`} /> : null}</dl> : <p className="mt-4 border-t pt-3 text-xs text-muted-foreground">Baseline, treatment, and absolute values are unavailable.</p>}</article>;
}

function Metrics({ experiment }: { experiment: ExperimentDetailRecord }) {
  const supporting = experiment.metrics.filter((metric) => metric.name !== experiment.primaryMetric.name);
  return <section aria-labelledby="experiment-metrics"><h2 className="mb-3 text-xl font-semibold" id="experiment-metrics">Metrics</h2><ContentCard><div className="grid gap-4 md:grid-cols-2"><MetricCard metric={experiment.primaryMetric} primary />{supporting.map((metric) => <MetricCard key={metric.name} metric={metric} />)}</div><p className="mt-5 text-sm leading-6 text-muted-foreground">Observed differences are descriptive values in this record, not a causal impact estimate. Inferential statistics are unavailable unless an attached analysis result explicitly provides them.</p></ContentCard></section>;
}

function BusinessImpact({ experiment }: { experiment: ExperimentDetailRecord }) {
  return <section aria-labelledby="business-impact"><h2 className="mb-3 text-xl font-semibold" id="business-impact">Business impact</h2><ContentCard><p className="font-medium">{businessImpactLabels[experiment.businessImpact]}</p><p className="mt-2 text-sm leading-6 text-muted-foreground">Automated business-impact estimation is not connected. No currency value, annualisation, or impact range is calculated in this UI.</p></ContentCard></section>;
}

function ExperimentReport({ experiment }: { experiment: ExperimentDetailRecord }) {
  const report = experiment.report;
  return <section aria-labelledby="experiment-report"><div className="mb-3 flex items-center gap-2"><FileText aria-hidden="true" className="size-4 text-primary" /><h2 className="text-xl font-semibold" id="experiment-report">Experiment report</h2></div><ContentCard>{!report ? <p className="text-sm text-muted-foreground">No report content is attached to this experiment record.</p> : <div><p className="text-sm text-muted-foreground">Source: {report.source}</p><div className="mt-5 space-y-5"><ReportField title="Executive summary" value={report.executiveSummary} /><ReportField title="Methodology" value={report.methodology} /><ReportField title="Results summary" value={report.results} /><ReportField title="Interpretation" value={report.interpretation} /><ReportField title="Recommendation" value={report.recommendation} /><ReportField title="Limitations" value={report.limitations} />{report.followUpActions?.length ? <div><h3 className="text-sm font-medium">Follow-up actions</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">{report.followUpActions.map((action) => <li key={action}>{action}</li>)}</ul></div> : null}</div></div>}</ContentCard></section>;
}

function ReportField({ title, value }: { title: string; value?: string }) {
  return value ? <div><h3 className="text-sm font-medium">{title}</h3><p className="mt-1 max-w-3xl whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{value}</p></div> : null;
}

const readinessLabels: Record<AnalysisReadiness["status"], string> = { eligible: "Eligible", ineligible: "Not eligible", needs_more_data: "Needs more data", unavailable: "Unavailable" };
const readinessCheckLabels: Record<ReadinessCheckStatus, string> = { pass: "Pass", fail: "Fail", unavailable: "Unavailable" };

function AnalysisReadinessSection({ readiness }: { readiness?: AnalysisReadiness }) {
  return <section aria-labelledby="analysis-readiness"><div className="mb-3 flex items-center gap-2"><ListChecks aria-hidden="true" className="size-4 text-primary" /><h2 className="text-xl font-semibold" id="analysis-readiness">Analysis readiness</h2></div><ContentCard>{!readiness ? <p className="text-sm text-muted-foreground">Analysis eligibility has not been recorded for this experiment.</p> : <div><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-medium">{readiness.stage}</p><p className="mt-1 text-sm text-muted-foreground">Readiness is fixture metadata; this page does not run an analysis.</p></div><Badge className="border-border bg-muted/60">{readinessLabels[readiness.status]}</Badge></div><ul className="mt-5 space-y-3">{readiness.checks.map((check) => <li className="rounded-md border bg-background/35 p-3" key={check.label}><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium">{check.label}</p><Badge className="border-border bg-muted/60">{readinessCheckLabels[check.status]}</Badge></div><p className="mt-2 text-sm leading-6 text-muted-foreground">{check.detail}</p></li>)}</ul>{readiness.blockedBy ? <p className="mt-4 text-sm leading-6 text-muted-foreground"><span className="font-medium text-foreground">Current boundary: </span>{readiness.blockedBy}</p> : null}</div>}</ContentCard></section>;
}

function CapabilityMatrix({ capabilities }: { capabilities: readonly Capability[] }) {
  return <section aria-labelledby="capability-status"><h2 className="mb-3 text-xl font-semibold" id="capability-status">Analysis capabilities</h2><ContentCard><p className="text-sm leading-6 text-muted-foreground">Capability status communicates maturity only. Planned methods are not executable from this record.</p>{capabilities.length === 0 ? <p className="mt-5 text-sm text-muted-foreground">No analysis capability status is attached to this experiment record.</p> : <ul className="mt-5 divide-y rounded-md border">{capabilities.map((capability) => <li className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between" key={capability.name}><div><p className="font-medium">{capability.name}</p><p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">{capability.detail}</p></div><StatusBadge status={capability.status} /></li>)}</ul>}</ContentCard></section>;
}

function Evidence({ experiment }: { experiment: ExperimentDetailRecord }) {
  const chunks = experiment.retrievedChunks ?? [];
  const citations = experiment.citations ?? [];
  return <section aria-labelledby="retrieved-chunks"><h2 className="mb-3 text-xl font-semibold" id="retrieved-chunks">Retrieved chunks and citations</h2><ContentCard>{chunks.length === 0 ? <p className="text-sm text-muted-foreground">No retrieved report chunks are attached to this experiment record.</p> : <><p className="text-sm leading-6 text-muted-foreground">These excerpts contribute to the fixture record. Higher similarity indicates closer embedding-space relevance, not answer certainty.</p><div className="mt-5 space-y-3">{chunks.map((chunk, index) => <details className="rounded-md border bg-background/35 p-4" key={chunk.id} open={index === 0}><summary className="cursor-pointer text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">#{index + 1} · {chunk.documentName}{chunk.section ? ` · ${chunk.section}` : ""}</summary><p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{chunk.text || "No excerpt was returned."}</p><div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted-foreground"><span>Chunk: {chunk.id}</span><span>Document: {chunk.documentId || "Unavailable"}</span>{chunk.similarity !== undefined ? <span>Similarity {chunk.similarity.toFixed(2)}</span> : <span>Similarity unavailable</span>}{chunk.citationId ? <span>Citation {chunk.citationId}</span> : null}</div></details>)}</div>{citations.length ? <div className="mt-6 border-t pt-5"><h3 className="text-sm font-medium">Citation references</h3><ol className="mt-3 space-y-2">{citations.map((citation) => <li className="text-sm text-muted-foreground" key={citation.id}><span className="font-mono text-foreground">{citation.id}</span> {citation.documentName}{citation.section ? ` · ${citation.section}` : ""}{citation.chunkId ? ` · chunk ${citation.chunkId}` : ""}</li>)}</ol></div> : null}</>}</ContentCard></section>;
}

function RecordMetadata({ experiment }: { experiment: ExperimentDetailRecord }) {
  const items = [{ label: "Experiment ID", value: experiment.id }, ...(experiment.recordMetadata ?? [])];
  return <section aria-labelledby="record-metadata"><h2 className="mb-3 text-xl font-semibold" id="record-metadata">Record metadata</h2><ContentCard><dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{items.map((item) => <Metadata key={item.label} label={item.label} value={item.value} />)}</dl></ContentCard></section>;
}

function LoadingState({ explorerSearch }: { explorerSearch?: string }) {
  return <div className="space-y-6" aria-busy="true" aria-label="Loading experiment detail"><BackToExplorer explorerSearch={explorerSearch} /><div className="space-y-3"><Skeleton className="h-9 w-80" /><Skeleton className="h-5 w-full max-w-2xl" /></div><Skeleton className="h-48 w-full" /><div className="grid gap-4 md:grid-cols-2"><Skeleton className="h-40" /><Skeleton className="h-40" /></div></div>;
}

function NotFound({ experimentId, explorerSearch }: { experimentId: string; explorerSearch?: string }) {
  const href = explorerSearch ? `/experiment-explorer?${explorerSearch}` : "/experiment-explorer";
  return <div className="space-y-6"><BackToExplorer explorerSearch={explorerSearch} /><ContentCard aria-live="polite" className="max-w-2xl"><h1 className="text-2xl font-semibold">Experiment not found</h1><p className="mt-3 text-sm leading-6 text-muted-foreground">The requested experiment record could not be found.</p><p className="mt-3 break-all font-mono text-xs text-muted-foreground">{experimentId}</p><Link className="mt-5 inline-flex h-9 items-center justify-center rounded-md border border-input bg-transparent px-3 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={href}>Return to Experiment Explorer</Link></ContentCard></div>;
}

function ErrorState({ explorerSearch, message, onRetry }: { explorerSearch?: string; message: string; onRetry: () => void }) {
  return <div className="space-y-6"><BackToExplorer explorerSearch={explorerSearch} /><ContentCard aria-live="polite" className="max-w-2xl"><h1 className="text-2xl font-semibold">Experiment detail could not be loaded</h1><p className="mt-3 text-sm leading-6 text-muted-foreground">{message}</p><Button className="mt-5" onClick={onRetry} type="button">Retry loading experiment</Button></ContentCard></div>;
}

export function ExperimentDetail({ experimentId, explorerSearch }: { experimentId: string; explorerSearch?: string }) {
  const isValid = isExperimentIdentifier(experimentId);
  const query = useExperimentDetailQuery(isValid ? experimentId : "");

  if (!isValid) return <NotFound experimentId={experimentId} explorerSearch={explorerSearch} />;
  if (query.isPending) return <LoadingState explorerSearch={explorerSearch} />;
  if (query.isError && query.error.code === "not_found") return <NotFound experimentId={experimentId} explorerSearch={explorerSearch} />;
  if (query.isError) return <ErrorState explorerSearch={explorerSearch} message={query.error.userMessage} onRetry={() => { void query.refetch(); }} />;
  if (!query.data) return <NotFound experimentId={experimentId} explorerSearch={explorerSearch} />;

  const experiment = query.data;
  return <div className="space-y-8"><BackToExplorer explorerSearch={explorerSearch} /><Header experiment={experiment} /><DataSourceDisclosure /><Overview experiment={experiment} /><DecisionSummary experiment={experiment} /><Metrics experiment={experiment} /><BusinessImpact experiment={experiment} /><ExperimentReport experiment={experiment} /><AnalysisReadinessSection readiness={experiment.analysisReadiness} /><CapabilityMatrix capabilities={experiment.capabilities} /><Evidence experiment={experiment} /><RecordMetadata experiment={experiment} /></div>;
}
