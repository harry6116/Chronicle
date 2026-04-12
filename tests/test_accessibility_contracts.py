import io
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

from chronicle_core import normalize_streamed_html_document, write_header
from chronicle_app.services.runtime_policies import DEFAULT_CLAUDE_MODEL


def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _install_gui_import_stubs():
    _stub_module("cv2")
    pil_module = _stub_module("PIL")
    pil_image_module = _stub_module("PIL.Image")
    pil_module.Image = pil_image_module
    _stub_module("pypdf", PdfReader=object, PdfWriter=object)
    _stub_module("docx")
    _stub_module("fpdf", FPDF=object)
    google_module = _stub_module("google")
    google_genai_module = _stub_module("google.genai")
    google_module.genai = google_genai_module
    _stub_module("openpyxl")
    ebooklib_module = _stub_module("ebooklib")
    ebooklib_epub_module = _stub_module("ebooklib.epub")
    ebooklib_module.epub = ebooklib_epub_module
    _stub_module("chronicle_app.services.legacy_pdf_runtime", process_pdf_gemini=lambda *args, **kwargs: None)
    wx_module = _stub_module(
        "wx",
        Dialog=type("Dialog", (object,), {}),
        Frame=type("Frame", (object,), {}),
        ID_HIGHEST=10000,
        NOT_FOUND=-1,
        CallAfter=lambda fn, *args, **kwargs: fn(*args, **kwargs),
        Window=type("Window", (object,), {"FindFocus": staticmethod(lambda: None)}),
    )
    wx_module.dataview = _stub_module("wx.dataview")
    wx_module.adv = _stub_module("wx.adv")
    wx_module.grid = _stub_module(
        "wx.grid",
        Grid=type("Grid", (object,), {"GridSelectRows": object()}),
        EVT_GRID_SELECT_CELL=object(),
        EVT_GRID_RANGE_SELECT=object(),
        EVT_GRID_CELL_LEFT_DCLICK=object(),
        EVT_GRID_CELL_RIGHT_CLICK=object(),
    )


_install_gui_import_stubs()

import chronicle_runtime as chronicle
import chronicle_gui


class _FakeEpubHtml:
    def __init__(self, title, file_name, lang):
        self.title = title
        self.file_name = file_name
        self.lang = lang
        self.content = ""


class _FakeEpubBook:
    def __init__(self):
        self.identifier = None
        self.title = None
        self.language = None
        self.items = []
        self.spine = []

    def set_identifier(self, value):
        self.identifier = value

    def set_title(self, value):
        self.title = value

    def set_language(self, value):
        self.language = value

    def add_item(self, item):
        self.items.append(item)


class _FakeEpubNav:
    pass


class _FakeEpubNcx:
    pass


class AccessibilityContractsTest(unittest.TestCase):
    def _base_cfg(self, **overrides):
        cfg = {
            "doc_profile": "standard",
            "format_type": "html",
            "translate_mode": "none",
            "translate_target": "English",
            "modernize_punctuation": False,
            "unit_conversion": False,
            "image_descriptions": True,
            "preserve_original_page_numbers": False,
            "abbrev_expansion": False,
            "merge_files": False,
            "custom_prompt": "",
            "custom_commands": "",
            "academic_footnote_mode": "endnotes",
            "academic_annotation_mode": "inline",
        }
        cfg.update(overrides)
        return cfg

    def test_cli_prompt_keeps_core_accessibility_and_recovery_rules(self):
        prompt = chronicle.get_prompt(self._base_cfg())

        self.assertIn("STRIKETHROUGH RECOVERY", prompt)
        self.assertIn("STAMPS & SIGNATURES", prompt)
        self.assertIn("ARCHIVE RECOVERY", prompt)
        self.assertIn("FLUID HEADINGS", prompt)
        self.assertIn("SEMANTIC METADATA", prompt)
        self.assertIn("SEMANTIC ATTRIBUTION", prompt)
        self.assertIn("NON-HTML OUTPUT RULE", prompt)
        self.assertIn("NO RAW BINARY", prompt)
        self.assertIn("NO FENCE WRAPPERS", prompt)

    def test_gui_prompt_keeps_core_accessibility_and_recovery_rules(self):
        prompt = chronicle_gui.build_prompt(self._base_cfg())

        self.assertIn("STRIKETHROUGH RECOVERY", prompt)
        self.assertIn("STAMPS & SIGNATURES", prompt)
        self.assertIn("ARCHIVE RECOVERY", prompt)
        self.assertIn("FLUID HEADINGS", prompt)
        self.assertIn("SEMANTIC METADATA", prompt)
        self.assertIn("SEMANTIC ATTRIBUTION", prompt)
        self.assertIn("NON-HTML OUTPUT RULE", prompt)
        self.assertIn("NO RAW BINARY", prompt)
        self.assertIn("NO FENCE WRAPPERS", prompt)

    def test_cli_and_gui_prompts_both_enforce_language_and_bidi_accessibility(self):
        cfg = self._base_cfg(translate_mode="both", image_descriptions=False)

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("LANGUAGE", prompt)
            self.assertIn("dir=", prompt)
            self.assertIn("screen readers", prompt)

    def test_academic_prompt_keeps_math_accessibility_rules(self):
        cfg = self._base_cfg(doc_profile="academic")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("MATH ACCESSIBILITY STRUCTURE", prompt)
            self.assertIn("FIGURE DESCRIPTIONS", prompt)
            self.assertIn("Footnotes:", prompt)

    def test_book_prompt_keeps_long_form_pdf_and_word_rules(self):
        cfg = self._base_cfg(doc_profile="book", format_type="docx")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("BOOK / NOVEL / LONG-FORM PROSE RULES", prompt)
            self.assertIn("Preserve paragraph continuity across page breaks", prompt)
            self.assertIn("CORRUPTION QUARANTINE", prompt)
            self.assertIn("STRAY PROMPT/JUNK PHRASE SUPPRESSION", prompt)
            self.assertIn("FOLIO SUPPRESSION FOR PROSE", prompt)
            self.assertIn("OBVIOUS OCR WORD REPAIR", prompt)
            self.assertIn("TAIL-END SAFETY", prompt)
            self.assertIn("ENDING CONTINUITY", prompt)
            self.assertIn("WORD / DOCX OUTPUT RULES", prompt)
            self.assertIn("Do not use inline markdown emphasis markers", prompt)
            self.assertIn("pipe table", prompt)

    def test_docx_prompt_does_not_prepend_generic_plaintext_scaffolding(self):
        prompt = chronicle_gui.build_prompt(self._base_cfg(doc_profile="book", format_type="docx"))

        self.assertNotIn("Format content logically.", prompt)
        self.assertNotIn("Format content logically.beginning", prompt)

    def test_page_number_toggle_changes_prompt_contract(self):
        suppressed_cfg = self._base_cfg(doc_profile="book", preserve_original_page_numbers=False)
        preserved_cfg = self._base_cfg(doc_profile="book", preserve_original_page_numbers=True)

        suppressed_prompt = chronicle_gui.build_prompt(suppressed_cfg)
        preserved_prompt = chronicle_gui.build_prompt(preserved_cfg)

        self.assertIn("Suppress standalone printed page numbers", suppressed_prompt)
        self.assertIn("Preserve visible original printed page numbers", preserved_prompt)
        self.assertIn("[Original Page Number: X]", preserved_prompt)
        self.assertIn("preserve it once as a stable boundary marker", preserved_prompt)

    def test_book_prompt_filters_hard_returns_unless_line_endings_support_them(self):
        prompt = chronicle_gui.build_prompt(self._base_cfg(doc_profile="book", format_type="docx"))

        self.assertIn("HARD-RETURN FILTER FOR PROSE", prompt)
        self.assertIn("Treat ordinary wrapped scan lines as one continuous paragraph", prompt)
        self.assertIn("full stop, question mark, exclamation mark, or closing quotation mark", prompt)

    def test_book_prompt_distinguishes_apostrophes_from_dialogue_quotes(self):
        prompt = chronicle_gui.build_prompt(self._base_cfg(doc_profile="book", format_type="docx"))

        self.assertIn("QUOTE DISAMBIGUATION", prompt)
        self.assertIn("Keep true apostrophes in contractions and possessives", prompt)
        self.assertIn("DIALOGUE QUOTE NORMALIZATION", prompt)
        self.assertIn("normalize those dialogue quotes into proper double quotation marks", prompt)
        self.assertIn("Convert opening and closing dialogue quotes consistently across the paragraph", prompt)

    def test_book_prompt_suppresses_ocr_wrappers_and_enforces_page_reference_discipline(self):
        prompt = chronicle_gui.build_prompt(
            self._base_cfg(doc_profile="book", format_type="docx", preserve_original_page_numbers=True)
        )

        self.assertIn("OCR WRAPPER MARKER SUPPRESSION", prompt)
        self.assertIn("==Start of OCR for page X==", prompt)
        self.assertIn("PRINTED PAGE REFERENCE DISCIPLINE", prompt)
        self.assertIn("Do not leave duplicate bare number lines", prompt)
        self.assertIn("HEADING FUSION PREVENTION", prompt)
        self.assertIn("CHAPTER-FOLIO PRESERVATION", prompt)
        self.assertIn("MATHEMATICAL PAGINATION & BLIND FOLIOS", prompt)
        self.assertIn("perfectly sequential", prompt)
        self.assertIn("FOLIO DE-DUPLICATION (ANTI-FUSION)", prompt)
        self.assertIn("Never output artifacts such as `[Original Page Number: 82]81`", prompt)
        self.assertIn("FRONT-MATTER ISOLATION", prompt)
        self.assertIn("Treat review blurbs, `Books by` lists, contents pages, copyright blocks", prompt)
        self.assertIn("GLOBAL QUOTE NORMALIZATION", prompt)

    def test_standard_prompt_keeps_recovery_and_accessibility_remediation_rules(self):
        cfg = self._base_cfg(doc_profile="standard", format_type="docx")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("ACCESSIBILITY REMEDIATION & RECOVERY", prompt)
            self.assertIn("MALFORMED SOURCE RECOVERY", prompt)
            self.assertIn("OUTPUT IMPROVEMENT RULE", prompt)
            self.assertIn("[[PAGE BREAK]]", prompt)

    def test_key_specialist_presets_exist(self):
        self.assertIn(("office", "Reports / Business Files"), chronicle_gui.PROFILE_CHOICES)
        self.assertIn(("government", "Government Reports / Records"), chronicle_gui.PROFILE_CHOICES)
        self.assertIn(("medical", "Medical Records / Clinical Handwriting"), chronicle_gui.PROFILE_CHOICES)
        self.assertIn(("flyer", "Flyers / Posters"), chronicle_gui.PROFILE_CHOICES)
        self.assertIn(("forms", "Forms / Checklists"), chronicle_gui.PROFILE_CHOICES)
        self.assertIn(("slides", "Slides / Presentations"), chronicle_gui.PROFILE_CHOICES)
        self.assertIn(("comic", "Comics / Manga / Graphic Novels"), chronicle_gui.PROFILE_CHOICES)

    def test_every_preset_has_a_distinct_tooltip_summary(self):
        summaries = {}
        for key, label in chronicle_gui.PROFILE_CHOICES:
            tooltip = chronicle_gui.profile_tooltip_text(key)
            self.assertTrue(tooltip.strip(), f"Missing tooltip for {key}")
            first_line = tooltip.splitlines()[0].strip()
            self.assertTrue(first_line.startswith(f"{label}: "), f"Tooltip first line should start with preset label for {key}")
            self.assertNotIn(first_line, summaries.values(), f"Duplicate tooltip summary detected for {key}")
            summaries[key] = first_line

    def test_flyer_prompt_keeps_short_form_hierarchy_rules(self):
        cfg = self._base_cfg(doc_profile="flyer")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("FLYERS / POSTERS / ONE-PAGE NOTICES RULES", prompt)
            self.assertIn("date/time/location", prompt)
            self.assertIn("call-to-action", prompt)

    def test_forms_prompt_keeps_checkbox_and_blank_field_rules(self):
        cfg = self._base_cfg(doc_profile="forms")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("FORMS / CHECKLISTS / WORKSHEETS RULES", prompt)
            self.assertIn("[Checkbox: Selected]", prompt)
            self.assertIn("Keep blank fields visible", prompt)

    def test_slides_prompt_keeps_presentation_structure_rules(self):
        cfg = self._base_cfg(doc_profile="slides")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("SLIDES / DECKS / HANDOUTS RULES", prompt)
            self.assertIn("agenda slides", prompt)
            self.assertIn("chart, diagram, or dense visual", prompt)

    def test_comic_prompt_keeps_panel_balloon_and_manga_direction_rules(self):
        cfg = self._base_cfg(doc_profile="comic")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("COMICS / MANGA / GRAPHIC NOVELS RULES", prompt)
            self.assertIn("PANEL ORDER", prompt)
            self.assertIn("speech balloons", prompt)
            self.assertIn("right-to-left panel order", prompt)
            self.assertIn("SFX:", prompt)
            self.assertIn("TEXTLESS PANELS", prompt)
            self.assertIn("Even a single-panel page must have `<h1>...</h1>` followed by `<h2>Panel 1</h2>`", prompt)
            self.assertIn("Never emit an empty panel heading", prompt)
            self.assertIn("Do not bury visible SFX only inside an image description", prompt)
            self.assertIn("Every panel/story-beat section must include a concise `[Image Description: ...]`", prompt)

    def test_comic_heading_enforcement_adds_page_and_panel_headings(self):
        raw = '<html><body><main id="content"><p>Pepper and Carrot</p><p>[Image Description: A cat.]</p></main></body></html>'

        cleaned = chronicle_gui.enforce_archival_heading_structure(raw, "html", "comic")

        self.assertIn("<h1>Pepper and Carrot</h1>", cleaned)
        self.assertIn("<h2>Panel 1</h2>", cleaned)

    def test_comic_heading_enforcement_adds_panel_heading_when_h1_exists(self):
        raw = '<html><body><main id="content"><h1>Little Nemo</h1><p>[Image Description: Nemo falls.]</p></main></body></html>'

        cleaned = chronicle_gui.enforce_archival_heading_structure(raw, "html", "comic")

        self.assertIn("<h1>Little Nemo</h1><h2>Panel 1</h2>", cleaned)

    def test_comic_heading_enforcement_wraps_bare_image_description_lines(self):
        raw = '<html><body><main id="content"><h1>Little Nemo</h1><h2>Panel 1</h2>\n[Image Description: Nemo falls.]\n</main></body></html>'

        cleaned = chronicle_gui.enforce_archival_heading_structure(raw, "html", "comic")

        self.assertIn("<p>[Image Description: Nemo falls.]</p>", cleaned)

    def test_archival_prompts_keep_handwriting_uncertainty_contract(self):
        cfg = self._base_cfg(doc_profile="archival")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("HANDWRITING UNCERTAINTY POLICY", prompt)
            self.assertIn("[Unclear Word: ...]", prompt)
            self.assertIn("do not substitute a cleaner dictionary word from context", prompt)
            self.assertIn("Do not expand abbreviated or broken handwritten words", prompt)

    def test_medical_prompt_keeps_clinical_uncertainty_contract(self):
        cfg = self._base_cfg(doc_profile="medical")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("MEDICAL / CLINICAL NOTE RULES", prompt)
            self.assertIn("Do not silently expand them", prompt)
            self.assertIn("Never convert an uncertain term into a specific diagnosis, medication, or instruction", prompt)
            self.assertIn("Every medical HTML extraction must begin with a concise `<h1>`", prompt)
            self.assertIn("Re-read the bottom quarter of the page before finalizing", prompt)

    def test_handwritten_prompt_requires_headings_and_bottom_page_reread(self):
        cfg = self._base_cfg(doc_profile="handwritten")

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("HANDWRITTEN PAGE RULES", prompt)
            self.assertIn("must begin with a concise accessible `<h1>`", prompt)
            self.assertIn("add at least one `<h2>`", prompt)
            self.assertIn("Re-read the bottom quarter of the page before finalizing", prompt)

    def test_html_wrapper_carries_lang_dir_and_main_semantics(self):
        buf = io.StringIO()

        write_header(buf, "Chronicle Sample", "html", lang_code="mi", text_dir="rtl")
        rendered = buf.getvalue()

        self.assertIn('<html lang="mi" dir="rtl">', rendered)
        self.assertIn('<main id="content" role="main">', rendered)
        self.assertIn("<title>Chronicle Sample</title>", rendered)

    def test_gui_queue_display_status_marks_review_recommended_jobs(self):
        frame = types.SimpleNamespace()

        status = chronicle_gui.MainFrame.GetQueueDisplayStatus(
            frame,
            {"status": "Done", "review_recommended": True},
        )

        self.assertEqual(status, "Done (Review)")

    def test_queue_accessibility_name_marks_empty_queue(self):
        name = chronicle_gui.build_queue_accessibility_name(0, 0)

        self.assertIn("empty queue", name)

    def test_queue_accessibility_description_includes_current_row_summary(self):
        description = chronicle_gui.build_queue_accessibility_description(
            2,
            1,
            "Row 1 of 2. File: alpha.pdf. Reading settings: HTML. Status: Queued.",
        )

        self.assertIn("2 queued rows are available", description)
        self.assertIn("1 row is currently selected", description)
        self.assertIn("Current row: Row 1 of 2. File: alpha.pdf.", description)

    def test_build_queue_current_row_announcement_uses_clean_row_order(self):
        frame = types.SimpleNamespace(
            queue=[{"path": "/tmp/alpha.pdf", "status": "Queued"}],
            GetQueueCurrentRowIndex=lambda: 0,
            NormalizeRowSettings=lambda row: {"format_type": "html"},
            FormatRowSettingsSummary=lambda settings: "HTML | Standard | strict punctuation",
            GetQueueDisplayStatus=lambda row: "Queued",
        )

        summary = chronicle_gui.MainFrame.BuildQueueCurrentRowAnnouncement(frame)

        self.assertIn("Row 1 of 1.", summary)
        self.assertIn("File: alpha.pdf.", summary)
        self.assertIn("Reading settings: HTML | Standard | strict punctuation.", summary)
        self.assertIn("Status: Queued.", summary)

    def test_build_queue_current_row_announcement_reports_empty_queue(self):
        frame = types.SimpleNamespace(queue=[])

        summary = chronicle_gui.MainFrame.BuildQueueCurrentRowAnnouncement(frame)

        self.assertEqual(summary, "Queue empty. Use Add Files or Add Folder to load items.")

    def test_gui_progress_summary_includes_review_count(self):
        frame = types.SimpleNamespace(
            queue=[
                {"status": "Done", "review_recommended": True},
                {"status": "Done", "review_recommended": False},
                {"status": "Queued", "review_recommended": False},
            ],
            current_file_ordinal=0,
            current_file_page_total=0,
            current_file_page_done=0,
            total_pages_processed=0,
        )

        summary = chronicle_gui.MainFrame.BuildProgressSummary(frame)

        self.assertIn("Done: 2.", summary)
        self.assertIn("Review: 1.", summary)

    def test_runtime_settings_persist_into_cfg(self):
        cfg = self._base_cfg()
        settings = {
            "format_type": "pdf",
            "doc_profile": "archival",
            "model_name": "gemini-2.5-pro",
            "translate_mode": "both",
            "translate_target": "French",
            "modernize_punctuation": True,
            "unit_conversion": True,
            "abbrev_expansion": True,
            "image_descriptions": False,
            "large_print": True,
            "pdf_page_scope": "Custom pages...",
            "pdf_custom_pages": "1-5",
        }

        updated = chronicle_gui.persist_runtime_settings_to_cfg(cfg, settings)

        self.assertIs(updated, cfg)
        self.assertTrue(cfg["modernize_punctuation"])
        self.assertEqual(cfg["doc_profile"], "archival")
        self.assertEqual(cfg["format_type"], "pdf")
        self.assertEqual(cfg["pdf_custom_pages"], "1-5")

    def test_queue_table_landing_selects_first_row_when_nothing_is_current(self):
        class FakeItem:
            def __init__(self, ok):
                self._ok = ok

            def IsOk(self):
                return self._ok

        class FakeFileList:
            def __init__(self):
                self.current = FakeItem(False)
                self.selected_rows = []
                self.focused = False
                self.current_item = None
                self.visible_item = None

            def GetCurrentItem(self):
                return self.current

            def RowToItem(self, row):
                return FakeItem(True)

            def SelectRow(self, row):
                self.selected_rows.append(row)

            def SetCurrentItem(self, item):
                self.current_item = item

            def EnsureVisible(self, item):
                self.visible_item = item

            def SetFocus(self):
                self.focused = True

        frame = types.SimpleNamespace(
            file_list=FakeFileList(),
            queue=[{'path': 'a.pdf'}, {'path': 'b.pdf'}],
            GetSelectedIndices=lambda: [],
        )

        landed = chronicle_gui.MainFrame.EnsureQueueTableLanding(frame, focus=True)

        self.assertTrue(landed)
        self.assertEqual(frame.file_list.selected_rows, [0])
        self.assertTrue(frame.file_list.focused)
        self.assertIsNotNone(frame.file_list.current_item)
        self.assertIsNotNone(frame.file_list.visible_item)

    def test_queue_table_landing_uses_existing_selection_before_defaulting(self):
        class FakeItem:
            def __init__(self, ok):
                self._ok = ok

            def IsOk(self):
                return self._ok

        class FakeFileList:
            def __init__(self):
                self.current = FakeItem(False)
                self.selected_rows = []
                self.current_row = None

            def GetCurrentItem(self):
                return self.current

            def RowToItem(self, row):
                self.current_row = row
                return FakeItem(True)

            def SelectRow(self, row):
                self.selected_rows.append(row)

            def SetCurrentItem(self, item):
                pass

            def EnsureVisible(self, item):
                pass

            def SetFocus(self):
                pass

        frame = types.SimpleNamespace(
            file_list=FakeFileList(),
            queue=[{'path': 'a.pdf'}, {'path': 'b.pdf'}, {'path': 'c.pdf'}],
            GetSelectedIndices=lambda: [2],
        )

        landed = chronicle_gui.MainFrame.EnsureQueueTableLanding(frame, focus=False)

        self.assertTrue(landed)
        self.assertEqual(frame.file_list.current_row, 2)
        self.assertEqual(frame.file_list.selected_rows, [2])

    def test_queue_table_landing_uses_placeholder_row_when_queue_empty(self):
        class FakeItem:
            def __init__(self, ok):
                self._ok = ok

            def IsOk(self):
                return self._ok

        class FakeFileList:
            def __init__(self):
                self.current_item = None
                self.visible_item = None
                self.focused = False
                self.unselected = False

            def GetItemCount(self):
                return 1

            def RowToItem(self, row):
                return FakeItem(True)

            def UnselectAll(self):
                self.unselected = True

            def SetCurrentItem(self, item):
                self.current_item = item

            def EnsureVisible(self, item):
                self.visible_item = item

            def SetFocus(self):
                self.focused = True

        frame = types.SimpleNamespace(file_list=FakeFileList(), queue=[])

        landed = chronicle_gui.MainFrame.EnsureQueueTableLanding(frame, focus=True, select_row=False)

        self.assertTrue(landed)
        self.assertTrue(frame.file_list.unselected)
        self.assertIsNotNone(frame.file_list.current_item)
        self.assertIsNotNone(frame.file_list.visible_item)
        self.assertTrue(frame.file_list.focused)

    def test_get_selected_indices_ignores_empty_placeholder_row(self):
        class FakeItem:
            def IsOk(self):
                return True

        class FakeFileList:
            def GetSelections(self):
                return [FakeItem()]

            def ItemToRow(self, item):
                return 0

            def GetSelectedRow(self):
                return 0

        frame = types.SimpleNamespace(file_list=FakeFileList(), queue=[])

        selected = chronicle_gui.MainFrame.GetSelectedIndices(frame)

        self.assertEqual(selected, [])

    def test_refresh_queue_inserts_placeholder_row_when_empty(self):
        class FakeFileList:
            def __init__(self):
                self.rows = []

            def GetCurrentItem(self):
                return None

            def DeleteAllItems(self):
                self.rows.clear()

            def AppendItem(self, values):
                self.rows.append(values)

            def UnselectAll(self):
                pass

        frame = types.SimpleNamespace(
            file_list=FakeFileList(),
            queue=[],
            GetSelectedIndices=lambda: [],
            UpdateQueueButtons=lambda: None,
            UpdateProgressIndicators=lambda: None,
        )

        chronicle_gui.MainFrame.RefreshQueue(frame)

        self.assertEqual(frame.file_list.rows, [[chronicle_gui.QUEUE_EMPTY_PLACEHOLDER]])

    def test_queue_accessibility_description_includes_columns_and_selection_state(self):
        name = chronicle_gui.build_queue_accessibility_name(3, 2)
        description = chronicle_gui.build_queue_accessibility_description(3, 2)

        self.assertIn("Files Table", name)
        self.assertIn("3 rows", name)
        self.assertIn("2 selected", name)
        self.assertIn("columns Name, Reading Settings, and Status", description)
        self.assertIn("2 rows are currently selected", description)
        self.assertIn("Task Actions for selected file commands", description)

    def test_prompt_requires_real_image_descriptions_not_filenames(self):
        cfg = self._base_cfg(image_descriptions=True)

        cli_prompt = chronicle.get_prompt(cfg)
        gui_prompt = chronicle_gui.build_prompt(cfg)

        for prompt in (cli_prompt, gui_prompt):
            self.assertIn("title-page artwork", prompt)
            self.assertIn("instead of omitting it or substituting a source filename", prompt)

    def test_strip_synthetic_page_filename_headings_removes_image_extensions_from_citations(self):
        html_raw = "<header><cite>The National Archives' reference WO-95-1668-1_001.jpg</cite></header>"

        cleaned_html = chronicle_gui.strip_synthetic_page_filename_headings(html_raw, "html")

        self.assertIn("WO-95-1668-1_001", cleaned_html)
        self.assertNotIn(".jpg", cleaned_html.lower())

    def test_gui_pdf_chunk_pages_are_more_conservative_for_slow_engines_and_large_newspapers(self):
        self.assertEqual(chronicle_gui.get_pdf_chunk_pages(DEFAULT_CLAUDE_MODEL, "newspaper", 36), 1)
        self.assertEqual(chronicle_gui.get_pdf_chunk_pages("gpt-4o", "newspaper", 36), 1)
        self.assertEqual(chronicle_gui.get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 36), 2)
        self.assertEqual(chronicle_gui.get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 8, file_size_mb=8.9), 1)
        self.assertEqual(chronicle_gui.get_pdf_chunk_pages("gemini-2.5-pro", "comic", 24), 1)
        self.assertEqual(chronicle_gui.get_pdf_chunk_pages("gemini-2.5-pro", "standard", 10), 2)

    def test_cli_pdf_chunk_pages_match_gentle_large_document_policy(self):
        self.assertEqual(chronicle.get_pdf_chunk_pages(DEFAULT_CLAUDE_MODEL, "newspaper", 36), 1)
        self.assertEqual(chronicle.get_pdf_chunk_pages("gpt-4o", "newspaper", 36), 1)
        self.assertEqual(chronicle.get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 36), 2)
        self.assertEqual(chronicle.get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 8, file_size_mb=8.9), 1)

    def test_gui_process_text_wrapper_accepts_page_progress_callback(self):
        captured = {}

        def fake_shared_process_text(*args, **kwargs):
            captured["page_progress_cb"] = kwargs.get("page_progress_cb")
            return "ok"

        with mock.patch.object(chronicle_gui, "shared_process_text", side_effect=fake_shared_process_text):
            result = chronicle_gui.process_text(
                client=object(),
                path="/tmp/example.docx",
                out="/tmp/example.tmp",
                ext=".docx",
                fmt="docx",
                prompt="prompt",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=[],
                log_cb=lambda message: None,
                pause_cb=lambda: None,
                page_progress_cb="progress-marker",
            )

        self.assertEqual(result, "ok")
        self.assertEqual(captured["page_progress_cb"], "progress-marker")

    def test_gui_process_epub_wrapper_accepts_page_progress_callback(self):
        captured = {}

        def fake_shared_process_epub(*args, **kwargs):
            captured["page_progress_cb"] = kwargs.get("page_progress_cb")
            return "ok"

        with mock.patch.object(chronicle_gui, "shared_process_epub", side_effect=fake_shared_process_epub):
            result = chronicle_gui.process_epub(
                client=object(),
                path="/tmp/example.epub",
                out="/tmp/example.tmp",
                fmt="epub",
                prompt="prompt",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=[],
                log_cb=lambda message: None,
                pause_cb=lambda: None,
                page_progress_cb="progress-marker",
            )

        self.assertEqual(result, "ok")
        self.assertEqual(captured["page_progress_cb"], "progress-marker")

    def test_gui_wait_for_gemini_upload_ready_times_out_instead_of_hanging_forever(self):
        upload = types.SimpleNamespace(name="files/123", state=types.SimpleNamespace(name="PROCESSING"))
        client = types.SimpleNamespace(files=types.SimpleNamespace(get=lambda name: upload))
        clock = iter([0.0, 0.0, 1.0, 2.1])

        with self.assertRaises(TimeoutError):
            chronicle_gui.wait_for_gemini_upload_ready(
                client,
                upload,
                log_cb=lambda *_args, **_kwargs: None,
                poll_sec=0.5,
                max_wait_sec=2.0,
                time_fn=lambda: next(clock),
                sleep_fn=lambda _seconds: None,
            )

    def test_cli_wait_for_gemini_upload_ready_returns_ready_upload(self):
        ready = types.SimpleNamespace(name="files/456", state=types.SimpleNamespace(name="ACTIVE"))
        processing = types.SimpleNamespace(name="files/456", state=types.SimpleNamespace(name="PROCESSING"))
        states = iter([ready])
        client = types.SimpleNamespace(files=types.SimpleNamespace(get=lambda name: next(states)))

        result = chronicle.wait_for_gemini_upload_ready(
            client,
            processing,
            poll_sec=0.5,
            max_wait_sec=5.0,
            time_fn=lambda: 0.0,
            sleep_fn=lambda _seconds: None,
            log_cb=lambda *_args, **_kwargs: None,
        )

        self.assertIs(result, ready)

    def test_gui_process_pdf_gearshifts_down_before_falling_back(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage("page 1 text"), FakePage("page 2 text"), FakePage("page 3 text")]

        class FakeWriter:
            def __init__(self):
                self.pages = []

            def add_page(self, page):
                self.pages.append(page)

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        calls = []
        logs = []
        page_progress = []

        def fake_stream_with_cache(cache_key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None, profile_key=None):
            calls.append(cache_key)
            if len(calls) == 1:
                raise Exception("simulated chunk failure")
            mem.append("ok")
            return "ok"

        with mock.patch.object(chronicle_gui, "PdfReader", FakeReader),              mock.patch.object(chronicle_gui, "PdfWriter", FakeWriter),              mock.patch.object(chronicle_gui, "sha256_file", return_value="fingerprint"),              mock.patch.object(chronicle_gui, "build_payload", return_value=["payload"]),              mock.patch.object(chronicle_gui, "stream_with_cache", side_effect=fake_stream_with_cache),              mock.patch.object(chronicle_gui, "generate_retry", return_value="unused"):
            chronicle_gui.process_pdf(
                client=object(),
                path="dummy.pdf",
                out="dummy.html",
                fmt="html",
                prompt="HISTORICAL NEWSPAPER RULES",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=[],
                log_cb=logs.append,
                page_progress_cb=lambda done, total: page_progress.append((done, total)),
            )

        self.assertEqual(len(calls), 3)
        self.assertIn("0:2", calls[0])
        self.assertIn("0:1", calls[1])
        self.assertIn("1:3", calls[2])
        self.assertTrue(any("Gearshift Triggered" in line for line in logs))
        self.assertTrue(any("Throttling down" in line for line in logs))
        self.assertEqual(page_progress[-1], (3, 3))

    def test_pdf_page_scope_parser_accepts_space_separated_ranges(self):
        selected = chronicle_gui.parse_pdf_page_scope_spec("1-30 185-220 530-574", 574)

        self.assertEqual(selected[0], 0)
        self.assertEqual(selected[29], 29)
        self.assertEqual(selected[30], 184)
        self.assertEqual(selected[-1], 573)

    def test_gui_process_pdf_auto_escalates_single_page_after_flash_failure(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage("page 1 text")]

        class FakeWriter:
            def __init__(self):
                self.pages = []

            def add_page(self, page):
                self.pages.append(page)

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        calls = []
        logs = []

        def fake_stream_with_cache(cache_key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None, profile_key=None):
            calls.append(cache_key)
            if len(calls) == 1:
                raise Exception("simulated flash failure")
            mem.append("ok")
            return "ok"

        with mock.patch.object(chronicle_gui, "PdfReader", FakeReader),              mock.patch.object(chronicle_gui, "PdfWriter", FakeWriter),              mock.patch.object(chronicle_gui, "sha256_file", return_value="fingerprint"),              mock.patch.object(chronicle_gui, "build_payload", return_value=["payload"]),              mock.patch.object(chronicle_gui, "stream_with_cache", side_effect=fake_stream_with_cache),              mock.patch.object(chronicle_gui, "generate_retry", return_value="unused"):
            chronicle_gui.process_pdf(
                client=object(),
                path="dummy.pdf",
                out="dummy.html",
                fmt="html",
                prompt="STANDARD RULES",
                model="gemini-2.5-flash",
                f_obj=None,
                mem=[],
                log_cb=logs.append,
                auto_escalation_model="gemini-2.5-pro",
            )

        self.assertEqual(len(calls), 2)
        self.assertIn("pdf-upload", calls[0])
        self.assertIn("pdf-auto-escalate-upload", calls[1])
        self.assertTrue(any("[Auto Engine] Escalating page 1 to gemini-2.5-pro" in line for line in logs))

    def test_pdf_page_scope_parser_normalizes_mixed_separators(self):
        normalized = chronicle_gui.normalize_pdf_page_scope_text("1-5; 7\n10-12 15")

        self.assertEqual(normalized, "1-5,7,10-12,15")
        self.assertTrue(chronicle_gui.is_valid_pdf_page_scope_text("1-5; 7\n10-12 15"))

    def test_model_tradeoff_text_is_explicit_about_speed_and_strengths(self):
        text = chronicle_gui.get_model_tradeoff_text("gemini-2.5-flash")

        self.assertIn("Fastest", text)
        self.assertIn("clean pages", text)

    def test_gui_exposes_processing_speed_warning_helper(self):
        text = chronicle_gui.get_processing_speed_warning("newspaper", "gemini-2.5-pro")

        self.assertIn("Warning:", text)

    def test_profile_selection_summary_shows_runtime_hint_and_recommendation(self):
        text = chronicle_gui.build_profile_selection_summary("newspaper", "gemini-2.5-flash")

        self.assertIn("Newspapers", text)
        self.assertIn("slowest", text)
        self.assertIn("Recommended engine: Deep Engine (Gemini 2.5 Pro).", text)
        self.assertIn("Current override: Fast Engine (Gemini 2.5 Flash).", text)
        self.assertIn("Engine manually overridden.", text)

    def test_profile_selection_summary_describes_comic_profile(self):
        text = chronicle_gui.build_profile_selection_summary("comic", "gemini-2.5-pro")

        self.assertIn("Comics / Manga / Graphic Novels", text)
        self.assertIn("panel order", text)
        self.assertIn("speech balloons", text)
        self.assertIn("Recommended engine: Deep Engine (Gemini 2.5 Pro).", text)

    def test_html_normalizer_promotes_page_metadata_and_source_footer(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<p>Page 7</p>
<h1>Title</h1>
<p>Body text.</p>
<p>National Library of Australia</p>
<p>https://example.com/source</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertIn("<header><cite>Page 7</cite></header>", normalized)
        self.assertIn("<footer><cite>National Library of Australia<br>https://example.com/source</cite></footer>", normalized)
        self.assertIn('<h1 id="heading-1">Title</h1>', normalized)

    def test_synthetic_page_filename_headings_are_removed_from_reader_output(self):
        html_raw = "<h1>page 002.JPG</h1><p>Real content</p>"
        txt_raw = "# page 002.JPG\nReal content"

        cleaned_html = chronicle_gui.strip_synthetic_page_filename_headings(html_raw, "html")
        cleaned_txt = chronicle_gui.strip_synthetic_page_filename_headings(txt_raw, "txt")

        self.assertNotIn("page 002.JPG", cleaned_html)
        self.assertNotIn("page 002.JPG", cleaned_txt)
        self.assertIn("Real content", cleaned_html)
        self.assertIn("Real content", cleaned_txt)

    def test_gui_epub_save_builds_nav_and_chapter_structure(self):
        captured = {}

        fake_epub = types.SimpleNamespace(
            EpubBook=_FakeEpubBook,
            EpubHtml=_FakeEpubHtml,
            EpubNav=_FakeEpubNav,
            EpubNcx=_FakeEpubNcx,
            write_epub=lambda path, book, opts: captured.update({"path": path, "book": book, "opts": opts}),
        )
        original_epub = chronicle_gui.epub
        chronicle_gui.epub = fake_epub
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                target = os.path.join(tmpdir, "sample.epub")
                chronicle_gui.save_epub(
                    target,
                    "Chronicle Reader Sample",
                    "<h1>Front Matter</h1><p>Intro</p><h2>Chapter One</h2><p>Body</p>",
                    lang_code="en",
                    text_dir="ltr",
                )
        finally:
            chronicle_gui.epub = original_epub

        self.assertEqual(captured["path"], target)
        self.assertEqual(captured["book"].language, "en")
        self.assertEqual(captured["book"].spine[0], "nav")
        self.assertGreaterEqual(len(captured["book"].spine), 2)
        chapter_items = [item for item in captured["book"].items if isinstance(item, _FakeEpubHtml)]
        self.assertGreaterEqual(len(chapter_items), 1)
        self.assertTrue(any('dir="ltr"' in item.content for item in chapter_items))

    def test_cli_epub_save_builds_nav_and_heading_based_chapters(self):
        captured = {}

        fake_epub = types.SimpleNamespace(
            EpubBook=_FakeEpubBook,
            EpubHtml=_FakeEpubHtml,
            EpubNav=_FakeEpubNav,
            EpubNcx=_FakeEpubNcx,
            write_epub=lambda path, book, opts: captured.update({"path": path, "book": book, "opts": opts}),
        )
        original_epub = chronicle.epub
        chronicle.epub = fake_epub
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                target = os.path.join(tmpdir, "sample.epub")
                chronicle.save_as_epub(
                    target,
                    "Chronicle Sample",
                    "<h1>Cover</h1><p>Intro</p><h2>Contents</h2><p>Section</p><h3>Subsection</h3><p>Detail</p>",
                    lang_code="en",
                    text_dir="rtl",
                )
        finally:
            chronicle.epub = original_epub

        self.assertEqual(captured["path"], target)
        self.assertEqual(captured["book"].spine[0], "nav")
        chapter_items = [item for item in captured["book"].items if isinstance(item, _FakeEpubHtml)]
        self.assertGreaterEqual(len(chapter_items), 2)
        self.assertTrue(any('dir="rtl"' in item.content for item in chapter_items))


if __name__ == "__main__":
    unittest.main()
