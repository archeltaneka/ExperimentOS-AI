import type { CapabilityStatus as DomainCapabilityStatus, RoadmapPhaseStatus } from "@/types/domain";

export type CapabilityStatus = DomainCapabilityStatus;

export const capabilityStatuses = {
  completed: {
    label: "Completed",
    className: "border-status-completed/30 bg-status-completed/10 text-status-completed",
  },
  "in-progress": {
    label: "In progress",
    className: "border-status-progress/30 bg-status-progress/10 text-status-progress",
  },
  planned: {
    label: "Planned",
    className: "border-status-planned/30 bg-status-planned/10 text-status-planned",
  },
  "future-research": {
    label: "Future research",
    className: "border-status-research/30 bg-status-research/10 text-status-research",
  },
  unavailable: {
    label: "Unavailable",
    className: "border-status-unavailable/30 bg-status-unavailable/10 text-status-unavailable",
  },
} as const satisfies Record<DomainCapabilityStatus, { label: string; className: string }>;

export const roadmapPhaseStatuses = {
  completed: capabilityStatuses.completed,
  in_progress: capabilityStatuses["in-progress"],
  planned: capabilityStatuses.planned,
  future: capabilityStatuses["future-research"],
  research: capabilityStatuses["future-research"],
} as const satisfies Record<RoadmapPhaseStatus, { label: string; className: string }>;
