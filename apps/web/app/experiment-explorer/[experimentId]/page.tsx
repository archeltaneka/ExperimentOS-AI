import { ApplicationShell } from "@/components/application-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Section } from "@/components/layout/section";
import { ExperimentDetail } from "@/features/experiment-detail/experiment-detail";

interface ExperimentDetailPageProps {
  params: Promise<{ experimentId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function toSearchString(searchParams: Record<string, string | string[] | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (typeof value === "string") params.set(key, value);
    if (Array.isArray(value)) value.forEach((item) => params.append(key, item));
  }
  return params.toString();
}

export default async function ExperimentDetailPage({
  params,
  searchParams,
}: ExperimentDetailPageProps) {
  const [{ experimentId }, rawSearchParams] = await Promise.all([params, searchParams]);
  return <ApplicationShell><PageContainer><Section><ExperimentDetail experimentId={experimentId} explorerSearch={toSearchString(rawSearchParams)} /></Section></PageContainer></ApplicationShell>;
}
