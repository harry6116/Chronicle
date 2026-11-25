"""Restrict authenticated provider traffic to Chronicle's supported origins."""

from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, build_opener


PROVIDER_ORIGINS = {
    "gemini": "https://generativelanguage.googleapis.com",
    "openai": "https://api.openai.com",
    "claude": "https://api.anthropic.com",
}


class NoProviderRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def provider_url_opener():
    return build_opener(ProxyHandler({}), HTTPSHandler(context=_provider_tls_context()), NoProviderRedirect())


def _provider_request_guard(provider):
    allowed_host = PROVIDER_ORIGINS[provider].split("://", 1)[1]

    def check(request):
        if (request.url.scheme != "https" or request.url.host != allowed_host
                or request.url.port not in {None, 443} or request.url.userinfo):
            raise RuntimeError("Chronicle blocked an authenticated request outside the provider's official HTTPS API.")
    return check


def _provider_tls_context():
    import certifi
    import ssl

    return ssl.create_default_context(cafile=certifi.where())


def secure_httpx_options(provider):
    return {
        "trust_env": False,
        "follow_redirects": False,
        "verify": _provider_tls_context(),
        "event_hooks": {"request": [_provider_request_guard(provider)]},
    }
