import os

from chronicle_app.services.runtime_policies import DEFAULT_CLAUDE_MODEL, normalize_model_name


FORCE_DEEP_PROFILES = {"newspaper", "military"}
SPECIALTY_BASELINE_PROFILES = {"poetry", "transcript", "museum"}
ADAPTIVE_FLASH_PROFILES = {
    "standard",
    "office",
    "government",
    "archival",
    "intelligence",
    "book",
    "manual",
    "tabular",
    "academic",
}


def should_use_automatic_engine(job_cfg):
    return not str(job_cfg.get("model_override", "") or "").strip()


def _sample_page_indices(total_pages, selected_page_indices, *, max_pages=18):
    indices = list(selected_page_indices or [])
    if not indices:
        indices = list(range(total_pages))
    if len(indices) <= max_pages:
        return indices
    candidate_positions = {
        0,
        min(len(indices) - 1, 1),
        min(len(indices) - 1, 2),
        len(indices) // 4,
        len(indices) // 3,
        len(indices) // 2,
        (2 * len(indices)) // 3,
        (3 * len(indices)) // 4,
        len(indices) - 1,
    }
    sampled = []
    seen = set()
    for pos in sorted(candidate_positions):
        index = indices[pos]
        if index in seen:
            continue
        seen.add(index)
        sampled.append(index)
        if len(sampled) >= max_pages:
            break
    if len(sampled) < max_pages:
        stride = max(1, len(indices) // max_pages)
        for pos in range(0, len(indices), stride):
            index = indices[pos]
            if index in seen:
                continue
            seen.add(index)
            sampled.append(index)
            if len(sampled) >= max_pages:
                break
    return sampled


def _extract_page_text_metrics(reader, page_indices):
    metrics = []
    for index in page_indices:
        text = ""
        try:
            text = reader.pages[index].extract_text() or ""
        except Exception:
            text = ""
        compact = " ".join(text.split())
        alpha_chars = sum(1 for ch in compact if ch.isalpha())
        digit_chars = sum(1 for ch in compact if ch.isdigit())
        metrics.append(
            {
                "chars": len(compact),
                "alpha_chars": alpha_chars,
                "digit_chars": digit_chars,
                "has_text": bool(compact),
            }
        )
    return metrics


def _is_strong_text_backed_pdf(metrics, *, avg_page_mb):
    textful_pages = sum(1 for item in metrics if item["has_text"])
    if textful_pages <= 0:
        return False
    avg_chars = sum(item["chars"] for item in metrics if item["has_text"]) / textful_pages
    strong_pages = sum(1 for item in metrics if item["chars"] >= 1200 and item["alpha_chars"] >= 500)
    return (
        textful_pages >= max(1, len(metrics) - 1)
        and strong_pages >= max(1, min(2, len(metrics)))
        and avg_chars >= 1200
        and avg_page_mb <= 0.45
    )


def classify_pdf_for_auto_engine(
    path,
    job_cfg,
    *,
    pdf_reader_factory,
    normalize_pdf_page_scope_text_fn,
    parse_pdf_page_scope_spec_fn,
    getsize_fn=os.path.getsize,
):
    profile = str(job_cfg.get("doc_profile", "standard") or "standard").lower()
    if profile in FORCE_DEEP_PROFILES:
        return {"difficulty": "hard", "reason": f"{profile} profile stays on the deep engine by default.", "sampled_pages": 0}
    if profile in SPECIALTY_BASELINE_PROFILES:
        return {"difficulty": "specialty", "reason": f"{profile} profile keeps its specialty baseline engine.", "sampled_pages": 0}

    try:
        reader = pdf_reader_factory(path)
        total_pages = len(reader.pages)
    except Exception as ex:
        return {"difficulty": "unknown", "reason": f"PDF preflight could not inspect the file ({ex}).", "sampled_pages": 0}

    file_size_mb = 0.0
    try:
        file_size_mb = float(getsize_fn(path)) / (1024.0 * 1024.0)
    except Exception:
        file_size_mb = 0.0

    selected_scope = ""
    selected_page_indices = list(range(total_pages))
    if normalize_pdf_page_scope_text_fn is not None and parse_pdf_page_scope_spec_fn is not None:
        try:
            selected_scope = normalize_pdf_page_scope_text_fn(job_cfg.get("pdf_page_scope", ""))
            selected_page_indices = parse_pdf_page_scope_spec_fn(selected_scope, total_pages)
        except Exception:
            selected_page_indices = list(range(total_pages))

    sample_indices = _sample_page_indices(total_pages, selected_page_indices)
    metrics = _extract_page_text_metrics(reader, sample_indices)
    sample_count = max(1, len(metrics))
    textful_pages = sum(1 for item in metrics if item["has_text"])
    avg_chars = sum(item["chars"] for item in metrics) / sample_count
    avg_page_mb = file_size_mb / max(1, total_pages)

    if profile == "legal":
        if _is_strong_text_backed_pdf(metrics, avg_page_mb=avg_page_mb):
            return {
                "difficulty": "mixed",
                "reason": (
                    f"legal PDF appears born-digital with a strong text layer across {len(sample_indices)} sampled pages, "
                    "so Chronicle can start faster and escalate only if needed."
                ),
                "sampled_pages": len(sample_indices),
            }
        return {
            "difficulty": "hard",
            "reason": (
                f"legal PDF looked scan-heavy, weak-text, or structurally risky across {len(sample_indices)} sampled pages, "
                "so Chronicle kept the deep path."
            ),
            "sampled_pages": len(sample_indices),
        }

    if total_pages >= 120 and avg_page_mb >= 0.75 and textful_pages <= 1:
        return {
            "difficulty": "hard",
            "reason": f"large scanned PDF with weak text-layer evidence across {len(sample_indices)} sampled pages.",
            "sampled_pages": len(sample_indices),
        }
    if textful_pages == sample_count and avg_chars >= 1400 and avg_page_mb <= 0.35 and profile in ADAPTIVE_FLASH_PROFILES:
        return {
            "difficulty": "easy",
            "reason": f"born-digital PDF with a strong text layer across {len(sample_indices)} sampled pages.",
            "sampled_pages": len(sample_indices),
        }
    if textful_pages >= max(1, sample_count - 1) and avg_chars >= 700 and avg_page_mb <= 0.55 and profile in ADAPTIVE_FLASH_PROFILES:
        return {
            "difficulty": "mixed",
            "reason": (
                f"PDF looks mostly text-backed across {len(sample_indices)} sampled pages, "
                "but still worth conservative per-page fallback protection."
            ),
            "sampled_pages": len(sample_indices),
        }
    return {
        "difficulty": "hard",
        "reason": f"PDF preflight found weak text extraction or scan-heavy pages across {len(sample_indices)} sampled pages.",
        "sampled_pages": len(sample_indices),
    }


def select_execution_model_for_job(
    path,
    ext,
    job_cfg,
    preferred_model,
    *,
    pdf_reader_factory=None,
    normalize_pdf_page_scope_text_fn=None,
    parse_pdf_page_scope_spec_fn=None,
    getsize_fn=os.path.getsize,
):
    baseline_model = normalize_model_name(preferred_model)
    manual_override = not should_use_automatic_engine(job_cfg)
    profile = str(job_cfg.get("doc_profile", "standard") or "standard").lower()

    result = {
        "model_name": baseline_model,
        "baseline_model": baseline_model,
        "routing_mode": "manual" if manual_override else "automatic",
        "routing_reason": "Manual engine override is set." if manual_override else "Preset baseline engine selected.",
        "auto_escalation_model": None,
        "difficulty": "baseline",
    }
    if manual_override:
        return result
    if ext != ".pdf":
        result["routing_reason"] = "Non-PDF input kept the preset baseline engine."
        return result
    if pdf_reader_factory is None:
        result["routing_reason"] = "PDF preflight helpers were unavailable, so Chronicle kept the preset baseline engine."
        return result
    if profile in SPECIALTY_BASELINE_PROFILES:
        result["routing_reason"] = f"{profile} preset keeps its specialty baseline engine."
        result["difficulty"] = "specialty"
        return result

    assessment = classify_pdf_for_auto_engine(
        path,
        job_cfg,
        pdf_reader_factory=pdf_reader_factory,
        normalize_pdf_page_scope_text_fn=normalize_pdf_page_scope_text_fn,
        parse_pdf_page_scope_spec_fn=parse_pdf_page_scope_spec_fn,
        getsize_fn=getsize_fn,
    )
    result["difficulty"] = assessment.get("difficulty", "unknown")
    result["routing_reason"] = assessment.get("reason", result["routing_reason"])

    if baseline_model == "gemini-2.5-pro" and assessment.get("difficulty") in {"easy", "mixed"} and profile in (ADAPTIVE_FLASH_PROFILES | {"legal"}):
        result["model_name"] = "gemini-2.5-flash"
        result["auto_escalation_model"] = "gemini-2.5-pro"
        result["routing_reason"] = (
            f"Auto selected Gemini 2.5 Flash first because the document looks {assessment.get('difficulty')}; "
            f"{assessment.get('reason', '').rstrip('.')}. "
            "Chronicle will escalate hard pages to Gemini 2.5 Pro if needed."
        )
        return result

    if baseline_model in {"gemini-2.5-flash", "gemini-2.5-pro"} and assessment.get("difficulty") == "hard":
        result["model_name"] = "gemini-2.5-pro"
        result["routing_reason"] = (
            f"Auto kept Gemini 2.5 Pro because the document looks hard; {assessment.get('reason', '').rstrip('.')}"
        ).strip()
        return result

    if baseline_model in {DEFAULT_CLAUDE_MODEL, "gpt-4o"}:
        result["routing_reason"] = "Auto kept the preset specialty engine for this document type."
        return result

    return result
