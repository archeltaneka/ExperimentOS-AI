import type { BusinessImpactState, DecisionStatus, Experiment, ExperimentStatus } from "@/types/domain";

export const experimentStatusLabels: Record<ExperimentStatus, string> = {
  completed: "Completed",
  running: "Running",
  inconclusive: "Inconclusive",
  stopped: "Stopped",
};

export const decisionStatusLabels: Record<DecisionStatus, string> = {
  approved: "Ship",
  rejected: "Do not ship",
  pending: "Pending",
  not_required: "Not applicable",
};

export const businessImpactLabels: Record<BusinessImpactState, string> = {
  available: "Stored historical value",
  not_estimated: "Not estimated",
  unavailable: "Unavailable",
};

const sortableFields = ["name", "status", "owner", "startedAt", "primaryMetric"] as const;
const directions = ["asc", "desc"] as const;

export type ExplorerSort = (typeof sortableFields)[number];
export type ExplorerDirection = (typeof directions)[number];

export interface ExplorerState {
  query: string;
  status: ExperimentStatus | "";
  owner: string;
  from: string;
  to: string;
  sort: ExplorerSort;
  direction: ExplorerDirection;
}

export const defaultExplorerState: ExplorerState = {
  query: "",
  status: "",
  owner: "",
  from: "",
  to: "",
  sort: "startedAt",
  direction: "desc",
};

function isDate(value: string | null): value is string {
  return Boolean(value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`)));
}

function includes<T extends readonly string[]>(values: T, value: string | null): value is T[number] {
  return Boolean(value && values.includes(value));
}

export function normalizeExplorerState(
  params: URLSearchParams,
  experiments: readonly Experiment[],
): ExplorerState {
  const status = params.get("status");
  const owner = params.get("owner");
  const from = params.get("from");
  const to = params.get("to");
  const sort = params.get("sort");
  const direction = params.get("direction");
  const ownerIds = new Set(experiments.map((experiment) => experiment.owner.id));

  return {
    query: params.get("q")?.trim() ?? "",
    status: includes(Object.keys(experimentStatusLabels) as ExperimentStatus[], status) ? status : "",
    owner: owner && ownerIds.has(owner) ? owner : "",
    from: isDate(from) ? from : "",
    to: isDate(to) ? to : "",
    sort: includes(sortableFields, sort) ? sort : defaultExplorerState.sort,
    direction: includes(directions, direction) ? direction : defaultExplorerState.direction,
  };
}

function searchText(experiment: Experiment): string {
  return [
    experiment.name,
    experiment.id,
    experiment.owner.name,
    experiment.owner.team,
    experiment.decision.recommendation,
    experiment.decision.rationale,
    experiment.primaryMetric.name,
  ]
    .join(" ")
    .toLocaleLowerCase();
}

function sortValue(experiment: Experiment, field: ExplorerSort): string | number | null {
  if (field === "name") return experiment.name;
  if (field === "status") return experimentStatusLabels[experiment.status];
  if (field === "owner") return experiment.owner.name;
  if (field === "startedAt") return experiment.startedAt;
  return Number.isFinite(experiment.primaryMetric.value) ? experiment.primaryMetric.value : null;
}

function compareValues(left: string | number | null, right: string | number | null): number {
  if (left === null) return right === null ? 0 : 1;
  if (right === null) return -1;
  if (typeof left === "number" && typeof right === "number") return left - right;
  return String(left).localeCompare(String(right));
}

export function getExplorerResults(
  experiments: readonly Experiment[],
  state: ExplorerState,
): readonly Experiment[] {
  const query = state.query.trim().toLocaleLowerCase();
  const filtered = experiments.filter((experiment) => {
    const startedDate = experiment.startedAt.slice(0, 10);
    return (
      (!query || searchText(experiment).includes(query)) &&
      (!state.status || experiment.status === state.status) &&
      (!state.owner || experiment.owner.id === state.owner) &&
      (!state.from || startedDate >= state.from) &&
      (!state.to || startedDate <= state.to)
    );
  });

  return filtered
    .map((experiment, index) => ({ experiment, index }))
    .sort((left, right) => {
      const leftValue = sortValue(left.experiment, state.sort);
      const rightValue = sortValue(right.experiment, state.sort);
      if (leftValue === null) return rightValue === null ? left.index - right.index : 1;
      if (rightValue === null) return -1;
      const comparison = compareValues(leftValue, rightValue);
      return comparison === 0 ? left.index - right.index : state.direction === "asc" ? comparison : -comparison;
    })
    .map(({ experiment }) => experiment);
}
