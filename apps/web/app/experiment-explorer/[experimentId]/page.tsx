import { ApplicationShell } from "@/components/application-shell";
import { PagePlaceholder } from "@/components/page-placeholder";

export default function ExperimentDetailPlaceholder() {
  return <ApplicationShell><PagePlaceholder description="Experiment detail inspection will be added in Issue #7." issue={7} title="Experiment detail" /></ApplicationShell>;
}
