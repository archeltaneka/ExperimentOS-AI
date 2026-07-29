import { Badge } from "@/components/ui/badge";
import { capabilityStatuses, type CapabilityStatus } from "@/lib/capability-status";

export function StatusBadge({ status }: Readonly<{ status: CapabilityStatus }>) {
  const definition = capabilityStatuses[status];

  return <Badge className={definition.className}>{definition.label}</Badge>;
}
