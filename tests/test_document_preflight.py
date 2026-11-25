import unittest

import fitz

from chronicle_app.services.document_preflight import inspect_pdf


class DocumentPreflightTests(unittest.TestCase):
    def make_page(self, document, columns):
        page = document.new_page(width=900, height=1100)
        for x in columns:
            for y in (105, 310, 570, 820):
                page.insert_text((x, y), "Several articles appear in this narrow column.\n"
                                 "This is one of the stories of the day.\n"
                                 "Another line stays within the column.", fontsize=8)
        return page

    def test_digitised_newspaper_takes_precedence_over_accidental_academic_headings(self):
        with fitz.open() as doc:
            page = self.make_page(doc, (25, 205, 385, 565, 745))
            page.insert_text((25, 75), "Abstract\nReferences", fontsize=9)
            page.insert_text((20, 1070), "National Library of Australia http://nla.gov.au/nla.news-page12345")
            doc.set_metadata({"subject": "Page image from a Newspaper Digitisation Program"})
            evidence = inspect_pdf(doc, [0])
        self.assertEqual(evidence.recommended_profile, "newspaper")
        self.assertEqual(evidence.text_pages, 1)
        self.assertEqual(evidence.narrow_columns, 5)

    def test_unit_war_diary_identified_from_archive_metadata_and_page_references(self):
        with fitz.open() as doc:
            doc.set_metadata({"title": "WO-95-1772-1_031.jpg", "author": "The National Archives"})
            for number in range(1, 22):
                page = doc.new_page()
                page.insert_text((30, 20), f"The National Archives' reference WO-95-1772-1_{number:03}.jpg")
                page.insert_text((30, 810), "© Crown Copyright")
            evidence = inspect_pdf(doc, list(range(len(doc))))
        self.assertTrue(evidence.unit_war_diary)
        self.assertEqual(evidence.recommended_profile, "military")
        self.assertEqual(evidence.text_pages, 0)
        self.assertEqual(evidence.archive_reference_pages, len(evidence.inspected_pages))
        self.assertIn(11, evidence.trials)
        self.assertEqual(evidence.trials[-1], 21)

    def test_unattributed_title_alone_does_not_identify_war_diary(self):
        with fitz.open() as doc:
            doc.set_metadata({"title": "WO-95-1772-1_031.jpg"})
            doc.new_page().insert_text((50, 70), "Personal diary")
            evidence = inspect_pdf(doc, [0])
        self.assertFalse(evidence.unit_war_diary)
        self.assertEqual(evidence.recommended_profile, "standard")

    def test_report_and_flyer_use_consolidated_presets(self):
        cases = (
            ("Department of Example\nAnnual Report\n2023–24", "reports"),
            ("Phoenix Spring Hamfest\nElectronics Swap\nApril 4, 2026\nHours: 7:00 AM\nAdmission $5",
             "promotional"),
            ("Meeting notes\nThe committee mentioned the annual report.\nContact the secretary.", "standard"),
        )
        for source, expected in cases:
            with self.subTest(expected=expected), fitz.open() as doc:
                doc.new_page().insert_text((30, 55), source)
                self.assertEqual(inspect_pdf(doc, [0]).recommended_profile, expected)

    def test_one_event_notice_does_not_classify_a_long_mixed_document(self):
        with fitz.open() as doc:
            doc.new_page().insert_text((30, 55), "Community Fair\nHours: 9 AM\nAdmission $5")
            for _ in range(7):
                doc.new_page().insert_text((30, 55), "Miscellaneous notes and reference details.")
            self.assertEqual(inspect_pdf(doc, list(range(len(doc)))).recommended_profile, "standard")

    def test_plain_academic_paper_still_uses_academic_preset(self):
        with fitz.open() as doc:
            page = self.make_page(doc, (45, 490))
            page.insert_text((45, 75), "Abstract\nReferences", fontsize=9)
            evidence = inspect_pdf(doc, [0])
        self.assertEqual(evidence.recommended_profile, "academic")

    def test_multi_column_layout_alone_does_not_choose_newspaper(self):
        with fitz.open() as doc:
            self.make_page(doc, (25, 235, 445, 655))
            evidence = inspect_pdf(doc, [0])
        self.assertEqual(evidence.recommended_profile, "standard")

    def test_magazine_metadata_keeps_its_own_preset(self):
        with fitz.open() as doc:
            self.make_page(doc, (25, 235, 445, 655))
            doc.set_metadata({"subject": "pulp magazines; science fiction"})
            evidence = inspect_pdf(doc, [0])
        self.assertEqual(evidence.recommended_profile, "magazine")
        self.assertFalse(evidence.webpage)
