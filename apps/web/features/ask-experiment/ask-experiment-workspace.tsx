"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { FileSearch, RotateCcw, Send } from "lucide-react";
import { ContentCard } from "@/components/layout/content-card";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { SourceDisclosure } from "@/components/source-disclosure";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAskDataSource, useAskMutation, useAskSamples, useExperimentsQuery } from "@/hooks/use-services";
import type { AskSample } from "@/services/contracts";
import type { ApiError } from "@/services/errors";
import type { DataSource, RagAnswer } from "@/types/domain";

const liveExamples = [
  "What evidence supported this experiment’s recommendation?",
  "What limitations does this experiment’s report describe?",
];
const maxQuestionLength = 1_000;

export function AskExperimentWorkspace({ initialAnswer, experimentId, embedded = false }: { initialAnswer?: RagAnswer; experimentId?: string; embedded?: boolean }) {
  const source = useAskDataSource();
  const samples = useAskSamples();
  const query = useExperimentsQuery();
  const [selectedExperimentId, setSelectedExperimentId] = useState("");
  const activeExperimentId = experimentId || selectedExperimentId || query.data?.[0]?.id || "";

  let content: ReactNode;
  if (!experimentId && query.isPending) {
    content = <p role="status" className="mt-8">Loading experiment contexts…</p>;
  } else if (!experimentId && query.isError) {
    content = <ContentCard className="mt-8 space-y-4 p-5" role="alert"><p>Experiment contexts could not be loaded. {query.error?.userMessage}</p><Button onClick={() => void query.refetch()}>Retry loading experiments</Button></ContentCard>;
  } else if (!experimentId && !query.data?.length) {
    content = <ContentCard className="mt-8 space-y-4 p-5"><p role="status">No experiments are available.</p><p className="text-sm text-muted-foreground">An experiment report is needed before you can ask a question. Reload after records have been added to the current data source.</p><Button variant="outline" onClick={() => void query.refetch()}>Reload experiments</Button></ContentCard>;
  } else {
    content = <QuestionWorkspace key={activeExperimentId} experimentId={activeExperimentId} source={source} samples={samples} initialAnswer={initialAnswer} contextSelector={!experimentId && <div className="space-y-2"><label className="text-sm font-medium" htmlFor="experiment-id">Experiment context</label><select id="experiment-id" value={activeExperimentId} onChange={(event) => setSelectedExperimentId(event.target.value)} className="h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-describedby="experiment-help">{query.data?.map((experiment) => <option key={experiment.id} value={experiment.id}>{experiment.name}</option>)}</select><p id="experiment-help" className="text-sm text-muted-foreground">Choose the experiment whose evidence you want to inspect.</p></div>} />;
  }

  if (embedded) return <div><header className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-2xl font-semibold tracking-tight">Ask Experiment</h2><p className="mt-2 text-sm text-muted-foreground">Ask about this experiment and inspect the evidence behind its answer.</p></div><SourceDisclosure compact source={source} /></header>{content}</div>;
  return <PageContainer className="py-8 sm:py-10"><PageHeader title="Ask Experiment" description="Ask about one experiment and inspect the evidence behind its answer." actions={<SourceDisclosure compact source={source} />} />{content}</PageContainer>;
}

// A different experiment mounts a fresh workspace: drafts, errors and late answers
// from a previous request cannot be presented as evidence for the new context.
function QuestionWorkspace({ experimentId, source, samples, initialAnswer, contextSelector }: {
  experimentId: string;
  source: DataSource;
  samples: readonly AskSample[];
  initialAnswer?: RagAnswer;
  contextSelector: ReactNode;
}) {
  const mutation = useAskMutation();
  const submitting = useRef(false);
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | undefined>(() => {
    const evidence = [...(initialAnswer?.citations ?? []), ...(initialAnswer?.retrievedChunks ?? [])];
    return evidence.length > 0 && evidence.every((item) => item.experimentId === experimentId) ? initialAnswer : undefined;
  });
  const [validation, setValidation] = useState<string | undefined>();
  const isDemo = source.kind === "deterministic_fixture";
  const examples = isDemo ? samples.filter((sample) => sample.experimentId === experimentId).map((sample) => sample.question) : liveExamples;
  const unavailable = isDemo && examples.length === 0;
  const error = mutation.error as ApiError | null;

  const submit = (event?: FormEvent, retryQuestion?: string) => {
    event?.preventDefault();
    if (unavailable || submitting.current || mutation.isPending) return;
    const normalizedQuestion = (retryQuestion ?? question).trim();
    if (!normalizedQuestion) { setValidation("Enter a question before asking."); return; }
    if (normalizedQuestion.length > maxQuestionLength) { setValidation(`Keep questions to ${maxQuestionLength} characters or fewer.`); return; }
    submitting.current = true;
    setValidation(undefined);
    setSubmittedQuestion(normalizedQuestion);
    setAnswer(undefined);
    mutation.mutate({ question: normalizedQuestion, experimentId }, {
      onSuccess: setAnswer,
      onSettled: () => { submitting.current = false; },
    });
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); submit(); }
  };
  const resetResult = () => { setAnswer(undefined); setSubmittedQuestion(""); setValidation(undefined); mutation.reset(); };
  const canRetry = error && ["network", "timeout", "server", "invalid_response"].includes(error.code);

  return <div id="question-workspace" className="mt-8 grid scroll-mt-8 gap-6 xl:grid-cols-[minmax(19rem,0.78fr)_minmax(0,1.22fr)]">
    <ContentCard className="atlas-question-panel min-w-0 h-fit space-y-6 p-5 sm:p-6">
      <div><h2 className="text-lg font-semibold">Question workspace</h2><p className="mt-1 text-sm text-muted-foreground">Questions use evidence from this experiment only.</p></div>
      <form className="space-y-4" onSubmit={submit}>
        {contextSelector}
        {isDemo && <div id="demo-help" className="space-y-2 text-sm leading-6" role={unavailable ? "status" : undefined}>
          <p className="font-medium">Saved-answer demo</p>
          <p>{unavailable ? "Saved answers are available only for experiments with supported sample questions." : "This demo shows saved answers to the sample questions below. It does not generate answers to other questions."}</p>
          {unavailable && <><p>There are no saved answers for this experiment.</p>{samples[0] && <Link className="inline-flex min-h-11 items-center rounded-sm text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={`/ask-experiment/${samples[0].experimentId}`}>Open the payment sample</Link>}</>}
        </div>}
      {examples.length > 0 && <div><h3 className="text-sm font-medium">{isDemo ? "Supported sample questions" : "Example prompts"}</h3><p className="mt-1 text-sm text-muted-foreground">{isDemo ? "Choose a sample, then ask" : "Choose a prompt or write your own question."}</p><div className="mt-3 flex flex-col items-start gap-2">{examples.map((example) => <Button key={example} aria-pressed={question === example} type="button" variant="outline" disabled={mutation.isPending} className="min-h-11 h-auto max-w-full whitespace-normal break-words py-2 text-left" onClick={() => { setQuestion(example); setValidation(undefined); mutation.reset(); }}>{example}</Button>)}</div></div>}
        <div className="space-y-2"><label className="text-sm font-medium" htmlFor="ask-question">Question</label><textarea id="ask-question" name="question" value={question} onChange={(event) => { setQuestion(event.target.value); setValidation(undefined); }} onKeyDown={onKeyDown} maxLength={maxQuestionLength} rows={4} disabled={unavailable || mutation.isPending} className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-base leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60" placeholder={isDemo ? "Choose a supported sample question above." : "What evidence supported the recommendation?"} aria-invalid={Boolean(validation || error?.code === "demo_unavailable")} aria-describedby={["question-help", isDemo && "demo-help", (validation || error) && "ask-feedback"].filter(Boolean).join(" ")} /><p id="question-help" className="text-sm text-muted-foreground">Use Ctrl+Enter or Cmd+Enter to submit. Enter adds a new line.</p></div>
        {(validation || error) && <p id="ask-feedback" role="alert" className="text-sm text-destructive">{validation ?? error?.userMessage}</p>}
        <div className="flex flex-wrap gap-3"><Button type="submit" disabled={mutation.isPending || unavailable}><Send aria-hidden="true" className="mr-2 size-4" />{mutation.isPending ? "Asking…" : "Ask question"}</Button>{(answer || mutation.isError) && <Button type="button" variant="outline" onClick={resetResult}><RotateCcw aria-hidden="true" className="mr-2 size-4" />Reset result</Button>}</div>
      </form>
    </ContentCard>
    <section aria-live="polite" aria-busy={mutation.isPending} aria-label="Ask Experiment result workspace" className="min-w-0">
      {mutation.isPending ? <LoadingResult question={submittedQuestion} isDemo={isDemo} /> : error ? <ErrorResult error={error} onRetry={canRetry ? () => submit(undefined, submittedQuestion) : undefined} /> : answer ? <><p className="mb-3 break-words text-sm text-muted-foreground">{submittedQuestion && `Question: ${submittedQuestion}`}{isDemo && " · Saved sample answer"}</p><div className="mb-4 border-b border-border pb-4"><h2 className="text-sm font-medium">Next, inspect the evidence</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">Compare the answer with its citations and expand the retrieved context to check the supporting report excerpts.</p></div><AnswerResult answer={answer} sourceLabel={source.label} /></> : <EmptyResult isDemo={isDemo} unavailable={unavailable} />}
    </section>
  </div>;
}

function EmptyResult({ isDemo, unavailable }: { isDemo: boolean; unavailable: boolean }) {
  return <ContentCard className="atlas-empty-evidence flex min-h-64 flex-col justify-center p-5 sm:p-6">
    <FileSearch aria-hidden="true" className="size-6 text-primary" />
    <h2 className="mt-4 text-lg font-semibold">Evidence appears here</h2>
    <p className="mt-2 max-w-lg text-sm leading-6 text-muted-foreground">{unavailable ? "This experiment has no saved answers. Open an available sample from the question workspace to explore an answer with citations." : isDemo ? "Choose a supported sample question and select Ask question to load its saved answer." : "Enter a question and select Ask question to review an answer grounded in this experiment’s report."}</p>
    {!unavailable && <ol className="mt-5 list-decimal space-y-2 pl-5 text-sm leading-6 text-muted-foreground"><li>Read the answer and its limitations.</li><li>Check the cited report sections.</li><li>Expand retrieved context to inspect the source excerpts.</li></ol>}
  </ContentCard>;
}
function LoadingResult({ question, isDemo }: { question: string; isDemo: boolean }) { return <ContentCard className="space-y-5 p-5 sm:p-6"><div><p className="text-sm font-medium">{isDemo ? "Loading saved answer" : "Retrieving relevant experiment context"}</p><p className="mt-1 text-sm text-muted-foreground">{isDemo ? "Opening the saved sample" : "Preparing a grounded answer"}{question ? ` for “${question}”` : ""}.</p></div><Skeleton className="h-5 w-5/6" /><Skeleton className="h-5 w-full" /><Skeleton className="h-24 w-full" /></ContentCard>; }
function ErrorResult({ error, onRetry }: { error: ApiError; onRetry?: () => void }) { return <ContentCard className="p-5 sm:p-6"><h2 className="text-lg font-semibold">The request could not be completed</h2><p className="mt-2 text-sm text-muted-foreground">{error.userMessage}</p>{onRetry && <Button className="mt-5" type="button" onClick={onRetry}>Retry question</Button>}</ContentCard>; }

function AnswerResult({ answer, sourceLabel }: { answer: RagAnswer; sourceLabel: string }) {
  const metadata = answer.requestMetadata;
  return <div className="atlas-answer space-y-6"><ContentCard className="p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Grounded answer</h2><span className="text-xs text-muted-foreground">Source: {sourceLabel}</span></div><p className="mt-4 break-words whitespace-pre-wrap text-sm leading-7 text-foreground">{answer.answer}</p></ContentCard><ContentCard className="p-5 sm:p-6"><h2 className="text-lg font-semibold">Citations</h2><ol className="mt-4 space-y-3">{answer.citations.map((citation, index) => <li key={`${citation.documentId}-${index}`} className="border-t border-border py-3 text-sm"><span className="font-mono text-xs text-muted-foreground">[{index + 1}]</span> <span className="font-medium">{citation.documentName}</span>{citation.section && <span className="text-muted-foreground"> · {citation.section}</span>}{citation.score !== undefined && <p className="mt-1 text-xs text-muted-foreground">Similarity {citation.score.toFixed(2)}</p>}</li>)}</ol></ContentCard><ContentCard className="p-5 sm:p-6"><h2 className="text-lg font-semibold">Retrieved context</h2><p className="mt-1 text-sm text-muted-foreground">The report excerpts below are the evidence considered for this answer.</p><p className="mt-2 text-xs text-muted-foreground">Higher similarity indicates closer embedding-space relevance, not answer certainty.</p><div className="mt-4 space-y-3">{answer.retrievedChunks.map((chunk, index) => <details key={`${chunk.documentId}-${index}`} open={index === 0} className="border-t border-border py-3"><summary className="cursor-pointer break-words text-sm font-medium">#{index + 1} {chunk.experimentName ?? chunk.documentName}{chunk.section ? ` · ${chunk.section}` : ""}</summary><p className="mt-3 break-words whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{chunk.text || "No excerpt was returned."}</p><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted-foreground"><span className="break-all">Document: {chunk.documentId || "Unavailable"}</span>{chunk.similarity !== undefined ? <span>Similarity {chunk.similarity.toFixed(2)}</span> : <span>Similarity unavailable</span>}</div></details>)}</div></ContentCard><ContentCard className="p-5 sm:p-6"><h2 className="text-lg font-semibold">Request metadata</h2><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">{metadata.intent && <Metadata label="Intent" value={metadata.intent} />}{metadata.prompt && <Metadata label="Prompt" value={`${metadata.prompt.id} · ${metadata.prompt.version}`} />}{metadata.model && <Metadata label="Model" value={metadata.model} />}{metadata.retrievedChunkCount !== undefined && <Metadata label="Retrieved chunks" value={String(metadata.retrievedChunkCount)} />}<Metadata label="Data source" value={sourceLabel} />{metadata.approvalStatus && <Metadata label="Approval" value={metadata.approvalStatus} />}</dl>{metadata.workflow && <div className="mt-5 border-t pt-5"><h3 className="text-sm font-medium">Workflow metadata</h3>{metadata.requiredAgents.length > 0 && <p className="mt-2 text-sm text-muted-foreground">Required stages: {metadata.requiredAgents.join(", ")}</p>}{metadata.workflow.trace.length > 0 && <ul className="mt-3 space-y-1 font-mono text-xs text-muted-foreground">{metadata.workflow.trace.map((event, index) => <li key={`${event.node}-${index}`}>{event.node}: {event.event}</li>)}</ul>}</div>}</ContentCard></div>;
}
function Metadata({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words font-mono text-xs">{value}</dd></div>; }
