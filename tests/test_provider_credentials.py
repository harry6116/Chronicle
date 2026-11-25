from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from chronicle_app.services.provider_credentials import CredentialError, CredentialStore, RESET_MARKER, credential_reset_pending
from chronicle_app.services.security import sanitize_log_text


class FakeVault(dict):
    def read(self, service, account):
        return self.get((service, account), "")

    def write(self, service, account, value):
        self[service, account] = value

    def delete(self, service, account):
        self.pop((service, account), None)


class CredentialStoreTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.native = FakeVault()
        self.store = CredentialStore(self.native, service="Chronicle Test")
        self.key = "DisposableOpaqueProviderCredential78219"

    def test_explicit_import_does_not_modify_external_item(self):
        self.native.write("Other Tool", "Named Account", self.key)
        key = self.store.read_external("Other Tool", "Named Account")
        self.store.save({"openai": key})
        self.store.save({"openai": ""})
        self.assertEqual(self.store.get("openai"), "")
        self.assertEqual(self.native.read("Other Tool", "Named Account"), self.key)

    def test_fresh_profile_is_marked_without_deleting_entries(self):
        marker = self.root / RESET_MARKER
        with patch.object(self.native, "delete", wraps=self.native.delete) as delete:
            self.assertTrue(self.store.reset_for_upgrade(marker, self.root, only_if_empty=True))
            delete.assert_not_called()
        self.assertFalse(credential_reset_pending(marker, self.root))

    def test_empty_probe_leaves_old_vault_keys_untouched(self):
        marker = self.root / RESET_MARKER
        self.store.save({"gemini": self.key})
        self.assertFalse(self.store.reset_for_upgrade(marker, self.root, only_if_empty=True))
        self.assertTrue(credential_reset_pending(marker, self.root))
        self.assertEqual(self.store.get("gemini"), self.key)
        self.assertNotIn(self.key, sanitize_log_text("Provider returned " + self.key))

    def test_reset_removes_malformed_files_without_reading_them(self):
        marker = self.root / RESET_MARKER
        legacy = self.root / "api_keys.json"
        legacy.write_bytes(b"\xff invalid text")
        with patch.object(Path, "open", side_effect=AssertionError("Old credential files must stay unread")):
            self.assertFalse(self.store.reset_for_upgrade(marker, self.root, only_if_empty=True))
            self.assertTrue(legacy.exists())
            self.assertTrue(self.store.reset_for_upgrade(marker, self.root))
        self.assertFalse(legacy.exists())

    def test_vault_denial_leaves_legacy_files_and_reset_can_retry(self):
        marker = self.root / RESET_MARKER
        legacy = self.root / "api_key_openai.txt"
        legacy.write_text(self.key)
        self.store.save({"gemini": self.key})
        with patch.object(self.native, "delete", side_effect=CredentialError("Permission denied")):
            with self.assertRaisesRegex(CredentialError, "Permission denied"):
                self.store.reset_for_upgrade(marker, self.root)
        self.assertFalse(marker.exists())
        self.assertTrue(legacy.exists())
        self.store.reset_for_upgrade(marker, self.root)
        self.assertFalse(legacy.exists())

    def test_unverified_vault_removal_keeps_reset_pending(self):
        marker = self.root / RESET_MARKER
        self.store.save({"gemini": self.key})
        with patch.object(self.native, "delete"):
            with self.assertRaisesRegex(CredentialError, "could not verify"):
                self.store.reset_for_upgrade(marker, self.root)
        self.assertTrue(credential_reset_pending(marker, self.root))

    def test_returning_legacy_copy_is_removed_without_deleting_new_or_external_keys(self):
        marker = self.root / RESET_MARKER
        self.store.reset_for_upgrade(marker, self.root)
        self.store.save({"gemini": self.key})
        self.native.write("Other Tool", "gemini", self.key)
        restored = self.root / "api_key_gemini.txt"
        restored.write_text("DisposableRestoredOldValue")
        self.assertTrue(credential_reset_pending(marker, self.root))
        with patch.object(self.native, "delete") as delete:
            self.store.reset_for_upgrade(marker, self.root)
            delete.assert_not_called()
        self.assertFalse(restored.exists())
        self.assertEqual(self.store.get("gemini"), self.key)
        self.assertEqual(self.native.read("Other Tool", "gemini"), self.key)

    def test_upgrade_reset_removes_saved_and_legacy_keys_then_preserves_new_keys(self):
        receipt = self.root / ".credential-reset-v1"
        legacy = self.root / "api_keys.json"
        legacy.write_text('{"gemini":"DisposableLegacy"}')
        self.store.save({"gemini": self.key, "openai": "DisposableVaultOpenAI"})
        self.store.reset_for_upgrade(receipt, self.root)
        self.assertTrue(receipt.exists())
        self.assertFalse(legacy.exists())
        self.assertEqual(self.store.load(), {"gemini": "", "claude": "", "openai": ""})
        self.store.save({"gemini": "DisposableAfterReset"})
        self.store.reset_for_upgrade(receipt, self.root)
        self.assertEqual(self.store.get("gemini"), "DisposableAfterReset")
