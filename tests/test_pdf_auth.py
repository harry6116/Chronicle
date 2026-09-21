import os
import unittest
from unittest import mock

from chronicle_app.services.pdf_auth import (
    PDF_PASSWORD_ENV,
    PDF_PASSWORD_CACHE_MAX_ENTRIES,
    PdfPasswordInvalidError,
    PdfPasswordRequiredError,
    authenticate_pdf_document,
    authenticate_pdf_document_with_cache,
    clear_cached_pdf_password,
    get_cached_pdf_password,
    remember_pdf_password,
)
from chronicle_app.services.pdf_rendering import PdfPageRenderer


class FakeEncryptedDocument:
    needs_pass = True

    def __init__(self, accepted_password):
        self.accepted_password = accepted_password
        self.attempts = []

    def authenticate(self, password):
        self.attempts.append(password)
        return password == self.accepted_password


class PdfAuthTest(unittest.TestCase):
    def tearDown(self):
        clear_cached_pdf_password()

    def test_authenticate_pdf_document_returns_none_for_unprotected_pdf(self):
        document = mock.Mock(needs_pass=False)

        self.assertIsNone(authenticate_pdf_document(document, "/tmp/plain.pdf"))
        document.authenticate.assert_not_called()

    def test_authenticate_pdf_document_accepts_environment_password(self):
        document = FakeEncryptedDocument("secret")

        with mock.patch.dict(os.environ, {PDF_PASSWORD_ENV: "secret"}):
            password = authenticate_pdf_document(document, "/tmp/protected.pdf")

        self.assertEqual(password, "secret")
        self.assertEqual(document.attempts, ["secret"])

    def test_authenticate_pdf_document_prompts_after_empty_password_fails(self):
        document = FakeEncryptedDocument("secret")
        prompts = []

        def provider(path, invalid_previous):
            prompts.append((path, invalid_previous))
            return "secret"

        password = authenticate_pdf_document(document, "/tmp/protected.pdf", password_provider=provider)

        self.assertEqual(password, "secret")
        self.assertEqual(document.attempts, ["", "secret"])
        self.assertEqual(prompts, [("/tmp/protected.pdf", False)])

    def test_authenticate_pdf_document_reprompts_after_invalid_password(self):
        document = FakeEncryptedDocument("secret")
        answers = iter(["wrong", "secret"])

        password = authenticate_pdf_document(
            document,
            "/tmp/protected.pdf",
            password_provider=lambda _path, _invalid_previous: next(answers),
        )

        self.assertEqual(password, "secret")
        self.assertEqual(document.attempts, ["", "wrong", "secret"])

    def test_authenticate_pdf_document_reports_required_password_without_provider(self):
        document = FakeEncryptedDocument("secret")

        with self.assertRaises(PdfPasswordRequiredError):
            authenticate_pdf_document(document, "/tmp/protected.pdf")

    def test_authenticate_pdf_document_rejects_explicit_bad_password(self):
        document = FakeEncryptedDocument("secret")

        with self.assertRaises(PdfPasswordInvalidError):
            authenticate_pdf_document(document, "/tmp/protected.pdf", password="wrong")

    def test_authenticate_pdf_document_with_cache_prompts_only_once_for_same_path(self):
        prompts = []

        def provider(path, invalid_previous):
            prompts.append((path, invalid_previous))
            return "secret"

        first = FakeEncryptedDocument("secret")
        second = FakeEncryptedDocument("secret")

        self.assertEqual(
            authenticate_pdf_document_with_cache(first, "/tmp/protected.pdf", password_provider=provider),
            "secret",
        )
        self.assertEqual(
            authenticate_pdf_document_with_cache(second, "/tmp/protected.pdf", password_provider=provider),
            "secret",
        )

        self.assertEqual(prompts, [("/tmp/protected.pdf", False)])
        self.assertEqual(first.attempts, ["", "secret"])
        self.assertEqual(second.attempts, ["secret"])

    def test_authenticate_pdf_document_with_cache_reprompts_after_stale_cached_password(self):
        prompts = []
        remember_pdf_password("/tmp/protected.pdf", "old")
        document = FakeEncryptedDocument("secret")

        password = authenticate_pdf_document_with_cache(
            document,
            "/tmp/protected.pdf",
            password_provider=lambda path, invalid_previous: prompts.append((path, invalid_previous)) or "secret",
        )

        self.assertEqual(password, "secret")
        self.assertEqual(prompts, [("/tmp/protected.pdf", False)])
        self.assertEqual(document.attempts, ["old", "", "secret"])

    def test_cached_pdf_passwords_are_capped(self):
        for idx in range(PDF_PASSWORD_CACHE_MAX_ENTRIES + 3):
            remember_pdf_password(f"/tmp/protected-{idx}.pdf", f"secret-{idx}")

        _password, has_oldest = get_cached_pdf_password("/tmp/protected-0.pdf")
        newest_password, has_newest = get_cached_pdf_password(f"/tmp/protected-{PDF_PASSWORD_CACHE_MAX_ENTRIES + 2}.pdf")

        self.assertFalse(has_oldest)
        self.assertTrue(has_newest)
        self.assertEqual(newest_password, f"secret-{PDF_PASSWORD_CACHE_MAX_ENTRIES + 2}")


class PdfRenderingAuthTest(unittest.TestCase):
    def test_renderer_authenticates_reopened_pdf_with_reader_password(self):
        class FakePage:
            rect = mock.Mock(width=100, x0=0, x1=100, y0=0, y1=200)

            def get_pixmap(self, **_kwargs):
                return mock.Mock(tobytes=lambda _fmt: b"png")

            def get_text(self, _kind):
                return "page text"

        class FakeDoc(FakeEncryptedDocument):
            def __len__(self):
                return 1

            def load_page(self, _index):
                return FakePage()

            def close(self):
                pass

        opened = []

        class FakeFitz:
            csRGB = object()

            @staticmethod
            def Matrix(_x, _y):
                return object()

            @staticmethod
            def Rect(x0, y0, x1, y1):
                return (x0, y0, x1, y1)

            @staticmethod
            def open(_path):
                doc = FakeDoc("secret")
                opened.append(doc)
                return doc

        reader = mock.Mock(pdf_password="secret")
        renderer = PdfPageRenderer(
            path="/tmp/protected.pdf",
            reader=reader,
            selected_page_indices=[0],
            pdf_writer_cls=mock.Mock(),
            fitz_module=FakeFitz,
        )

        self.assertEqual(renderer.build_page_png_bytes(0), b"png")
        self.assertEqual(opened[0].attempts, ["secret"])


if __name__ == "__main__":
    unittest.main()
