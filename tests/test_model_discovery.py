import io
import json
import unittest
from unittest.mock import Mock

from chronicle_app.services.model_discovery import describe_models, discover_models
from chronicle_app.services.provider_transport import NoProviderRedirect, secure_httpx_options
from chronicle_app.services.runtime_policies import GEMINI_FAST_MODEL


class ModelDiscoveryTests(unittest.TestCase):
    def test_gemini_sends_key_only_in_header_to_fixed_origin(self):
        key = "DisposableMockCredentialModelList"
        opener = Mock()
        opener.open.side_effect = [
            io.BytesIO(json.dumps({
                "models": [{"name": f"models/{GEMINI_FAST_MODEL}", "supportedGenerationMethods": ["generateContent"]}],
                "nextPageToken": "https://external.invalid/leak",
            }).encode()),
            io.BytesIO(b'{"models":[{"name":"models/vector","supportedGenerationMethods":["embedContent"]}]}'),
        ]
        names = discover_models("gemini", key, opener=opener)
        self.assertEqual(names, [GEMINI_FAST_MODEL])
        for call in opener.open.call_args_list:
            request = call.args[0]
            self.assertEqual(request.host, "generativelanguage.googleapis.com")
            self.assertNotIn(key, request.full_url)
            self.assertIn(key, dict(request.header_items()).values())
            self.assertIsNone(request.data)
        self.assertIsNone(NoProviderRedirect().redirect_request(None, None, 302, "", {}, "https://external.invalid"))

    def test_sdk_http_options_block_redirects_and_wrong_origins(self):
        import httpx
        options = secure_httpx_options("claude")
        called = []
        def redirect(request):
            called.append(request.url.host)
            return httpx.Response(307, headers={"location": "https://other.invalid"})
        with httpx.Client(transport=httpx.MockTransport(redirect), **options) as client:
            self.assertEqual(client.get("https://api.anthropic.com/v1/models").status_code, 307)
            for url in ("http://api.anthropic.com", "https://api.anthropic.com:8000", "https://other.invalid"):
                with self.assertRaises(RuntimeError):
                    client.get(url)
        self.assertEqual(called, ["api.anthropic.com"])

    def test_model_results_distinguish_plan_and_access(self):
        result = describe_models("gemini", [GEMINI_FAST_MODEL], "Free API")
        self.assertIn("Free API", result)
        self.assertIn("does not verify billing or quota", result)
        self.assertIn(GEMINI_FAST_MODEL, result)
