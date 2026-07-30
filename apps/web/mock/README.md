# Deterministic mock data

The portfolio UI uses versioned, deterministic development fixtures until a backend contract is
explicitly available. Fixtures are consumed through services and TanStack Query hooks; presentation
components must not import files in this directory directly.

`experiments.ts` supplies Experiment Explorer summaries with stable IDs, name, status, owner,
started date, primary metric, decision, analysis status, and business-impact availability state.
The current backend has no verified experiment list or read contract. Explorer data therefore remains
a development fixture and must not be presented as live telemetry or an ExperimentOS-generated impact
estimate.
