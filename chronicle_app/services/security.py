import re


SENSITIVE_KEY_PARTS = ("api", "key", "token", "secret", "password", "credential")

SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)(x-goog-api-key\s*[:=]\s*)[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)(key=)[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(
        r"-----BEGIN (?:RSA|EC|OPENSSH|DSA)? ?PRIVATE KEY-----.*?"
        r"-----END (?:RSA|EC|OPENSSH|DSA)? ?PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def sanitize_log_text(value):
    text = str(value)
    for pattern in SECRET_PATTERNS:
        def repl(match):
            if match.lastindex:
                return f"{match.group(1)}[redacted]"
            return "[redacted]"

        text = pattern.sub(repl, text)
    return text


def redact_sensitive(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS):
                redacted[key] = "[redacted]" if item else ""
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return sanitize_log_text(value)
    return value
