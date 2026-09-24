---
name: "ExperimentOS AI \u2014 Evidence Atlas"
description: "An expressive analytical workspace organized around experiment evidence."
colors:
  background: "#edf2f4"
  foreground: "#173842"
  card: "#ffffff"
  card-foreground: "#173842"
  muted: "#e2eaed"
  muted-foreground: "#52676f"
  border: "#cbd9de"
  input: "#9cafb8"
  primary: "#2457d6"
  primary-foreground: "#ffffff"
  secondary: "#dce8ec"
  secondary-foreground: "#143d48"
  accent: "#e0e9ff"
  accent-foreground: "#1d43a0"
  destructive: "#b02e3d"
  destructive-foreground: "#ffffff"
  ring: "#2457d6"
  status-completed: "#197052"
  status-progress: "#875007"
  status-planned: "#2457d6"
  status-research: "#754c99"
  status-unavailable: "#596a74"
  atlas-teal: "#143d48"
  atlas-amber: "#f3a33b"
typography:
  display:
    fontFamily: "Geist, sans-serif"
    fontSize: "clamp(2.7rem, 4.6vw, 4.8rem)"
    fontWeight: 600
    lineHeight: 1.04
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Geist, sans-serif"
    fontSize: "clamp(1.9rem, 3.2vw, 2.9rem)"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Geist, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
  body:
    fontFamily: "Geist, sans-serif"
    fontSize: "1rem"
    lineHeight: 1.6
  label:
    fontFamily: "Geist, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: "1.25rem"
  reference:
    fontFamily: "Geist Mono, monospace"
    fontSize: "0.75rem"
  score:
    fontFamily: "Geist, sans-serif"
    fontSize: "2rem"
    fontWeight: 600
    lineHeight: 1.2
rounded:
  sm: "0.625rem"
  md: "0.75rem"
  lg: "0.875rem"
  panel: "16px"
  pill: "9999px"
spacing:
  2: "0.5rem"
  3: "0.75rem"
  4: "1rem"
  5: "1.25rem"
  6: "1.5rem"
  8: "2rem"
  10: "2.5rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.secondary-foreground}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.foreground}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
  question-field:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.card-foreground}"
    rounded: "{rounded.lg}"
  status-chip:
    rounded: "{rounded.pill}"
    padding: "0.125rem 0.5rem"
  navigation-active:
    backgroundColor: "{colors.atlas-amber}"
    textColor: "#193b43"
    rounded: "{rounded.md}"
  evaluation-score:
    textColor: "{colors.primary}"
    typography: "{typography.score}"
---

# Design System: ExperimentOS AI

## Overview

**Creative North Star: "Evidence Atlas"**

Evidence Atlas uses deep teal framing, cobalt section fields, a cool pale canvas, and white evidence surfaces to make analysis prominent and sources inspectable. Geist provides a readable operating interface, with enlarged, tightly set headings and aligned numerical measurements.

The system is expressive through color, hierarchy, and asymmetric evidence layouts. Fixture disclosure, uncertainty, capability status, and human decision authority remain visible alongside results.

**Key Characteristics:**
- Strong teal framing and cobalt orientation fields.
- Prominent measurements with readable source material.
- Restrained rounded containers and flat ruled evidence rows.

## Colors

The palette combines cool analytical surfaces with confident cobalt and warm amber references. Frontmatter records the implemented global primitives; scoped rail and header colors belong to their components.

### Primary
Cobalt (`primary`) marks actions, page fields, links, and prominent measurements. `accent` is its pale selected-state companion.

### Secondary
Deep teal (`atlas-teal`) anchors navigation, availability panels, and public framing. Pale blue-gray (`secondary`) groups controls and supporting evidence.

### Tertiary
Reference amber (`atlas-amber`) marks the brand and active rail item. Semantic status colors distinguish completed, in-progress, planned, research, and unavailable states; always pair them with text. Destructive red marks error feedback.

### Neutral
Cool paper (`background`), white (`card`), and pale muted surfaces separate working regions. Dark ink (`foreground`), subdued supporting ink (`muted-foreground`), and distinct border/input strokes retain readable hierarchy.

## Typography

Geist is the display and body family; Geist Mono carries source identifiers, citations, and request metadata. The interface combines compact labels with generous analytical headings. Frontmatter defines the observed roles, rather than an invented modular scale.

Display is reserved for the public product statement. Headline sets workspace page titles; title sets evidence-card headings. Body copy uses comfortable leading, while compact interface descriptions commonly use the smaller label size. Page-header descriptions stop at (65ch). Numeric cells and definition values use tabular numerals.

**The Measured Evidence Rule.** Use the enlarged evaluation score treatment only for finite numerical scores; unavailable labels retain normal text size.

## Layout

Page containers cap at (1440px), with horizontal padding of (20px), then (32px) from (640px), and (40px) from (1024px). At desktop widths the workspace uses a sticky (16rem) teal rail and a flexible content column; smaller widths use a mobile navigation header. The top bar disappears below (1024px).

The public hero pairs statement and sample evidence at (1.05fr / 1fr), stacking below (1024px). Detail columns become (1.2fr / 1fr) at (1280px). Evaluation metrics use two columns, collapsing below (640px). Preserve scrollable dense tables and wrapping controls. The body supports a (320px) minimum width. Regular container padding is (20–24px), with section gaps commonly (24–32px).

## Elevation & Depth

Depth comes primarily from tonal separation, borders, and colored section fields. Standard cards have no shadow. The public sample evidence panel alone uses a diffuse shadow (`0 18px 50px #143d4814`). Avoid extending this lift to every data region.

## Shapes

Controls use gently rounded medium corners; ordinary cards use the large radius. Prominent headers and feature panels use the panel radius. Chips are fully rounded. Evidence rows use simple top rules within their outer containers, keeping nested content visually flat.

## Components

### Buttons
Primary cobalt, blue-gray secondary, and transparent outlined variants share compact label typography, medium corners, (12px / 8px) horizontal/vertical padding, and minimum (44px) width and height. Hover changes color; keyboard focus receives a visible ring with offset. Disabled buttons suppress pointer interaction and reduce opacity. Cobalt page headers invert primary actions to white with cobalt text.

### Inputs / Fields
The question textarea uses the canvas background, a distinct input stroke, medium corners, (12px / 8px) padding, and a visible cobalt focus ring. It resizes vertically. Error feedback uses destructive text and accessible invalid/description relationships; disabled fields reduce opacity.

### Chips
Status chips combine a semantic text color, a faint tinted fill, and a low-opacity border. Labels remain explicit so meaning does not depend on hue.

### Cards / Containers
White bordered cards hold primary evidence, usually with (20px) padding and (24px) from the small breakpoint. Pale blue metric panels emphasize recorded values. Citations and expandable retrieved excerpts are ruled rows inside outer cards, without an additional card around each row.

### Navigation
The teal rail uses pale labels, generous rows, amber active fill, and matching amber focus treatment. Active destinations expose `aria-current`. Mobile navigation replaces the desktop rail; retain its keyboard and disclosure behavior.

### Evidence and measurements
Selected sample questions use pale cobalt fill, cobalt stroke, and an explicit pressed state. Actual evaluation scores use `.atlas-score`; missing values retain normal-sized text. Tables use pale headers, alternate rows, hover tint, and aligned measurements. The answer arrival animation fades a pale cobalt background to white over (700ms); reduced-motion preferences reduce animation and transition duration to (0.01ms).

## Do's and Don'ts

### Do:
- Do retain fixture disclosures, source links, and uncertainty beside the evidence they qualify.
- Do use tabular numerals for measurements and Geist Mono for identifiers and references.
- Do preserve visible selected, focus, disabled, and unavailable states.
- Do keep citations and retrieved context as flat ruled rows inside their outer cards.

### Don't:
- Don't apply the enlarged evaluation score style to unavailable text.
- Don't turn execution status into a claim of quality or rollout approval.
- Don't add decorative raster imagery as a substitute for actual evidence.
