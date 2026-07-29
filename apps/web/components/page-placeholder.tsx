import { ContentCard } from "@/components/layout/content-card";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Section } from "@/components/layout/section";

export function PagePlaceholder({ title, description, issue }: { title: string; description: string; issue: number }) {
  return <PageContainer><Section><PageHeader title={title} description={description} /><ContentCard className="mt-8 text-sm text-muted-foreground">Coming in Issue #{issue}</ContentCard></Section></PageContainer>;
}
