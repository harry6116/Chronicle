#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path


WORD_RE = re.compile(r"\b[\w']+\b")
TAG_RE = re.compile(r"<[^>]+>")
BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class AuditResult:
    file: str
    word_count: int
    paragraph_count: int
    has_unclear_marker: bool
    has_image_description: bool
    has_signature_marker: bool
    long_sentence_count: int
    review_flags: list[str]


def html_to_text(html: str) -> str:
    normalized = BREAK_RE.sub("\n", html)
    normalized = TAG_RE.sub(" ", normalized)
    normalized = unescape(normalized)
    normalized = WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


def extract_main_html(html: str) -> str:
    match = re.search(r"<main\b[^>]*>(.*)</main>", html, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else html


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def audit_file(path: Path) -> AuditResult:
    html = path.read_text(encoding="utf-8", errors="ignore")
    main_html = extract_main_html(html)
    text = html_to_text(main_html)
    lower_html = main_html.lower()
    words = WORD_RE.findall(text)
    sentences = split_sentences(text)
    long_sentences = [s for s in sentences if len(WORD_RE.findall(s)) >= 22]
    paragraph_count = len(re.findall(r"<p\b", main_html, flags=re.IGNORECASE))
    has_unclear_marker = "[unclear word:" in lower_html or "[unclear letters:" in lower_html
    has_image_description = "[image description:" in lower_html
    has_signature_marker = "[signed]" in lower_html or "[illegible signature]" in lower_html

    review_flags: list[str] = []
    if len(words) >= 45 and not has_unclear_marker:
        review_flags.append("long_output_without_uncertainty_markers")
    if len(long_sentences) >= 2:
        review_flags.append("multiple_long_fluent_sentences")
    if paragraph_count <= 2 and len(words) >= 80:
        review_flags.append("dense_handwriting_collapsed_into_few_paragraphs")
    if has_image_description:
        review_flags.append("contains_image_description_in_handwriting_output")
    if has_signature_marker:
        review_flags.append("contains_signature_marker")

    return AuditResult(
        file=path.name,
        word_count=len(words),
        paragraph_count=paragraph_count,
        has_unclear_marker=has_unclear_marker,
        has_image_description=has_image_description,
        has_signature_marker=has_signature_marker,
        long_sentence_count=len(long_sentences),
        review_flags=review_flags,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Chronicle handwriting HTML outputs for suspiciously fluent transcriptions."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing Chronicle HTML outputs to audit.")
    parser.add_argument("--report-path", type=Path, help="Optional JSON path for the audit report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_dir.exists():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    files = sorted(args.input_dir.glob("*.html"))
    if not files:
        raise SystemExit(f"No .html files found in: {args.input_dir}")

    results = [audit_file(path) for path in files]
    report = {
        "input_dir": str(args.input_dir),
        "results": [asdict(result) for result in results],
        "flagged_files": [result.file for result in results if result.review_flags],
    }
    rendered = json.dumps(report, indent=2)
    if args.report_path:
        args.report_path.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
