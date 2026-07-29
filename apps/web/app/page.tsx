import type { Metadata } from "next";

import { LandingPage } from "@/components/landing-page";
import { createServices } from "@/services/adapters";

export const metadata: Metadata = {
  title: "Experiment evidence and decision support",
  description:
    "ExperimentOS AI turns experiment artifacts into searchable evidence, grounded answers, and repeatable evaluations.",
  openGraph: {
    title: "ExperimentOS AI | Experiment evidence and decision support",
    description: "Traceable experiment evidence, grounded answers, and repeatable AI evaluation workflows.",
  },
};

export default async function Home() {
  const roadmap = await createServices().roadmap.list();

  return <LandingPage roadmap={roadmap} />;
}
