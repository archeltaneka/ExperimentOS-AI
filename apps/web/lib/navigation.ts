import type { LucideIcon } from "lucide-react";
import { Bot, ChartNoAxesCombined, FlaskConical, House, Map } from "lucide-react";

export type NavigationItem = {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
};

export const navigationItems: readonly NavigationItem[] = [
  { href: "/", label: "Overview", description: "Workspace overview", icon: House },
  { href: "/ask-experiment", label: "Ask Experiment", description: "Evidence assistant", icon: Bot },
  { href: "/experiment-explorer", label: "Experiment Explorer", description: "Experiment records", icon: FlaskConical },
  { href: "/evaluation-dashboard", label: "Evaluation Dashboard", description: "Evaluation insights", icon: ChartNoAxesCombined },
  { href: "/roadmap", label: "Roadmap", description: "Product direction", icon: Map },
];
