import { ApplicationShell } from "@/components/application-shell";
import { ExperimentReportPage } from "@/features/ask-experiment/experiment-browser";

export default async function AskExperimentDetail({ params }: { params: Promise<{ experimentId: string }> }) {
  const { experimentId } = await params;
  return <ApplicationShell><ExperimentReportPage experimentId={experimentId} /></ApplicationShell>;
}
