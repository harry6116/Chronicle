# Chronicle Accessibility Compliance Statement

**Software Version:** 1.8.0  
**Target Standards:** WCAG 2.2 (Level AA), US Section 508, AS EN 301 549  

## Overview
Chronicle is engineered from the ground up as an accessibility-first application. Unlike standard generative AI wrappers, Chronicle's extraction engine explicitly enforces programmatic semantics to ensure that all generated outputs are natively compatible with assistive technologies, including Apple VoiceOver, NVDA, and JAWS.

## WCAG 2.2 Semantic Enforcement
The Chronicle engine algorithmically enforces the following Web Content Accessibility Guidelines (WCAG) 2.2 criteria across all HTML and EPUB outputs:

* **1.1.1 Non-text Content:** Visual elements (photographs, diagrams) are automatically translated into highly descriptive, equivalent text alternatives. If the user toggles visual descriptions off, the engine generates null attributes (`alt=""`) to prevent screen reader clutter.
* **1.3.1 Info and Relationships:** The engine strictly maps document structures to hierarchical heading tags (H1, H2, H3). Visual formatting (e.g., bold text) is never used to simulate structural meaning. All extracted tabular data is formatted with strict `<th>`, `scope="col"`, and `scope="row"` associations to ensure screen reader table navigation is preserved.
* **2.4.1 Bypass Blocks (Auto-Linking TOC):** To facilitate rapid navigation of massive documents, Chronicle automatically generates an internal Table of Contents using standard HTML anchor tags, allowing screen reader users to jump instantly to specific document sections.
* **2.4.2 Page Titled:** All generated files inject dynamic, highly specific `<title>` tags based on the original filename, ensuring immediate orientational context upon opening.
* **3.1.1 Language of Page:** The extraction engine dynamically detects the primary language of the historical document and injects the corresponding ISO code into the `<html lang="x">` attribute.
* **3.1.2 Language of Parts (Cultural Preservation):** When processing bilingual or cultural documents, the engine utilizes strict language span tags (e.g., `<span lang="mi">` for te reo Māori). This ensures that screen readers dynamically switch pronunciation profiles for individual indigenous or ancient words embedded within English sentences, correctly voicing critical diacritical marks such as macrons.

## Academic, Mathematical & Epigraphic Accessibility
Chronicle includes a specialized Academic Engine designed to parse highly complex visual academic formats:
* **Mathematical & Chemical Formatting:** Visual formulas are reconstructed into structured LaTeX/MathML, allowing screen readers to voice complex equations correctly.
* **Footnote Anchoring:** Footnotes are automatically relocated and logically anchored to a dedicated section at the end of the document to prevent disruption of the primary reading flow.
* **Ancient Scripts & Hieroglyphs:** The engine is programmed to extract and preserve ancient scripts (e.g., Egyptian Hieroglyphs, Classical Chinese, Sanskrit), providing the original Unicode characters alongside structured transliterations and English translations.
* **Multi-Column Layouts:** Dense, multi-column academic layouts are strictly flattened into continuous narrative sequences.

## Data Integrity & Anti-Hallucination Directives
Chronicle adheres to a strict "Zero-Guessing" policy to maintain archival fidelity. When processing degraded physical media (e.g., microfilm, microfiche, or damaged projector slides), the engine utilizes algorithmic Lanczos resampling to magnify the text non-destructively. If the text remains illegible, the AI is explicitly forbidden from hallucinating or guessing words, and will systematically output `[Illegible Micro-text: approximately X words]`. 

## Braille Ready Format (BRF) Architecture
Chronicle's extraction pipeline is architected to support direct-to-Braille translation. By utilizing the global open-source Liblouis library, Chronicle's highly semantic text outputs can be mapped directly to strict BRF structural grids (40 cells per line, 25 lines per page). The system supports dynamic translation tables, allowing users to output in Unified English Braille (UEB) Grade 1 or Grade 2, alongside hundreds of international and language-specific Braille standards.