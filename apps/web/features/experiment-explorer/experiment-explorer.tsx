"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, Database, RotateCcw, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useExperimentDataSource, useExperimentsQuery } from "@/hooks/use-services";
import {
  businessImpactLabels,
  decisionStatusLabels,
  defaultExplorerState,
  experimentStatusLabels,
  getExplorerResults,
  normalizeExplorerState,
  type ExplorerSort,
  type ExplorerState,
} from "@/features/experiment-explorer/explorer-model";
import type { Experiment } from "@/types/domain";

const dateFormatter = new Intl.DateTimeFormat("en-AU", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});
const noExperiments: readonly Experiment[] = [];

function formatStartedAt(startedAt: string): string {
  const date = new Date(startedAt);
  return Number.isNaN(date.valueOf()) ? "Unavailable" : dateFormatter.format(date);
}

function hasActiveFilters(state: ExplorerState): boolean {
  return Boolean(state.query || state.status || state.owner || state.from || state.to);
}

function stateToParams(state: ExplorerState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.status) params.set("status", state.status);
  if (state.owner) params.set("owner", state.owner);
  if (state.from) params.set("from", state.from);
  if (state.to) params.set("to", state.to);
  if (state.sort !== defaultExplorerState.sort) params.set("sort", state.sort);
  if (state.direction !== defaultExplorerState.direction) params.set("direction", state.direction);
  return params;
}

function ExplorerSkeleton() {
  return <div aria-label="Loading experiments" className="overflow-hidden rounded-lg border"><div className="grid grid-cols-[minmax(15rem,2fr)_repeat(4,minmax(8rem,1fr))] gap-4 border-b bg-card/50 px-5 py-3">{Array.from({ length: 5 }, (_, index) => <Skeleton className="h-4" key={index} />)}</div>{Array.from({ length: 4 }, (_, row) => <div className="grid grid-cols-[minmax(15rem,2fr)_repeat(4,minmax(8rem,1fr))] gap-4 border-b px-5 py-5" key={row}>{Array.from({ length: 5 }, (_, column) => <Skeleton className="h-5" key={column} />)}</div>)}</div>;
}

function EmptyState({ title, detail, actionLabel = "Reset explorer", onReset }: { title: string; detail: string; actionLabel?: string; onReset?: () => void }) {
  return <div className="rounded-lg border border-dashed bg-card/30 px-6 py-12 text-center"><h2 className="font-medium">{title}</h2><p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{detail}</p>{onReset ? <Button aria-label={actionLabel} className="mt-5" onClick={onReset} variant="outline"><RotateCcw aria-hidden="true" className="mr-2 size-4" />{actionLabel}</Button> : null}</div>;
}

function StatusBadge({ status }: { status: Experiment["status"] }) {
  const color = status === "completed" ? "border-status-completed/40 bg-status-completed/15" : status === "running" ? "border-status-progress/40 bg-status-progress/15" : status === "inconclusive" ? "border-status-research/40 bg-status-research/15" : "border-status-unavailable/40 bg-status-unavailable/15";
  return <Badge className={color}>{experimentStatusLabels[status]}</Badge>;
}

function DecisionBadge({ decision }: { decision: Experiment["decision"]["status"] }) {
  return <Badge className="border-border bg-muted/60">{decisionStatusLabels[decision]}</Badge>;
}

function SortButton({ field, label, state, onSort }: { field: ExplorerSort; label: string; state: ExplorerState; onSort: (field: ExplorerSort) => void }) {
  const active = state.sort === field;
  const direction = active ? (state.direction === "asc" ? "ascending" : "descending") : "not sorted";
  return <button aria-label={`Sort by ${label}, currently ${direction}`} className="inline-flex items-center gap-1 text-left font-medium hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onSort(field)} type="button">{label}{active ? state.direction === "asc" ? <ArrowUp aria-hidden="true" className="size-3.5" /> : <ArrowDown aria-hidden="true" className="size-3.5" /> : null}</button>;
}

function ExperimentTable({ experiments, state, onSort }: { experiments: readonly Experiment[]; state: ExplorerState; onSort: (field: ExplorerSort) => void }) {
  const explorerSearch = stateToParams(state).toString();
  return <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[54rem] border-collapse text-left text-sm"><thead className="bg-card/65 text-muted-foreground"><tr><th aria-sort={state.sort === "name" ? (state.direction === "asc" ? "ascending" : "descending") : "none"} className="min-w-72 px-5 py-3"><SortButton field="name" label="Experiment" onSort={onSort} state={state} /></th><th aria-sort={state.sort === "status" ? (state.direction === "asc" ? "ascending" : "descending") : "none"} className="px-4 py-3"><SortButton field="status" label="Status" onSort={onSort} state={state} /></th><th className="px-4 py-3">Decision</th><th aria-sort={state.sort === "primaryMetric" ? (state.direction === "asc" ? "ascending" : "descending") : "none"} className="px-4 py-3"><SortButton field="primaryMetric" label="Primary metric" onSort={onSort} state={state} /></th><th className="px-4 py-3">Business impact</th><th aria-sort={state.sort === "owner" ? (state.direction === "asc" ? "ascending" : "descending") : "none"} className="px-4 py-3"><SortButton field="owner" label="Owner" onSort={onSort} state={state} /></th><th aria-sort={state.sort === "startedAt" ? (state.direction === "asc" ? "ascending" : "descending") : "none"} className="px-4 py-3"><SortButton field="startedAt" label="Started" onSort={onSort} state={state} /></th></tr></thead><tbody>{experiments.map((experiment) => <tr className="border-t transition-colors hover:bg-muted/35" key={experiment.id}><td className="px-5 py-4 align-top"><Link className="font-medium text-foreground underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={`/experiment-explorer/${experiment.id}${explorerSearch ? `?${explorerSearch}` : ""}`}>{experiment.name}<span className="sr-only"> — inspect experiment details</span></Link><p className="mt-1 font-mono text-xs text-muted-foreground">{experiment.id}</p></td><td className="px-4 py-4 align-top"><StatusBadge status={experiment.status} /></td><td className="px-4 py-4 align-top"><DecisionBadge decision={experiment.decision.status} /><p className="mt-1 text-xs text-muted-foreground">{experiment.decision.recommendation}</p></td><td className="px-4 py-4 align-top"><p className="font-medium">{Number.isFinite(experiment.primaryMetric.value) ? `${experiment.primaryMetric.value} ${experiment.primaryMetric.unit}` : "Unavailable"}</p><p className="mt-1 text-xs text-muted-foreground">{experiment.primaryMetric.name}</p></td><td className="px-4 py-4 align-top"><p>{businessImpactLabels[experiment.businessImpact]}</p><p className="mt-1 text-xs text-muted-foreground">{experiment.businessImpact === "available" ? "Source metadata; not calculated by ExperimentOS." : "Automated impact estimation is not connected."}</p></td><td className="px-4 py-4 align-top"><p>{experiment.owner.name}</p><p className="mt-1 text-xs text-muted-foreground">{experiment.owner.team}</p></td><td className="px-4 py-4 align-top text-muted-foreground">{formatStartedAt(experiment.startedAt)}</td></tr>)}</tbody></table></div>;
}

export function ExperimentExplorer() {
  const dataSource = useExperimentDataSource();
  const query = useExperimentsQuery();
  const experiments = query.data ?? noExperiments;
  const [state, setState] = useState<ExplorerState>(defaultExplorerState);

  useEffect(() => {
    const syncFromUrl = () => setState(normalizeExplorerState(new URLSearchParams(window.location.search), experiments));
    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, [experiments]);

  const results = useMemo(() => getExplorerResults(experiments, state), [experiments, state]);
  const owners = useMemo(() => Array.from(new Map(experiments.map((experiment) => [experiment.owner.id, experiment.owner])).values()).sort((left, right) => left.name.localeCompare(right.name)), [experiments]);

  const updateState = (next: ExplorerState, replace = false) => {
    const params = stateToParams(next);
    const target = params.toString() ? `/experiment-explorer?${params}` : "/experiment-explorer";
    window.history[replace ? "replaceState" : "pushState"]({}, "", target);
    setState(next);
  };
  const update = (changes: Partial<ExplorerState>, replace = false) => updateState({ ...state, ...changes }, replace);
  const reset = () => updateState(defaultExplorerState);
  const sort = (field: ExplorerSort) => update({ sort: field, direction: state.sort === field && state.direction === "asc" ? "desc" : "asc" });

  return <div className="space-y-6"><div className="rounded-lg border bg-card/35 p-4 text-sm text-muted-foreground"><div className="flex items-start gap-3"><Database aria-hidden="true" className="mt-0.5 size-4 shrink-0" /><div><p className="font-medium text-foreground">{dataSource.label}</p><p className="mt-1">{dataSource.detail}</p></div></div></div><div className="rounded-lg border bg-card/35 p-4"><div className="flex flex-col gap-3 lg:flex-row lg:items-end"><div className="min-w-0 flex-1"><label className="mb-1.5 block text-sm font-medium" htmlFor="experiment-search">Search experiments</label><div className="relative"><Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><input aria-label="Search experiments" className="h-10 w-full rounded-md border bg-transparent pl-9 pr-10 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" id="experiment-search" onChange={(event) => update({ query: event.target.value.trim() }, true)} placeholder="Name, owner, decision, metric, or ID" type="search" value={state.query} />{state.query ? <button aria-label="Clear search" className="absolute right-2 top-1/2 rounded p-1 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => update({ query: "" }, true)} type="button"><X aria-hidden="true" className="size-4" /></button> : null}</div></div><div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:flex"><label className="text-sm font-medium">Status<select className="mt-1.5 h-10 w-full rounded-md border bg-background px-2 text-sm" onChange={(event) => update({ status: event.target.value as ExplorerState["status"] })} value={state.status}><option value="">All statuses</option>{Object.entries(experimentStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="text-sm font-medium">Owner<select className="mt-1.5 h-10 w-full rounded-md border bg-background px-2 text-sm" onChange={(event) => update({ owner: event.target.value })} value={state.owner}><option value="">All owners</option>{owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.name}</option>)}</select></label><label className="text-sm font-medium">From<input className="mt-1.5 h-10 w-full rounded-md border bg-background px-2 text-sm" onChange={(event) => update({ from: event.target.value })} type="date" value={state.from} /></label><label className="text-sm font-medium">To<input className="mt-1.5 h-10 w-full rounded-md border bg-background px-2 text-sm" onChange={(event) => update({ to: event.target.value })} type="date" value={state.to} /></label></div></div></div>{!query.isPending && !query.isError ? <div aria-live="polite" className="flex flex-wrap items-center justify-between gap-3 text-sm"><p className="text-muted-foreground">{results.length === experiments.length ? `${experiments.length} experiment${experiments.length === 1 ? "" : "s"}` : `${results.length} of ${experiments.length} experiments`}</p>{hasActiveFilters(state) ? <Button aria-label="Clear all filters" onClick={reset} variant="outline">Clear all filters</Button> : null}</div> : null}{query.isPending ? <ExplorerSkeleton /> : query.isError ? <EmptyState actionLabel="Retry loading experiments" detail={query.error?.userMessage ?? "The experiment source could not be loaded."} title="Experiments could not be loaded" onReset={() => { void query.refetch(); }} /> : experiments.length === 0 ? <EmptyState detail="The configured source returned no experiment records." title="No experiments are available" /> : results.length === 0 ? <EmptyState detail="Try removing a search term or filter to return to the complete fixture set." onReset={reset} title="No experiments match your explorer settings" /> : <ExperimentTable experiments={results} onSort={sort} state={state} />}</div>;
}
