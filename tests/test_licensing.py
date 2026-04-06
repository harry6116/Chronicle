import os
import tempfile
import unittest
from unittest import mock

from chronicle_app.services import licensing


class LicensingTest(unittest.TestCase):
    def test_sign_and_verify_round_trip(self):
        private_key, public_key = licensing.generate_keypair()
        payload = licensing.build_license_payload(
            license_id="CHR-2026-000001",
            issued_to="Example User",
            email="example@example.com",
            tier="personal_indie",
            seats=1,
            issued_at="2026-03-30",
            valid_for_major_version="1",
            notes="Personal / Indie license",
        )

        signed = licensing.sign_license_payload(payload, private_key)
        result = licensing.verify_license_data(signed, public_key)

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "ok")
        self.assertEqual(result.license_data["license_id"], "CHR-2026-000001")

    def test_verify_rejects_tampered_license(self):
        private_key, public_key = licensing.generate_keypair()
        payload = licensing.build_license_payload(
            license_id="CHR-2026-000002",
            issued_to="Example User",
            email="example@example.com",
            tier="commercial",
            seats=2,
            issued_at="2026-03-30",
            valid_for_major_version="1",
        )
        signed = licensing.sign_license_payload(payload, private_key)
        signed["tier"] = "personal_indie"

        result = licensing.verify_license_data(signed, public_key)

        self.assertFalse(result.valid)
        self.assertIn("verification failed", result.reason.lower())

    def test_install_and_load_license_round_trip(self):
        private_key, public_key = licensing.generate_keypair()
        payload = licensing.build_license_payload(
            license_id="CHR-2026-000003",
            issued_to="Archive Tester",
            email="archive@example.com",
            tier="institutional",
            seats=5,
            issued_at="2026-03-30",
            valid_for_major_version="1",
        )
        signed = licensing.sign_license_payload(payload, private_key)

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, "issued-license.json")
            licensing.write_license_file(source_path, signed)

            install_result = licensing.install_license_file(
                source_path,
                app_data_dir=tmpdir,
                public_key=public_key,
            )
            self.assertTrue(install_result.valid)

            loaded_result = licensing.load_installed_license(
                app_data_dir=tmpdir,
                public_key=public_key,
            )
            self.assertTrue(loaded_result.valid)
            self.assertEqual(loaded_result.license_data["seats"], 5)

    def test_resolve_public_key_prefers_env_file(self):
        private_key, public_key = licensing.generate_keypair()
        public_pem = licensing.serialize_public_key_pem(public_key)

        with tempfile.TemporaryDirectory() as tmpdir:
            public_key_path = os.path.join(tmpdir, licensing.PUBLIC_KEY_FILENAME)
            with open(public_key_path, "wb") as fh:
                fh.write(public_pem)

            with mock.patch.dict(os.environ, {licensing.PUBLIC_KEY_FILE_ENV: public_key_path}, clear=False):
                resolved = licensing.resolve_public_key(app_data_dir="/ignored", script_dir="/ignored")

            self.assertIsNotNone(resolved)
            payload = licensing.build_license_payload(
                license_id="CHR-2026-000004",
                issued_to="Verifier",
                email="verify@example.com",
                tier="personal_indie",
                issued_at="2026-03-30",
            )
            signed = licensing.sign_license_payload(payload, private_key)
            self.assertTrue(licensing.verify_license_data(signed, resolved).valid)

    def test_format_license_status_covers_main_states(self):
        self.assertIn(
            "not configured",
            licensing.format_license_status(None, public_key_available=False).lower(),
        )
        self.assertIn(
            "currently unlicensed",
            licensing.format_license_status(
                licensing.LicenseValidationResult(valid=False, reason="No installed license found."),
                public_key_available=True,
            ).lower(),
        )
        self.assertIn(
            "license installed and valid",
            licensing.format_license_status(
                licensing.LicenseValidationResult(
                    valid=True,
                    reason="ok",
                    license_data={
                        "issued_to": "Example User",
                        "email": "example@example.com",
                        "organization": "",
                        "tier": "personal_indie",
                        "seats": 1,
                        "valid_for_major_version": "1",
                        "license_id": "CHR-2026-000005",
                        "issued_at": "2026-03-30",
                        "notes": "",
                    },
                ),
                public_key_available=True,
            ).lower(),
        )


if __name__ == "__main__":
    unittest.main()
