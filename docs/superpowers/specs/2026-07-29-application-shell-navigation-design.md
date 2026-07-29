# Application Shell and Navigation Design

## Goal

Create the shared, accessible ExperimentOS AI workspace shell for Issue #115 without adding any
page-specific product functionality or backend integration.

## Architecture

The root App Router layout remains server-rendered and renders an `ApplicationShell` around every
route. Navigation metadata lives in one typed module and is consumed by desktop and mobile
navigation components. Client-side code is limited to a route-aware navigation list and the mobile
drawer interaction; route pages and layout primitives remain Server Components by default.

The implementation restores the two missing Issue #1 support modules, `lib/utils.ts` and
`lib/capability-status.ts`, unchanged in responsibility: class-name composition and honest
capability status presentation. This is a prerequisite repair, not a new product capability.

## Navigation Pattern

Use a persistent, sticky sidebar on viewports at or above the `lg` breakpoint. It contains the
ExperimentOS AI wordmark, concise product description, five primary routes, and the GitHub and
demo actions required by the issue. The sidebar is selected over a top navigation because the five
peer-level product areas form a workspace information architecture that will expand naturally.

Below `lg`, navigation is exposed through a labelled menu button in the shared header. Opening it
shows a left drawer over a backdrop. The drawer closes when a navigation link is selected, the
backdrop is activated, or Escape is pressed. Escape returns focus to the triggering menu button;
focus remains within the drawer while it is open. Motion is limited to a short opacity and
translation transition that respects reduced-motion preferences.

## Component Boundaries

- `lib/navigation.ts`: typed central metadata for route, label, icon, and description; future pages
  are added here only.
- `components/application-shell.tsx`: server composition for desktop shell, main landmark, and
  mobile header.
- `components/navigation.tsx`: client navigation list that derives visual and `aria-current` state
  from `usePathname`.
- `components/mobile-navigation.tsx`: client disclosure/drawer with focus management and close
  behavior.
- `components/layout/*`: server-safe `PageContainer`, `Section`, `PageHeader`, `DashboardGrid`,
  and `ContentCard` primitives, built on Issue #1 tokens and UI primitives.
- `app/*/page.tsx`: server-rendered placeholder pages only.

## Routes and Content Boundaries

The shell will expose Landing (`/`), Ask Experiment, Experiment Explorer, Evaluation Dashboard,
and Roadmap. Each route renders a single heading, one-line description, and a `Coming in Issue #X`
notice. No RAG interface, experiment data, charts, timelines, API calls, mocks, loading states,
authentication, or search belongs to this issue.

## Visual System

Use the existing dark-first semantic tokens, Geist typography, border treatment, radius scale, and
existing Button/Card/Separator primitives. The desktop sidebar has a consistent readable width;
main content uses one responsive maximum width and shared horizontal padding. Active navigation is
distinguished by contrast and a subtle token-backed background, rather than decorative motion.

## Accessibility

Use `aside` and labelled `nav` elements for navigation, `main` for route content, and exactly one
page-level `h1` from each `PageHeader`. Each icon is decorative when adjacent text supplies the
label. The mobile trigger has an accessible name and accurate expanded state. Links retain visible
keyboard focus, the active route exposes `aria-current="page"`, and touch controls meet a
comfortable minimum target size.

## Verification

Add focused Vitest + Testing Library tests for centralized metadata rendering, active-route state,
keyboard drawer open/close, Escape behavior, focus return, and deterministic narrow/desktop
viewport behavior. Run `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run build`
from `apps/web` after installation from the existing lockfile. No backend files are changed.
