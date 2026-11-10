"""Bounded, page-local Flash/Argon reading with atomic output selection."""
from dataclasses import dataclass
import html
import re

from chronicle_app.services.generation_completion import IncompleteGenerationError
from chronicle_app.services.output_quality import analyze_output_quality
from chronicle_app.services.runtime_policies import GEMINI_FAST_MODEL, GEMINI_REASONING_MODEL


_OUTPUT_LIMIT_REASONS = {'MAX_TOKENS', 'LENGTH', 'MAX_OUTPUT_TOKENS', 'MODEL_CONTEXT_WINDOW_EXCEEDED'}
_UNCERTAIN = re.compile(
    r'\[(?:unclear(?:\s+(?:word|words|letters|text|math))?|illegible(?:\s+(?:word|words|letters|text|signature|micro-text))?|'
    r'unreadable(?:\s+image\s+layer)?|translator\s+uncertain)(?:\s*:[^\]]*)?\]', re.IGNORECASE,
)


@dataclass(frozen=True)
class AdaptivePageResult:
    text: str
    model: str
    retried: bool
    needs_review: bool


def _visible_text(content, fmt):
    text = str(content or '')
    if fmt in {'html', 'epub'}:
        text = html.unescape(re.sub(r'<[^>]+>', ' ', text))
    return re.sub(r'\s+', ' ', text).strip()


def _has_page_content(content, fmt):
    visible = _visible_text(content, fmt)
    return bool(visible) and not re.fullmatch(r'(?:Source\s+)?Page\s+\d+', visible, re.IGNORECASE)


def page_review_reason(content, *, fmt):
    text = str(content or '')
    if not _has_page_content(text, fmt):
        return 'no readable page content was returned'
    if _UNCERTAIN.search(_visible_text(text, fmt)):
        return 'the reading contains explicitly uncertain or unreadable text'
    quality = analyze_output_quality(text, fmt=fmt)
    if not quality['ok']:
        return 'the reading has a document-structure warning'
    return None


def _is_output_limit(error):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, IncompleteGenerationError):
            return error.reason in _OUTPUT_LIMIT_REASONS
        error = error.__cause__
    return False


def read_adaptive_page(read_fn, *, fmt, log_cb, pause_cb=None, page_label='Page'):
    """Read one page; never carry its chosen model into the next call."""
    if pause_cb:
        pause_cb()
    primary = None
    try:
        primary = read_fn(GEMINI_FAST_MODEL)
        if pause_cb:
            pause_cb()
    except Exception as error:
        if not _is_output_limit(error):
            raise
        reason = 'Flash reached its output limit'
    else:
        reason = page_review_reason(primary, fmt=fmt)
        if reason is None:
            return AdaptivePageResult(primary, GEMINI_FAST_MODEL, False, False)

    log_cb(f'[Automatic Flash/Argon] {page_label}: {reason}; retrying this page with Argon. The next page starts with Flash.')
    if pause_cb:
        pause_cb()
    try:
        retry = read_fn(GEMINI_REASONING_MODEL)
    except InterruptedError:
        raise
    except Exception:
        if pause_cb:
            pause_cb()
        if _has_page_content(primary, fmt):
            log_cb(f'[Automatic Flash/Argon] {page_label}: Argon retry failed; the complete Flash reading was retained for review.')
            return AdaptivePageResult(primary, GEMINI_FAST_MODEL, True, True)
        raise
    if pause_cb:
        pause_cb()
    retry_reason = page_review_reason(retry, fmt=fmt)
    if not _has_page_content(retry, fmt):
        if not _has_page_content(primary, fmt):
            raise RuntimeError('Neither reading engine returned complete page content.')
        log_cb(f'[Automatic Flash/Argon] {page_label}: Argon returned no readable content; the complete Flash reading was retained for review.')
        return AdaptivePageResult(primary, GEMINI_FAST_MODEL, True, True)
    if retry_reason:
        log_cb(f'[Automatic Flash/Argon] {page_label}: the Argon reading still needs review.')
    else:
        log_cb(f'[Automatic Flash/Argon] {page_label}: using the Argon reading. Check important details against the source.')
    return AdaptivePageResult(retry, GEMINI_REASONING_MODEL, True, bool(retry_reason))
