import { ApplicationShell } from "@/components/application-shell";
import { ExperimentBrowser } from "@/features/ask-experiment/experiment-browser";

export default function AskExperiment() {
  return <ApplicationShell><ExperimentBrowser /></ApplicationShell>;
}
