"use client";

import { motion } from "framer-motion";
import { Layers3, Sparkles } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { type CapabilityStatus } from "@/lib/capability-status";

const statuses: CapabilityStatus[] = [
  "completed",
  "in-progress",
  "planned",
  "future-research",
  "unavailable",
];

export function FoundationPreview() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-5 py-12 sm:px-8">
      <motion.section
        animate={{ opacity: 1, y: 0 }}
        className="w-full"
        initial={{ opacity: 0, y: 8 }}
        transition={{ duration: 0.24, ease: "easeOut" }}
      >
        <div className="mb-6 flex items-center gap-3 text-muted-foreground">
          <div className="flex size-9 items-center justify-center rounded-md border bg-card">
            <Layers3 aria-hidden="true" className="size-4 text-primary" />
          </div>
          <span className="font-mono text-xs tracking-[0.16em] uppercase">Foundation preview</span>
        </div>

        <Card className="overflow-hidden">
          <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[1.2fr_0.8fr]">
            <div>
              <p className="mb-3 text-sm text-muted-foreground">Experiment analysis workspace</p>
              <h1 className="max-w-xl text-3xl font-semibold tracking-tight sm:text-4xl">
                ExperimentOS AI
              </h1>
              <p className="mt-4 max-w-xl text-sm leading-6 text-muted-foreground">
                Temporary design-system verification. Product surfaces and backend integrations are
                intentionally not available in this foundation.
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                {statuses.map((status) => (
                  <StatusBadge key={status} status={status} />
                ))}
              </div>
              <div className="mt-8 flex items-center gap-3">
                <Button disabled>
                  <Sparkles aria-hidden="true" className="size-4" />
                  Foundation only
                </Button>
                <Button disabled variant="outline">
                  Interface pending
                </Button>
              </div>
            </div>

            <div className="rounded-md border bg-muted/35 p-5">
              <p className="font-mono text-xs text-muted-foreground">SYSTEM / PREVIEW</p>
              <Separator className="my-4" />
              <div className="space-y-3">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-4/5" />
                <Skeleton className="mt-6 h-16 w-full" />
              </div>
            </div>
          </div>
        </Card>
      </motion.section>
    </main>
  );
}
