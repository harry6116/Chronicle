"""Fetch model metadata from the selected provider's official HTTPS API."""

import json
from urllib.parse import urlencode
from urllib.request import Request

from chronicle_app.config import MODEL_OVERRIDE_CHOICES
from chronicle_app.services.runtime_policies import get_model_vendor
from chronicle_app.services.security import sanitize_log_text
from chronicle_app.services.provider_transport import PROVIDER_ORIGINS, provider_url_opener


ENDPOINTS = {
    "gemini": PROVIDER_ORIGINS["gemini"] + "/v1beta/models",
    "openai": PROVIDER_ORIGINS["openai"] + "/v1/models",
    "claude": PROVIDER_ORIGINS["claude"] + "/v1/models",
}


def discover_models(provider, key, *, opener=None):
    if not key or provider not in ENDPOINTS:
        raise ValueError("Choose a provider with a configured API key.")
    headers = {"Accept": "application/json"}
    if provider == "gemini":
        headers["x-goog-api-key"] = key
    elif provider == "claude":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = f"Bearer {key}"
    opener = opener or provider_url_opener()
    models = set()
    params = {}
    for _ in range(12):
        url = ENDPOINTS[provider] + ("?" + urlencode(params) if params else "")
        with opener.open(Request(url, headers=headers), timeout=12) as response:
            payload = json.loads(response.read(2_000_000))
        if provider == "gemini":
            for model in payload.get("models", []):
                if "generateContent" in model.get("supportedGenerationMethods", []):
                    name = model.get("name", "").removeprefix("models/")
                    if name:
                        models.add(name)
            page = payload.get("nextPageToken")
            params = {"pageToken": page} if page else {}
        else:
            models.update(model["id"] for model in payload.get("data", []) if model.get("id"))
            page = payload.get("last_id") if payload.get("has_more") else None
            params = {"after_id": page} if page else {}
        if not params:
            break
    return sorted(models)


def describe_models(provider, models, plan):
    matching = [(model, label) for model, label in MODEL_OVERRIDE_CHOICES
                if model in models and get_model_vendor(model) == provider]
    lines = ["Models listed by the provider and selectable in Chronicle.", ""]
    lines.extend(f"• {label} ({model})" for model, label in matching)
    if not matching:
        lines.append("No returned model matched a Chronicle engine.")
    labels = [label for model, label in matching if "flash" in model.lower()]
    deep = [label for model, label in matching if any(word in model.lower() for word in ("pro", "argon"))]
    lines.extend(["", f"API plan selected for advice: {plan}. Model listing does not verify billing or quota."])
    if provider == "gemini":
        if labels:
            lines.append(f"For straightforward text and a limited quota, start with {labels[0]} if your project allows it.")
        if deep and plan == "Paid API":
            lines.append(f"For difficult scans, compare a few representative pages using {deep[0]} before committing a batch.")
        if plan != "Paid API":
            lines.append("Check the project’s eligibility and model-specific free-tier limits in Google AI Studio.")
    elif matching:
        lines.append(f"Try {matching[0][1]} on a small representative sample. Verify API credits and permissions in the provider console.")
    lines.extend(["", "Other models reported by this provider may be outside Chronicle’s supported engine list."])
    compatible = {model for model, _ in matching}
    lines.extend(sanitize_log_text(model) for model in models if model not in compatible)
    return "\n".join(lines)
