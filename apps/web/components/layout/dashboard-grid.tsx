import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";
export function DashboardGrid({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={cn("grid gap-4 md:grid-cols-2 xl:grid-cols-3", className)} {...props} />; }
