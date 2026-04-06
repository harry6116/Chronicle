import base64
import hashlib
import os
import random
import threading
import time
from collections import OrderedDict

from chronicle_app.services.runtime_policies import normalize_model_name

CLAUDE_FILES_API_BETA = "files-api-2025-04-14"


class HeartbeatMonitor:
    def __init__(self, timeout=300, exit_fn=None, print_fn=print, timer_cls=threading.Timer):
        self.timeout = timeout
        self._exit_fn = exit_fn
        self._print_fn = print_fn
        self._timer_cls = timer_cls
        self.timer = None

    def _stall_abort(self):
        self._print_fn("\n[NETWORK STALL ALERT] API connection hung for over 5 minutes. Forcing fail-safe reboot.")
        if self._exit_fn is not None:
            self._exit_fn(1)

    def ping(self):
        if self.timer:
            self.timer.cancel()
        self.timer = self._timer_cls(self.timeout, self._stall_abort)
        self.timer.start()

    def stop(self):
        if self.timer:
            self.timer.cancel()


class RequestRuntime:
    def __init__(
        self,
        *,
        api_min_request_interval_sec,
        api_max_pending_requests,
        api_request_queue_poll_sec,
        api_max_concurrent_requests,
        api_cache_max_entries,
    ):
        self.api_min_request_interval_sec = api_min_request_interval_sec
        self.api_max_pending_requests = api_max_pending_requests
        self.api_request_queue_poll_sec = api_request_queue_poll_sec
        self.api_cache_max_entries = api_cache_max_entries
        self._api_request_lock = threading.Lock()
        self._last_api_request_ts = 0.0
        self._api_request_semaphore = threading.Semaphore(api_max_concurrent_requests)
        self._api_queue_lock = threading.Lock()
        self._api_pending_requests = 0
        self._chunk_cache = OrderedDict()
        self._chunk_cache_lock = threading.Lock()

    def pace_api_request(self, log_cb=print, *, time_module=time):
        with self._api_request_lock:
            now = time_module.time()
            wait = self.api_min_request_interval_sec - (now - self._last_api_request_ts)
            if wait > 0:
                log_cb(f"[Throttle] Waiting {wait:.1f}s before next API request.")
                time_module.sleep(wait)
            self._last_api_request_ts = time_module.time()

    def cache_get(self, cache_key):
        with self._chunk_cache_lock:
            value = self._chunk_cache.get(cache_key)
            if value is None:
                return None
            self._chunk_cache.move_to_end(cache_key)
            return value

    def cache_put(self, cache_key, text):
        if not text:
            return
        with self._chunk_cache_lock:
            self._chunk_cache[cache_key] = text
            self._chunk_cache.move_to_end(cache_key)
            while len(self._chunk_cache) > self.api_cache_max_entries:
                self._chunk_cache.popitem(last=False)

    def wait_for_request_slot(self, log_cb=print, *, time_module=time):
        warned = False
        while True:
            with self._api_queue_lock:
                if self._api_pending_requests < self.api_max_pending_requests:
                    self._api_pending_requests += 1
                    break
            if not warned:
                log_cb(f"[Backpressure] API queue full ({self.api_max_pending_requests}). Waiting for capacity...")
                warned = True
            time_module.sleep(self.api_request_queue_poll_sec)
        self._api_request_semaphore.acquire()
        with self._api_queue_lock:
            self._api_pending_requests = max(0, self._api_pending_requests - 1)

    def release_request_slot(self):
        self._api_request_semaphore.release()


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


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def build_request_cache_key(model, prompt, payload_kind, payload_fingerprint):
    return f"{model}|{payload_kind}|{sha256_text(prompt)}|{payload_fingerprint}"


def handle_stream(
    response,
    output_path,
    fmt_type,
    file_obj,
    memory,
    log_cb,
    *,
    pause_cb=None,
    heartbeat=None,
    sanitize_model_output_fn,
    clean_text_fn,
):
    if heartbeat is not None:
        heartbeat.ping()
    raw_parts = []
    try:
        for chunk in response:
            if pause_cb:
                pause_cb()
            if heartbeat is not None:
                heartbeat.ping()
            text = ""
            if hasattr(chunk, "text") and chunk.text:
                text = chunk.text
            elif hasattr(chunk, "type") and chunk.type == "content_block_delta":
                text = chunk.delta.text
            elif hasattr(chunk, "choices") and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
            if text:
                raw_parts.append(text)
    finally:
        if heartbeat is not None:
            heartbeat.stop()
    raw_text = "".join(raw_parts)
    cleaned = sanitize_model_output_fn(clean_text_fn(raw_text), fmt_type)
    if fmt_type in ["html", "txt", "md"] and file_obj and cleaned:
        file_obj.write(cleaned)
        file_obj.flush()
    if memory is not None and cleaned:
        memory.append(cleaned)
    return cleaned


def stream_with_cache(
    cache_key,
    request_fn,
    output_path,
    fmt,
    file_obj,
    memory,
    log_cb,
    *,
    pause_cb=None,
    runtime,
    append_generated_text_fn,
    handle_stream_fn,
):
    cached = runtime.cache_get(cache_key)
    if cached is not None:
        log_cb("[Cache] Reusing previously processed chunk.")
        append_generated_text_fn(fmt, file_obj, memory, cached)
        return cached
    cleanup_fn = None
    request_result = request_fn()
    if isinstance(request_result, tuple) and len(request_result) == 2 and callable(request_result[1]):
        response, cleanup_fn = request_result
    else:
        response = request_result
    try:
        generated = handle_stream_fn(response, output_path, fmt, file_obj, memory, log_cb, pause_cb=pause_cb)
        runtime.cache_put(cache_key, generated)
        return generated
    finally:
        if cleanup_fn:
            cleanup_fn()


def generate_retry(
    client,
    model,
    contents,
    *,
    runtime,
    max_r,
    delay,
    backoff_max_sec,
    log_cb=print,
    time_module=time,
    random_module=random,
):
    model = normalize_model_name(model)
    for attempt in range(max_r):
        try:
            runtime.wait_for_request_slot(log_cb=log_cb, time_module=time_module)
            try:
                runtime.pace_api_request(log_cb=log_cb, time_module=time_module)
                if "claude" in model:
                    if isinstance(contents, dict) and contents.get("_chronicle_claude_request") == "message":
                        request_kwargs = {
                            "model": model,
                            "max_tokens": 8192,
                            "messages": [{"role": "user", "content": contents.get("content", "")}],
                            "stream": True,
                        }
                        betas = list(contents.get("betas") or [])
                        if betas and hasattr(client, "beta") and hasattr(client.beta, "messages"):
                            return client.beta.messages.create(**request_kwargs, betas=betas)
                        return client.messages.create(**request_kwargs)
                    return client.messages.create(
                        model=model,
                        max_tokens=8192,
                        messages=[{"role": "user", "content": contents}],
                        stream=True,
                    )
                if "gpt" in model:
                    return client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": contents}],
                        stream=True,
                    )
                return client.models.generate_content_stream(model=model, contents=contents)
            finally:
                runtime.release_request_slot()
        except Exception as exc:
            err = str(exc).lower()
            if any(x in err for x in ["401", "unauthorized", "invalid api key", "authentication"]):
                raise Exception("Authentication failed (401/invalid API key). Check your API key in API Keys.")
            if any(x in err for x in ["429", "exhausted", "quota", "overloaded", "503", "timeout", "temporarily unavailable"]):
                jitter = random_module.uniform(0.2, 1.2)
                wait = min(backoff_max_sec, delay * (2 ** attempt)) + jitter
                log_cb(f"[Rate Limit] Backing off {wait:.1f}s (Attempt {attempt+1}/{max_r})...")
                time_module.sleep(wait)
            else:
                raise exc
    raise Exception("Max retries exceeded. API unresponsive.")


def build_payload(model, prompt, file_path=None, mime="image/png", file_bytes=None):
    if not file_path and file_bytes is None:
        return prompt
    if file_bytes is None:
        with open(file_path, "rb") as fh:
            file_bytes = fh.read()
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    if "claude" in model:
        payload_type = "document" if "pdf" in mime else "image"
        return [
            {"type": payload_type, "source": {"type": "base64", "media_type": mime, "data": b64}},
            {"type": "text", "text": prompt},
        ]
    if "gpt" in model:
        if "pdf" in mime:
            raise Exception("GPT-4o cannot read Base64 PDF. Forcing text fallback.")
        return [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]
    return None
