import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";
export function Section({ className, ...props }: HTMLAttributes<HTMLElement>) { return <section className={cn("py-8 sm:py-10", className)} {...props} />; }
