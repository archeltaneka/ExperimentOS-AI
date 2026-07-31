export const askQueryKeys = {
  experiments: ["experiments"] as const,
  experimentList: () => [...askQueryKeys.experiments, "list"] as const,
  experimentDetail: (id: string) => [...askQueryKeys.experiments, "detail", id] as const,
  evaluationSummary: () => ["evaluations", "summary"] as const,
  evaluationHistory: () => ["evaluations", "history"] as const,
  evaluationDashboard: () => ["evaluations", "dashboard"] as const,
  roadmap: () => ["roadmap"] as const,
};
