# Chronicle Accessibility Compliance Statement

**Software State:** Main release documentation refresh, March 21, 2026  
**Target Standards:** WCAG 2.2 (Level AA), US Section 508, AS EN 301 549

> Development note: Chronicle was built using AI-assisted ("vibe-coded") workflows, with final integration, review, and testing directed by the author.

## Overview

Chronicle is engineered as an accessibility-first application and output generator. Its accessibility story has two parts:

- accessible operational workflows in the GUI
- accessible generated outputs for downstream reading in browsers, Word, EPUB readers, and assistive technologies

Chronicle is intended to be workable with Apple VoiceOver, NVDA, and JAWS, while recognizing that real-host screen-reader validation remains necessary before declaring a specific build release-ready.

## GUI Accessibility Principles

Chronicle's GUI currently emphasizes:

- native picker-based multi-choice controls for consistent screen-reader announcement
- queue-first workflow so users do not have to manually highlight files just to include them in a run
- explicit accessible names on key controls and dialogs
- reduced-noise status messaging designed to avoid constant interruption
- keyboard-accessible menu commands for Preferences, API keys, device import actions, and saved logs
- exportable processing logs for offline review and QA

Current menu-level accessibility-relevant actions include:

- `Preferences...`
- `API Keys...`
- `Find Connected Devices...`
- `Scan via NAPS2...`
- `Save Processing Log...`
- `Open User Guide`
- `About Build...`

## WCAG-Oriented Output Enforcement

Chronicle's output pipeline is designed to preserve machine-readable structure for assistive technology.

### 1.1.1 Non-text Content

Meaningful visual elements can be converted into descriptive text alternatives. When image descriptions are disabled, Chronicle suppresses assistive clutter rather than inventing decorative noise.

### 1.3.1 Info and Relationships

Chronicle preserves headings, tables, labels, and relationships as programmatic structure rather than purely visual styling.

Examples include:

- hierarchical heading output
- scoped table headers
- list preservation where possible
- structured metadata and attribution handling

### 2.4.1 Bypass Blocks

Chronicle supports accessible document navigation through semantic structure and, for HTML outputs, internal navigation patterns such as a generated table of contents where appropriate.

### 2.4.2 Page Titled

Generated HTML outputs include a document title derived from the source context to improve orientation for assistive users.

### 3.1.1 Language of Page

Chronicle detects output language and applies language metadata to HTML output.

### 3.1.2 Language of Parts

Where mixed-language content is preserved, Chronicle can emit inline language tagging to improve pronunciation behavior in screen readers.

## Accessibility-Relevant Output Behaviors

Chronicle's accessible output strategy includes:

- semantic HTML with `lang` and `dir`
- heading hierarchy preservation
- malformed-source recovery into cleaner heading/list/table structure when that can be done faithfully
- structured citations and source attribution where supported
- table scoping for accessible cell navigation
- support for HTML as the preferred screen-reader-first output format
- edit-friendly DOCX output for review workflows, including heading/list/table mapping and major page-break boundaries
- plain-text and Markdown options for simpler downstream tooling

## Document-Class Accessibility Support

Chronicle includes profile-specific behavior to preserve structure important for accessibility.

Examples:

- office docs/reports: heading recovery, list repair, table cleanup, and Word-friendly section structure
- government/public records: repeated-header suppression, appendix structure, and numbered-section fidelity
- archival material: letters, ledgers, docket marks, and sign-off structures
- military records: chronology, routing, abbreviations, and strikethrough recovery
- newspapers: column flattening, metadata recovery, and article boundary preservation
- books/novels: chapter continuity, paragraph flow across page turns, and front/back matter separation
- manuals/forms: checkbox semantics, form-state flattening, and instructional reading order
- academic content: equations, notes, annotations, and multi-column flattening
- legal documents: clause hierarchy and defined-term fidelity
- museum labels: caption-object linkage and provenance metadata

## Diagnostic and QA Controls

Chronicle includes several controls that support accessible QA workflows:

- processing log save/export
- PDF text-layer omission audit
- page confidence scoring
- low-memory mode for constrained devices
- merge cleanup that removes synthetic filename headings from seamless output

## Windows NVDA and JAWS Validation Expectations

Before a Windows build is considered release-ready, the following should be checked on a real Windows host:

- app launch and focus landing
- menu navigation by keyboard
- queue traversal and row/state announcement
- Preferences dialog traversal
- API Keys dialog traversal and masked/unmasked field clarity
- processing log readability and save flow
- connected-device lookup messages
- NAPS2 import dialog workflow
- HTML output review with heading, landmark, and table navigation

## Limits and Responsibilities

Accessibility intent does not remove the need for human review.

Users should still verify:

- transcription accuracy
- legal or evidentiary adequacy
- suitability of a chosen output format for the final audience
- compatibility with their specific assistive-technology/browser/editor combination

## Current Documentation Position

This statement reflects Chronicle's intended accessibility design and documented operational controls as of March 21, 2026. It should be read together with:

- `docs/user/chronicle_help.html`
- `docs/user/README.md`
- `docs/user/SYSTEM_REQUIREMENTS.md`
- `docs/policies/DISCLAIMER.md`
