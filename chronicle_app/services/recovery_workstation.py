import html
import json
import os
import re
import time

from chronicle_app.services.output_quality import analyze_output_quality


CAPABILITY_REGISTRY = [
    ("review_workbench", "Review Workbench", "accessible post-run review surface"),
    ("extraction_receipts", "Extraction Receipts", "transparent per-output provenance report"),
    ("triage_before_run", "Triage Before Run", "pre-run document classification and route planning"),
    ("corpus_projects", "Corpus Projects", "collection-level settings and status manifests"),
    ("profile_composer", "Profile Composer", "saved profile variants built from Chronicle presets"),
    ("error_recovery_center", "Error Recovery Center", "retry and recovery action recommendations"),
    ("accessible_output_qa", "Accessible Output QA", "deterministic accessibility and leakage checks"),
    ("sensitive_document_mode", "Sensitive Document Mode", "privacy-first run posture"),
    ("domain_packs", "Domain Packs", "domain glossary and preset bundles"),
    ("source_aware_newspapers", "Source-Aware Newspaper Tools", "newspaper citation and article structure helpers"),
    ("book_reconstruction", "Book Reconstruction Mode", "long-form reading-copy reconstruction planning"),
    ("confidence_heatmap", "Confidence Heatmap", "page and warning index for review"),
    ("batch_economics", "Batch Economics", "effort, provider, and quota-risk estimation"),
    ("export_personas", "A11y-First Export Templates", "output intent labels and guidance"),
    ("maintainability_roadmap", "Maintainability Roadmap", "next service-extraction priorities"),
]


SENSITIVE_PROFILES = {"forms", "legal", "medical", "office", "government", "tabular"}
HARD_VISUAL_PROFILES = {
    "academic",
    "archival",
    "book",
    "comic",
    "handwritten",
    "magazine",
    "medical",
    "military",
    "modern_newspaper",
    "newspaper",
}


def _now_stamp(time_module=time):
    return time_module.strftime("%Y-%m-%d %H:%M:%S")


def _sidecar_path(output_path, suffix):
    root, _ext = os.path.splitext(output_path)
    return f"{root}{suffix}"


def _read_output_excerpt(path, *, max_chars=5000):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(max_chars)
    except Exception:
        return ""


def _strip_tags(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def _write_text(path, content):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content.rstrip() + "\n")
    return path


def classify_triage(path, job_cfg, *, ext=None, total_units=0, routing=None):
    profile = str((job_cfg or {}).get("doc_profile") or "standard").lower()
    ext = (ext or os.path.splitext(path or "")[1]).lower()
    routing = routing or {}
    signals = []
    recommendations = []
    if ext == ".pdf":
        signals.append("PDF input")
    elif ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}:
        signals.append("image scan input")
    else:
        signals.append("source-text or office input")
    if profile in HARD_VISUAL_PROFILES:
        signals.append(f"{profile} profile is visually or structurally demanding")
    if profile in SENSITIVE_PROFILES:
        recommendations.append("Consider Sensitive Document Mode when privacy matters.")
    if total_units and total_units >= 50:
        signals.append("large batch or long document")
        recommendations.append("Run a first-pages trial before committing provider quota.")
    if str((job_cfg or {}).get("model_override") or "").strip():
        signals.append("manual engine override")
    difficulty = str(routing.get("difficulty") or "")
    if difficulty:
        signals.append(f"automatic routing difficulty: {difficulty}")
    if not recommendations:
        recommendations.append("Use the selected preset and review the receipt after extraction.")
    return {
        "profile": profile,
        "extension": ext,
        "signals": signals,
        "recommendations": recommendations,
    }


def build_batch_economics(job_cfg, *, selected_model="", total_units=0, file_size_mb=None):
    total_units = max(0, int(total_units or 0))
    model = str(selected_model or (job_cfg or {}).get("model_name") or "automatic")
    provider = "offline" if "offline" in model.lower() or "ollama" in model.lower() else model.split("-", 1)[0]
    if total_units >= 120:
        effort = "very long"
    elif total_units >= 40:
        effort = "long"
    elif total_units >= 10:
        effort = "moderate"
    else:
        effort = "short"
    quota_risk = "high" if provider.startswith("gemini") and total_units >= 40 else "normal"
    if file_size_mb and file_size_mb > 100:
        quota_risk = "elevated"
    return {
        "provider": provider,
        "selected_model": model,
        "estimated_units": total_units,
        "effort": effort,
        "quota_risk": quota_risk,
    }


def build_profile_variant(name, base_profile, overrides=None):
    return {
        "name": str(name or "Custom Chronicle Profile").strip(),
        "base_profile": str(base_profile or "standard").strip().lower(),
        "overrides": dict(overrides or {}),
        "accessibility_contract": "Preserve semantic headings, readable order, table scopes, language metadata, and reviewable uncertainty markers.",
    }


def build_corpus_project_manifest(name, *, output_dir="", profile_variant=None, queue_rows=None):
    rows = queue_rows or []
    return {
        "project_name": str(name or "Chronicle Corpus Project").strip(),
        "output_dir": output_dir,
        "profile_variant": profile_variant or build_profile_variant("", "standard"),
        "rows": [
            {
                "path": row.get("path", ""),
                "status": row.get("status", "Queued"),
                "settings": row.get("settings", {}),
            }
            for row in rows
            if isinstance(row, dict)
        ],
    }


def recommend_recovery_actions(status, *, output_path="", warnings=None):
    warnings = list(warnings or [])
    actions = []
    lowered = str(status or "").lower()
    if "error" in lowered or "failed" in lowered:
        actions.append("Retry only the failed item with the same preset.")
        actions.append("Run preflight and consider a deeper engine for weak scans.")
    if warnings:
        actions.append("Open the review workbench and inspect flagged output sections.")
    if output_path:
        actions.append(f"Compare a rerun against {os.path.basename(output_path)} before replacing reviewed work.")
    if not actions:
        actions.append("No recovery action is needed.")
    return actions


def recommend_sensitive_mode(job_cfg):
    profile = str((job_cfg or {}).get("doc_profile") or "standard").lower()
    enabled = profile in SENSITIVE_PROFILES
    return {
        "recommended": enabled,
        "reason": (
            "This preset often contains private personal, medical, legal, financial, or organizational data."
            if enabled
            else "This preset is not automatically treated as sensitive, but users can still choose Private Offline Mode."
        ),
        "default_posture": "Prefer local/offline processing, redacted logs, conservative formats, and human verification." if enabled else "Use normal Chronicle privacy guidance.",
    }


def domain_pack_for_profile(profile):
    profile = str(profile or "standard").lower()
    packs = {
        "medical": ["medical abbreviations", "lab table preservation", "form-field markers"],
        "military": ["military abbreviations", "war diary structure", "unit/date handling"],
        "newspaper": ["masthead/citation recovery", "article segmentation", "advert/caption labeling"],
        "modern_newspaper": ["masthead/citation recovery", "article segmentation", "advert/caption labeling"],
        "legal": ["statutory heading repair", "clause numbering", "citation preservation"],
        "book": ["chapter reconstruction", "running-head cleanup", "paragraph continuity"],
        "comic": ["panel order", "balloon reading order", "visual description policy"],
    }
    return {"profile": profile, "pack_items": packs.get(profile, ["general accessibility cleanup", "document structure recovery"])}


def build_newspaper_toolkit(profile):
    enabled = str(profile or "").lower() in {"newspaper", "modern_newspaper", "magazine"}
    return {
        "enabled": enabled,
        "tools": [
            "Recover publication/title/date/source citation.",
            "Separate article text, captions, advertisements, and page furniture.",
            "Offer reading-edition and research-edition export intents.",
        ]
        if enabled
        else [],
    }


def build_book_reconstruction_plan(profile):
    enabled = str(profile or "").lower() == "book"
    return {
        "enabled": enabled,
        "steps": [
            "Detect front matter, chapters, and back matter.",
            "Remove running heads while preserving source-page references when requested.",
            "Repair paragraph continuity and dialogue punctuation conservatively.",
            "Export reviewable EPUB/DOCX reading copies.",
        ]
        if enabled
        else [],
    }


def build_confidence_heatmap(qa_report, *, total_units=0):
    warnings = list((qa_report or {}).get("warnings") or [])
    units = max(0, int(total_units or 0))
    if not warnings:
        return {"summary": "No output QA warnings.", "review_points": []}
    review_points = []
    for idx, warning in enumerate(warnings, start=1):
        unit_hint = min(units, idx) if units else idx
        review_points.append({"label": f"Review point {idx}", "unit_hint": unit_hint, "warning": warning})
    return {"summary": f"{len(review_points)} review point(s) need attention.", "review_points": review_points}


def export_persona_for_format(fmt, *, doc_profile="standard"):
    fmt = str(fmt or "").lower()
    if fmt == "html":
        intent = "Screen-reader review HTML"
    elif fmt == "docx":
        intent = "Word remediation draft"
    elif fmt == "epub":
        intent = "Accessible reading copy"
    elif fmt in {"csv", "json"}:
        intent = "Structured data review"
    else:
        intent = "Plain review transcript"
    return {
        "format": fmt,
        "intent": intent,
        "guidance": f"Use for {doc_profile} review; preserve Chronicle's uncertainty markers until human verification is complete.",
    }


def maintainability_roadmap():
    return [
        "Extract legal HTML cleanup from chronicle_core.py as a cohesive service.",
        "Extract provider/upload orchestration from pdf_processor.py.",
        "Keep Review Workbench and receipts in service modules so the GUI remains thin.",
    ]


def build_workstation_plan(*, path="", output_path="", job_cfg=None, fmt="", selected_model="", total_units=0, routing=None, qa_report=None):
    job_cfg = job_cfg or {}
    profile = str(job_cfg.get("doc_profile") or "standard").lower()
    return {
        "capabilities": CAPABILITY_REGISTRY,
        "triage": classify_triage(path, job_cfg, ext=os.path.splitext(path or "")[1], total_units=total_units, routing=routing),
        "economics": build_batch_economics(job_cfg, selected_model=selected_model, total_units=total_units),
        "profile_variant": build_profile_variant(f"{profile.title()} Review", profile, job_cfg),
        "recovery_actions": recommend_recovery_actions("Done", output_path=output_path, warnings=(qa_report or {}).get("warnings")),
        "sensitive_mode": recommend_sensitive_mode(job_cfg),
        "domain_pack": domain_pack_for_profile(profile),
        "newspaper_tools": build_newspaper_toolkit(profile),
        "book_reconstruction": build_book_reconstruction_plan(profile),
        "confidence_heatmap": build_confidence_heatmap(qa_report, total_units=total_units),
        "export_persona": export_persona_for_format(fmt, doc_profile=profile),
        "maintainability": maintainability_roadmap(),
    }


def format_workstation_plan_text(plan):
    plan = plan or {}
    lines = [
        "Recovery Workbench Plan",
        "",
        "Priority 1: Review Workbench and Extraction Receipts are enabled after successful single-output extractions.",
        "",
        "Triage signals:",
    ]
    lines.extend(f"- {item}" for item in plan.get("triage", {}).get("signals", []))
    lines.extend(["", "Recommendations:"])
    lines.extend(f"- {item}" for item in plan.get("triage", {}).get("recommendations", []))
    economics = plan.get("economics", {})
    lines.extend(
        [
            "",
            "Batch economics:",
            f"- Engine: {economics.get('selected_model', '')}",
            f"- Estimated units: {economics.get('estimated_units', 0)}",
            f"- Effort: {economics.get('effort', '')}",
            f"- Quota risk: {economics.get('quota_risk', '')}",
            "",
            "Sensitive document mode:",
            f"- Recommended: {'yes' if plan.get('sensitive_mode', {}).get('recommended') else 'no'}",
            f"- {plan.get('sensitive_mode', {}).get('reason', '')}",
            "",
            "Domain pack:",
        ]
    )
    lines.extend(f"- {item}" for item in plan.get("domain_pack", {}).get("pack_items", []))
    export_persona = plan.get("export_persona", {})
    lines.extend(
        [
            "",
            "Export persona:",
            f"- {export_persona.get('intent', '')}",
            f"- {export_persona.get('guidance', '')}",
            "",
            "Implemented capability areas:",
        ]
    )
    lines.extend(f"- {label}: {purpose}" for _key, label, purpose in plan.get("capabilities", []))
    return "\n".join(lines)


def build_extraction_receipt_text(receipt):
    lines = [
        "# Chronicle Extraction Receipt",
        "",
        f"Generated: {receipt.get('generated_at', '')}",
        f"Source: {receipt.get('source_name', '')}",
        f"Output: {receipt.get('output_name', '')}",
        f"Format: {str(receipt.get('format', '')).upper()}",
        f"Preset: {receipt.get('doc_profile', 'standard')}",
        f"Engine: {receipt.get('engine_label', '')}",
        f"Work units: {receipt.get('total_units', 0)}",
        "",
        "## Accessibility Review",
        "",
        receipt.get("qa_summary", "Output QA unavailable."),
        "",
        "## Review Workbench",
        "",
        f"Workbench: {receipt.get('review_workbench_name', '')}",
        "",
        "## Triage",
        "",
    ]
    for signal in receipt.get("plan", {}).get("triage", {}).get("signals", []):
        lines.append(f"- {signal}")
    lines.extend(["", "## Recommendations", ""])
    for recommendation in receipt.get("plan", {}).get("triage", {}).get("recommendations", []):
        lines.append(f"- {recommendation}")
    lines.extend(["", "## Batch Economics", ""])
    economics = receipt.get("plan", {}).get("economics", {})
    for key in ("provider", "selected_model", "estimated_units", "effort", "quota_risk"):
        lines.append(f"- {key.replace('_', ' ').title()}: {economics.get(key, '')}")
    lines.extend(["", "## Future Workstation Capabilities", ""])
    for _key, label, purpose in CAPABILITY_REGISTRY:
        lines.append(f"- {label}: {purpose}")
    return "\n".join(lines)


def build_review_workbench_html(receipt):
    qa = receipt.get("qa_report") or {}
    plan = receipt.get("plan") or {}
    review_points = plan.get("confidence_heatmap", {}).get("review_points", [])
    warnings = qa.get("warnings") or []
    warning_items = "\n".join(f"<li>{html.escape(str(item))}</li>" for item in warnings) or "<li>No warnings.</li>"
    review_items = "\n".join(
        f"<li><strong>{html.escape(point['label'])}</strong>: {html.escape(point['warning'])}</li>"
        for point in review_points
    ) or "<li>No review points were generated.</li>"
    capability_items = "\n".join(
        f"<li><strong>{html.escape(label)}</strong>: {html.escape(purpose)}</li>"
        for _key, label, purpose in CAPABILITY_REGISTRY
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Chronicle Review Workbench</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; line-height: 1.55; margin: 0; color: #111; background: #fff; }}
    header, main, footer {{ max-width: 78rem; margin: 0 auto; padding: 1rem; }}
    nav ul {{ display: flex; flex-wrap: wrap; gap: .75rem; padding-left: 1rem; }}
    section {{ border-top: 1px solid #777; padding-top: 1rem; margin-top: 1rem; }}
    pre {{ white-space: pre-wrap; border: 1px solid #777; padding: 1rem; overflow-wrap: anywhere; }}
    .skip-link {{ position: absolute; left: .5rem; top: .5rem; background: #fff; padding: .5rem; }}
    .meta dt {{ font-weight: 700; }}
    .meta dd {{ margin: 0 0 .5rem 0; }}
  </style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to review content</a>
  <header role="banner">
    <h1>Chronicle Review Workbench</h1>
    <p>{html.escape(receipt.get('qa_summary', 'Output QA unavailable.'))}</p>
    <nav aria-label="Review sections">
      <ul>
        <li><a href="#receipt">Receipt</a></li>
        <li><a href="#warnings">Warnings</a></li>
        <li><a href="#review-points">Review Points</a></li>
        <li><a href="#privacy">Privacy</a></li>
        <li><a href="#capabilities">Capabilities</a></li>
      </ul>
    </nav>
  </header>
  <main id="main" role="main">
    <section id="receipt" aria-labelledby="receipt-heading">
      <h2 id="receipt-heading">Extraction Receipt</h2>
      <dl class="meta">
        <dt>Source</dt><dd>{html.escape(receipt.get('source_name', ''))}</dd>
        <dt>Output</dt><dd>{html.escape(receipt.get('output_name', ''))}</dd>
        <dt>Preset</dt><dd>{html.escape(receipt.get('doc_profile', 'standard'))}</dd>
        <dt>Engine</dt><dd>{html.escape(receipt.get('engine_label', ''))}</dd>
        <dt>Format</dt><dd>{html.escape(str(receipt.get('format', '')).upper())}</dd>
      </dl>
    </section>
    <section id="warnings" aria-labelledby="warnings-heading">
      <h2 id="warnings-heading">Accessibility QA Warnings</h2>
      <ul>{warning_items}</ul>
    </section>
    <section id="review-points" aria-labelledby="review-points-heading">
      <h2 id="review-points-heading">Review Points</h2>
      <ul>{review_items}</ul>
    </section>
    <section id="privacy" aria-labelledby="privacy-heading">
      <h2 id="privacy-heading">Privacy</h2>
      <p>This workbench does not copy extracted document text. Review the saved Chronicle output file directly when content inspection is needed.</p>
    </section>
    <section id="capabilities" aria-labelledby="capabilities-heading">
      <h2 id="capabilities-heading">Recovery Workstation Capabilities</h2>
      <ul>{capability_items}</ul>
    </section>
  </main>
  <footer role="contentinfo">
    <p>Human review remains required for final legal, medical, financial, academic, and public accessibility sign-off.</p>
  </footer>
</body>
</html>"""


def write_recovery_workstation_artifacts(
    *,
    source_path,
    output_path,
    fmt,
    job_cfg,
    file_name="",
    engine_label="",
    total_units=0,
    routing=None,
    time_module=time,
):
    if not output_path:
        return {}
    output_sample = _read_output_excerpt(output_path)
    qa_report = analyze_output_quality(output_sample, fmt=fmt, doc_profile=(job_cfg or {}).get("doc_profile", "standard"))
    plan = build_workstation_plan(
        path=source_path,
        output_path=output_path,
        job_cfg=job_cfg,
        fmt=fmt,
        selected_model=engine_label or (job_cfg or {}).get("model_name", ""),
        total_units=total_units,
        routing=routing,
        qa_report=qa_report,
    )
    receipt_path = _sidecar_path(output_path, ".chronicle_receipt.md")
    workbench_path = _sidecar_path(output_path, ".chronicle_review.html")
    json_path = _sidecar_path(output_path, ".chronicle_receipt.json")
    receipt = {
        "generated_at": _now_stamp(time_module),
        "source_name": os.path.basename(source_path or ""),
        "output_name": os.path.basename(output_path or ""),
        "file_name": file_name or os.path.basename(source_path or output_path),
        "format": fmt,
        "doc_profile": (job_cfg or {}).get("doc_profile", "standard"),
        "engine_label": engine_label or (job_cfg or {}).get("model_name", ""),
        "total_units": int(total_units or 0),
        "qa_summary": qa_report.get("summary", "Output QA unavailable."),
        "qa_report": qa_report,
        "plan": plan,
        "review_workbench_path": workbench_path,
        "review_workbench_name": os.path.basename(workbench_path),
    }
    _write_text(workbench_path, build_review_workbench_html(receipt))
    _write_text(receipt_path, build_extraction_receipt_text(receipt))
    _write_text(json_path, json.dumps(receipt, indent=2, sort_keys=True))
    return {
        "receipt_path": receipt_path,
        "review_workbench_path": workbench_path,
        "json_path": json_path,
        "qa_report": qa_report,
        "plan": plan,
    }
