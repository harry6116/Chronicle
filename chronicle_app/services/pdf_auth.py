import os


PDF_PASSWORD_ENV = "CHRONICLE_PDF_PASSWORD"
PDF_PASSWORD_CACHE_MAX_ENTRIES = 32
_PDF_PASSWORD_CACHE = {}


class PdfPasswordRequiredError(RuntimeError):
    pass


class PdfPasswordInvalidError(RuntimeError):
    pass


def _cache_key(path):
    try:
        return os.path.abspath(os.path.expanduser(str(path)))
    except Exception:
        return str(path)


def clear_cached_pdf_password(path=None):
    if path is None:
        _PDF_PASSWORD_CACHE.clear()
        return
    _PDF_PASSWORD_CACHE.pop(_cache_key(path), None)


def get_cached_pdf_password(path):
    key = _cache_key(path)
    if key not in _PDF_PASSWORD_CACHE:
        return None, False
    return _PDF_PASSWORD_CACHE[key], True


def remember_pdf_password(path, password):
    key = _cache_key(path)
    if key in _PDF_PASSWORD_CACHE:
        _PDF_PASSWORD_CACHE.pop(key, None)
    _PDF_PASSWORD_CACHE[key] = password or ""
    while len(_PDF_PASSWORD_CACHE) > PDF_PASSWORD_CACHE_MAX_ENTRIES:
        oldest_key = next(iter(_PDF_PASSWORD_CACHE), None)
        if oldest_key is None:
            break
        _PDF_PASSWORD_CACHE.pop(oldest_key, None)


def _needs_password(document):
    value = getattr(document, "needs_pass", False)
    return bool(value() if callable(value) else value)


def _authenticate(document, password):
    result = document.authenticate(password or "")
    return bool(result)


def authenticate_pdf_document(document, path, *, password=None, password_provider=None):
    """Authenticate a PyMuPDF document and return the password that worked."""
    if not _needs_password(document):
        return None

    env_password = os.environ.get(PDF_PASSWORD_ENV)
    explicit_password = password if password is not None else env_password
    tried = []

    def try_password(candidate):
        if candidate in tried:
            return False
        tried.append(candidate)
        try:
            return _authenticate(document, candidate)
        except Exception:
            return False

    if explicit_password is not None:
        if try_password(explicit_password):
            return explicit_password
        if password is not None or env_password:
            raise PdfPasswordInvalidError("The PDF password was not accepted.")

    if try_password(""):
        return ""

    if password_provider is None:
        raise PdfPasswordRequiredError("This PDF is password protected. Enter its password before scanning.")

    invalid_previous = False
    while True:
        candidate = password_provider(path, invalid_previous)
        if candidate is None:
            raise PdfPasswordRequiredError("This PDF is password protected. Enter its password before scanning.")
        if try_password(candidate):
            return candidate
        invalid_previous = True


def authenticate_pdf_document_with_cache(document, path, *, password_provider=None):
    """Authenticate a PDF, reusing a password already accepted for this path."""
    cached_password, has_cached_password = get_cached_pdf_password(path)
    if has_cached_password:
        try:
            return authenticate_pdf_document(document, path, password=cached_password)
        except PdfPasswordInvalidError:
            clear_cached_pdf_password(path)

    password = authenticate_pdf_document(document, path, password_provider=password_provider)
    if password is not None:
        remember_pdf_password(path, password)
    return password
