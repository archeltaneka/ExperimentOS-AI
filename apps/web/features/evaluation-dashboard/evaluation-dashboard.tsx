"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useEvaluationDashboardQuery, useEvaluationDataSource } from "@/hooks/use-services";
import type { EvaluationStatus } from "@/types/domain";

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
  pass: "border-emerald-200 bg-emerald-50 text-emerald-800",
  fail: "border-red-200 bg-red-50 text-red-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  not_evaluated: "border-border bg-muted text-muted-foreground",
  regressed: "border-red-200 bg-red-50 text-red-800",
  improved: "border-emerald-200 bg-emerald-50 text-emerald-800",
  unchanged: "border-border bg-muted text-muted-foreground",
  not_gated: "border-border bg-muted text-muted-foreground",
};

function Status({ status }: { status: EvaluationStatus }) {
  return <Badge className={statusClasses[status]}>{labels[status]}</Badge>;
}

export function EvaluationDashboardView() {
  const query = useEvaluationDashboardQuery();
  const source = useEvaluationDataSource();

  if (query.isPending) {
    return (
      <div aria-live="polite" className="space-y-4">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <Card className="p-6" role="alert">
        <h2 className="font-semibold">Evaluation results could not be loaded</h2>
        <p className="mt-2 text-sm text-muted-foreground">{query.error.userMessage}</p>
        <button
          className="mt-4 rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => void query.refetch()}
        >
          Retry loading evaluations
        </button>
      </Card>
    );
  }

  const dashboard = query.data;
  const criteria = dashboard.gate.blockers.join(", ") || "No blocking criteria";

  return (
    <div className="space-y-3">
      <Card className="overflow-hidden rounded-xl bg-card shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b px-6 py-5">
          <h1 className="text-2xl font-semibold tracking-tight">Evaluations</h1>
          <div>
            <Button
              className="bg-emerald-600 text-white hover:bg-emerald-600"
              disabled
              title="Evaluation runs are not connected yet."
            >
              Run evaluation
            </Button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[48rem] text-left text-sm">
            <thead className="border-b bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Dataset</th>
                <th className="px-4 py-3 text-center font-medium">Rows</th>
                <th className="px-4 py-3 font-medium">Criteria</th>
                <th className="px-6 py-3 font-medium">Run</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b last:border-b-0">
                <td className="px-6 py-5 font-medium">{dashboard.run.name}</td>
                <td className="px-4 py-5"><Status status={dashboard.run.status} /></td>
                <td className="px-4 py-5 text-muted-foreground">{dashboard.run.dataset}</td>
                <td className="px-4 py-5 text-center text-muted-foreground">{dashboard.cases.length}</td>
                <td className="px-4 py-5 text-muted-foreground">
                  {dashboard.metrics.length} metrics · {criteria}
                </td>
                <td className="px-6 py-5 font-mono text-muted-foreground">
                  {dashboard.run.model ?? "Model unavailable"} · {dashboard.run.id}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
      <p className="px-1 text-xs text-muted-foreground">
        {source.label}: {source.detail} Evaluation runs are not connected yet.
      </p>
    </div>
  );
}
