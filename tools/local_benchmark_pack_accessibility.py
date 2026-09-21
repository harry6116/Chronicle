#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import re
import sys
import time
from typing import Any
from dataclasses import dataclass, asdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from chronicle_app.config import PROFILE_PRESETS

def resolve_default_pack_dir() -> Path:
    env_value = os.environ.get("CHRONICLE_BENCHMARK_PACK_DIR")
    if env_value:
        return Path(env_value).expanduser()

    candidates = [
        BASE_DIR.parent / "Chronicle Benchmarks" / "Chronicle Benchmark Pack",
        BASE_DIR / "Chronicle Benchmark Pack",
        BASE_DIR.parent / "Chronicle Benchmark Pack",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DEFAULT_PACK_DIR = resolve_default_pack_dir()
BENCHMARK_ROOT = BASE_DIR / "artifacts" / "benchmarks" / "pack"
DEFAULT_OUTPUT_ROOT = BENCHMARK_ROOT / "benchmark_pack_outputs"
DEFAULT_REPORT_PATH = BENCHMARK_ROOT / "benchmark_pack_report.json"
STREAMABLE = {"html", "txt", "md"}
NEGATIVE_CHECK_KEYS = (
    "has_nested_doctype",
    "has_nested_html_tag",
    "has_fence_wrappers",
    "has_synthetic_page_filename_heading",
    "has_leading_content_before_doctype",
)
PROFILE_SCORE_WEIGHTS = {
    "newspaper": {
        "has_lang_dir_root": 10,
        "has_main_landmark": 10,
        "has_page_header_cite": 20,
        "has_source_footer_cite": 20,
        "has_h1": 10,
        "has_h2": 10,
        "has_image_description": 10,
        "no_structural_regressions": 10,
    },
    "manual": {
        "has_lang_dir_root": 15,
        "has_main_landmark": 15,
        "has_h1": 15,
        "has_h2": 10,
        "has_checkbox_markup": 15,
        "has_radio_markup": 15,
        "has_text_field_markup": 5,
        "no_structural_regressions": 10,
    },
    "military": {
        "has_lang_dir_root": 15,
        "has_main_landmark": 15,
        "has_h1": 15,
        "has_h2": 10,
        "has_strikethrough_recovery": 15,
        "no_structural_regressions": 30,
    },
    "archival": {
        "has_lang_dir_root": 15,
        "has_main_landmark": 15,
        "has_h1": 15,
        "has_h2": 10,
        "has_image_description": 10,
        "no_structural_regressions": 35,
    },
    "comic": {
        "has_lang_dir_root": 10,
        "has_main_landmark": 10,
        "has_h1": 10,
        "has_h2": 10,
        "has_panel_heading": 15,
        "has_image_description": 15,
        "no_empty_panel_sections": 15,
        "no_bare_image_description_lines": 5,
        "no_structural_regressions": 10,
    },
}
CHECK_LABELS = {
    "has_lang_dir_root": "HTML root has language and direction metadata",
    "has_main_landmark": "Output has a main landmark",
    "has_page_header_cite": "Publication/page metadata is wrapped in <header><cite>",
    "has_source_footer_cite": "Source attribution is wrapped in <footer><cite>",
    "has_h1": "Primary heading is present",
    "has_h2": "Secondary heading structure is present",
    "has_image_description": "Image descriptions are preserved when relevant",
    "has_strikethrough_recovery": "Struck-through text recovery is present when relevant",
    "has_checkbox_markup": "Checkbox semantics are preserved",
    "has_radio_markup": "Radio button semantics are preserved",
    "has_text_field_markup": "Text field semantics are preserved",
    "has_panel_heading": "Panel headings are present",
    "no_empty_panel_sections": "Panel sections are not empty",
    "no_bare_image_description_lines": "Image descriptions are wrapped in semantic elements",
    "no_structural_regressions": "No structural wrapper/fence/filename regressions detected",
}


def image_description_applicable(checks: dict) -> bool:
    return bool(checks.get("has_visual_elements"))


def strikethrough_recovery_applicable(checks: dict) -> bool:
    return bool(checks.get("has_strikethrough_recovery"))


def manual_form_semantics_applicable(checks: dict) -> bool:
    return bool(
        checks.get("has_checkbox_markup")
        or checks.get("has_radio_markup")
        or checks.get("has_text_field_markup")
    )


@dataclass(frozen=True)
class Case:
    key: str
    relative_path: str
    profile: str
    model: str
    format_type: str = "html"
    notes: str = ""


CASES = [
    Case(
        key="handwritten_letter",
        relative_path="easy/handwritten-letter-resignation.jpg",
        profile="archival",
        model="gemini-2.5-pro",
        notes="Handwriting / archival correspondence check.",
    ),
    Case(
        key="war_diary",
        relative_path="easy/war-diary-page-1.jpg",
        profile="military",
        model="gemini-2.5-pro",
        notes="Strikethrough, archival fidelity, and military document structure.",
    ),
    Case(
        key="newspaper_scan",
        relative_path="easy/old-newspaper-scan-sample.pdf",
        profile="newspaper",
        model="gemini-2.5-pro",
        notes="Page metadata, article structure, and newspaper reading order.",
    ),
    Case(
        key="trove_age",
        relative_path="easy/trove-the-age-1930-04-30-page-1.pdf",
        profile="newspaper",
        model="gemini-2.5-pro",
        notes="Historical newspaper layout and attribution handling.",
    ),
    Case(
        key="services_form",
        relative_path="easy/services-australia-foi-form-ss293.pdf",
        profile="manual",
        model="gemini-2.5-flash",
        notes="Form semantics, checkbox/radio states, and structured sections.",
    ),
    Case(
        key="aged_care_bill_2024_opening",
        relative_path="hard benchmark files part two/aged-care-bill-2024-page-001.pdf",
        profile="legal",
        model="gemini-2.5-pro",
        notes="Opening page sample from the 2024 Aged Care Bill benchmark source.",
    ),
    Case(
        key="aged_care_bill_2024_midpoint",
        relative_path="hard benchmark files part two/aged-care-bill-2024-page-288.pdf",
        profile="legal",
        model="gemini-2.5-pro",
        notes="Mid-document legislative sample page from the 2024 Aged Care Bill.",
    ),
    Case(
        key="aged_care_bill_2024_closing",
        relative_path="hard benchmark files part two/aged-care-bill-2024-page-574.pdf",
        profile="legal",
        model="gemini-2.5-pro",
        notes="Closing-page legislative sample from the 2024 Aged Care Bill benchmark source.",
    ),
    Case(
        key="war_diary_wo_95_1668_3_2_midpoint",
        relative_path="hard benchmark files part two/wo-95-1668-3-2-page-040.pdf",
        profile="military",
        model="gemini-2.5-pro",
        notes="Representative midpoint sample from WO 95/1668/3_2.",
    ),
    Case(
        key="war_diary_wo_95_1668_3_1_midpoint",
        relative_path="hard benchmark files part two/wo-95-1668-3-1-page-071.pdf",
        profile="military",
        model="gemini-2.5-pro",
        notes="Representative midpoint sample from WO 95/1668/3_1.",
    ),
    Case(
        key="war_diary_wo_95_1668_2_midpoint",
        relative_path="hard benchmark files part two/wo-95-1668-2-page-071.pdf",
        profile="military",
        model="gemini-2.5-pro",
        notes="Representative midpoint sample from WO 95/1668/2.",
    ),
    Case(
        key="war_diary_wo_95_1668_1_midpoint",
        relative_path="hard benchmark files part two/wo-95-1668-1-page-071.pdf",
        profile="military",
        model="gemini-2.5-pro",
        notes="Representative midpoint sample from WO 95/1668/1.",
    ),
    Case(
        key="gold_casio_guide_opening",
        relative_path="gold mix samples/casio_gshock_5611-page-001.pdf",
        profile="manual",
        model="gemini-2.5-flash",
        notes="Operation-guide opening sample from the gold-mix corpus.",
    ),
    Case(
        key="gold_casio_guide_inner",
        relative_path="gold mix samples/casio_gshock_5611-page-004.pdf",
        profile="manual",
        model="gemini-2.5-flash",
        notes="Inner instruction page from the Casio operation guide.",
    ),
    Case(
        key="gold_cia_scan_opening",
        relative_path="gold mix samples/cia_rdp89_01258-page-001.pdf",
        profile="intelligence",
        model="gemini-2.5-pro",
        notes="Opening page from a scanned CIA record.",
    ),
    Case(
        key="gold_cia_scan_midpoint",
        relative_path="gold mix samples/cia_rdp89_01258-page-017.pdf",
        profile="intelligence",
        model="gemini-2.5-pro",
        notes="Midpoint page from a scanned CIA record.",
    ),
    Case(
        key="gold_criminal_code_opening",
        relative_path="gold mix samples/criminal_code_act_1995_vol1-page-001.pdf",
        profile="legal",
        model="gemini-2.5-pro",
        notes="Opening page from the Criminal Code Act 1995.",
    ),
    Case(
        key="gold_criminal_code_midpoint",
        relative_path="gold mix samples/criminal_code_act_1995_vol1-page-293.pdf",
        profile="legal",
        model="gemini-2.5-pro",
        notes="Midpoint legal-content sample from the Criminal Code Act 1995.",
    ),
    Case(
        key="gold_criminal_code_closing",
        relative_path="gold mix samples/criminal_code_act_1995_vol1-page-585.pdf",
        profile="legal",
        model="gemini-2.5-pro",
        notes="Closing-page legal-content sample from the Criminal Code Act 1995.",
    ),
    Case(
        key="gold_zoom_h6_opening",
        relative_path="gold mix samples/zoom_h6essential-page-001.pdf",
        profile="manual",
        model="gemini-2.5-flash",
        notes="Opening page from the Zoom H6essential manual.",
    ),
    Case(
        key="gold_zoom_h6_inner",
        relative_path="gold mix samples/zoom_h6essential-page-072.pdf",
        profile="manual",
        model="gemini-2.5-flash",
        notes="Inner workflow page from the Zoom H6essential manual.",
    ),
    Case(
        key="gold_anzac_history_opening",
        relative_path="gold mix samples/anzac_official_history_vol1-page-001.pdf",
        profile="military",
        model="gemini-2.5-pro",
        notes="Opening page from the official ANZAC history volume.",
    ),
    Case(
        key="gold_anzac_history_midpoint",
        relative_path="gold mix samples/anzac_official_history_vol1-page-150.pdf",
        profile="military",
        model="gemini-2.5-pro",
        notes="Mid-volume page from the official ANZAC history volume.",
    ),
    Case(
        key="gold_hamfest_before",
        relative_path="gold mix samples/hamfest_flyer_before.pdf",
        profile="office",
        model="gemini-2.5-pro",
        notes="Messy flyer PDF sample for layout cleanup and accessible restructuring.",
    ),
    Case(
        key="gold_middle_egyptian_opening",
        relative_path="gold mix samples/middle_egyptian_allen-page-002.pdf",
        profile="academic",
        model="gemini-2.5-pro",
        notes="Opening content page from Middle Egyptian.",
    ),
    Case(
        key="gold_middle_egyptian_midpoint",
        relative_path="gold mix samples/middle_egyptian_allen-page-263.pdf",
        profile="academic",
        model="gemini-2.5-pro",
        notes="Mid-book linguistic content page from Middle Egyptian.",
    ),
    Case(
        key="gold_middle_egyptian_index",
        relative_path="gold mix samples/middle_egyptian_allen-page-524.pdf",
        profile="academic",
        model="gemini-2.5-pro",
        notes="Index page from Middle Egyptian.",
    ),
    Case(
        key="gold_newspaper_issue1261581",
        relative_path="gold mix samples/nla_news_issue1261581-page-001.pdf",
        profile="newspaper",
        model="gemini-2.5-pro",
        notes="Gold-mix historical newspaper issue sample 1261581.",
    ),
    Case(
        key="gold_newspaper_issue2019607",
        relative_path="gold mix samples/nla_news_issue2019607-page-001.pdf",
        profile="newspaper",
        model="gemini-2.5-pro",
        notes="Gold-mix historical newspaper issue sample 2019607.",
    ),
    Case(
        key="gold_titanic_csv",
        relative_path="gold mix samples/titanic.csv",
        profile="tabular",
        model="gemini-2.5-pro",
        notes="CSV table benchmark from the gold-mix corpus.",
    ),
    Case(
        key="gold_trivia_xlsx",
        relative_path="gold mix samples/trivia.xlsx",
        profile="tabular",
        model="gemini-2.5-pro",
        notes="XLSX table benchmark from the gold-mix corpus.",
    ),
    Case(
        key="gold_valimaki_opening",
        relative_path="gold mix samples/valimaki_taslp2010-page-001.pdf",
        profile="academic",
        model="gemini-2.5-pro",
        notes="Opening page from the Valimaki/Nam/Smith/Abel paper.",
    ),
    Case(
        key="gold_valimaki_midpoint",
        relative_path="gold mix samples/valimaki_taslp2010-page-007.pdf",
        profile="academic",
        model="gemini-2.5-pro",
        notes="Mid-paper figure/math page from the Valimaki/Nam/Smith/Abel paper.",
    ),
    Case(
        key="gold_yunzii_manual_opening",
        relative_path="gold mix samples/yunzii_c75_manual-page-001.pdf",
        profile="manual",
        model="gemini-2.5-flash",
        notes="Opening page from the YUNZII C75 manual.",
    ),
    Case(
        key="gold_yunzii_manual_inner",
        relative_path="gold mix samples/yunzii_c75_manual-page-006.pdf",
        profile="manual",
        model="gemini-2.5-flash",
        notes="Inner instruction page from the YUNZII C75 manual.",
    ),
]


def resolve_gemini_key_path() -> Path:
    env_value = os.environ.get("CHRONICLE_GEMINI_API_KEY_FILE")
    if env_value:
        return Path(env_value).expanduser()

    candidates = [
        BASE_DIR / "api_key_gemini.txt",
        BASE_DIR / "api_keys" / "gemini.txt",
    ]

    if sys.platform == "darwin":
        candidates.append(Path.home() / "Library/Application Support/Chronicle/api_key_gemini.txt")
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "Chronicle" / "api_key_gemini.txt")
    else:
        candidates.append(Path.home() / ".config" / "Chronicle" / "api_key_gemini.txt")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_gemini_client() -> Any:
    from google import genai

    key_path = resolve_gemini_key_path()
    if not key_path.exists():
        raise SystemExit(f"Gemini API key not found: {key_path}")
    api_key = key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise SystemExit(f"Gemini API key file is empty: {key_path}")
    return genai.Client(api_key=api_key)


def _load_chronicle():
    import chronicle_runtime as chronicle

    return chronicle


def build_config(case: Case, output_dir: Path) -> dict:
    cfg = dict(PROFILE_PRESETS.get(case.profile, {}))
    cfg.update({
        "format_type": case.format_type,
        "output_dir": str(output_dir),
        "model_name": case.model,
        "doc_profile": case.profile,
        "translate_mode": "none",
        "translate_target": "English",
        "modernize_punctuation": False,
        "unit_conversion": case.profile in {"archival", "military", "newspaper"},
        "merge_files": False,
        "collision_mode": "overwrite",
        "image_descriptions": True,
        "large_print": False,
        "abbrev_expansion": case.profile in {"manual", "military", "intelligence", "archival"},
        "batch_mode": "flat",
        "academic_mode": case.profile == "academic",
        "source_path": "",
    })
    return cfg


def run_case(client: Any, source_path: Path, case: Case, output_root: Path) -> Path:
    chronicle = _load_chronicle()
    cfg = build_config(case, output_root)
    cfg["source_path"] = str(source_path)
    prompt_text = chronicle.get_prompt(cfg)
    base_name = source_path.stem
    out_path = output_root / f"{base_name}.{case.format_type}"
    tmp_out = Path(str(out_path) + ".tmp")
    if tmp_out.exists():
        tmp_out.unlink()

    memory: list[str] = []
    file_obj = None
    try:
        if case.format_type in STREAMABLE:
            file_obj = open(tmp_out, "w", encoding="utf-8")
            chronicle.write_header(
                file_obj,
                base_name,
                case.format_type,
                chronicle.get_output_lang_code(cfg),
                chronicle.get_output_text_direction(cfg),
            )

        ext = source_path.suffix.lower()
        if ext == ".pdf":
            chronicle.process_pdf(client, str(source_path), str(tmp_out), case.format_type, prompt_text, case.model, file_obj, memory)
        elif ext == ".pptx":
            chronicle.process_pptx_document(client, str(source_path), str(tmp_out), case.format_type, prompt_text, case.model, file_obj, memory)
        elif ext in {".docx", ".txt", ".md", ".rtf", ".csv", ".js", ".xlsx", ".xls", ".epub"}:
            chronicle.process_text_document(client, str(source_path), str(tmp_out), ext, case.format_type, prompt_text, case.model, file_obj, memory)
        elif ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}:
            chronicle.process_image(client, str(source_path), str(tmp_out), case.format_type, prompt_text, case.model, file_obj, memory)
        else:
            raise RuntimeError(f"Unsupported source extension for benchmark case: {ext}")

        chronicle.dispatch_save(cfg, str(tmp_out), memory, base_name)
        if file_obj:
            chronicle.write_footer(file_obj, case.format_type)
            file_obj.close()
        if case.format_type == "html" and tmp_out.exists():
            cleaned = chronicle.normalize_streamed_html_document(tmp_out.read_text(encoding="utf-8", errors="ignore"))
            cleaned = chronicle.apply_newspaper_html_safety_fallback(cleaned, "html", cfg.get("doc_profile"))
            cleaned = chronicle.recover_newspaper_header_citation(
                cleaned,
                "html",
                cfg.get("doc_profile"),
                cfg.get("source_path"),
            )
            cleaned = chronicle.recover_source_attribution_footer(
                cleaned,
                "html",
                cfg.get("doc_profile"),
                cfg.get("source_path"),
            )
            cleaned = chronicle.apply_handwriting_audit_flag(
                cleaned,
                "html",
                cfg.get("doc_profile"),
                whole_document=True,
            )
            cleaned = chronicle.enforce_archival_heading_structure(cleaned, "html", cfg.get("doc_profile"))
            tmp_out.write_text(cleaned, encoding="utf-8")
        os.replace(tmp_out, out_path)
        return out_path
    finally:
        if file_obj and not file_obj.closed:
            file_obj.close()
        if tmp_out.exists():
            try:
                tmp_out.unlink()
            except Exception:
                pass


def _run_case_worker(queue: multiprocessing.Queue, source_path_str: str, case_payload: dict, output_root_str: str) -> None:
    try:
        case = Case(**case_payload)
        source_path = Path(source_path_str)
        output_root = Path(output_root_str)
        client = load_gemini_client()
        output_path = run_case(client, source_path, case, output_root)
        queue.put({"status": "ok", "output_path": str(output_path)})
    except Exception as ex:  # pragma: no cover - exercised via parent watchdog behavior
        queue.put({"status": "error", "error": str(ex)})


def run_case_with_watchdog(
    source_path: Path,
    case: Case,
    output_root: Path,
    *,
    case_timeout_sec: float,
    idle_timeout_sec: float,
    poll_sec: float = 1.0,
    process_cls=multiprocessing.Process,
    queue_cls=multiprocessing.Queue,
    time_fn=time.time,
    sleep_fn=time.sleep,
) -> Path:
    queue = queue_cls()
    process = process_cls(
        target=_run_case_worker,
        args=(queue, str(source_path), asdict(case), str(output_root)),
        daemon=True,
    )
    started_at = time_fn()
    tmp_out = output_root / f"{source_path.stem}.{case.format_type}.tmp"
    last_progress_at = started_at
    last_size = -1
    saw_content_growth = False
    startup_idle_timeout_sec = max(idle_timeout_sec, 180.0) if idle_timeout_sec > 0 else 0.0
    process.start()
    try:
        while process.is_alive():
            now = time_fn()
            if case_timeout_sec > 0 and now - started_at > case_timeout_sec:
                process.terminate()
                process.join(timeout=5)
                raise TimeoutError(f"benchmark case exceeded {int(case_timeout_sec)}s total runtime")
            if tmp_out.exists():
                try:
                    current_size = tmp_out.stat().st_size
                except OSError:
                    current_size = last_size
                if current_size != last_size:
                    if last_size >= 0 and current_size > last_size:
                        saw_content_growth = True
                    last_size = current_size
                    last_progress_at = now
            idle_limit = idle_timeout_sec if saw_content_growth else startup_idle_timeout_sec
            if idle_limit > 0 and now - last_progress_at > idle_limit:
                process.terminate()
                process.join(timeout=5)
                raise TimeoutError(f"benchmark case was idle for more than {int(idle_limit)}s")
            if not queue.empty():
                break
            sleep_fn(poll_sec)

        process.join(timeout=1)
        if not queue.empty():
            result = queue.get_nowait()
            if result.get("status") == "ok":
                return Path(result["output_path"])
            raise RuntimeError(result.get("error") or "benchmark worker failed")
        if process.exitcode == 0 and not queue.empty():
            result = queue.get_nowait()
            if result.get("status") == "ok":
                return Path(result["output_path"])
        if process.exitcode not in (0, None):
            raise RuntimeError(f"benchmark worker exited with code {process.exitcode}")
        raise RuntimeError("benchmark worker finished without returning a result")
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        queue.close()
        queue.join_thread()


def audit_html_output(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    stripped = text.lstrip()
    img_with_alt = bool(
        re.search(r"<img\b[^>]*\balt=(['\"])(?!(?:\s*|image|photo)\1).+?\1", text, flags=re.IGNORECASE | re.DOTALL)
    )
    has_visual_elements = "<img" in lower or "<figure" in lower or "[image description:" in lower
    image_description_present = "[image description:" in lower or img_with_alt
    panel_heading_matches = list(re.finditer(r"<h2\b[^>]*>\s*panel\b.*?</h2>", text, flags=re.IGNORECASE | re.DOTALL))
    empty_panel_sections = []
    for index, match in enumerate(panel_heading_matches):
        end = panel_heading_matches[index + 1].start() if index + 1 < len(panel_heading_matches) else len(text)
        segment = text[match.end():end]
        segment_text = re.sub(r"<[^>]+>", " ", segment)
        if not re.sub(r"\s+", " ", segment_text).strip():
            empty_panel_sections.append(match.group(0))
    bare_image_description_line = bool(
        re.search(r"(?im)^\s*\[(?:Image Description|Panel Description):[^\n<]*\]\s*$", text)
    )
    checks = {
        "has_lang_dir_root": '<html lang="' in lower and ' dir="' in lower,
        "has_main_landmark": '<main id="content" role="main">' in lower,
        "has_page_header_cite": "<header><cite>" in lower,
        "has_source_footer_cite": "<footer><cite>" in lower,
        "has_h1": "<h1" in lower,
        "has_h2": "<h2" in lower,
        "has_panel_heading": bool(panel_heading_matches),
        "no_empty_panel_sections": not empty_panel_sections,
        "no_bare_image_description_lines": not bare_image_description_line,
        "has_visual_elements": has_visual_elements,
        "has_image_description": image_description_present,
        "has_strikethrough_recovery": "[struck through:" in lower or "<del" in lower or "<s>" in lower or "<strike" in lower,
        "has_checkbox_markup": "[checkbox:" in lower,
        "has_radio_markup": "[radio button:" in lower,
        "has_text_field_markup": "[text field:" in lower,
        "has_nested_doctype": lower.count("<!doctype html>") > 1,
        "has_nested_html_tag": len(re.findall(r"<html\b", lower)) > 1,
        "has_fence_wrappers": "```" in text,
        "has_leading_content_before_doctype": bool(
            not stripped.lower().startswith("<!doctype html>")
            and not stripped.lower().startswith("<html")
            and re.search(r"<[^>]+>", stripped[:300])
        ),
        "has_synthetic_page_filename_heading": bool(
            re.search(r"page[\s._-]*0*\d+\.(?:jpg|jpeg|png|bmp|tiff|tif|webp)", lower)
        ),
    }
    return checks


def grade_from_score(score: float, is_perfect: bool) -> str:
    if is_perfect and score >= 100.0:
        return "A+"
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 77:
        return "C+"
    if score >= 73:
        return "C"
    if score >= 70:
        return "C-"
    if score >= 67:
        return "D+"
    if score >= 63:
        return "D"
    if score >= 60:
        return "D-"
    return "F"


def score_html_checks(profile: str, checks: dict) -> dict:
    weights = PROFILE_SCORE_WEIGHTS.get(
        profile,
        {
            "has_lang_dir_root": 20,
            "has_main_landmark": 20,
            "has_h1": 15,
            "has_h2": 15,
            "no_structural_regressions": 30,
        },
    )
    breakdown = []
    earned = 0
    possible = sum(weights.values())
    structural_clean = not any(checks.get(key, False) for key in NEGATIVE_CHECK_KEYS)

    for key, weight in weights.items():
        if key == "no_structural_regressions":
            passed = structural_clean
        elif key == "has_image_description" and profile != "comic" and not image_description_applicable(checks):
            passed = True
        elif key == "has_strikethrough_recovery" and not strikethrough_recovery_applicable(checks):
            passed = True
        elif key in {"has_checkbox_markup", "has_radio_markup", "has_text_field_markup"} and not manual_form_semantics_applicable(checks):
            passed = True
        else:
            passed = bool(checks.get(key, False))
        if passed:
            earned += weight
        breakdown.append(
            {
                "key": key,
                "label": CHECK_LABELS.get(key, key),
                "passed": passed,
                "points_earned": weight if passed else 0,
                "points_possible": weight,
            }
        )

    score = round((earned / possible) * 100, 2) if possible else 0.0
    perfect = earned == possible and structural_clean
    return {
        "score": score,
        "grade": grade_from_score(score, perfect),
        "points_earned": earned,
        "points_possible": possible,
        "perfect_score": perfect,
        "breakdown": breakdown,
    }


def summarize_report(report: dict) -> dict:
    results = report.get("results", [])
    graded = [r for r in results if "scorecard" in r]
    if not graded:
        return {
            "cases_total": len(results),
            "cases_graded": 0,
            "average_score": 0.0,
            "overall_grade": "N/A",
            "a_plus_count": 0,
        }

    average_score = round(sum(r["scorecard"]["score"] for r in graded) / len(graded), 2)
    all_perfect = all(r["scorecard"]["perfect_score"] for r in graded) and len(graded) == len(results)
    return {
        "cases_total": len(results),
        "cases_graded": len(graded),
        "average_score": average_score,
        "overall_grade": grade_from_score(average_score, all_perfect),
        "a_plus_count": sum(1 for r in graded if r["scorecard"]["grade"] == "A+"),
    }


def accessibility_gate_failures(report: dict, fail_under: float = 100.0) -> list[str]:
    failures = []
    for result in report.get("results", []):
        case = result.get("case", {})
        case_key = case.get("key") or "unknown"
        status = result.get("status")
        if status != "ok":
            failures.append(f"{case_key}: benchmark status is {status or 'missing'}")
            continue
        scorecard = result.get("scorecard")
        if not scorecard:
            failures.append(f"{case_key}: missing accessibility scorecard")
            continue
        score = float(scorecard.get("score", 0.0))
        if fail_under > 0 and score < fail_under:
            failed_checks = [
                item.get("label") or item.get("key")
                for item in scorecard.get("breakdown", [])
                if not item.get("passed")
            ]
            details = "; ".join(item for item in failed_checks if item)
            suffix = f" ({details})" if details else ""
            failures.append(f"{case_key}: accessibility score {score} is below {fail_under}{suffix}")
    return failures


def build_markdown_summary(report: dict) -> str:
    summary = report.get("summary", summarize_report(report))
    lines = [
        "# Chronicle Benchmark Scorecard",
        "",
        f"- Generated: {report.get('generated_at', 'unknown')}",
        f"- Cases graded: {summary['cases_graded']} of {summary['cases_total']}",
        f"- Average score: {summary['average_score']}/100",
        f"- Overall grade: {summary['overall_grade']}",
        f"- A+ cases: {summary['a_plus_count']}",
        "",
    ]
    for result in report.get("results", []):
        case = result.get("case", {})
        key = case.get("key", "unknown")
        if "scorecard" not in result:
            lines.extend(
                [
                    f"## {key}",
                    "",
                    f"- Status: {result.get('status', 'unknown')}",
                    f"- Error: {result.get('error', 'not graded')}",
                    "",
                ]
            )
            continue
        scorecard = result["scorecard"]
        lines.extend(
            [
                f"## {key}",
                "",
                f"- Grade: {scorecard['grade']}",
                f"- Score: {scorecard['score']}/100 ({scorecard['points_earned']}/{scorecard['points_possible']} points)",
                f"- Status: {result.get('status', 'unknown')}",
                f"- Output: {result.get('output_path')}",
                "",
                "| Factor | Result | Points |",
                "|---|---|---:|",
            ]
        )
        for factor in scorecard["breakdown"]:
            result_text = "Pass" if factor["passed"] else "Miss"
            points_text = f"{factor['points_earned']}/{factor['points_possible']}"
            lines.append(f"| {factor['label']} | {result_text} | {points_text} |")
        if result.get("issues"):
            lines.extend(["", f"- Structural issues: {', '.join(result['issues'])}"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_report_entry(case: Case, source_path: Path, output_path: Path, started_at: float, error: str | None = None) -> dict:
    entry = {
        "case": asdict(case),
        "source_path": str(source_path),
        "output_path": str(output_path) if output_path else None,
        "elapsed_sec": round(time.time() - started_at, 2),
        "status": "ok" if error is None else "error",
    }
    if error is not None:
        entry["error"] = error
        return entry

    checks = audit_html_output(output_path)
    entry["checks"] = checks
    entry["issues"] = [name for name, value in checks.items() if value and name in NEGATIVE_CHECK_KEYS]
    entry["scorecard"] = score_html_checks(case.profile, checks)
    return entry


def resolve_cases(requested: list[str] | None) -> list[Case]:
    if not requested:
        return CASES
    lookup = {case.key: case for case in CASES}
    resolved = []
    for key in requested:
        if key not in lookup:
            raise SystemExit(f"Unknown case key: {key}")
        resolved.append(lookup[key])
    return resolved


def build_explicit_source_cases(
    source_files: list[str] | None,
    profile: str,
    model: str,
    format_type: str,
) -> list[Case]:
    if not source_files:
        return []
    cases = []
    for raw_path in source_files:
        path = Path(raw_path).expanduser().resolve()
        cases.append(
            Case(
                key=path.stem,
                relative_path=str(path),
                profile=profile,
                model=model,
                format_type=format_type,
                notes=f"Explicit source file benchmark for {path.name}.",
            )
        )
    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a controlled live accessibility benchmark against the Chronicle Benchmark Pack."
    )
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK_DIR, help="Path to the benchmark pack.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Directory for generated outputs.")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH, help="JSON report path.")
    parser.add_argument("--summary-path", type=Path, help="Markdown summary/scorecard path.")
    parser.add_argument("--case", action="append", dest="cases", help="Case key to run. Repeat for multiple cases.")
    parser.add_argument("--source-file", action="append", dest="source_files", help="Explicit source file to benchmark. Repeat for multiple files.")
    parser.add_argument("--profile", default="newspaper", help="Profile to use with --source-file entries.")
    parser.add_argument("--model", default="gemini-2.5-pro", help="Model to use with --source-file entries.")
    parser.add_argument("--format-type", default="html", help="Output format to use with --source-file entries.")
    parser.add_argument("--case-timeout-sec", type=float, default=900.0, help="Maximum wall-clock time per benchmark case.")
    parser.add_argument("--idle-timeout-sec", type=float, default=90.0, help="Maximum time a benchmark case may go without growing its temp output.")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=100.0,
        help="Exit non-zero when any completed case scores below this accessibility percentage. Use 0 to disable the score gate.",
    )
    parser.add_argument("--list", action="store_true", help="List available benchmark cases and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list:
        for case in CASES:
            print(f"{case.key}: {case.relative_path} [{case.profile} / {case.model}] - {case.notes}")
        return 0

    explicit_cases = build_explicit_source_cases(args.source_files, args.profile, args.model, args.format_type)
    selected_cases = explicit_cases or resolve_cases(args.cases)
    if not explicit_cases and not args.pack_dir.exists():
        raise SystemExit(f"Benchmark pack directory not found: {args.pack_dir}")

    args.output_root.mkdir(parents=True, exist_ok=True)
    summary_path = args.summary_path or args.report_path.with_name(args.report_path.stem + "_summary.md")
    report = {
        "pack_dir": str(args.pack_dir),
        "output_root": str(args.output_root),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": [],
    }

    for case in selected_cases:
        source_path = Path(case.relative_path) if explicit_cases else args.pack_dir / case.relative_path
        started_at = time.time()
        if not source_path.exists():
            report["results"].append({
                "case": asdict(case),
                "source_path": str(source_path),
                "status": "missing",
                "elapsed_sec": 0.0,
                "error": "source file not found",
            })
            continue
        try:
            output_path = run_case_with_watchdog(
                source_path,
                case,
                args.output_root,
                case_timeout_sec=args.case_timeout_sec,
                idle_timeout_sec=args.idle_timeout_sec,
            )
            report["results"].append(build_report_entry(case, source_path, output_path, started_at))
            print(f"[ok] {case.key} -> {output_path}")
        except Exception as ex:
            report["results"].append(build_report_entry(case, source_path, Path(), started_at, error=str(ex)))
            print(f"[error] {case.key}: {ex}")

    report["summary"] = summarize_report(report)
    args.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary_path.write_text(build_markdown_summary(report), encoding="utf-8")
    print(f"\nReport written to {args.report_path}")
    print(f"Scorecard written to {summary_path}")
    failures = accessibility_gate_failures(report, fail_under=args.fail_under)
    if failures:
        print("\nAccessibility gate failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
