"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Database, RotateCcw, Send, Sparkles } from "lucide-react";
import { ContentCard } from "@/components/layout/content-card";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAskDataSource, useAskMutation } from "@/hooks/use-services";
import type { ApiError } from "@/services/errors";
import type { RagAnswer } from "@/types/domain";

const experimentId = "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750";
const examples = [
  "Which experiment produced the highest conversion lift?",
  "Why was the hotel image quality experiment stopped?",
  "What evidence supported the payment experiment recommendation?",
  "Which experiments had inconclusive results?",
  "What experiment affected mobile users most strongly?",
];
const maxQuestionLength = 1_000;

export function AskExperimentWorkspace({ initialAnswer }: { initialAnswer?: RagAnswer }) {
  const mutation = useAskMutation();
  const source = useAskDataSource();
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | undefined>(initialAnswer);
  const [validation, setValidation] = useState<string | undefined>();
  const canUseFixtureContext = source.kind === "deterministic_fixture";
  const [selectedExperimentId, setSelectedExperimentId] = useState(canUseFixtureContext ? experimentId : "");

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion) { setValidation("Enter a question before asking."); return; }
    if (normalizedQuestion.length > maxQuestionLength) { setValidation(`Keep questions to ${maxQuestionLength} characters or fewer.`); return; }
    if (!selectedExperimentId.trim()) { setValidation("Enter the experiment UUID for this request."); return; }
    if (mutation.isPending) return;
    setValidation(undefined); setSubmittedQuestion(normalizedQuestion); setAnswer(undefined);
    mutation.mutate({ question: normalizedQuestion, experimentId: selectedExperimentId.trim() }, { onSuccess: setAnswer });
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); submit(); }
  };
  const resetResult = () => { setAnswer(undefined); setSubmittedQuestion(""); setValidation(undefined); mutation.reset(); };
  const error = mutation.error as ApiError | null;

  return <PageContainer className="py-8 sm:py-10">
    <PageHeader title="Ask Experiment" description="Ask questions about product experiments and inspect the evidence used to construct the answer." actions={<DataSourceBadge label={source.label} detail={source.detail} />} />
    <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(19rem,0.78fr)_minmax(0,1.22fr)]">
      <ContentCard className="h-fit space-y-6">
        <div><h2 className="text-lg font-semibold">Question workspace</h2><p className="mt-1 text-sm text-muted-foreground">Questions are scoped to one experiment because the current live API requires its UUID.</p></div>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-2"><label className="text-sm font-medium" htmlFor="experiment-id">Experiment context</label><input id="experiment-id" value={selectedExperimentId} onChange={(event) => setSelectedExperimentId(event.target.value)} className="h-10 w-full rounded-md border border-input bg-background px-3 font-mono text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-describedby="experiment-help" placeholder="Experiment UUID" /><p id="experiment-help" className="text-xs text-muted-foreground">{canUseFixtureContext ? "Deterministic demo context is preselected." : "Paste the UUID of an experiment available to the live backend."}</p></div>
          <div className="space-y-2"><label className="text-sm font-medium" htmlFor="ask-question">Question</label><textarea id="ask-question" name="question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={onKeyDown} maxLength={maxQuestionLength} rows={7} className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="For example: What evidence supported the recommendation?" aria-describedby={validation || error ? "ask-feedback" : undefined} /><p className="text-xs text-muted-foreground">Use Ctrl+Enter or Cmd+Enter to submit. Enter adds a new line.</p></div>
          {(validation || error) && <p id="ask-feedback" role="alert" className="text-sm text-destructive">{validation ?? error?.userMessage}</p>}
          <div className="flex flex-wrap gap-3"><Button type="submit" disabled={mutation.isPending}><Send aria-hidden="true" className="mr-2 size-4" />{mutation.isPending ? "Asking…" : "Ask question"}</Button>{(answer || mutation.isError) && <Button type="button" variant="outline" onClick={resetResult}><RotateCcw aria-hidden="true" className="mr-2 size-4" />Reset result</Button>}</div>
        </form>
        <div><h3 className="text-sm font-medium">Example prompts</h3><div className="mt-3 flex flex-wrap gap-2">{examples.map((example) => <Button key={example} type="button" variant="outline" className="h-auto whitespace-normal py-2 text-left" onClick={() => { setQuestion(example); setValidation(undefined); }}>{example}</Button>)}</div></div>
      </ContentCard>
      <section aria-live="polite" aria-busy={mutation.isPending} aria-label="Ask Experiment result workspace" className="min-w-0">
        {mutation.isPending ? <LoadingResult question={submittedQuestion} /> : error ? <ErrorResult error={error} onRetry={submit} /> : answer ? <AnswerResult answer={answer} sourceLabel={source.label} /> : <EmptyResult />}
      </section>
    </div>
  </PageContainer>;
}

function DataSourceBadge({ label, detail }: { label: string; detail: string }) { return <Badge title={detail} className="gap-1.5 border-primary/35 bg-primary/10 text-primary"><Database aria-hidden="true" className="size-3" />{label}</Badge>; }
function EmptyResult() { return <ContentCard className="flex min-h-80 flex-col justify-center"><Sparkles aria-hidden="true" className="size-6 text-primary" /><h2 className="mt-4 text-lg font-semibold">Evidence appears here</h2><p className="mt-2 max-w-lg text-sm leading-6 text-muted-foreground">Ask about an experiment to review a grounded answer, its citations, and the retrieved report context behind it.</p></ContentCard>; }
function LoadingResult({ question }: { question: string }) { return <ContentCard className="space-y-5"><div><p className="text-sm font-medium">Retrieving relevant experiment context</p><p className="mt-1 text-sm text-muted-foreground">Preparing a grounded answer{question ? ` for “${question}”` : ""}.</p></div><Skeleton className="h-5 w-5/6" /><Skeleton className="h-5 w-full" /><Skeleton className="h-24 w-full" /></ContentCard>; }
function ErrorResult({ error, onRetry }: { error: ApiError; onRetry: () => void }) { return <ContentCard><h2 className="text-lg font-semibold">The request could not be completed</h2><p className="mt-2 text-sm text-muted-foreground">{error.userMessage}</p><Button className="mt-5" type="button" onClick={onRetry}>Retry question</Button></ContentCard>; }

function AnswerResult({ answer, sourceLabel }: { answer: RagAnswer; sourceLabel: string }) {
  const metadata = answer.requestMetadata;
  return <div className="space-y-6"><ContentCard><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Grounded answer</h2><DataSourceBadge label={sourceLabel} detail="Active Ask service data source." /></div><p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-foreground">{answer.answer}</p></ContentCard><ContentCard><h2 className="text-lg font-semibold">Citations</h2><ol className="mt-4 space-y-3">{answer.citations.map((citation, index) => <li key={`${citation.documentId}-${index}`} className="rounded-md border border-border bg-background/40 p-3 text-sm"><span className="font-mono text-xs text-muted-foreground">[{index + 1}]</span> <span className="font-medium">{citation.documentName}</span>{citation.section && <span className="text-muted-foreground"> · {citation.section}</span>}{citation.score !== undefined && <p className="mt-1 text-xs text-muted-foreground">Similarity {citation.score.toFixed(2)}</p>}</li>)}</ol></ContentCard><ContentCard><h2 className="text-lg font-semibold">Retrieved context</h2><p className="mt-1 text-sm text-muted-foreground">The report excerpts below are the evidence considered for this answer.</p><p className="mt-2 text-xs text-muted-foreground">Higher similarity indicates closer embedding-space relevance, not answer certainty.</p><div className="mt-4 space-y-3">{answer.retrievedChunks.map((chunk, index) => <details key={`${chunk.documentId}-${index}`} open={index === 0} className="rounded-md border border-border bg-background/40 p-3"><summary className="cursor-pointer text-sm font-medium">#{index + 1} {chunk.experimentName ?? chunk.documentName}{chunk.section ? ` · ${chunk.section}` : ""}</summary><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{chunk.text || "No excerpt was returned."}</p><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted-foreground"><span>Document: {chunk.documentId || "Unavailable"}</span>{chunk.similarity !== undefined ? <span>Similarity {chunk.similarity.toFixed(2)}</span> : <span>Similarity unavailable</span>}</div></details>)}</div></ContentCard><ContentCard><h2 className="text-lg font-semibold">Request metadata</h2><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">{metadata.intent && <Metadata label="Intent" value={metadata.intent} />}{metadata.prompt && <Metadata label="Prompt" value={`${metadata.prompt.id} · ${metadata.prompt.version}`} />}{metadata.model && <Metadata label="Model" value={metadata.model} />}{metadata.retrievedChunkCount !== undefined && <Metadata label="Retrieved chunks" value={String(metadata.retrievedChunkCount)} />}<Metadata label="Data source" value={sourceLabel} />{metadata.approvalStatus && <Metadata label="Approval" value={metadata.approvalStatus} />}</dl>{metadata.workflow && <div className="mt-5 border-t pt-5"><h3 className="text-sm font-medium">Workflow metadata</h3>{metadata.requiredAgents.length > 0 && <p className="mt-2 text-sm text-muted-foreground">Required stages: {metadata.requiredAgents.join(", ")}</p>}{metadata.workflow.trace.length > 0 && <ul className="mt-3 space-y-1 font-mono text-xs text-muted-foreground">{metadata.workflow.trace.map((event, index) => <li key={`${event.node}-${index}`}>{event.node}: {event.event}</li>)}</ul>}</div>}</ContentCard></div>;
}
function Metadata({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words font-mono text-xs">{value}</dd></div>; }
