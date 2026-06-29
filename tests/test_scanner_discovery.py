import json
import unittest
from unittest import mock

from chronicle_app.services import scanner_discovery


class ScannerDiscoveryTest(unittest.TestCase):
    def test_canon_pixma_name_is_treated_as_scanner_candidate(self):
        scanners = []
        seen = set()

        scanner_discovery._append_unique_scanner(
            scanners,
            seen,
            name="Canon TS6400 series",
            manufacturer="Canon",
            source="Windows PnP",
            details="Printer",
        )

        self.assertEqual(len(scanners), 1)
        self.assertEqual(scanners[0]["name"], "Canon TS6400 series")

    def test_windows_discovery_includes_printer_class_devices(self):
        payload = json.dumps(
            {
                "FriendlyName": "Canon TS6400 series",
                "Manufacturer": "Canon",
                "Status": "OK",
                "Class": "Printer",
            }
        )

        with mock.patch.object(scanner_discovery, "_run_command_capture", return_value=(0, payload, "")):
            scanners, err = scanner_discovery.discover_scanners_windows()

        self.assertIsNone(err)
        self.assertEqual(len(scanners), 1)
        self.assertEqual(scanners[0]["source"], "Windows PnP")

    def test_macos_printer_items_are_listed_as_device_candidates(self):
        payload = json.dumps(
            {
                "SPUSBDataType": [],
                "SPPrintersDataType": [
                    {
                        "_name": "Canon TS6400 series",
                        "manufacturer": "Canon",
                        "printer_status": "Idle",
                    }
                ],
            }
        )

        with mock.patch.object(scanner_discovery, "_run_command_capture", return_value=(0, payload, "")):
            scanners, err = scanner_discovery.discover_scanners_macos()

        self.assertIsNone(err)
        self.assertEqual(len(scanners), 1)
        self.assertEqual(scanners[0]["source"], "macOS Printers")


if __name__ == "__main__":
    unittest.main()
