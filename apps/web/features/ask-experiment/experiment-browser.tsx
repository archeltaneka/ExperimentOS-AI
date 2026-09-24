"use client";

import Link from "next/link";
import { ContentCard } from "@/components/layout/content-card";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { SourceDisclosure } from "@/components/source-disclosure";
import { Button } from "@/components/ui/button";
import { AskExperimentWorkspace } from "@/features/ask-experiment/ask-experiment-workspace";
import { useAskDataSource, useAskSamples, useExperimentDataSource, useExperimentDetailQuery, useExperimentsQuery } from "@/hooks/use-services";

const linkClass = "inline-flex min-h-11 items-center rounded-sm text-sm text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function ExperimentBrowser() {
  const query = useExperimentsQuery();
  const source = useExperimentDataSource();
  const askSource = useAskDataSource();
  const samples = useAskSamples();
  const recommended = askSource.kind === "deterministic_fixture" && !query.isPending && !query.isError
    ? query.data?.find((experiment) => samples.some((sample) => sample.experimentId === experiment.id))
    : undefined;
  return <PageContainer className="py-8 sm:py-10">
    <PageHeader title="Experiments" description="Open an experiment to review its report and ask grounded questions." actions={<SourceDisclosure compact source={source} />} />
    {recommended && <section aria-labelledby="sample-start" className="mt-8 border-y border-border py-6 sm:py-8">
      <h2 id="sample-start" className="text-xl font-semibold">Start with a cited answer</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Try {recommended.name}. Choose a supported question, view its saved answer, then inspect the citations and report excerpts behind it.</p>
      <p className="mt-2 text-sm text-muted-foreground">This sample uses demo fixtures. No setup is needed.</p>
      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Link className="inline-flex min-h-11 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={`/ask-experiment/${recommended.id}#question-workspace`}>Try a sample question</Link>
        <a className={linkClass} href="#all-experiments">Browse all experiments</a>
      </div>
    </section>}
    {query.isPending ? <p role="status" className="mt-8">Loading experiments…</p> : query.isError ?
      <ContentCard className="mt-8 space-y-4 p-5" role="alert"><p>Experiments could not be loaded. {query.error.userMessage}</p><Button onClick={() => void query.refetch()}>Retry loading experiments</Button></ContentCard> :
      !query.data?.length ? <ContentCard className="mt-8 space-y-4 p-5"><p role="status">No experiments are available.</p><p className="text-sm text-muted-foreground">An experiment report is needed before you can inspect answers and citations. Reload after records have been added to the current data source.</p><Button variant="outline" onClick={() => void query.refetch()}>Reload experiments</Button></ContentCard> :
      <div id="all-experiments" className="mt-8 grid scroll-mt-8 gap-4 sm:grid-cols-2">{query.data.map((experiment) => <Link className="min-w-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" key={experiment.id} href={`/ask-experiment/${experiment.id}`}><ContentCard className="h-full p-5 transition-colors hover:bg-muted/50"><h2 className="break-words font-semibold">{experiment.name}</h2><p className="mt-2 text-sm text-muted-foreground">{experiment.status}</p></ContentCard></Link>)}</div>}
  </PageContainer>;
}

export function ExperimentReportPage({ experimentId }: { experimentId: string }) {
  const query = useExperimentDetailQuery(experimentId);
  const source = useExperimentDataSource();
  const back = <Link className={linkClass} href="/ask-experiment">Back to experiments</Link>;
  if (query.isPending) return <PageContainer className="py-8">{back}<p role="status" className="mt-4">Loading report…</p></PageContainer>;
  if (query.isError || !query.data) {
    const missing = query.isError ? query.error.code === "not_found" : true;
    return <PageContainer className="py-8">{back}<ContentCard className="mt-4 space-y-4 p-5" role="alert"><h1 className="text-xl font-semibold">{missing ? "Experiment report was not found." : "Experiment report could not be loaded."}</h1><p className="text-sm text-muted-foreground">{missing ? "Return to the experiment list and choose an available record." : query.error?.userMessage}</p>{!missing && <Button onClick={() => void query.refetch()}>Retry loading report</Button>}</ContentCard></PageContainer>;
  }
  const experiment = query.data;
  return <PageContainer className="py-8 sm:py-10">
    <div className="mb-4">{back}</div>
    <PageHeader title={experiment.name} description={experiment.summary} actions={<SourceDisclosure compact source={source} />} />
    <ContentCard className="mt-8 p-5 sm:p-6"><h2 className="text-lg font-semibold">Experiment report</h2>{experiment.report?.executiveSummary ? <p className="mt-4 break-words whitespace-pre-wrap text-base leading-7">{experiment.report.executiveSummary}</p> : <p className="mt-4 text-sm text-muted-foreground">No report content is available.</p>}</ContentCard>
    <div className="mt-8"><AskExperimentWorkspace experimentId={experimentId} /></div>
  </PageContainer>;
}
