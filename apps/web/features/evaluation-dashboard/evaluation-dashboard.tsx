"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SourceDisclosure } from "@/components/source-disclosure";
import { useEvaluationDashboardQuery, useEvaluationDataSource } from "@/hooks/use-services";
import type { EvaluationCase, EvaluationDashboard, EvaluationMetric, EvaluationStatus } from "@/types/domain";

const labels: Record<EvaluationStatus, string> = {
  pass: "Passed",
  fail: "Failed",
  warning: "Warning",
  not_evaluated: "Not evaluated",
  regressed: "Regressed",
  improved: "Improved",
  unchanged: "Unchanged",
  not_gated: "Not gated",
};

const statusClasses: Record<EvaluationStatus, string> = {
  pass: "border-status-completed/30 bg-status-completed/10 text-status-completed",
  fail: "border-destructive/30 bg-destructive/10 text-destructive",
  warning: "border-status-progress/30 bg-status-progress/10 text-status-progress",
  not_evaluated: "border-border bg-muted text-muted-foreground",
  regressed: "border-destructive/30 bg-destructive/10 text-destructive",
  improved: "border-status-completed/30 bg-status-completed/10 text-status-completed",
  unchanged: "border-border bg-muted text-muted-foreground",
  not_gated: "border-border bg-muted text-muted-foreground",
};

function Status({ status }: { status: EvaluationStatus }) {
  return <Badge className={statusClasses[status]}>{labels[status]}</Badge>;
}

const numberFormat = new Intl.NumberFormat("en", { maximumFractionDigits: 4 });
const dateFormat = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
const focusClass = "rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function valueLabel(value?: number) {
  return value === undefined || !Number.isFinite(value) ? "Not recorded" : numberFormat.format(value);
}

function thresholdLabel(metric: EvaluationMetric) {
  if (metric.threshold === undefined || !Number.isFinite(metric.threshold)) return "Not recorded";
  const value = valueLabel(metric.threshold);
  return metric.operator ? `${metric.operator === ">=" ? "≥" : "≤"} ${value}` : `${value} (comparison rule not recorded)`;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="min-w-0"><dt className="text-sm text-muted-foreground">{label}</dt><dd className="mt-1 break-words text-base tabular-nums">{children}</dd></div>;
}

function MetricResult({ metric }: { metric: EvaluationMetric }) {
  return (
    <article id={`metric-${metric.id}`} aria-labelledby={`metric-title-${metric.id}`} tabIndex={-1} className={`atlas-evaluation-metric scroll-mt-6 ${focusClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0"><h3 id={`metric-title-${metric.id}`} className="break-words text-lg font-medium">{metric.label}</h3><p className="mt-1 text-sm text-muted-foreground">{metric.framework ?? "Framework not recorded"}</p></div>
        <Status status={metric.status} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4">
        <Field label="Current score"><span className={metric.value !== undefined && Number.isFinite(metric.value) ? "atlas-score" : undefined}>{valueLabel(metric.value)}</span></Field>
        <Field label="Required threshold">{thresholdLabel(metric)}</Field>
        <Field label="Baseline score">{valueLabel(metric.baseline)}</Field>
        <Field label="Sample count">{valueLabel(metric.sampleCount)}</Field>
      </dl>
      <p className="mt-4 text-sm font-medium">{metric.blocking === true ? "Release-blocking check" : metric.blocking === false ? "Non-blocking check" : "Release-gate role not recorded"}</p>
      {metric.detail && <p className="mt-2 max-w-prose break-words text-sm leading-6 text-muted-foreground">{metric.detail}</p>}
    </article>
  );
}

function CaseResult({ result, open, onToggle }: { result: EvaluationCase; open: boolean; onToggle: () => void }) {
  const detailId = `case-details-${result.id}`;
  return (
    <article id={`case-${result.id}`} tabIndex={-1} className={`scroll-mt-6 border-t py-2 ${focusClass}`}>
      <h3>
        <button id={`case-toggle-${result.id}`} type="button" aria-expanded={open} aria-controls={detailId} onClick={onToggle} className="flex min-h-14 w-full flex-wrap items-center justify-between gap-3 rounded-md px-1 py-3 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="min-w-0 flex-1 break-words text-base font-medium">{result.name}</span>
          <span className="flex items-center gap-3"><Status status={result.status} /><ChevronDown aria-hidden="true" className={`size-4 shrink-0 ${open ? "rotate-180" : ""}`} /></span>
        </button>
      </h3>
      <p className="mb-3 text-sm text-muted-foreground">{result.type} · {result.blocking ? "Release-blocking check" : "Non-blocking check"}</p>
      {open && <div id={detailId} role="region" aria-label={`${result.name} details`} className="space-y-5 pb-5">
        <dl className="grid gap-4 sm:grid-cols-3"><Field label="Current score">{valueLabel(result.current)}</Field><Field label="Baseline score">{valueLabel(result.baseline)}</Field><Field label="Framework">{result.framework || "Not recorded"}</Field></dl>
        <div><h4 className="font-medium">Expected behavior</h4><p className="mt-2 max-w-prose break-words text-base leading-7">{result.expected || "No expected behavior was recorded."}</p></div>
        <div><h4 className="font-medium">Recorded explanation</h4><p className="mt-2 max-w-prose break-words text-base leading-7">{result.reason || "No explanation was recorded."}</p></div>
        <div><h4 className="font-medium">Recorded answer excerpt</h4>{result.answerExcerpt ? <blockquote className="mt-2 max-w-prose break-words whitespace-pre-wrap rounded-md bg-muted/40 p-4 text-base leading-7">{result.answerExcerpt}</blockquote> : <p className="mt-2 text-sm text-muted-foreground">No answer excerpt was recorded.</p>}</div>
        <div><h4 className="font-medium">Recorded evidence</h4><p className="mt-2 max-w-prose break-words whitespace-pre-wrap text-base leading-7">{result.evidence || "No evidence reference was recorded."}</p></div>
      </div>}
    </article>
  );
}

function DashboardResults({ dashboard }: { dashboard: EvaluationDashboard }) {
  const [expandedCases, setExpandedCases] = useState<ReadonlySet<string>>(new Set());
  const { gate, run } = dashboard;
  const failedMetrics = dashboard.metrics.filter((metric) => metric.status === "fail" || metric.status === "regressed");
  const failedCases = dashboard.cases.filter((result) => result.status === "fail" || result.status === "regressed");
  const warnings = dashboard.metrics.filter((metric) => metric.status === "warning").length + dashboard.cases.filter((result) => result.status === "warning").length;
  const attentionResults = [
    ...failedMetrics.map((metric) => ({ kind: "metric" as const, result: metric })),
    ...failedCases.map((result) => ({ kind: "case" as const, result })),
  ].sort((a, b) => Number(b.result.blocking === true) - Number(a.result.blocking === true));
  const hasFailures = attentionResults.length > 0;
  const date = new Date(run.createdAt);
  const toggleCase = (id: string) => setExpandedCases((previous) => {
    const next = new Set(previous);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const openCase = (id: string) => setExpandedCases((previous) => new Set([...previous, id]));

  return <>
    <section aria-label="Evaluation quality gate" className={`rounded-lg border p-5 ${statusClasses[gate.status]}`}>
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold text-foreground">Sample release quality gate</h2><p className="mt-2 max-w-prose break-words text-base leading-7 text-foreground">{gate.message}</p></div><Status status={gate.status} /></div>
      {gate.blockers.length > 0 && <div className="mt-4 text-foreground"><p className="text-sm font-medium">Reported blockers</p><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{gate.blockers.map((blocker, index) => <li key={`${index}-${blocker}`} className="break-words">{blocker}</li>)}</ul></div>}
      <p className="mt-4 text-sm text-foreground">Reported gate totals: {gate.failed} failed · {gate.warnings} warnings · {gate.passed} passed · {gate.regressions} regressions.</p>
      <p className="mt-2 text-sm text-foreground">These totals come from the saved gate summary; metric and case results are listed separately below.</p>
    </section>

    <section aria-labelledby="attention-heading" className="space-y-4">
      <h2 id="attention-heading" className="text-xl font-semibold">Needs attention</h2>
      {hasFailures ? <>
        <p className="max-w-prose text-sm leading-6 text-muted-foreground">Inspect the failed checks and regressions first. Metric results and case examples are independent lists; no case-to-metric mapping was recorded.</p>
        <ul className="divide-y rounded-lg border bg-card px-4">
          {attentionResults.map((entry) => {
            const { result, kind } = entry;
            return <li key={`${kind}-${result.id}`} className="py-4">
              <a href={`#${kind}-${result.id}`} onClick={kind === "case" ? () => openCase(result.id) : undefined} className={`inline-flex min-h-11 items-center break-words font-medium text-primary underline underline-offset-4 ${focusClass}`}>
                {entry.kind === "metric" ? entry.result.label : entry.result.name} — inspect {kind}
              </a>
              <p className="mt-1 text-sm text-muted-foreground">{labels[result.status]} · {entry.kind === "metric" ? `Score ${valueLabel(entry.result.value)} · Required ${thresholdLabel(entry.result)}` : result.blocking ? "Release-blocking check" : "Non-blocking check"}</p>
            </li>;
          })}
        </ul>
      </> : <p className="text-base leading-7">{gate.status === "fail" || gate.failed > 0 || gate.regressions > 0 || gate.blockers.length > 0 ? "The gate reports a failure or blocker, but no failed metric or case details were recorded. Review the reported blockers above." : gate.status === "not_evaluated" ? "The gate was not evaluated. No failed check or regression details were recorded." : "No failed checks or regressions were recorded."}</p>}
      {(warnings > 0 || gate.status === "warning" || gate.warnings > 0) && <p className="text-sm text-muted-foreground">Warnings are recorded. Review their status and explanations in the results below.</p>}
    </section>

    <section aria-labelledby="metrics-heading"><h2 id="metrics-heading" className="text-xl font-semibold">All metrics</h2><p className="mb-4 mt-2 text-sm text-muted-foreground">Compare recorded scores with their thresholds. A missing score is not a failed score.</p>{dashboard.metrics.length ? <div className="atlas-evaluation-grid">{dashboard.metrics.map((metric) => <MetricResult key={metric.id} metric={metric} />)}</div> : <p className="py-5 text-sm text-muted-foreground">No metric results were recorded.</p>}</section>
    <section aria-labelledby="cases-heading" className="atlas-cases"><h2 id="cases-heading" className="text-xl font-semibold">All cases</h2><p className="mb-4 mt-2 text-sm text-muted-foreground">Expand a case to inspect its expected behavior, recorded answer, and evidence.</p>{dashboard.cases.length ? dashboard.cases.map((result) => <CaseResult key={result.id} result={result} open={expandedCases.has(result.id)} onToggle={() => toggleCase(result.id)} />) : <p className="py-5 text-sm text-muted-foreground">No case results were recorded.</p>}</section>

    <details className="rounded-lg border p-5"><summary className={`cursor-pointer text-lg font-medium ${focusClass}`}>Run metadata and integrations</summary><div className="mt-5 space-y-6">
      <dl className="grid gap-4 sm:grid-cols-2"><Field label="Run ID">{run.id}</Field><Field label="Dataset">{run.dataset}</Field><Field label="Model">{run.model || "Not recorded"}</Field><Field label="Prompt">{run.prompt || "Not recorded"}</Field><Field label="Recorded at">{Number.isNaN(date.getTime()) ? "Not recorded" : `${dateFormat.format(date)} UTC`}</Field><Field label="Saved run status"><Status status={run.status} /></Field></dl>
      <div><h3 className="font-medium">Prompt regression summary</h3><p className="mt-2 break-words text-sm leading-6">{dashboard.promptRegression.prompt} compared with {dashboard.promptRegression.baseline}. Reported totals: {dashboard.promptRegression.goldenCases} cases · {dashboard.promptRegression.passed} passed · {dashboard.promptRegression.failed} failed · {dashboard.promptRegression.regressed} regressed.</p></div>
      <div><h3 className="font-medium">Integrations for this run</h3>{dashboard.integrations.length ? <ul className="mt-3 space-y-3">{dashboard.integrations.map((integration) => <li key={integration.name}><p className="text-sm font-medium">{integration.name} · {integration.state === "available" ? "Available" : "Not connected"}</p><p className="mt-1 break-words text-sm leading-6 text-muted-foreground">{integration.detail}</p></li>)}</ul> : <p className="mt-2 text-sm text-muted-foreground">No integration information was recorded.</p>}</div>
    </div></details>
  </>;
}

export function EvaluationDashboardView() {
  const query = useEvaluationDashboardQuery();
  const source = useEvaluationDataSource();
  const dashboard = query.data;
  return <div className="min-w-0 space-y-8">
    <header className="atlas-page-header flex flex-wrap items-start justify-between gap-5"><div className="min-w-0"><h1 className="text-3xl font-semibold tracking-tight">Evaluations</h1>{dashboard && <p className="mt-2 break-words text-base text-muted-foreground">{dashboard.run.name}</p>}</div><div className="max-w-sm"><Button disabled aria-describedby="evaluation-run-help">Run evaluation</Button><p id="evaluation-run-help" className="mt-2 text-sm leading-6 text-muted-foreground">This page shows saved evaluation results. Starting a run from the web interface is not available.</p></div></header>
    <SourceDisclosure source={source} />
    {query.isPending ? <div role="status" aria-busy="true" className="space-y-4"><p>Loading evaluation results…</p><Skeleton className="h-16 w-full" /><Skeleton className="h-28 w-full" /></div> : query.isError ? <Card className="space-y-4 p-5" role="alert"><h2 className="font-semibold">Evaluation results could not be loaded</h2><p className="text-sm text-muted-foreground">{query.error.userMessage}</p><Button variant="outline" onClick={() => void query.refetch()}>Retry loading evaluations</Button></Card> : !dashboard ? <p role="status">No evaluation run is available.</p> : <DashboardResults key={dashboard.run.id} dashboard={dashboard} />}
  </div>;
}
