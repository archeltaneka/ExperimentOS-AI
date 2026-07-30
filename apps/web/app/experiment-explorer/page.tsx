import { ApplicationShell } from "@/components/application-shell";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Section } from "@/components/layout/section";
import { ExperimentExplorer } from "@/features/experiment-explorer/experiment-explorer";

export default function ExperimentExplorerPage() {
  return <ApplicationShell><PageContainer><Section><PageHeader description="Search experiment records, review decisions, and inspect analysis readiness." title="Experiment Explorer" /><div className="mt-8"><ExperimentExplorer /></div></Section></PageContainer></ApplicationShell>;
}
