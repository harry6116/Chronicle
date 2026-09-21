import unittest

from chronicle_app.services.gemini_rest_payloads import (
    build_gemini_file_payload,
    build_gemini_inline_image_payload,
    extract_gemini_text_from_data,
    extract_gemini_text_from_response_bytes,
)


class GeminiRestPayloadsTest(unittest.TestCase):
    def test_build_file_payload_uses_file_data_and_prompt(self):
        payload = build_gemini_file_payload(
            file_uri="files/abc",
            mime_type="application/pdf",
            text_prompt="Read this.",
        )

        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0]["fileData"]["fileUri"], "files/abc")
        self.assertEqual(parts[0]["fileData"]["mimeType"], "application/pdf")
        self.assertEqual(parts[1]["text"], "Read this.")

    def test_build_inline_image_payload_base64_encodes_image_bytes(self):
        payload = build_gemini_inline_image_payload(
            image_bytes=b"abc",
            text_prompt="Read image.",
            mime_type="image/png",
        )

        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0]["inlineData"]["data"], "YWJj")
        self.assertEqual(parts[1]["text"], "Read image.")

    def test_extract_text_concatenates_text_parts(self):
        text = extract_gemini_text_from_data(
            {"candidates": [{"content": {"parts": [{"text": "Hello "}, {"text": "world"}]}}]},
            error_prefix="Gemini REST request failed",
        )

        self.assertEqual(text, "Hello world")

    def test_extract_text_raises_prefixed_error(self):
        with self.assertRaisesRegex(RuntimeError, "Gemini REST request failed: no quota"):
            extract_gemini_text_from_data(
                {"error": {"message": "no quota"}},
                error_prefix="Gemini REST request failed",
            )

    def test_extract_text_from_response_bytes(self):
        text = extract_gemini_text_from_response_bytes(
            b'{"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
            error_prefix="Gemini REST request failed",
        )

        self.assertEqual(text, "ok")


if __name__ == "__main__":
    unittest.main()
