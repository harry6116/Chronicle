import os
import platform
import time
import json
import re
import logging
import shutil
import textwrap
import sys
import glob
import html
import csv
import io
import hashlib
import tempfile
import gc
from collections import OrderedDict
import threading

try:
    import cv2
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    cv2 = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    Image = None

try:
    import fitz
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    fitz = None

try:
    import docx
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    docx = None

try:
    from fpdf import FPDF
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    FPDF = None

try:
    from google import genai
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    genai = None

try:
    import openpyxl
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    openpyxl = None

try:
    from ebooklib import epub
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    epub = None
from chronicle_app.services.app_files import (
    emit_launch_continuity as shared_emit_launch_continuity,
    resolve_runtime_crash_log_path as shared_resolve_runtime_crash_log_path,
)
from chronicle_app.services.security import sanitize_log_text
from chronicle_app.services.prompting import (
    build_prompt as build_shared_prompt,
    enforce_archival_heading_structure as shared_enforce_archival_heading_structure,
)
from chronicle_app.services.runtime_policies import get_online_engine_settings
from chronicle_app.config import (
    PROFILE_CHOICES,
    PROFILE_PRESETS,
    RTL_LANGUAGE_CODES,
    TRANSLATION_TARGETS,
)
from chronicle_core import (
    apply_newspaper_html_safety_fallback as core_apply_newspaper_html_safety_fallback,
    apply_modern_punctuation as core_apply_modern_punctuation,
    apply_modern_currency as core_apply_modern_currency,
    apply_expanded_abbreviations as core_apply_expanded_abbreviations,
    apply_handwriting_audit_flag as core_apply_handwriting_audit_flag,
    build_tabular_html_fragment as core_build_tabular_html_fragment,
    build_newspaper_safety_notice as core_build_newspaper_safety_notice,
    clean_text_artifacts as core_clean_text_artifacts,
    csv_to_accessible_text as core_csv_to_accessible_text,
    get_newspaper_profile_rules as core_get_newspaper_profile_rules,
    parse_csv_rows as core_parse_csv_rows,
    recover_newspaper_header_citation as core_recover_newspaper_header_citation,
    recover_source_attribution_footer as core_recover_source_attribution_footer,
    sanitize_latin1 as core_sanitize_latin1,
    sanitize_model_output as core_sanitize_model_output,
    normalize_streamed_html_document as core_normalize_streamed_html_document,
    write_header as core_write_header,
    write_footer as core_write_footer,
)
from chronicle_app.services.document_processors import (
    PRESENTATION_EXTENSIONS,
    FITZ_TEXT_EXTENSIONS,
    RENDERABLE_DOCUMENT_EXTENSIONS,
    SOURCE_TEXT_EXTENSIONS,
    SUPPORTED_EXTENSIONS as SHARED_SUPPORTED_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    prepare_image_for_scan,
)

# Dynamically link Homebrew's Python site-packages for Mac users
brew_paths = glob.glob("/opt/homebrew/lib/python3.*/site-packages") + glob.glob("/usr/local/lib/python3.*/site-packages")
for path in brew_paths:
    if os.path.exists(path) and path not in sys.path:
        sys.path.append(path)


APP_NAME = "Chronicle"

def _get_crash_log_path():
    return shared_resolve_runtime_crash_log_path(app_name=APP_NAME)

class _RedactingStream:
    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        return self._stream.write(sanitize_log_text(text))

    def flush(self):
        return self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)

if getattr(sys, 'frozen', False):
    try:
        crash_log_path = _get_crash_log_path()
        sys.stdout = _RedactingStream(open(crash_log_path, 'a', buffering=1, encoding='utf-8', errors='replace'))
        sys.stderr = sys.stdout
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(SCRIPT_DIR, "input_files")
BATCH_INPUT_DIR = os.path.join(SCRIPT_DIR, "Input_Scans")

def _get_app_data_dir():
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    if platform.system() == "Darwin":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME)

APP_DATA_DIR = _get_app_data_dir()
os.makedirs(APP_DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DATA_DIR, "user_config.json")

PDF_CHUNK_PAGES = 5
TEXT_CHUNK_CHARS = 15000
HEARTBEAT_TIMEOUT_SEC = 480
API_POLITE_MODE = True
_ONLINE_ENGINE_SETTINGS = get_online_engine_settings(
    api_min_request_interval_sec=1.5 if API_POLITE_MODE else 1.0,
    api_backoff_base_sec=10,
    api_max_retries=5,
)
API_MIN_REQUEST_INTERVAL_SEC = _ONLINE_ENGINE_SETTINGS["api_min_request_interval_sec"]
API_BACKOFF_BASE_SEC = _ONLINE_ENGINE_SETTINGS["api_backoff_base_sec"]
API_BACKOFF_MAX_SEC = _ONLINE_ENGINE_SETTINGS["api_backoff_max_sec"]
API_MAX_RETRIES = _ONLINE_ENGINE_SETTINGS["api_max_retries"]
API_MAX_CONCURRENT_REQUESTS = _ONLINE_ENGINE_SETTINGS["api_max_concurrent_requests"]
API_MAX_PENDING_REQUESTS = _ONLINE_ENGINE_SETTINGS["api_max_pending_requests"]
API_REQUEST_QUEUE_POLL_SEC = _ONLINE_ENGINE_SETTINGS["api_request_queue_poll_sec"]
API_CACHE_MAX_ENTRIES = _ONLINE_ENGINE_SETTINGS["api_cache_max_entries"]
TEXT_BATCH_TARGET_CHARS = 24000
API_CONNECTION_FAILURE_DELAY_SEC = 20.0
GEMINI_UPLOAD_POLL_SEC = 2.5
GEMINI_UPLOAD_MAX_WAIT_SEC = 180.0
SUPPORTED_EXTENSIONS = sorted(SHARED_SUPPORTED_EXTENSIONS - {".xls", ".ppt"})
PROTECTED_INPUT_DIR_BASENAMES = {"checking documents"}
TRANSLATION_TARGETS = [
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
]
RTL_LANGUAGE_CODES = {"ar", "fa", "he", "ur", "yi", "ps", "sd", "ug"}
_api_request_lock = threading.Lock()
_api_last_request_ts = 0.0
_api_request_semaphore = threading.Semaphore(API_MAX_CONCURRENT_REQUESTS)
_api_queue_lock = threading.Lock()
_api_pending_requests = 0
_chunk_cache = OrderedDict()
_chunk_cache_lock = threading.Lock()

def _secure_chmod(path, mode=0o600):
    if os.name == "nt":
        return
    try:
        os.chmod(path, mode)
    except Exception:
        pass

def migrate_legacy_cli_key_files():
    for vendor in ("gemini", "anthropic", "openai"):
        legacy = os.path.join(SCRIPT_DIR, f"api_key_{vendor}.txt")
        target = os.path.join(APP_DATA_DIR, f"api_key_{vendor}.txt")
        if os.path.exists(legacy) and not os.path.exists(target):
            try:
                shutil.copy2(legacy, target)
                _secure_chmod(target, 0o600)
            except Exception:
                pass
        if os.path.exists(legacy) and os.path.exists(target):
            try:
                os.remove(legacy)
            except Exception:
                try:
                    with open(legacy, "w", encoding="utf-8") as fh:
                        fh.write("")
                except Exception:
                    pass

def get_translation_target(config):
    target = str(config.get("translate_target", "English")).strip()
    lookup = {name.lower(): (name, code) for name, code in TRANSLATION_TARGETS}
    return lookup.get(target.lower(), ("English", "en"))

def get_output_lang_code(config):
    explicit = str(
        config.get("output_lang_code")
        or config.get("source_lang_code")
        or config.get("language_code")
        or ""
    ).strip().lower()
    if re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?", explicit):
        return explicit
    _, code = get_translation_target(config)
    return code

def get_output_text_direction(config):
    code = get_output_lang_code(config).split("-", 1)[0]
    return "rtl" if code in RTL_LANGUAGE_CODES else "ltr"

def is_path_within_protected_input_dirs(path):
    try:
        target = os.path.normcase(os.path.abspath(path))
    except Exception:
        return False
    for dirname in PROTECTED_INPUT_DIR_BASENAMES:
        root = os.path.normcase(os.path.abspath(os.path.join(SCRIPT_DIR, dirname)))
        try:
            if os.path.commonpath([target, root]) == root:
                return True
        except Exception:
            continue
    return False

def get_api_key(model_name):
    vendor = "claude" if "claude" in model_name else "openai" if "gpt" in model_name else "gemini"
    candidate_files = [os.path.join(APP_DATA_DIR, f"api_key_{vendor}.txt")]
    if vendor == "claude":
        candidate_files.append(os.path.join(APP_DATA_DIR, "api_key_anthropic.txt"))
    for key_file in candidate_files:
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                key = f.read().strip()
                if key:
                    return key
    print(f"\nFIRST TIME SETUP - {vendor.upper()}")
    new_key = input(f"Please paste your {vendor.upper()} API Key here and press Enter: ").strip()
    if new_key:
        key_file = candidate_files[0]
        with open(key_file, "w") as f: f.write(new_key)
        _secure_chmod(key_file, 0o600)
        return new_key
    exit()

def get_prompt(config):
    return build_shared_prompt(
        config,
        translation_targets=TRANSLATION_TARGETS,
        rtl_language_codes=RTL_LANGUAGE_CODES,
        format_type=config.get("format_type", "html"),
    )
def enhance_image_for_microtext(file_path):
    try:
        img = cv2.imread(file_path)
        if img is None:
            return file_path
        width, height = int(img.shape[1] * 2), int(img.shape[0] * 2)
        resized = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        # Improve faint handwriting and soft scans without inventing content.
        denoised = cv2.fastNlMeansDenoising(gray, None, 8, 7, 21)
        contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(denoised)
        processed = cv2.addWeighted(contrast, 1.22, cv2.GaussianBlur(contrast, (0, 0), 1.1), -0.22, 0)
        safe_stem = re.sub(r"[^0-9A-Za-z._-]+", "_", os.path.basename(file_path))
        temp_path = os.path.join(
            tempfile.gettempdir(),
            f"chronicle_enhanced_{os.getpid()}_{safe_stem}.png",
        )
        if not cv2.imwrite(temp_path, processed):
            return file_path
        return temp_path
    except Exception as e:
        print(f"Warning: Could not enhance image ({e}). Using original.")
        return file_path

def clean_text_artifacts(text):
    return core_clean_text_artifacts(text)

def csv_to_accessible_text(raw_text, max_rows=None, max_cell_chars=None):
    return core_csv_to_accessible_text(raw_text, max_rows=max_rows, max_cell_chars=max_cell_chars)

def sanitize_latin1(text):
    return core_sanitize_latin1(text)

def sanitize_model_output(text_content, format_type, doc_profile=None, preserve_original_page_numbers=False):
    return core_sanitize_model_output(
        text_content,
        format_type,
        doc_profile,
        preserve_original_page_numbers,
    )

def apply_modern_punctuation(text_content):
    return core_apply_modern_punctuation(text_content)

def apply_modern_currency(text_content):
    return core_apply_modern_currency(text_content)


def apply_expanded_abbreviations(text_content, doc_profile=None):
    return core_apply_expanded_abbreviations(text_content, doc_profile)

def normalize_streamed_html_document(full_html, *, insert_page_navigation=True):
    return core_normalize_streamed_html_document(
        full_html,
        insert_page_navigation=insert_page_navigation,
    )


def enforce_archival_heading_structure(content, fmt, doc_profile):
    return shared_enforce_archival_heading_structure(content, fmt, doc_profile)

def apply_handwriting_audit_flag(text_content, format_type, doc_profile, whole_document=False):
    return core_apply_handwriting_audit_flag(text_content, format_type, doc_profile, whole_document=whole_document)

def apply_newspaper_html_safety_fallback(text_content, format_type, doc_profile, max_chars=14000):
    return core_apply_newspaper_html_safety_fallback(text_content, format_type, doc_profile, max_chars=max_chars)

def recover_source_attribution_footer(text_content, format_type, doc_profile, source_path=None):
    return core_recover_source_attribution_footer(
        text_content, format_type, doc_profile, source_path=source_path
    )


def recover_newspaper_header_citation(text_content, format_type, doc_profile, source_path=None):
    return core_recover_newspaper_header_citation(
        text_content, format_type, doc_profile, source_path=source_path
    )

def write_header(file_obj, title, format_type, lang_code='en', text_dir='ltr'):
    core_write_header(file_obj, title, format_type, lang_code=lang_code, text_dir=text_dir)

def write_footer(file_obj, format_type):
    core_write_footer(file_obj, format_type)

def _probe_pdf_text_layer(pdf_path, sample_pages=3, min_chars_per_page=200):
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return False
    try:
        total_pages = len(doc)
        if total_pages <= 0:
            return False
        pages_to_check = min(max(1, sample_pages), total_pages)
        total_chars = 0
        for page_index in range(pages_to_check):
            try:
                extracted = doc.load_page(page_index).get_text("text") or ""
            except Exception:
                extracted = ""
            total_chars += len(extracted.strip())
        average_chars = total_chars / pages_to_check
        return average_chars > min_chars_per_page
    finally:
        doc.close()

def _render_pdf_page_to_png_bytes(doc, page_index, zoom=2.0):
    page = doc.load_page(page_index)
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    image_bytes = pix.tobytes("png")
    pix = None
    page = None
    return image_bytes


def _write_temp_png(prefix, image_bytes):
    fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=".png")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(image_bytes)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    return temp_path


def _set_pdf_metadata(pdf, title="Chronicle PDF Output"):
    metadata = {
        "set_title": title,
        "set_author": "Chronicle",
        "set_creator": "Chronicle",
        "set_subject": "Untagged PDF output. For best accessibility, use Chronicle HTML, DOCX, or EPUB output.",
        "set_keywords": "untagged PDF, accessibility review, Chronicle",
    }
    for method_name, value in metadata.items():
        method = getattr(pdf, method_name, None)
        if callable(method):
            try:
                method(value)
            except Exception:
                pass


def save_as_pdf(pdf_path, text_content, large_print=False, title="Chronicle PDF Output"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    font_size = 18 if large_print else 11
    pdf.set_font("Helvetica", size=font_size)
    _set_pdf_metadata(pdf, title=title)
    if large_print:
        # Force FPDF HTML parser to respect large-font rendering.
        text_content = f"<div style='font-size: 24px; line-height: 1.5;'>{text_content}</div>"
    try:
        pdf.write_html(text_content)
        pdf.output(pdf_path)
    except Exception as e:
        print(f"Warning: HTML-PDF compilation failed, falling back to flat text. {e}")
        fallback = FPDF()
        fallback.add_page()
        fallback.set_auto_page_break(auto=True, margin=15)
        fallback.set_font("Helvetica", size=font_size)
        _set_pdf_metadata(fallback, title=title)

        # Strip HTML and unescape entities for clean plain-text fallback.
        import html as html_lib
        clean_fallback = re.sub(r'<[^>]+>', '', text_content)
        clean_fallback = html_lib.unescape(clean_fallback)

        fallback.multi_cell(0, 10 if not large_print else 16, text=sanitize_latin1(clean_fallback))
        fallback.output(pdf_path)

def append_to_docx(docx_path, text_content):
    doc = docx.Document(docx_path) if os.path.exists(docx_path) else docx.Document()
    for line in text_content.split('\n'):
        clean_line = line.strip()
        if clean_line.startswith('### '): doc.add_heading(clean_line[4:], level=3)
        elif clean_line.startswith('## '): doc.add_heading(clean_line[3:], level=2)
        elif clean_line.startswith('# '): doc.add_heading(clean_line[2:], level=1)
        elif clean_line.startswith('-') or clean_line.startswith('*'):
            clean_text = clean_line.lstrip('-* ').strip()
            doc.add_paragraph(clean_text, style='List Bullet')
        elif clean_line != "": doc.add_paragraph(clean_line)
    doc.save(docx_path)

def save_as_json(json_path, text_content):
    text_content = text_content.strip()
    if text_content.startswith("```json"): text_content = text_content[7:-3].strip()
    try: data = json.loads(text_content)
    except: data = {"chronicle_extracted_content": text_content}
    with open(json_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

def save_as_csv(csv_path, text_content):
    text_content = text_content.replace("```csv", "").replace("```", "").strip()
    with open(csv_path, 'w', encoding='utf-8') as f: f.write(text_content)

def save_as_epub(epub_path, title, text_content, lang_code='en', text_dir='ltr'):
    book = epub.EpubBook()
    book.set_identifier(f"chron_{int(time.time())}")
    book.set_title(title)
    book.set_language(lang_code)
    
    chapters = re.split(r'(<h[123].*?>.*?</h[123]>)', text_content, flags=re.IGNORECASE)
    epub_chapters, current_title, current_content, chap_idx = [], title, "", 1
    
    for segment in chapters:
        if segment.lower().startswith('<h1') or segment.lower().startswith('<h2') or segment.lower().startswith('<h3'):
            if current_content.strip():
                c = epub.EpubHtml(title=current_title, file_name=f'chap_{chap_idx}.xhtml', lang=lang_code)
                c.content = f"<h1>{current_title}</h1><div dir=\"{text_dir}\">{current_content}</div>"
                epub_chapters.append(c)
                chap_idx += 1
            current_title = re.sub(r'<[^>]+>', '', segment)
            current_content = segment 
        else:
            current_content += segment
            
    if current_content.strip():
        c = epub.EpubHtml(title=current_title, file_name=f'chap_{chap_idx}.xhtml', lang=lang_code)
        c.content = f"<h1>{current_title}</h1><div dir=\"{text_dir}\">{current_content}</div>"
        epub_chapters.append(c)

    for c in epub_chapters: book.add_item(c)
    book.spine = ['nav'] + epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(epub_path, book, {})

def dispatch_save(config, path, memory_list, title, clear_memory=False):
    content = "".join(memory_list)
    if not content: return
    fmt = config['format_type']
    content = sanitize_model_output(
        content,
        fmt,
        config.get('doc_profile'),
        config.get('preserve_original_page_numbers', False),
    )
    if config.get('modernize_punctuation'):
        content = apply_modern_punctuation(content)
    if config.get('unit_conversion'):
        content = apply_modern_currency(content)
    if config.get('abbrev_expansion'):
        content = apply_expanded_abbreviations(content, config.get('doc_profile'))
    content = apply_newspaper_html_safety_fallback(content, fmt, config.get('doc_profile'))
    content = recover_newspaper_header_citation(content, fmt, config.get('doc_profile'), config.get('source_path'))
    content = recover_source_attribution_footer(content, fmt, config.get('doc_profile'), config.get('source_path'))
    content = apply_handwriting_audit_flag(content, fmt, config.get('doc_profile'))
    content = enforce_archival_heading_structure(content, fmt, config.get('doc_profile'))
    
    if fmt == 'docx': 
        append_to_docx(path, content)
        if clear_memory: memory_list.clear()
    elif fmt == 'pdf': save_as_pdf(path, content, config.get('large_print', False), title)
    elif fmt == 'json': save_as_json(path, content)
    elif fmt == 'csv': save_as_csv(path, content)
    elif fmt == 'epub': save_as_epub(path, title, content, get_output_lang_code(config), get_output_text_direction(config))
def pace_api_request():
    global _api_last_request_ts
    with _api_request_lock:
        now = time.time()
        wait = API_MIN_REQUEST_INTERVAL_SEC - (now - _api_last_request_ts)
        if wait > 0:
            time.sleep(wait)
        _api_last_request_ts = time.time()

def wait_for_request_slot():
    global _api_pending_requests
    while True:
        with _api_queue_lock:
            if _api_pending_requests < API_MAX_PENDING_REQUESTS:
                _api_pending_requests += 1
                break
        time.sleep(API_REQUEST_QUEUE_POLL_SEC)
    _api_request_semaphore.acquire()
    with _api_queue_lock:
        _api_pending_requests = max(0, _api_pending_requests - 1)

def release_request_slot():
    _api_request_semaphore.release()

def is_connection_path_error(exc):
    err = str(exc).lower()
    return any(token in err for token in (
        "connecterror",
        "connection error",
        "temporary failure in name resolution",
        "nodename nor servname provided",
        "name or service not known",
        "getaddrinfo",
        "failed to establish a new connection",
        "connection refused",
        "network is unreachable",
    ))

def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()

def build_request_cache_key(model_name, prompt_text, payload_kind, payload_fingerprint):
    return f"{model_name}|{payload_kind}|{sha256_text(prompt_text)}|{payload_fingerprint}"

def cache_get(cache_key):
    with _chunk_cache_lock:
        val = _chunk_cache.get(cache_key)
        if val is None:
            return None
        _chunk_cache.move_to_end(cache_key)
        return val

def cache_put(cache_key, text):
    if not text:
        return
    with _chunk_cache_lock:
        _chunk_cache[cache_key] = text
        _chunk_cache.move_to_end(cache_key)
        while len(_chunk_cache) > API_CACHE_MAX_ENTRIES:
            _chunk_cache.popitem(last=False)

def append_generated_text(format_type, file_obj=None, memory_list=None, text=""):
    if not text:
        return
    if format_type in ['html', 'txt', 'md', 'epub']:
        text = sanitize_model_output(clean_text_artifacts(text), format_type)
        if not text:
            return
    if format_type in ['html', 'txt', 'md'] and file_obj:
        file_obj.write(text)
        file_obj.flush()
    if memory_list is not None:
        memory_list.append(text)

def batch_text_chunks(chunks, target_chars=TEXT_BATCH_TARGET_CHARS):
    batches = []
    current_batch = []
    current_len = 0
    for chunk in chunks:
        if not chunk:
            continue
        chunk_len = len(chunk)
        if current_batch and (current_len + chunk_len) > target_chars:
            batches.append("\n".join(current_batch))
            current_batch = [chunk]
            current_len = chunk_len
        else:
            current_batch.append(chunk)
            current_len += chunk_len
    if current_batch:
        batches.append("\n".join(current_batch))
    return batches

class HeartbeatMonitor:
    def __init__(self, timeout=HEARTBEAT_TIMEOUT_SEC):
        self.timeout = timeout
        self.timer = None
    def _stall_abort(self):
        print("\n[NETWORK STALL ALERT] API connection hung for over 5 minutes. Forcing exit to trigger fail-safe reboot.")
        import os
        os._exit(1)
    def ping(self):
        if self.timer: self.timer.cancel()
        self.timer = threading.Timer(self.timeout, self._stall_abort)
        self.timer.start()
    def stop(self):
        if self.timer: self.timer.cancel()

heartbeat = HeartbeatMonitor(HEARTBEAT_TIMEOUT_SEC)

def _filter_streaming_inline_image_payload(text, state):
    if not text:
        return ""
    if state is None:
        return text

    result = []
    idx = 0
    while idx < len(text):
        if state.get("suppressing"):
            quote = state.get("quote", '"')
            close_idx = text.find(quote, idx)
            if close_idx == -1:
                return "".join(result)
            result.append(quote)
            idx = close_idx + 1
            state["suppressing"] = False
            state["quote"] = '"'
            continue

        match = re.search(
            r'(?is)(src\s*=\s*)(["\'])(?:data:image\/[a-z0-9.+-]+;base64,|about:blank)',
            text[idx:],
        )
        if not match:
            result.append(text[idx:])
            break
        start = idx + match.start()
        end = idx + match.end()
        result.append(text[idx:start])
        result.append(f"{match.group(1)}{match.group(2)}about:blank")
        quote = match.group(2)
        close_idx = text.find(quote, end)
        if close_idx == -1:
            state["suppressing"] = True
            state["quote"] = quote
            return "".join(result)
        result.append(quote)
        idx = close_idx + 1
    return "".join(result)

def handle_stream(response, output_path, format_type, file_obj=None, memory_list=None, profile_key=None):
    global heartbeat
    heartbeat.ping()
    emitted = []
    total_chars = 0
    inline_image_state = {"suppressing": False, "quote": '"'} if format_type in ("html", "epub") else None
    try:
        if isinstance(response, str) or (hasattr(response, "text") and getattr(response, "text")):
            text_val = response if isinstance(response, str) else response.text
            if inline_image_state is not None:
                text_val = _filter_streaming_inline_image_payload(text_val, inline_image_state)
            clean_chunk = sanitize_model_output(clean_text_artifacts(text_val), format_type)
            emitted.append(clean_chunk)
            append_generated_text(format_type, file_obj=file_obj, memory_list=memory_list, text=clean_chunk)
            return "".join(emitted)
        for chunk in response:
            heartbeat.ping()
            text_val = ""
            if hasattr(chunk, 'text') and chunk.text: text_val = chunk.text
            elif hasattr(chunk, 'type') and chunk.type == 'content_block_delta': text_val = chunk.delta.text
            elif hasattr(chunk, 'choices') and len(chunk.choices) > 0 and chunk.choices[0].delta.content: text_val = chunk.choices[0].delta.content
            
            if text_val:
                if inline_image_state is not None:
                    text_val = _filter_streaming_inline_image_payload(text_val, inline_image_state)
                clean_chunk = sanitize_model_output(clean_text_artifacts(text_val), format_type)
                emitted.append(clean_chunk)
                total_chars += len(clean_chunk)
                append_generated_text(format_type, file_obj=file_obj, memory_list=memory_list, text=clean_chunk)
                if profile_key == "newspaper" and format_type == "html" and total_chars >= 12000:
                    notice = core_build_newspaper_safety_notice(format_type)
                    if notice:
                        append_generated_text(format_type, file_obj=file_obj, memory_list=memory_list, text="\n" + notice)
                        emitted.append("\n" + notice)
                    break
    finally:
        heartbeat.stop()
    return "".join(emitted)

def stream_with_cache(cache_key, request_fn, output_path, format_type, file_obj=None, memory_list=None, profile_key=None):
    cached = cache_get(cache_key)
    if cached is not None:
        append_generated_text(format_type, file_obj=file_obj, memory_list=memory_list, text=cached)
        return cached
    cleanup_fn = None
    request_result = request_fn()
    if (
        isinstance(request_result, tuple)
        and len(request_result) == 2
        and callable(request_result[1])
    ):
        response, cleanup_fn = request_result
    else:
        response = request_result
    try:
        generated = handle_stream(
            response,
            output_path,
            format_type,
            file_obj=file_obj,
            memory_list=memory_list,
            profile_key=profile_key,
        )
        cache_put(cache_key, generated)
        return generated
    finally:
        if cleanup_fn:
            cleanup_fn()

def play_completion_sound():
    print("\nProcessing complete!")
    if platform.system() == "Darwin":
        subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    elif platform.system() == "Windows":
        subprocess.Popen([
            "PowerShell",
            "-Command",
            "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\notify.wav').PlaySync();"
        ])

def get_pdf_chunk_pages(model_name, profile_key, total_pages, default_chunk_pages=PDF_CHUNK_PAGES, *, file_size_mb=None):
    model_name = str(model_name or "").lower()
    profile_key = str(profile_key or "")
    avg_page_mb = None
    if file_size_mb is not None and total_pages:
        try:
            avg_page_mb = float(file_size_mb) / max(1, int(total_pages))
        except (TypeError, ValueError):
            avg_page_mb = None
    if profile_key in {"newspaper", "modern_newspaper", "magazine"} and avg_page_mb is not None and avg_page_mb >= 0.9:
        return 1
    if "claude" in model_name or "gpt" in model_name:
        return 1
    if profile_key in {"newspaper", "modern_newspaper", "magazine"} and total_pages >= 24:
        return 2
    if profile_key in {"legal", "government"}:
        if total_pages >= 150:
            return 1
        if "gemini-2.5-pro" in model_name and total_pages >= 60:
            return 2
    if total_pages >= 60:
        return 2
    return min(2, max(1, int(default_chunk_pages)))


def process_pdf(client, pdf_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    profile_key = "newspaper" if "HISTORICAL NEWSPAPER RULES" in prompt_text else None
    if "MODERN NEWSPAPER / E-PAPER RULES" in prompt_text:
        profile_key = "modern_newspaper"
    allow_text_layer_fallback = os.environ.get("CHRONICLE_ALLOW_PDF_TEXT_LAYER_FALLBACK") == "1"

    doc = fitz.open(pdf_path)
    try:
        total_pages = len(doc)
        current_page = 0

        while current_page < total_pages:
            image_bytes = _render_pdf_page_to_png_bytes(doc, current_page)
            temp_png = _write_temp_png("chronicle_cli_pdf_page_", image_bytes)
            page_fingerprint = sha256_text(image_bytes.hex())

            try:
                if "claude" in model_name or "gpt" in model_name:
                    payload = build_multimodal_payload(model_name, prompt_text, temp_png, "image/png")
                    cache_key = build_request_cache_key(
                        model_name, prompt_text, "pdf-vision", f"{current_page}:{page_fingerprint}"
                    )
                    stream_with_cache(
                        cache_key,
                        lambda: generate_with_retry(client, model_name, payload),
                        output_path,
                        format_type,
                        file_obj=file_obj,
                        memory_list=memory_list,
                        profile_key=profile_key,
                    )
                else:
                    cache_key = build_request_cache_key(
                        model_name, prompt_text, "pdf-upload", f"{current_page}:{page_fingerprint}"
                    )

                    def _gemini_pdf_request():
                        uploaded = client.files.upload(file=temp_png)
                        uploaded = wait_for_gemini_upload_ready(client, uploaded)
                        response = generate_with_retry(client, model_name, [uploaded, prompt_text])

                        def _cleanup_upload():
                            try:
                                client.files.delete(name=uploaded.name)
                            except Exception as cleanup_ex:
                                print(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")

                        return response, _cleanup_upload

                    stream_with_cache(
                        cache_key,
                        _gemini_pdf_request,
                        output_path,
                        format_type,
                        file_obj=file_obj,
                        memory_list=memory_list,
                        profile_key=profile_key,
                    )
            except Exception as e:
                print(f"\n[Gearshift Triggered] Error processing page {current_page + 1}: {e}")
                if not allow_text_layer_fallback:
                    raise RuntimeError(
                        f"PDF vision/model processing failed for page {current_page + 1}, "
                        "and PDF text-layer emergency fallback is disabled."
                    ) from e
                print(f"\n[CRITICAL FAILURE] Single page vision failed for page {current_page + 1}. Initiating user-enabled emergency text-layer fallback.")
                fallback_text = doc.load_page(current_page).get_text("text") or "[Unreadable Image Layer]"
                payload = fallback_text + "\n\n" + prompt_text if ("claude" in model_name or "gpt" in model_name) else [fallback_text, prompt_text]
                cache_key = build_request_cache_key(
                    model_name, prompt_text, "pdf-text-fallback", sha256_text(fallback_text)
                )
                stream_with_cache(
                    cache_key,
                    lambda: generate_with_retry(client, model_name, payload),
                    output_path,
                    format_type,
                    file_obj=file_obj,
                    memory_list=memory_list,
                    profile_key=profile_key,
                )
            finally:
                if os.path.exists(temp_png):
                    os.remove(temp_png)
            current_page += 1
            if current_page > 0 and current_page % 2 == 0:
                gc.collect()
    finally:
        doc.close()

def process_text_document(client, file_path, output_path, ext, format_type, prompt_text, model_name, file_obj, memory_list):
    profile_key = "newspaper" if "HISTORICAL NEWSPAPER RULES" in prompt_text else None
    if "MODERN NEWSPAPER / E-PAPER RULES" in prompt_text:
        profile_key = "modern_newspaper"
    is_tabular_html = "TABULAR DATA & SPREADSHEETS RULES" in prompt_text and format_type == "html"
    if is_tabular_html and ext in ('.csv', '.tsv', '.xlsx'):
        datasets = []
        if ext in ('.csv', '.tsv'):
            raw_csv = open(file_path, 'r', encoding='utf-8', errors='ignore').read()
            rows = core_parse_csv_rows(raw_csv.replace("\t", ",") if ext == '.tsv' else raw_csv)
            if rows:
                datasets.append({
                    "name": "Table Data",
                    "headers": [str(cell).strip() for cell in rows[0]],
                    "rows": [[str(cell).strip() for cell in row] for row in rows[1:]],
                })
        elif ext == '.xlsx' and openpyxl is not None:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            for name in wb.sheetnames:
                rows = []
                for row in wb[name].iter_rows(values_only=True):
                    values = ["" if cell is None else str(cell).strip() for cell in row]
                    if any(values):
                        rows.append(values)
                if rows:
                    datasets.append({"name": name, "headers": rows[0], "rows": rows[1:]})
        if datasets:
            fragment = core_build_tabular_html_fragment(os.path.splitext(os.path.basename(file_path))[0], datasets)
            if file_obj:
                file_obj.write(fragment)
                file_obj.flush()
            if memory_list is not None:
                memory_list.append(fragment)
            return
    full_text = ""
    if ext == '.docx':
        full_text = "\n".join([p.text for p in docx.Document(file_path).paragraphs])
    elif ext in ('.csv', '.tsv'):
        raw_csv = open(file_path, 'r', encoding='utf-8', errors='ignore').read()
        full_text = csv_to_accessible_text(raw_csv.replace("\t", ",") if ext == '.tsv' else raw_csv)
    elif ext == '.xlsx':
        wb = openpyxl.load_workbook(file_path, data_only=True)
        for name in wb.sheetnames:
            full_text += f"\n[--- Tab: {name} ---]\n"
            for row in wb[name].iter_rows(values_only=True):
                if any(c for c in row if str(c).strip()):
                    full_text += " | ".join([str(c) if c else "" for c in row]) + "\n"
    else:
        full_text = open(file_path, 'r', encoding='utf-8', errors='ignore').read()
    
    scrubbed_text = clean_text_artifacts(full_text)
    
    chunks, current = [], ""
    for p in scrubbed_text.split('\n'):
        if len(current) + len(p) > TEXT_CHUNK_CHARS and current:
            chunks.append(current)
            current = p + "\n"
        else:
            current += p + "\n"
    if current:
        chunks.append(current)
    batches = batch_text_chunks(chunks)
    for chunk in batches:
        payload = chunk + "\n\n" + prompt_text if ("claude" in model_name or "gpt" in model_name) else [chunk, prompt_text]
        cache_key = build_request_cache_key(model_name, prompt_text, "text", sha256_text(chunk))
        stream_with_cache(
            cache_key,
            lambda: generate_with_retry(client, model_name, payload),
            output_path,
            format_type,
            file_obj=file_obj,
            memory_list=memory_list,
            profile_key=profile_key,
        )

def process_fitz_text_document_cli(client, file_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    if fitz is None:
        raise RuntimeError("This ebook format requires PyMuPDF.")
    doc = fitz.open(file_path)
    try:
        full_text = ""
        for page_index in range(len(doc)):
            text = doc[page_index].get_text("text")
            if text.strip():
                full_text += f"\n[--- Page: {page_index + 1} ---]\n{text}\n"
    finally:
        doc.close()
    scrubbed_text = clean_text_artifacts(full_text)
    chunks = [scrubbed_text[i:i + TEXT_CHUNK_CHARS] for i in range(0, len(scrubbed_text), TEXT_CHUNK_CHARS)]
    for chunk in batch_text_chunks(chunks or [""]):
        payload = chunk + "\n\n" + prompt_text if ("claude" in model_name or "gpt" in model_name) else [chunk, prompt_text]
        cache_key = build_request_cache_key(model_name, prompt_text, "fitz-text", sha256_text(chunk))
        stream_with_cache(
            cache_key,
            lambda: generate_with_retry(client, model_name, payload),
            output_path,
            format_type,
            file_obj=file_obj,
            memory_list=memory_list,
        )

def process_image(client, file_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    profile_key = "newspaper" if "HISTORICAL NEWSPAPER RULES" in prompt_text else None
    if "MODERN NEWSPAPER / E-PAPER RULES" in prompt_text:
        profile_key = "modern_newspaper"
    staged_path = prepare_image_for_scan(file_path, log_cb=print)
    enhanced_path = enhance_image_for_microtext(staged_path)
    try:
        if "claude" in model_name or "gpt" in model_name:
            payload = build_multimodal_payload(model_name, prompt_text, enhanced_path, "image/png")
            cache_key = build_request_cache_key(model_name, prompt_text, "image", sha256_file(enhanced_path))
            stream_with_cache(
                cache_key,
                lambda: generate_with_retry(client, model_name, payload),
                output_path,
                format_type,
                file_obj=file_obj,
                memory_list=memory_list,
                profile_key=profile_key,
            )
        else:
            cache_key = build_request_cache_key(model_name, prompt_text, "image-upload", sha256_file(enhanced_path))
            def _gemini_image_request():
                uploaded = client.files.upload(file=enhanced_path)
                uploaded = wait_for_gemini_upload_ready(client, uploaded, poll_sec=2.0)
                response = generate_with_retry(client, model_name, [uploaded, prompt_text])
                def _cleanup_upload():
                    try:
                        client.files.delete(name=uploaded.name)
                    except Exception as cleanup_ex:
                        print(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")
                return response, _cleanup_upload
            stream_with_cache(
                cache_key,
                _gemini_image_request,
                output_path,
                format_type,
                file_obj=file_obj,
                memory_list=memory_list,
                profile_key=profile_key,
            )
    finally:
        for cleanup_path in (enhanced_path, staged_path):
            if cleanup_path != file_path:
                try:
                    os.remove(cleanup_path)
                except FileNotFoundError:
                    pass

def process_rendered_document_cli(client, file_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    if fitz is None:
        raise RuntimeError("Renderable document support requires PyMuPDF.")
    doc = fitz.open(file_path)
    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            temp_png = _write_temp_png("chronicle_cli_rendered_doc_", pix.tobytes("png"))
            try:
                page_prompt = (
                    f"{prompt_text}\n\nRENDERED DOCUMENT PAGE MODE:\n"
                    f"- This is page {page_index + 1} of {len(doc)} rendered from {os.path.basename(file_path)}.\n"
                    "- Read the visible page image faithfully and preserve meaningful reading order."
                )
                process_image(client, temp_png, output_path, format_type, page_prompt, model_name, file_obj, memory_list)
            finally:
                if os.path.exists(temp_png):
                    os.remove(temp_png)
    finally:
        doc.close()

def wait_for_gemini_upload_ready(client, uploaded, poll_sec=GEMINI_UPLOAD_POLL_SEC, max_wait_sec=GEMINI_UPLOAD_MAX_WAIT_SEC, time_fn=time.time, sleep_fn=time.sleep, log_cb=print):
    start = time_fn()
    next_log_at = 0.0
    current = uploaded
    while getattr(getattr(current, "state", None), "name", "") == "PROCESSING":
        elapsed = max(0.0, time_fn() - start)
        if elapsed >= max_wait_sec:
            raise TimeoutError(
                f"Google file preparation exceeded {int(max_wait_sec)} seconds for {getattr(current, 'name', 'upload')}."
            )
        if elapsed >= next_log_at:
            log_cb(
                f"[Upload Processing] Waiting for Google to prepare {getattr(current, 'name', 'upload')} ({elapsed:.0f}s elapsed)..."
            )
            next_log_at += 15.0
        sleep_fn(min(poll_sec, max_wait_sec - elapsed))
        current = client.files.get(name=current.name)
    if getattr(getattr(current, "state", None), "name", "") == "FAILED":
        raise Exception("Google API failed to process the uploaded document.")
    return current

def generate_with_retry(client, model_name, contents, max_retries=API_MAX_RETRIES, base_delay=API_BACKOFF_BASE_SEC):
    import time
    for attempt in range(max_retries):
        try:
            wait_for_request_slot()
            try:
                pace_api_request()
                if "claude" in model_name:
                    return client.messages.create(
                        model=model_name,
                        max_tokens=8192,
                        messages=[{"role": "user", "content": contents}],
                        stream=True,
                        extra_headers={"anthropic-beta": "pdfs-2024-09-25"},
                    )
                if "gpt" in model_name:
                    return client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": contents}],
                        stream=True,
                    )
                return client.models.generate_content_stream(model=model_name, contents=contents)
            finally:
                release_request_slot()
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "unauthorized" in error_str or "invalid api key" in error_str or "authentication" in error_str:
                raise Exception("Authentication failed (401/invalid API key). Check your API key for the selected engine.")
            if is_connection_path_error(e):
                print(
                    f"\n[Polite Backoff] Connection path unavailable. Waiting {API_CONNECTION_FAILURE_DELAY_SEC:.0f}s "
                    "before giving up to avoid hammering the service."
                )
                time.sleep(API_CONNECTION_FAILURE_DELAY_SEC)
                raise Exception(
                    "Connection path unavailable. Chronicle stopped retrying to avoid hammering the API service."
                ) from e
            if "429" in error_str or "exhausted" in error_str or "quota" in error_str or "overloaded" in error_str:
                delay = min(API_BACKOFF_MAX_SEC, base_delay * (2 ** attempt))
                print(f"\n[API Rate Limit Hit] Backing off for {delay} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
            else:
                raise e
    raise Exception("Max retries exceeded. API is fundamentally unresponsive.")

def build_multimodal_payload(model_name, prompt_text, file_path=None, mime_type="image/png"):
    import base64
    if not file_path:
        return prompt_text
    with open(file_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode('utf-8')
    if "claude" in model_name:
        if "pdf" in mime_type:
            return [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64_data}},
                {"type": "text", "text": prompt_text},
            ]
        return [
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64_data}},
            {"type": "text", "text": prompt_text},
        ]
    if "gpt" in model_name:
        if "pdf" in mime_type:
            raise Exception("GPT-4o engine rejected Base64 PDF. Forcing sentence-level text fallback.")
        return [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}},
        ]
    return None

def process_pptx_document(client, file_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    import pptx
    try:
        from pptx.enum.shape import MSO_SHAPE_TYPE
    except ImportError:
        MSO_SHAPE_TYPE = None

    # Gemini can process native PPTX uploads; use this first to preserve visual context.
    if "claude" not in model_name and "gpt" not in model_name:
        upload_cache_key = build_request_cache_key(model_name, prompt_text, "pptx-upload", sha256_file(file_path))
        try:
            def _gemini_pptx_request():
                uploaded = client.files.upload(file=file_path)
                try:
                    while getattr(getattr(uploaded, "state", None), "name", "") == "PROCESSING":
                        time.sleep(2)
                        uploaded = client.files.get(name=uploaded.name)
                    if getattr(getattr(uploaded, "state", None), "name", "") == "FAILED":
                        raise Exception("Google API failed to process the PPTX document.")
                except Exception as poll_ex:
                    print(f"Warning: PPTX upload polling failed ({poll_ex}); attempting generation anyway.")
                response = generate_with_retry(client, model_name, [uploaded, prompt_text])
                def _cleanup_upload():
                    try:
                        client.files.delete(name=uploaded.name)
                    except Exception as cleanup_ex:
                        print(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")
                return response, _cleanup_upload

            stream_with_cache(
                upload_cache_key,
                _gemini_pptx_request,
                output_path,
                format_type,
                file_obj=file_obj,
                memory_list=memory_list,
            )
            return
        except Exception as upload_ex:
            print(f"Warning: native PPTX vision failed ({upload_ex}); falling back to structured slide extraction.")

    prs = pptx.Presentation(file_path)
    full_text = ""
    slide_num = 1
    for slide in prs.slides:
        full_text += f"\n[--- Slide: {slide_num} ---]\n"
        try:
            if slide.has_notes_slide and slide.notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = (slide.notes_slide.notes_text_frame.text or "").strip()
                if notes_text:
                    full_text += f"[Slide Notes]\n{notes_text}\n"
        except Exception:
            pass
        try:
            shapes = sorted(slide.shapes, key=lambda s: (s.top, s.left))
        except Exception:
            shapes = slide.shapes
        for shape_idx, shape in enumerate(shapes, start=1):
            shape_name = (getattr(shape, "name", "") or "").strip()
            shape_label = f"Slide {slide_num} Shape {shape_idx}"
            if shape_name:
                shape_label += f" ({shape_name})"

            if getattr(shape, "has_text_frame", False):
                shape_text = (getattr(shape, "text", "") or "").strip()
                if shape_text:
                    full_text += shape_text + "\n"

            if getattr(shape, "has_table", False):
                full_text += f"[Table Object: {shape_label}]\n"
                try:
                    for row in shape.table.rows:
                        row_vals = []
                        for cell in row.cells:
                            row_vals.append((cell.text or "").replace("\n", " ").strip())
                        full_text += " | ".join(row_vals) + "\n"
                except Exception:
                    full_text += "[Table content unreadable]\n"

            if getattr(shape, "has_chart", False):
                full_text += f"[Chart Object: {shape_label}]\n"
                try:
                    chart = shape.chart
                    full_text += f"Chart Type: {chart.chart_type}\n"
                    try:
                        if chart.has_title and chart.chart_title and chart.chart_title.text_frame:
                            chart_title = (chart.chart_title.text_frame.text or "").strip()
                            if chart_title:
                                full_text += f"Chart Title: {chart_title}\n"
                    except Exception:
                        pass
                    categories = []
                    try:
                        categories = [str(cat) for cat in chart.plots[0].categories]
                    except Exception:
                        categories = []
                    if categories:
                        full_text += "Categories: " + " | ".join(categories) + "\n"
                    for series_idx, series in enumerate(chart.series, start=1):
                        try:
                            series_name = str(series.name)
                        except Exception:
                            series_name = f"Series {series_idx}"
                        try:
                            values = [str(v) for v in series.values]
                        except Exception:
                            values = []
                        if values:
                            full_text += f"{series_name}: " + " | ".join(values) + "\n"
                        else:
                            full_text += f"{series_name}: [No numeric values extracted]\n"
                except Exception:
                    full_text += "[Chart metadata unreadable]\n"

            shape_type = getattr(shape, "shape_type", None)
            visual_shape_types = {
                getattr(MSO_SHAPE_TYPE, "GROUP", None),
                getattr(MSO_SHAPE_TYPE, "DIAGRAM", None),
                getattr(MSO_SHAPE_TYPE, "CANVAS", None),
                getattr(MSO_SHAPE_TYPE, "LINKED_PICTURE", None),
            }
            if MSO_SHAPE_TYPE is not None and shape_type == MSO_SHAPE_TYPE.PICTURE:
                full_text += f"[Image Object: {shape_label}]\n"
            elif shape_type in visual_shape_types:
                full_text += f"[Visual Object: {shape_label}; Type={shape_type}]\n"
        slide_num += 1
    
    scrubbed_input = clean_text_artifacts(full_text)
    chunks = [scrubbed_input[i:i+TEXT_CHUNK_CHARS] for i in range(0, len(scrubbed_input), TEXT_CHUNK_CHARS)]
    
    batches = batch_text_chunks(chunks)
    for chunk in batches:
        payload = chunk + "\n\n" + prompt_text if ("claude" in model_name or "gpt" in model_name) else [chunk, prompt_text]
        cache_key = build_request_cache_key(model_name, prompt_text, "pptx", sha256_text(chunk))
        stream_with_cache(
            cache_key,
            lambda: generate_with_retry(client, model_name, payload),
            output_path,
            format_type,
            file_obj=file_obj,
            memory_list=memory_list,
        )

def main():
    raise SystemExit("Chronicle's legacy CLI has been retired. Run the desktop GUI with `python chronicle_gui.py`.")


if __name__ == "__main__":
    main()
