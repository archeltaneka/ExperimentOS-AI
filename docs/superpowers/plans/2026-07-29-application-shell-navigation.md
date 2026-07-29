# Application Shell and Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the accessible ExperimentOS AI application shell and five placeholder routes for Issue #115.

**Architecture:** Keep the root layout, primitives, and pages server-rendered. Centralize navigation metadata in `lib/navigation.ts`; restrict client code to pathname-aware links and the mobile drawer.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4, Lucide React, Framer Motion, Vitest, Testing Library.

## Global Constraints

- Do not modify backend files, dependencies, APIs, mocks, or page-specific product content.
- Retain Issue #1 semantic tokens, typography, local UI primitives, and `@/*` aliases.
- Use semantic landmarks, visible focus states, `aria-current="page"`, and Lucide icons.
- Restore the missing Issue #1 `lib/utils.ts` and `lib/capability-status.ts` modules.

---

### Task 1: Restore Issue #1 helpers

**Files:**
- Create: `apps/web/lib/utils.ts`
- Create: `apps/web/lib/capability-status.ts`
- Modify: `apps/web/tests/foundation-page.test.tsx`

**Interfaces:** Produces `cn(...inputs: ClassValue[]): string`, `CapabilityStatus`, and `capabilityStatuses`.

- [ ] **Step 1: Write a failing helper test**

```tsx
expect(cn("base", false && "hidden", "active")).toBe("base active");
expect(capabilityStatuses.completed.label).toBe("Completed");
```

- [ ] **Step 2: Confirm it fails**

Run: `npm run test -- tests/foundation-page.test.tsx`

Expected: FAIL because `@/lib/utils` and `@/lib/capability-status` do not exist.

- [ ] **Step 3: Add the minimal helpers**

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```

```ts
export const capabilityStatuses = {
  completed: { label: "Completed", className: "" },
  "in-progress": { label: "In progress", className: "" },
  planned: { label: "Planned", className: "" },
  "future-research": { label: "Future research", className: "" },
  unavailable: { label: "Unavailable", className: "" },
} as const;
export type CapabilityStatus = keyof typeof capabilityStatuses;
```

- [ ] **Step 4: Confirm it passes**

Run: `npm run test -- tests/foundation-page.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/lib apps/web/tests/foundation-page.test.tsx
git commit -m "[Fix] Restore frontend foundation helpers"
```

### Task 2: Add metadata and layout primitives

**Files:**
- Create: `apps/web/lib/navigation.ts`
- Create: `apps/web/components/layout/page-container.tsx`
- Create: `apps/web/components/layout/page-header.tsx`
- Create: `apps/web/components/layout/section.tsx`
- Create: `apps/web/components/layout/dashboard-grid.tsx`
- Create: `apps/web/components/layout/content-card.tsx`
- Create: `apps/web/tests/navigation-metadata.test.tsx`

**Interfaces:** Produces `NavigationItem`, `navigationItems`, and server-safe layout components.

- [ ] **Step 1: Write the failing metadata contract**

```tsx
expect(navigationItems.map((item) => item.href)).toEqual([
  "/", "/ask-experiment", "/experiment-explorer", "/evaluation-dashboard", "/roadmap",
]);
expect(navigationItems.every((item) => item.icon && item.description)).toBe(true);
```

- [ ] **Step 2: Confirm it fails**

Run: `npm run test -- tests/navigation-metadata.test.tsx`

Expected: FAIL because `@/lib/navigation` does not exist.

- [ ] **Step 3: Implement metadata and primitives**

```ts
export type NavigationItem = {
  href: string; label: string; description: string; icon: LucideIcon;
};
export const navigationItems: readonly NavigationItem[] = [/* five route definitions */];
```

Use `mx-auto w-full max-w-6xl px-5 sm:px-8 lg:px-10` for `PageContainer`; have `PageHeader`
render its `title` as the page `h1`, optional description, and optional actions.

- [ ] **Step 4: Confirm it passes**

Run: `npm run test -- tests/navigation-metadata.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/lib/navigation.ts apps/web/components/layout apps/web/tests/navigation-metadata.test.tsx
git commit -m "[New Feature] Add shell layout primitives"
```

### Task 3: Implement desktop and mobile navigation

**Files:**
- Create: `apps/web/components/navigation.tsx`
- Create: `apps/web/components/mobile-navigation.tsx`
- Create: `apps/web/components/application-shell.tsx`
- Create: `apps/web/tests/application-shell.test.tsx`

**Interfaces:** Produces `ApplicationShell({ children }: { children: ReactNode })`, consuming `navigationItems`.

- [ ] **Step 1: Write failing interaction tests**

```tsx
await user.click(screen.getByRole("button", { name: "Open navigation" }));
expect(screen.getByRole("dialog", { name: "Navigation" })).toBeVisible();
await user.keyboard("{Escape}");
expect(screen.getByRole("button", { name: "Open navigation" })).toHaveFocus();
expect(screen.getByRole("link", { name: "Roadmap" })).toHaveAttribute("aria-current", "page");
```

- [ ] **Step 2: Confirm it fails**

Run: `npm run test -- tests/application-shell.test.tsx`

Expected: FAIL because `ApplicationShell` does not exist.

- [ ] **Step 3: Implement the shell**

Render a labelled desktop `aside`/ `nav` at `lg` and a `main` around route children. Below
`lg`, implement a labelled control, dialog drawer, backdrop close, Escape close, focus trap, and
focus return. Use Framer Motion only for reduced-motion-safe drawer/backdrop transitions.

- [ ] **Step 4: Confirm it passes**

Run: `npm run test -- tests/application-shell.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/components/application-shell.tsx apps/web/components/navigation.tsx apps/web/components/mobile-navigation.tsx apps/web/tests/application-shell.test.tsx
git commit -m "[New Feature] Add responsive application navigation"
```

### Task 4: Compose the root layout and placeholders

**Files:**
- Modify: `apps/web/app/layout.tsx`
- Modify: `apps/web/app/page.tsx`
- Create: `apps/web/app/ask-experiment/page.tsx`
- Create: `apps/web/app/experiment-explorer/page.tsx`
- Create: `apps/web/app/evaluation-dashboard/page.tsx`
- Create: `apps/web/app/roadmap/page.tsx`
- Create: `apps/web/tests/placeholder-routes.test.tsx`
- Modify: `docs/frontend.md`

**Interfaces:** Each route consumes `PageContainer`, `PageHeader`, and `ContentCard`.

- [ ] **Step 1: Write failing route tests**

```tsx
expect(screen.getByRole("heading", { name: "Ask Experiment" })).toBeInTheDocument();
expect(screen.getByText("Coming in Issue #3")).toBeInTheDocument();
```

- [ ] **Step 2: Confirm it fails**

Run: `npm run test -- tests/placeholder-routes.test.tsx`

Expected: FAIL because the placeholder route modules do not exist.

- [ ] **Step 3: Implement placeholders**

Wrap root-layout children in `ApplicationShell`. Each route renders only a `PageHeader` title,
one-line description, and `ContentCard` notice. Replace the temporary foundation preview at
`/` with the Landing placeholder. Document the sticky-sidebar and mobile-drawer breakpoint in
`docs/frontend.md`.

- [ ] **Step 4: Confirm it passes**

Run: `npm run test -- tests/placeholder-routes.test.tsx`

Expected: PASS.

- [ ] **Step 5: Verify and commit**

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
git add apps/web/app apps/web/tests/placeholder-routes.test.tsx docs/frontend.md
git commit -m "[New Feature] Build application shell and navigation"
```

