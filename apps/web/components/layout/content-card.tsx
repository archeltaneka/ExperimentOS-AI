import type { HTMLAttributes } from "react";
import { Card } from "@/components/ui/card";
export function ContentCard(props: HTMLAttributes<HTMLDivElement>) { return <Card className="p-5 sm:p-6" {...props} />; }
