import { Database } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DataSource } from "@/types/domain";

export function SourceDisclosure({
  source,
  compact = false,
  className,
}: Readonly<{ source: DataSource; compact?: boolean; className?: string }>) {
  if (compact) {
    return (
      <Badge className={cn("max-w-full gap-1.5 border-primary/35 bg-primary/10 text-primary", className)}>
        <Database aria-hidden="true" className="size-3 shrink-0" />
        <span className="truncate">{source.label}</span>
      </Badge>
    );
  }

  return (
    <div className={cn("flex items-start gap-3 rounded-lg border bg-card/35 p-4 text-sm", className)}>
      <Database aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
      <div className="min-w-0">
        <p className="font-medium text-foreground">{source.label}</p>
        <p className="mt-1 break-words text-muted-foreground">{source.detail}</p>
      </div>
    </div>
  );
}
