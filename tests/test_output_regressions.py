import unittest

from chronicle_core import (
    apply_newspaper_html_safety_fallback,
    apply_output_integrity_contract,
    apply_handwriting_audit_flag,
    build_tabular_html_fragment,
    recover_newspaper_header_citation,
    recover_source_attribution_footer,
    normalize_streamed_html_document,
    sanitize_model_output,
    should_flag_handwriting_audit,
)
from chronicle_app.services.prompting import enforce_archival_heading_structure
from tools.audit_handwriting_outputs import audit_file


class OutputRegressionTest(unittest.TestCase):
    def test_html_sanitizer_strips_wrapping_fence_markers(self):
        raw = "```html\n<h2>Title</h2>\n<p>Body</p>\n```"

        cleaned = sanitize_model_output(raw, "html")

        self.assertEqual(cleaned, "<h2>Title</h2>\n<p>Body</p>")
        self.assertNotIn("```", cleaned)

    def test_html_sanitizer_flattens_breaks_inside_headings(self):
        raw = "<h2>CHAPTER I.<br>Down the Rabbit-Hole</h2>"

        cleaned = sanitize_model_output(raw, "html")

        self.assertEqual(cleaned, "<h2>CHAPTER I. Down the Rabbit-Hole</h2>")
        self.assertNotIn("<br", cleaned.lower())

    def test_html_sanitizer_strips_nested_document_wrappers_and_inline_styles(self):
        raw = """<!DOCTYPE html>
<html>
<head><style>.x { display:grid; }</style></head>
<body>
<main>
<div style="display:grid"><h1>News</h1><p style="color:red">Body</p></div>
</main>
</body>
</html>"""

        cleaned = sanitize_model_output(raw, "html")

        self.assertNotIn("<!DOCTYPE html>", cleaned)
        self.assertNotIn("<html", cleaned.lower())
        self.assertNotIn("<head", cleaned.lower())
        self.assertNotIn("<body", cleaned.lower())
        self.assertNotIn("<main", cleaned.lower())
        self.assertNotIn("<style", cleaned.lower())
        self.assertNotIn('style="', cleaned.lower())
        self.assertIn("<h1>News</h1>", cleaned)
        self.assertIn("<p>Body</p>", cleaned)

    def test_html_sanitizer_strips_inline_base64_image_payloads(self):
        raw = '<p><img alt="Form logo" src="data:image/png;base64,QUJDREVGRw=="></p>'

        cleaned = sanitize_model_output(raw, "html")

        self.assertNotIn("data:image/png;base64", cleaned.lower())
        self.assertIn('src="about:blank"', cleaned)

    def test_html_sanitizer_strips_about_blank_base64_tail(self):
        raw = '<p><img src="about:blank' + ('A' * 300) + '"></p>'

        cleaned = sanitize_model_output(raw, "html")

        self.assertEqual(cleaned, '<p><img src="about:blank"></p>')

    def test_html_sanitizer_strips_malformed_about_blank_image_payload(self):
        raw = '<p><img src="about:blankw0KGgoAAAANSUhEUgAAAD0AAAA3CAYAAAAWv4tGAAAA"></p>'

        cleaned = sanitize_model_output(raw, "html")

        self.assertEqual(cleaned, '<p><img src="about:blank"></p>')

    def test_html_sanitizer_strips_unclosed_inline_image_tag(self):
        raw = '<p><img src="data:image/jpeg;base64,QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=</p>'

        cleaned = sanitize_model_output(raw, "html")

        self.assertEqual(cleaned, '<p><img src="about:blank"></p>')

    def test_html_sanitizer_strips_bare_split_image_payload_fragment(self):
        raw = '<p><img src="about:blank">QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=</p>'

        cleaned = sanitize_model_output(raw, "html")

        self.assertEqual(cleaned, '<p><img src="about:blank"></p>')

    def test_html_sanitizer_strips_page_wrapper_comments_and_markdown_page_markers(self):
        raw = """<!-- START OF PAGE 1 -->
## Page 1
<section><p>Real text.</p></section>
<!-- END OF PAGE 1 -->"""

        cleaned = sanitize_model_output(raw, "html")

        self.assertNotIn("START OF PAGE", cleaned)
        self.assertNotIn("END OF PAGE", cleaned)
        self.assertNotIn("## Page 1", cleaned)
        self.assertIn("<p>Real text.</p>", cleaned)

    def test_html_sanitizer_converts_markdown_headings_to_real_html_headings(self):
        raw = "## Section Title\n### Byline\n<p>Body.</p>"

        cleaned = sanitize_model_output(raw, "html")

        self.assertIn("<h2>Section Title</h2>", cleaned)
        self.assertIn("<h3>Byline</h3>", cleaned)
        self.assertIn("<p>Body.</p>", cleaned)

    def test_html_sanitizer_dedupes_adjacent_repeated_paragraph_blocks(self):
        raw = (
            "<section>"
            "<p>First paragraph.</p>"
            "<p>Second paragraph.</p>"
            "<p>First paragraph.</p>"
            "<p>Second paragraph.</p>"
            "</section>"
        )

        cleaned = sanitize_model_output(raw, "html")

        self.assertEqual(cleaned.count("<p>First paragraph.</p>"), 1)
        self.assertEqual(cleaned.count("<p>Second paragraph.</p>"), 1)

    def test_html_sanitizer_strips_placeholder_and_empty_source_images(self):
        raw = (
            "<figure>"
            '<img alt="Broken image" src="IMAGE_PLACEHOLDER"/>'
            '<img alt="Broken image suffixed" src="IMAGE_PLACEHOLDER_1"/>'
            '<img alt="Broken image 2" src="IMAGE_URL"/>'
            '<img alt="Broken image 3" src="IMAGE_URL_2"/>'
            '<img alt="Empty image" src=""/>'
            "<figcaption>[Image Description: Still useful.]</figcaption>"
            "</figure>"
        )

        cleaned = sanitize_model_output(raw, "html")

        self.assertNotIn("IMAGE_PLACEHOLDER", cleaned)
        self.assertNotIn("IMAGE_PLACEHOLDER_1", cleaned)
        self.assertNotIn("IMAGE_URL", cleaned)
        self.assertNotIn("IMAGE_URL_2", cleaned)
        self.assertNotIn('src=""', cleaned)
        self.assertIn("Still useful.", cleaned)

    def test_html_normalizer_generates_toc_and_heading_ids_inside_main(self):
        raw = """<main id="content" role="main">
<h1>Document Title</h1>
<p>Intro.</p>
<h2>Section One</h2>
<h3>Detail</h3>
</main>"""

        wrapped = f"<!DOCTYPE html><html><body>{raw}</body></html>"
        cleaned = normalize_streamed_html_document(wrapped)

        self.assertIn('<nav role="navigation" aria-label="Table of Contents">', cleaned)
        self.assertIn('<a href="#heading-1">Document Title</a>', cleaned)
        self.assertIn('<a href="#heading-2">Section One</a>', cleaned)
        self.assertIn('<a href="#heading-3">Detail</a>', cleaned)
        self.assertIn('<h1 id="heading-1">Document Title</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">Section One</h2>', cleaned)
        self.assertIn('<h3 id="heading-3">Detail</h3>', cleaned)
        self.assertRegex(cleaned, r'<main id="content" role="main">\s*<nav role="navigation" aria-label="Table of Contents">')

    def test_html_normalizer_rebuilds_toc_without_duplicate_nav_blocks(self):
        raw = """<main id="content" role="main">
<nav role="navigation" aria-label="Table of Contents">
<h2>Table of Contents</h2>
<ul><li><a href="#stale">Old</a></li></ul>
</nav>
<h1>Fresh Title</h1>
</main>"""

        wrapped = f"<!DOCTYPE html><html><body>{raw}</body></html>"
        cleaned = normalize_streamed_html_document(wrapped)

        self.assertEqual(cleaned.count('aria-label="Table of Contents"'), 1)
        self.assertIn('<a href="#heading-1">Fresh Title</a>', cleaned)
        self.assertNotIn('href="#stale"', cleaned)

    def test_html_normalizer_caps_large_toc_to_higher_level_unique_headings(self):
        headings = []
        for idx in range(1, 90):
            headings.append(f"<h1>Chapter {idx}</h1>")
            headings.append("<h2>Definitions</h2>")
            headings.append(f"<h3>Section {idx}</h3>")
        raw = "<main id=\"content\" role=\"main\">" + "".join(headings) + "</main>"

        cleaned = normalize_streamed_html_document(f"<!DOCTYPE html><html><body>{raw}</body></html>")

        self.assertIn('<a href="#heading-1">Chapter 1</a>', cleaned)
        self.assertEqual(cleaned.count('>Definitions</a>'), 1)
        self.assertNotIn('>Section 1</a>', cleaned)

    def test_html_normalizer_strips_repeated_periodical_running_head_h1s(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Oyungezer 190 - Standart Kalite</title></head>
<body>
<main id="content" role="main">
<footer>Oyungezer EYLUL 2023 105</footer>
<header><h1>Meddya</h1></header>
<section><h2>GRAN TURISMO</h2><p>Body.</p></section>
<footer>Oyungezer EYLUL 2023 107</footer>
<header><h1>Meddya</h1></header>
<section><h2>BLUE BEETLE</h2><p>Body.</p></section>
<footer>Oyungezer EYLUL 2023 109</footer>
<header><h1>Meddya</h1></header>
<section><h2>AHSOKA</h2><p>Body.</p></section>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn(">Meddya</h1>", cleaned)
        self.assertIn(">GRAN TURISMO</a>", cleaned)
        self.assertIn(">BLUE BEETLE</a>", cleaned)
        self.assertIn(">AHSOKA</a>", cleaned)

    def test_html_normalizer_strips_probable_page_furniture_triplets(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<p>22</p>
<p>Aged Care Bill 2024</p>
<p>No. , 2024</p>
<h1>Part 1</h1>
<p>Real body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>22</p>", cleaned)
        self.assertNotIn("<p>Aged Care Bill 2024</p>", cleaned)
        self.assertNotIn("<p>No. , 2024</p>", cleaned)
        self.assertIn("Real body text.", cleaned)

    def test_html_normalizer_strips_legal_running_head_paragraphs_and_footers(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<p>viii Aged Care Bill 2024 No. , 2024</p>
<footer>Aged Care Bill 2024 No. , 2024</footer>
<footer>No. , 2024 Aged Care Bill 2024</footer>
<p>Real body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("viii Aged Care Bill 2024 No. , 2024", cleaned)
        self.assertNotIn("<footer>Aged Care Bill 2024 No. , 2024</footer>", cleaned)
        self.assertNotIn("<footer>No. , 2024 Aged Care Bill 2024</footer>", cleaned)
        self.assertIn("Real body text.", cleaned)

    def test_html_normalizer_strips_legal_running_head_footer_with_nbsp_padding(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<p>Real body text.</p>
<footer><p>No. &nbsp;&nbsp;&nbsp;&nbsp;, 2024 &nbsp;&nbsp;&nbsp;&nbsp; Aged Care Bill 2024 &nbsp;&nbsp;&nbsp;&nbsp; [Original Page Number: 179]</p></footer>
<p>More body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Aged Care Bill 2024", cleaned)
        self.assertNotIn("[Original Page Number: 179]", cleaned)
        self.assertIn("Real body text.", cleaned)
        self.assertIn("More body text.", cleaned)

    def test_html_normalizer_strips_legal_running_head_table_row(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<table><tbody><tr><td>No. , 2024</td><td>Aged Care Bill 2024</td><td>185</td></tr></tbody></table>
<p>Real body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<td>No. , 2024</td>", cleaned)
        self.assertNotIn("<td>Aged Care Bill 2024</td>", cleaned)
        self.assertIn("Real body text.", cleaned)

    def test_html_normalizer_collapses_legal_header_citation_to_single_page_marker(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<p>Aged Care Bill 2024</p>
<header><cite>
[Original Page Number: 2]
<p>Chapter 1 Introduction</p>
<p>Part 1 Preliminary</p>
<p>Section 2</p>
</cite></header>
<p><b>2 Commencement</b></p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("<header><cite>[Original Page Number: 2]</cite></header>", cleaned)
        self.assertNotIn("Chapter 1 Introduction", cleaned)
        self.assertNotIn("Part 1 Preliminary", cleaned)
        self.assertNotIn("Section 2", cleaned)
        self.assertNotIn("<p>Aged Care Bill 2024</p>", cleaned)

    def test_html_normalizer_promotes_bold_numbered_legal_clauses_to_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<h1>Chapter 1-Introduction</h1>
<h2>Part 1-Preliminary</h2>
<p><b>1 Short title</b></p>
<p>This Act is the Aged Care Act 2024.</p>
<p><b>2 Commencement</b></p>
<p>Commencement text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">1 Short title</h4>", cleaned)
        self.assertIn(">2 Commencement</h4>", cleaned)
        self.assertNotIn("<p><b>1 Short title</b></p>", cleaned)

    def test_html_normalizer_strips_legal_breadcrumb_paragraphs_after_page_marker(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<h1>A Bill for an Act about aged care, and for related purposes</h1>
<h2>Chapter 1-Introduction</h2>
<h3>Part 1-Preliminary</h3>
<p>[Original Page Number: 2]</p>
<p>Chapter 1 Introduction</p>
<p>Part 1 Preliminary</p>
<p>Section 2</p>
<h4>2 Commencement</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("[Original Page Number: 2]", cleaned)
        self.assertIn(">2 Commencement</h4>", cleaned)
        self.assertNotIn("<p>Chapter 1 Introduction</p>", cleaned)
        self.assertNotIn("<p>Part 1 Preliminary</p>", cleaned)
        self.assertNotIn("<p>Section 2</p>", cleaned)

    def test_output_integrity_contract_promotes_plain_legal_paragraphs_and_strips_breadcrumbs(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care, and for related purposes</p>
<p>The Parliament of Australia enacts:</p>
<p>Chapter 1-Introduction</p>
<p>Part 1-Preliminary</p>
<p>1 Short title</p>
<p>This Act is the Aged Care Act 2024.</p>
<p>[Original Page Number: 2]</p>
<p>Chapter 1 Introduction</p>
<p>Part 1 Preliminary</p>
<p>Section 2</p>
<p>2 Commencement</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = apply_output_integrity_contract(raw, "html", "legal")

        self.assertIn("<h2>Chapter 1 Introduction</h2>", cleaned)
        self.assertIn("<h3>Part 1 Preliminary</h3>", cleaned)
        self.assertIn("<h4>1 Short title</h4>", cleaned)
        self.assertIn("<h4>2 Commencement</h4>", cleaned)
        self.assertNotIn("<p>Chapter 1 Introduction</p>", cleaned)
        self.assertNotIn("<p>Part 1 Preliminary</p>", cleaned)
        self.assertNotIn("<p>Section 2</p>", cleaned)

    def test_output_integrity_contract_collapses_duplicated_clause_number_before_heading_promotion(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>2 2 Commencement</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = apply_output_integrity_contract(raw, "html", "legal")

        self.assertIn("<h4>2 Commencement</h4>", cleaned)
        self.assertNotIn("2 2 Commencement", cleaned)

    def test_output_integrity_contract_strips_numeric_ladder_paragraphs_around_legal_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>[Original Page Number: 1]</p>
<p>1<br/>2<br/>3</p>
<p>A Bill for an Act about aged care</p>
<p>Chapter 1-Introduction</p>
<p>5<br/>6</p>
<p>Part 1-Preliminary</p>
<p>7<br/>8</p>
<p>1 Short title</p>
</main>
</body>
</html>"""

        cleaned = apply_output_integrity_contract(raw, "html", "legal")

        self.assertIn("<h2>Chapter 1 Introduction</h2>", cleaned)
        self.assertIn("<h3>Part 1 Preliminary</h3>", cleaned)
        self.assertIn("<h4>1 Short title</h4>", cleaned)
        self.assertNotIn("1<br/>2<br/>3", cleaned)
        self.assertNotIn("5<br/>6", cleaned)
        self.assertNotIn("7<br/>8", cleaned)

    def test_output_integrity_contract_splits_mixed_legal_break_paragraphs_before_heading_promotion(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care, and for related purposes<br/>The Parliament of Australia enacts:<br/>Chapter 1-Introduction</p>
<p>5<br/>Part 1-Preliminary<br/>6</p>
<p><b>1 Short title</b><br/>This Act is the <i>Aged Care Act 2024</i>.</p>
</main>
</body>
</html>"""

        cleaned = apply_output_integrity_contract(raw, "html", "legal")

        self.assertIn("<h2>Chapter 1 Introduction</h2>", cleaned)
        self.assertIn("<h3>Part 1 Preliminary</h3>", cleaned)
        self.assertNotIn("<h4>5 Part 1-Preliminary 6</h4>", cleaned)
        self.assertIn("<h4>1 Short title</h4>", cleaned)
        self.assertNotIn("<p><b>1 Short title</b>", cleaned)

    def test_html_toc_ignores_noise_heavy_fused_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h1>Title</h1>
<h2>Division 2-Protections relating to supporters 34 Protection of individual against liability for actions of supporter 62 35 Protection of supporter against liability 62 36 Offence for abuse of position as supporter 62 Division 3-Registration of supporters</h2>
<h2>Part 1-Preliminary</h2>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertIn('href="#heading-1">Title</a>', cleaned)
        self.assertIn('href="#heading-2">Part 1-Preliminary</a>', cleaned)
        self.assertNotIn("Division 2-Protections relating to supporters 34 Protection", nav_block)

    def test_html_toc_legal_mode_prefers_longest_heading_for_same_chapter(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h1>Aged Care Bill 2024</h1>
<h2>Chapter 3 Registered providers, aged care workers and aged care digital platform operators</h2>
<h2>Chapter 3 Registered providers, aged care</h2>
<h2>Chapter 3</h2>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertIn("Chapter 3 Registered providers, aged care workers and aged care digital platform operators", nav_block)
        self.assertNotIn('>Chapter 3 Registered providers, aged care</a>', nav_block)
        self.assertNotIn('>Chapter 3</a>', nav_block)

    def test_html_toc_legal_mode_rejects_numeric_and_cross_reference_heading_noise(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h1>Aged Care Bill 2024</h1>
<h2>498.</h2>
<h2>Chapter 3 see subsection 179(2).</h2>
<h2>Chapter 4 Funding of aged care services</h2>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn('>498.</a>', nav_block)
        self.assertNotIn('>Chapter 3 see subsection 179(2).</a>', nav_block)
        self.assertIn('>Chapter 4 Funding of aged care services</a>', nav_block)

    def test_html_normalizer_strips_probable_span_page_furniture_blocks(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<section><span>x</span><span>Aged Care Bill 2024</span><span>No. , 2024</span></section>
<h1>Title</h1>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<span>x</span>", cleaned)
        self.assertIn('<h1 id="heading-1">Title</h1>', cleaned)

    def test_html_normalizer_strips_leaked_head_wrapper_fragments_inside_body(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<h1>Title</h1>
<p>Intro text.</p>
<!DOCTYPE html>
<head>
    <meta charset="UTF-8">
    <title>Transcription</title>
<div>
    <h2>Section</h2>
    <p>Body text.</p>
</div>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertEqual(cleaned.lower().count("<!doctype html>"), 1)
        self.assertEqual(cleaned.lower().count("<head"), 1)
        self.assertIn("<h2", cleaned)
        self.assertIn("Body text.", cleaned)

    def test_html_normalizer_strips_repeated_nested_document_wrappers_inside_body(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<h1>Title</h1>
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head><meta charset="UTF-8"><title>Transcription</title></head>
<body>
<p>1</p>
<p>2</p>
<p>3</p>
<h2>Section</h2>
<p>Body text.</p>
</body>
</html>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertEqual(cleaned.lower().count("<!doctype html>"), 1)
        self.assertEqual(cleaned.lower().count("<html"), 1)
        self.assertEqual(cleaned.lower().count("<body"), 1)
        self.assertIn("Body text.", cleaned)

    def test_html_normalizer_strips_dense_bare_line_number_clusters(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<h2>Chapter 1</h2>
<p>1</p>
<p>2</p>
<p>3</p>
<p>4</p>
<p>5</p>
<h3>1 Short title</h3>
<p>This Act may be cited as the Aged Care Act 2024.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>1</p>", cleaned)
        self.assertNotIn("<p>5</p>", cleaned)
        self.assertIn("1 Short title", cleaned)
        self.assertIn("Aged Care Act 2024", cleaned)

    def test_html_normalizer_strips_bare_page_number_blocks(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<h2>Introduction</h2>
<p>Lead text.</p>
<p>1</p>
<p>Continued text.</p>
<section>2</section>
<p>More text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>1</p>", cleaned)
        self.assertNotIn("<section>2</section>", cleaned)
        self.assertIn("Continued text.", cleaned)
        self.assertIn("More text.", cleaned)

    def test_html_normalizer_strips_running_head_after_original_page_marker(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<p>[Original Page Number: 517]</p>
<header><cite>Aged Care Bill 2024</cite></header>
<h1>Chapter 8 Miscellaneous</h1>
<p>Real body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("[Original Page Number: 517]", cleaned)
        self.assertNotIn("<header><cite>Aged Care Bill 2024</cite></header>", cleaned)
        self.assertIn("Chapter 8 Miscellaneous", cleaned)

    def test_newspaper_html_safety_fallback_simplifies_dense_div_layout(self):
        raw = (
            '<div id="masthead"><div class="col"><h1>Title</h1></div></div>'
            + ("<div class=\"col\"><p>Body</p></div>" * 300)
        )

        cleaned = apply_newspaper_html_safety_fallback(raw, "html", "newspaper", max_chars=200)

        self.assertIn("Newspaper safety fallback", cleaned)
        body_without_notice = cleaned.split("</div>", 1)[-1]
        self.assertNotIn('class="', body_without_notice.lower())
        self.assertNotIn('id="', body_without_notice.lower())
        self.assertNotIn("<div", body_without_notice.lower())
        self.assertIn("<section>", cleaned.lower())

    def test_newspaper_html_safety_fallback_keeps_notice_inside_full_document_wrapper(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>News</title></head>
<body>
<main id="content" role="main">""" + ("<div><p>Body</p></div>" * 500) + """</main>
</body>
</html>"""

        cleaned = apply_newspaper_html_safety_fallback(raw, "html", "newspaper", max_chars=200)

        self.assertTrue(cleaned.lstrip().startswith("<!DOCTYPE html>"))
        self.assertIn('<main id="content" role="main"><div class="chronicle-audit-note"', cleaned)

    def test_newspaper_html_safety_fallback_moves_existing_leading_notice_inside_document(self):
        raw = """<div class="chronicle-audit-note" role="note" aria-label="Newspaper Safety Fallback"><p><strong>Chronicle Note:</strong> Newspaper safety fallback was applied to keep this reading output stable. Layout has been simplified to plain semantic blocks.</p></div>
<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>News</title></head>
<body>
<main id="content" role="main"><section><p>Body</p></section></main>
</body>
</html>"""

        cleaned = apply_newspaper_html_safety_fallback(raw, "html", "newspaper", max_chars=10_000)

        self.assertTrue(cleaned.lstrip().startswith("<!DOCTYPE html>"))
        self.assertIn('<main id="content" role="main"><div class="chronicle-audit-note"', cleaned)
        self.assertNotIn('<div class="chronicle-audit-note" role="note" aria-label="Newspaper Safety Fallback"><p><strong>Chronicle Note:</strong>', cleaned.split("<!DOCTYPE html>", 1)[0])

    def test_source_attribution_footer_is_recovered_from_pdf_signals(self):
        class _FakePage:
            def extract_text(self):
                return "National Library of Australia http://nla.gov.au/nla.news-page18959925"

        class _FakeReader:
            metadata = {"/Author": "National Library of Australia"}
            pages = [_FakePage()]

            def __init__(self, path):
                self.path = path

        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header><cite>The Age, Melbourne, Victoria, Wednesday, April 30, 1930, Page 12</cite></header>
<h1>The Age.</h1>
</main>
</body>
</html>"""

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "trove.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            cleaned = recover_source_attribution_footer(
                raw,
                "html",
                "newspaper",
                source_path=str(pdf_path),
                pdf_reader_cls=_FakeReader,
            )

        self.assertIn("<footer><cite>National Library of Australia</cite>", cleaned)
        self.assertIn("http://nla.gov.au/nla.news-page18959925", cleaned)

    def test_source_attribution_footer_infers_internet_archive_from_source_filename(self):
        class _FakePage:
            def extract_text(self):
                return "Scanned newspaper text without explicit source URL."

        class _FakeReader:
            metadata = {}
            pages = [_FakePage()]

            def __init__(self, path):
                self.path = path

        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header><cite>Example Newspaper, Wednesday, September 24, 1997</cite></header>
<h1>Example</h1>
</main>
</body>
</html>"""

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "cawsahs_000195_subset_2pages.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            cleaned = recover_source_attribution_footer(
                raw,
                "html",
                "newspaper",
                source_path=str(pdf_path),
                pdf_reader_cls=_FakeReader,
            )

        self.assertIn("<footer><cite>Internet Archive</cite>", cleaned)
        self.assertIn("https://archive.org/details/cawsahs_000195", cleaned)

    def test_html_normalizer_upgrades_form_semantics_and_text_fields(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>[Checkbox: Empty] No</p>
<p>[Checkbox: Selected] Yes</p>
<p>[Text input area]</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("[Radio Button: Empty] No", cleaned)
        self.assertIn("[Radio Button: Selected] Yes", cleaned)
        self.assertIn("[Text Field: Empty]", cleaned)
        self.assertNotIn("[Text input area]", cleaned)

    def test_html_normalizer_converts_raw_text_inputs_to_text_field_markers(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Name <input type="text"/></p>
<p>Notes</p>
<textarea>prefilled</textarea>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("[Text Field: Empty]", cleaned)
        self.assertNotIn('<input type="text"', cleaned)
        self.assertNotIn("<textarea", cleaned.lower())

    def test_html_normalizer_converts_raw_checkbox_and_radio_inputs_to_markers(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p><input type="checkbox" checked/> Subscribe</p>
<p><input type=radio/> Weekly</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("[Checkbox: Selected]", cleaned)
        self.assertIn("[Radio Button: Empty]", cleaned)
        self.assertNotIn('<input type="checkbox"', cleaned)
        self.assertNotIn('<input type="radio"', cleaned)

    def test_html_normalizer_promotes_h3_to_h2_when_no_h2_exists(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h1>The Age.</h1>
<h3>SHIPPING</h3>
<p>Port notices.</p>
<h3>BIRTHS</h3>
<p>Family notices.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h2 id="heading-2">SHIPPING</h2>', cleaned)
        self.assertIn('<h2 id="heading-3">BIRTHS</h2>', cleaned)
        self.assertNotIn("<h3>SHIPPING</h3>", cleaned)

    def test_html_normalizer_promotes_sparse_bare_main_blocks_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
7TH DIVISION<br>
91ST INFY [Infantry] BDE [Brigade]<br>
<br>
21ST BN [Battalion] MANCHESTER REGT [Regiment]<br>
<br>
JAN 1916 - [Struck through: AUG 1918]<br>
1916 NOV - 1917 NOV<br>
<br>
To ITALY
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">7TH DIVISION</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">91ST INFY [Infantry] BDE [Brigade]</h2>', cleaned)
        self.assertIn("<p>21ST BN [Battalion] MANCHESTER REGT [Regiment]</p>", cleaned)
        self.assertIn("<p>JAN 1916 - [Struck through: AUG 1918]</p>", cleaned)
        self.assertIn("<p>1916 NOV - 1917 NOV</p>", cleaned)
        self.assertIn("<p>To ITALY</p>", cleaned)

    def test_html_normalizer_promotes_sparse_paragraph_blocks_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>
  7th Division<br>
  91st Infantry Brigade
</p>
<p>21st Battalion Manchester Regiment</p>
<p>
  January 1916 - <del>August 1918</del><br>
  1916 November - 1917 November
</p>
<p>To ITALY</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">7th Division</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">91st Infantry Brigade</h2>', cleaned)
        self.assertIn("<p>21st Battalion Manchester Regiment</p>", cleaned)
        self.assertIn("<p>January 1916 - <del>August 1918</del></p>", cleaned)
        self.assertIn("<p>1916 November - 1917 November</p>", cleaned)
        self.assertIn("<p>To ITALY</p>", cleaned)

    def test_html_normalizer_promotes_first_two_sparse_paragraphs_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>7TH DIVISION</p>
<p>91ST INFY BDE</p>
<p>21ST BN MANCHESTER REGT</p>
<p>JAN 1916 - <span>AUG 1918</span></p>
<p>1916 NOV - 1917 NOV</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">7TH DIVISION</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">91ST INFY BDE</h2>', cleaned)
        self.assertIn("<p>21ST BN MANCHESTER REGT</p>", cleaned)
        self.assertIn("<p>JAN 1916 - <span>AUG 1918</span></p>", cleaned)

    def test_html_normalizer_promotes_first_h2_to_h1_when_document_starts_at_h2(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Chapter 8 Miscellaneous</h2>
<h3>Part 10 Rules</h3>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">Chapter 8 Miscellaneous</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">Part 10 Rules</h2>', cleaned)

    def test_html_normalizer_promotes_leading_section_paragraphs_to_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>19. THE SUBJUNCTIVE</p>
<p>Section 104.16</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">19. THE SUBJUNCTIVE</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">Section 104.16</h2>', cleaned)

    def test_html_normalizer_recovers_running_header_title_into_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Aug., 1914] THE FIRST CONTINGENT SAILS 83</p>
<p>Body text follows.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">THE FIRST CONTINGENT SAILS</h1>', cleaned)

    def test_html_normalizer_promotes_continuation_list_pages_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header><cite>The National Archives' reference WO-95-1668-1_071.jpg</cite></header>
<p>by 12 midnight tonight</p>
<ol start="5">
  <li><strong>Officers</strong><p>Officers not going into action with the Battalion will join B Echelon tonight -</p></li>
  <li><strong>Ammunition</strong><p>Coys will draw and issue the 2 extra bandoliers per man -</p></li>
</ol>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">by 12 midnight tonight</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">Officers</h2>', cleaned)

    def test_html_normalizer_promotes_numbered_instruction_paragraphs_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>by 12 midnight tonight -</p>
<p>5. Officers Officers not going up with action with the Battalion will join B Echelon tonight -</p>
<p>6. Ammunition. Company will draw and issue the 2 extra bandoliers per man -</p>
<p>7. Runners. Ten runners will again be required by Brigade.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">by 12 midnight tonight -</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">5. Officers</h2>', cleaned)

    def test_html_normalizer_promotes_contextual_legal_header_into_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Chapter 8 Miscellaneous</p>
<p>Part 10 Rules</p>
<h2>Section 602</h2>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">Chapter 8 Miscellaneous</h1>', cleaned)
        self.assertIn('<h3 id="heading-2">Part 10 Rules</h3>', cleaned)
        self.assertIn('<h2 id="heading-3">Section 602</h2>', cleaned)

    def test_html_normalizer_legal_heuristic_skips_military_sparse_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>7th Division</p>
<p>91st Infantry Brigade</p>
<p>21st Battalion Manchester Regiment</p>
<p>January 1916 - August 1918</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">7th Division</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">91st Infantry Brigade</h2>', cleaned)
        self.assertNotIn("<h4>7th Division</h4>", cleaned)

    def test_html_normalizer_promotes_index_h2_to_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>INDEX</h2>
<p>entry</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">INDEX</h1>', cleaned)

    def test_html_normalizer_promotes_first_h3_to_h1_when_no_h1_or_h2_exist(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h3>NOTE</h3>
<p>Body text.</p>
<h3>HINT</h3>
<p>More text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">NOTE</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">HINT</h2>', cleaned)

    def test_html_normalizer_promotes_ordered_list_instruction_page_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>by 12 midnight tonight</p>
<ol start="5">
  <li>Officers<br>Officers not going into action with the Battalion will join B Echelon tonight -</li>
  <li>Ammunition<br>Companies will draw and issue the 2 extra bandoliers per man -</li>
</ol>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">by 12 midnight tonight</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">Officers</h2>', cleaned)

    def test_html_normalizer_promotes_strong_paragraph_labels_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<section>
  <p><strong>NOTE</strong><br>Body text.</p>
  <p><strong>HINT</strong><br>More text.</p>
</section>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">NOTE</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">HINT</h2>', cleaned)

    def test_html_normalizer_promotes_definition_list_instruction_page_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>by 12 midnight tonight</p>
<dl>
  <dt>5. Officers</dt>
  <dd>Officers not going into action with the Battalion will join B Echelon tonight -</dd>
  <dt>6. Ammunition</dt>
  <dd>Companies will draw and issue the 2 extra bandoliers per man -</dd>
</dl>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">by 12 midnight tonight</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">5. Officers</h2>', cleaned)

    def test_html_normalizer_promotes_bold_paragraph_labels_into_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p><b>NOTE</b><br>Body text.</p>
<p><b>HINT</b><br>More text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">NOTE</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">HINT</h2>', cleaned)

    def test_html_normalizer_promotes_short_h2_with_bold_followup(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>NOTE</h2>
<p>Body text.</p>
<p><b>HINT</b></p>
<p>More text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">NOTE</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">HINT</h2>', cleaned)

    def test_html_normalizer_promotes_bold_only_followup_after_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h1>NOTE</h1>
<p>Body text.</p>
<p><b>HINT</b></p>
<p>More text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">NOTE</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">HINT</h2>', cleaned)

    def test_html_normalizer_promotes_short_first_h2_when_multiple_content_h2s_exist(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<nav role="navigation" aria-label="Table of Contents"><h2>Table of Contents</h2></nav>
<h2>NOTE</h2>
<p>Body text.</p>
<h2>HINT</h2>
<p>More text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('<h1 id="heading-1">NOTE</h1>', cleaned)
        self.assertIn('<h2 id="heading-2">HINT</h2>', cleaned)

    def test_newspaper_header_citation_is_recovered_from_title_metadata(self):
        class _FakePage:
            def extract_text(self):
                return "National Library of Australia http://nla.gov.au/nla.news-article134243010"

        class _FakeReader:
            metadata = {
                "/Title": "Newcastle Morning Herald and Miners' Advocate (NSW : 1876 - 1954), Saturday 15 November 1947, page 1"
            }
            pages = [_FakePage()]

            def __init__(self, path):
                self.path = path

        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<article><h1>Young Woman Electrocuted Using Cleaner</h1></article>
</main>
</body>
</html>"""

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "article.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            cleaned = recover_newspaper_header_citation(
                raw,
                "html",
                "newspaper",
                source_path=str(pdf_path),
                pdf_reader_cls=_FakeReader,
            )

        self.assertIn(
            "<header><cite>Newcastle Morning Herald and Miners&#x27; Advocate (NSW : 1876 - 1954), Saturday 15 November 1947, page 1</cite></header>",
            cleaned,
        )

    def test_newspaper_header_citation_is_recovered_from_heading_date_and_filename_page(self):
        class _FakePage:
            def extract_text(self):
                return "National Library of Australia http://nla.gov.au/nla.news-page18959925"

        class _FakeReader:
            metadata = {"/Author": "National Library of Australia"}
            pages = [_FakePage()]

            def __init__(self, path):
                self.path = path

        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<section>
<h1>The Age.</h1>
<p>MELBOURNE, WEDNESDAY, APRIL 30, 1930.</p>
</section>
</main>
</body>
</html>"""

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "trove-the-age-1930-04-30-page-1.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            cleaned = recover_newspaper_header_citation(
                raw,
                "html",
                "newspaper",
                source_path=str(pdf_path),
                pdf_reader_cls=_FakeReader,
            )

        self.assertIn(
            "<header><cite>The Age, MELBOURNE, WEDNESDAY, APRIL 30, 1930, Page 1</cite></header>",
            cleaned,
        )

    def test_html_normalizer_flattens_breaks_inside_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<h2>CHAPTER I.<br>Down the Rabbit-Hole</h2>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertIn('<h2 id="heading-1">CHAPTER I. Down the Rabbit-Hole</h2>', normalized)
        self.assertNotIn("<h2>CHAPTER I.<br>Down the Rabbit-Hole</h2>", normalized)

    def test_html_normalizer_removes_nested_main_wrappers(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<main>
<h1>Nested Title</h1>
</main>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertEqual(normalized.lower().count("<main"), 1)
        self.assertIn('<h1 id="heading-1">Nested Title</h1>', normalized)

    def test_html_normalizer_collapses_semantic_cite_whitespace_and_split_footer(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<header>
<cite>Page 1</cite>
</header>
<h1>Title</h1>
<footer>
<cite>National Library of Australia</cite>
<cite>http://nla.gov.au/nla.news-page123</cite>
</footer>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertIn("<header><cite>Page 1</cite></header>", normalized)
        self.assertIn("<footer><cite>National Library of Australia<br>http://nla.gov.au/nla.news-page123</cite></footer>", normalized)

    def test_html_normalizer_strips_legal_breadcrumb_header_block(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header>
<p>Introduction Chapter 1<br/>Definitions and key concepts Part 2<br/>Definitions Division 1</p>
</header>
<p>Section 7</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertNotIn("Introduction Chapter 1", normalized)
        self.assertNotIn("Definitions and key concepts Part 2", normalized)
        self.assertNotIn("Definitions Division 1", normalized)
        self.assertIn("Section 7", normalized)

    def test_html_normalizer_strips_legal_breadcrumb_header_block_with_br_only_lines(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header>
<p>Introduction Chapter 1<br/>Preliminary Part 1</p>
</header>
<section>
<h2>Section 5</h2>
<p>Body text.</p>
</section>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertNotIn("Introduction Chapter 1", normalized)
        self.assertNotIn("Preliminary Part 1", normalized)
        self.assertIn("Section 5", normalized)

    def test_html_normalizer_strips_repeated_legal_restart_after_page_marker(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>[Original Page Number: 2]</p>
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<p>Section 2</p>
<h4>2 Commencement</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertIn("[Original Page Number: 2]", normalized)
        self.assertIn("<h4>2 Commencement</h4>", normalized)
        self.assertNotIn("<h2>Chapter 1 Introduction</h2>", normalized)
        self.assertNotIn("<h3>Part 1 Preliminary</h3>", normalized)
        self.assertNotIn("<p>Section 2</p>", normalized)

    def test_output_integrity_contract_strips_bare_section_label_before_numbered_clause_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<h3>Section 2</h3>
<h4>2 Commencement</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = apply_output_integrity_contract(raw, "html", "legal")

        self.assertIn("<h4>2 Commencement</h4>", cleaned)
        self.assertNotIn(">Section 2</h3>", cleaned)

    def test_html_normalizer_strips_legal_footer_cite_with_page_marker(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Real body text.</p>
<footer><cite>No. 2024 Aged Care Bill 2024</cite><p>[Original Page Number: 69]</p></footer>
<p>More body text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertNotIn("No. 2024 Aged Care Bill 2024", normalized)
        self.assertNotIn("[Original Page Number: 69]", normalized)
        self.assertIn("Real body text.", normalized)
        self.assertIn("More body text.", normalized)

    def test_html_normalizer_strips_legal_running_head_section_block(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Body text.</p>
<section>No. 2024 Aged Care Bill 2024 3</section>
<p>More body text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertNotIn("No. 2024 Aged Care Bill 2024 3", normalized)
        self.assertIn("Body text.", normalized)
        self.assertIn("More body text.", normalized)

    def test_html_normalizer_removes_bare_section_heading_after_late_promotion_pass(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care, and for related purposes</p>
<p>The Parliament of Australia enacts:</p>
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<h2>Section 2</h2>
<h4>2 Commencement</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertIn("<h4>2 Commencement</h4>", normalized)
        self.assertNotIn(">Section 2</h2>", normalized)

    def test_html_normalizer_strips_legal_cite_breadcrumb_block_without_page_marker(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header><cite>
<p>Introduction Chapter 1</p>
<p>Definitions and key concepts Part 2</p>
<p>Key concepts Division 2</p>
<p>Section 21</p>
</cite></header>
<p>Body text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertNotIn("Introduction Chapter 1", normalized)
        self.assertNotIn("Definitions and key concepts Part 2", normalized)
        self.assertNotIn("Key concepts Division 2", normalized)
        self.assertNotIn("Section 21", normalized)
        self.assertIn("Body text.", normalized)

    def test_html_normalizer_strips_inline_legal_breadcrumb_paragraph_block(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Body text.</p>
<p>Introduction Chapter 1<br/>Aged care rights and principles Part 3<br/>Aged care principles Division 2<br/>Section 25</p>
<h4>25 Statement of Principles</h4>
<p>More body text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertNotIn("Introduction Chapter 1", normalized)
        self.assertNotIn("Aged care rights and principles Part 3", normalized)
        self.assertNotIn("Section 25</p>", normalized)
        self.assertIn("<h4>25 Statement of Principles</h4>", normalized)

    def test_html_normalizer_strips_restarted_section_heading_when_clause_is_already_active(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<h4>5 Objects of this Act</h4>
<p>Lead-in text.</p>
<p>[Original Page Number: 8]</p>
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<h2>Section 5</h2>
<p>Continuation text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertIn("<h4>5 Objects of this Act</h4>", normalized)
        self.assertNotIn(">Section 5</h2>", normalized)
        self.assertEqual(normalized.count('<h1 id="heading-1">Chapter 1 Introduction</h1>'), 1)
        self.assertEqual(normalized.count('<h2 id="heading-2">Part 1 Preliminary</h2>'), 1)

    def test_html_normalizer_strips_late_section_heading_before_matching_ordered_list(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<h1>Section 2</h1>
<ol start="2">
  <li><h3>Commencement</h3><p>Body text.</p></li>
</ol>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertNotIn(">Section 2</h1>", normalized)
        self.assertIn("<ol start=\"2\">", normalized)
        self.assertIn("Commencement</h", normalized)

    def test_html_normalizer_strips_late_section_heading_before_alpha_continuation_list(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<ol start="2">
  <li><h3>Objects of this Act</h3><p>The objects are to:</p></li>
</ol>
<h2>Section 5</h2>
<ol type="a">
  <li>First continuation item.</li>
</ol>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertNotIn(">Section 5</h2>", normalized)
        self.assertIn("<ol type=\"a\">", normalized)

    def test_html_normalizer_collapses_hyphen_fused_legal_restart_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Chapter 1-Introduction</h2>
<h3>Part 1-Preliminary</h3>
<h4>5 Objects of this Act</h4>
<p>The objects of this Act are to:</p>
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<ol start="7" type="a">
  <li>Continuation item.</li>
</ol>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertEqual(normalized.count('<h1 id="heading-1">Chapter 1 Introduction</h1>'), 1)
        self.assertEqual(normalized.count('<h2 id="heading-2">Part 1 Preliminary</h2>'), 1)

    def test_html_normalizer_unwraps_footer_wrapped_page_marker(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Body text.</p>
<footer><p>[Original Page Number: 49]</p></footer>
<p>More body text.</p>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertIn("<p>[Original Page Number: 49]</p>", normalized)
        self.assertNotIn("<footer><p>[Original Page Number: 49]</p></footer>", normalized)

    def test_html_normalizer_strips_leading_markup_before_doctype(self):
        raw = """<div class="chronicle-audit-note">Note</div>
<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main"><h1>Title</h1></main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        self.assertTrue(normalized.lstrip().startswith("<!DOCTYPE html>"))
        self.assertNotIn('<div class="chronicle-audit-note">Note</div>\n<!DOCTYPE html>', normalized)

    def test_html_normalizer_strips_body_level_metadata_style_leaks_and_div_wrappers(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<meta charset="UTF-8">
<title>Leaked chunk title</title>
<style>p { color: red; }</style>
<header><cite>Example Page</cite></header>
<div><p style="text-align: left; font-size: smaller;">Body</p></div>
</main>
</body>
</html>"""

        normalized = normalize_streamed_html_document(raw)

        body = normalized.split('<main id="content" role="main">', 1)[1]
        self.assertNotIn('<meta charset="UTF-8">', body)
        self.assertNotIn('<title>Leaked chunk title</title>', body)
        self.assertNotIn('<style>', body)
        self.assertNotIn('style="text-align: left; font-size: smaller;"', body)
        self.assertIn('<section><p>Body</p></section>', body)

    def test_html_normalizer_strips_wrapping_fence_markers(self):
        raw = """```html
<!DOCTYPE html>
<html lang="und" dir="auto">
<head><meta charset="utf-8"><title>Sample</title></head>
<body>
<main id="content" role="main">
<p>Body</p>
</main>
</body>
</html>
```"""

        normalized = normalize_streamed_html_document(raw)

        self.assertIn("<p>Body</p>", normalized)
        self.assertNotIn("```", normalized)

    def test_non_html_sanitizer_strips_html_and_fence_leaks(self):
        raw = "```html\n<div><span>Hello</span></div>\n```"

        cleaned = sanitize_model_output(raw, "txt")

        self.assertEqual(cleaned.strip(), "Hello")
        self.assertNotIn("<div", cleaned.lower())
        self.assertNotIn("```", cleaned)

    def test_non_html_sanitizer_strips_ocr_wrapper_markers(self):
        raw = "==Start of OCR for page 1==\nBody line one.\n==End of OCR for page 1==\n\n==Start of OCR for page 2==\nBody line two.\n==End of OCR for page 2=="

        cleaned = sanitize_model_output(raw, "txt")

        self.assertEqual(cleaned.strip(), "Body line one.\n\nBody line two.")
        self.assertNotIn("Start of OCR", cleaned)
        self.assertNotIn("End of OCR", cleaned)

    def test_non_html_sanitizer_strips_inline_ocr_wrapper_markers_and_duplicate_page_line(self):
        raw = "==End of OCR for page 3==Books by Eoin Colfer\n[Original Page Number: 2]\n2\nBody starts here."

        cleaned = sanitize_model_output(raw, "txt")

        self.assertEqual(cleaned.strip(), "Books by Eoin Colfer\n[Original Page Number: 2]\nBody starts here.")
        self.assertNotIn("End of OCR", cleaned)
        self.assertNotIn("[Original Page Number: 2]\n2\n", cleaned)

    def test_book_plain_text_cleanup_normalizes_dialogue_quotes_and_heading_fusion(self):
        raw = "doesn't know could hurt him . . .# Books by Eoin Colfer\n'Why must you circle so, Butler?' asked Artemis.\n'You know perfectly well why, Artemis,' replied Butler."

        cleaned = sanitize_model_output(raw, "txt", "book", True)

        self.assertIn("doesn't know could hurt him . . .\n# Books by Eoin Colfer", cleaned)
        self.assertIn('"Why must you circle so, Butler?" asked Artemis.', cleaned)
        self.assertIn('"You know perfectly well why, Artemis," replied Butler.', cleaned)

    def test_book_plain_text_cleanup_splits_fused_front_matter_blocks(self):
        raw = (
            "And what he doesn't know could hurt him ...Books by Eoin Colfer\n"
            "ARTEMIS FOWL\n"
            "NEVER BEFORE HAS A CRIMINAL MASTERMIND\n"
            "PENGUIN BOOKS"
        )

        cleaned = sanitize_model_output(raw, "txt", "book", True)

        self.assertIn("hurt him ...\n\nBooks by Eoin Colfer", cleaned)
        self.assertIn("ARTEMIS FOWL\n\nNEVER BEFORE HAS A CRIMINAL MASTERMIND", cleaned)
        self.assertIn("NEVER BEFORE HAS A CRIMINAL MASTERMIND\n\nPENGUIN BOOKS", cleaned)

    def test_book_plain_text_cleanup_infers_missing_page_markers_sequentially(self):
        raw = (
            "[Original Page Number: 52]\n"
            "Chapter opening text.\n"
            "[Original Page Number: 55]\n"
            "Next page text."
        )

        cleaned = sanitize_model_output(raw, "txt", "book", True)

        self.assertIn("[Original Page Number: 53]\n[Original Page Number: 54]\n[Original Page Number: 55]", cleaned)

    def test_book_plain_text_cleanup_normalizes_wrapped_front_matter_quotes(self):
        raw = (
            "'Pacy, playful and very funny, an inventive mix of myth\n"
            "and modernity, magic and crime' - Time\n"
        )

        cleaned = sanitize_model_output(raw, "txt", "book", True)

        self.assertIn('"Pacy, playful and very funny, an inventive mix of myth', cleaned)
        self.assertIn('and modernity, magic and crime" - Time', cleaned)

    def test_book_plain_text_cleanup_removes_numeric_quote_noise_from_barcode_lines(self):
        raw = 'ISBN 0-14-138269-4\n9"780141"382692"\nA$22.95 RRP'

        cleaned = sanitize_model_output(raw, "txt", "book", True)

        self.assertIn("9780141382692", cleaned)
        self.assertNotIn('"', cleaned.splitlines()[1])

    def test_book_plain_text_cleanup_repairs_obvious_suffix_split_scan_wraps(self):
        raw = "Norma was lead-ing Pollione to the pyre.\nThe hero was enlarg-ing rapidly."

        cleaned = sanitize_model_output(raw, "txt", "book", True)

        self.assertIn("leading Pollione", cleaned)
        self.assertIn("enlarging rapidly", cleaned)

    def test_handwriting_audit_flags_long_clean_output_without_uncertainty(self):
        import tempfile
        from pathlib import Path

        html = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Celeste, Michael this is so you understand the explosion and the reason my butt feet genitals chest and back did not burn is because the shorts socks and t-shirt I was wearing was pure cotton and the shiny tracksuit material is very dangerous.</p>
<p>SAFE IS PURE COTTON OR PURE WOOL.</p>
</main>
</body>
</html>"""

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "page 02.html"
            path.write_text(html, encoding="utf-8")
            result = audit_file(path)

        self.assertIn("long_output_without_uncertainty_markers", result.review_flags)
        self.assertGreaterEqual(result.word_count, 45)

    def test_handwriting_audit_trigger_requires_archival_long_text_without_unclear_marker(self):
        html = "<p>" + ("word " * 50) + "</p>"

        self.assertTrue(should_flag_handwriting_audit(html, "html", "archival"))
        self.assertFalse(should_flag_handwriting_audit(html, "html", "medical"))
        self.assertFalse(should_flag_handwriting_audit("<p>short note</p>", "html", "archival"))
        self.assertFalse(should_flag_handwriting_audit("<p>" + ("word " * 50) + "[Unclear Word: test]</p>", "html", "archival"))
        self.assertFalse(should_flag_handwriting_audit(html, "html", "newspaper"))

    def test_sanitize_model_output_strips_leading_html_language_hint(self):
        raw = "html\n<header><h1>Title</h1></header>"

        cleaned = sanitize_model_output(raw, "html", "medical")

        self.assertNotIn("\nhtml\n", f"\n{cleaned}\n")
        self.assertTrue(cleaned.startswith("<header>"))

    def test_sanitize_model_output_strips_blank_image_refusal_line(self):
        raw = "<p>Real content.</p><p>I am unable to provide a transcription because the image is completely blank.</p><p>More content.</p>"

        cleaned = sanitize_model_output(raw, "html", "academic")

        self.assertIn("Real content.", cleaned)
        self.assertIn("More content.", cleaned)
        self.assertNotIn("unable to provide a transcription", cleaned.lower())

    def test_medical_heading_structure_promotes_first_content_h2_to_h1(self):
        raw = """<nav role="navigation" aria-label="Table of Contents"><h2>Table of Contents</h2></nav>
<h2>Concomitant Medications Form</h2>
<section><p>Body</p></section>"""

        cleaned = enforce_archival_heading_structure(raw, "html", "medical")

        self.assertIn("<nav", cleaned)
        self.assertIn("<h1>Concomitant Medications Form</h1>", cleaned)

    def test_medical_heading_structure_injects_fallback_headings_for_plain_paragraph_page(self):
        raw = """<main id="content" role="main">
<p>38</p>
<p>Fragmentary note text</p>
</main>"""

        cleaned = enforce_archival_heading_structure(raw, "html", "medical")

        self.assertIn("<h1>Clinical Note</h1>", cleaned)
        self.assertIn("<h2>Page 38</h2>", cleaned)

    def test_handwritten_heading_structure_injects_fallback_headings_for_plain_paragraph_page(self):
        raw = """<main id="content" role="main">
<p>38</p>
<p>Diary text line one</p>
</main>"""

        cleaned = enforce_archival_heading_structure(raw, "html", "handwritten")

        self.assertIn("<h1>Handwritten Page</h1>", cleaned)
        self.assertIn("<h2>Page 38</h2>", cleaned)

    def test_handwriting_audit_injects_html_note_inside_main(self):
        doc = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>""" + ("word " * 50) + """</p>
</main>
</body>
</html>"""

        flagged = apply_handwriting_audit_flag(doc, "html", "archival", whole_document=True)

        self.assertIn('aria-label="Transcription Audit Flag"', flagged)
        self.assertIn(".chronicle-audit-note", flagged)
        self.assertIn("<strong>Chronicle Note:</strong>", flagged)
        self.assertLess(flagged.index('aria-label="Transcription Audit Flag"'), flagged.index("<p>word"))

    def test_handwriting_audit_prepends_plain_text_warning(self):
        content = ("word " * 50).strip()

        flagged = apply_handwriting_audit_flag(content, "txt", "archival", whole_document=True)

        self.assertTrue(flagged.startswith("[CHRONICLE AUDIT FLAG:"))

    def test_html_normalizer_promotes_leading_index_section_to_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<section><span>Index</span><span>511</span></section>
<section><p>Entry A - 1</p></section>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">Index</h1>", cleaned)

    def test_html_normalizer_promotes_nested_index_paragraph_to_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<section><p>Entry A - 1</p></section>
<section><p>INDEX</p><p>Entry B - 2</p></section>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('>INDEX</h1>', cleaned)

    def test_html_normalizer_promotes_header_index_block_and_adds_subheading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header><span>511</span>INDEX</header>
<section><p>Entry A - 1</p></section>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn('>INDEX</h1>', cleaned)
        self.assertIn('>Index Entries</h2>', cleaned)

    def test_html_normalizer_promotes_single_short_h2_after_figures_to_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<figure><figcaption>Fig. 6</figcaption></figure>
<h2>E. Multirate Method</h2>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">E. Multirate Method</h1>", cleaned)

    def test_html_normalizer_promotes_bare_heading_after_figure_to_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<figure><figcaption>Fig. 6</figcaption></figure>
E. Multirate Method

It has been shown previously that an oversampled version improves alias reduction.
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">E. Multirate Method</h1>", cleaned)

    def test_html_normalizer_promotes_running_header_without_period_to_h1(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>August, 1914] THE FIRST CONTINGENT SAILS 83</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">THE FIRST CONTINGENT SAILS</h1>", cleaned)

    def test_html_normalizer_uses_document_title_when_cover_page_is_image_only(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><title>zoom_h6essential-page-001</title></head>
<body>
<main id="content" role="main">
<header><cite><img src="data:image/jpeg;base64,QUJDREVGRw=="></cite></header>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">Zoom H6Essential</h1>", cleaned)
        self.assertIn(">H6Essential</h2>", cleaned)

    def test_html_normalizer_uses_document_title_for_image_heavy_section_cover(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><title>yunzii_c75_manual-page-001</title></head>
<body>
<main id="content" role="main">
<section><p>[Image Description: cover art]</p><p>YUNZII</p></section>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">YUNZII</h1>", cleaned)
        self.assertIn(">C75 Manual</h2>", cleaned)

    def test_html_normalizer_promotes_military_order_page_to_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header><cite>The National Archives' reference WO 95/1668/3</cite></header>
<p>SECRET.<br>LAKE<br>OPERATION ORDER Number 74.</p>
<ol><li>First order.</li><li>Second order.</li></ol>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">SECRET. LAKE OPERATION ORDER Number 74</h1>", cleaned)
        self.assertIn(">Operational Orders</h2>", cleaned)

    def test_html_normalizer_promotes_bare_military_instruction_page_to_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
by 12 midnight tonight

5. Officers. Officers not going up with action with the Battalion will join B Echelon tonight -

6. Ammunition. Company will draw and issue the 2 extra bandoliers per man -
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">by 12 midnight tonight</h1>", cleaned)
        self.assertIn(">5. Officers. Officers not going up with action with the Battalion will join B Echelon tonight</h2>", cleaned)

    def test_html_normalizer_promotes_nested_index_sections_to_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<section><section>INDEX</section><section>511</section></section>
<section><p>Entry A - 1</p></section>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">INDEX</h1>", cleaned)
        self.assertIn(">Index Entries</h2>", cleaned)

    def test_tabular_html_fragment_includes_primary_heading_and_sheet_heading(self):
        rendered = build_tabular_html_fragment(
            "trivia",
            [{"name": "2018", "headers": ["Date", "Caroline", "Bruce"], "rows": [["2018-01-01", "10", "9"]]}],
        )

        self.assertIn("<h1>Trivia</h1>", rendered)
        self.assertIn("<h2>2018</h2>", rendered)
        self.assertIn("<table>", rendered)

    def test_html_normalizer_promotes_headingless_military_continuation_pages(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<header><cite>The National Archives' reference WO-95-1668-1_071.jpg</cite></header>
5. Officers. Officers not going into action with the Battalion will join B Echelon tonight -<br><br>
6. Ammunition. Company will draw and issue the 2 extra bandoliers per man -<br><br>
7. Runners. Ten runners will again be required by Brigade.
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(">Military Diary Continuation</h1>", cleaned)
        self.assertIn(">Operational Orders</h2>", cleaned)

    def test_html_normalizer_strips_reversed_legal_section_breadcrumb_blocks(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<section>Governance of the aged care system Chapter 5</section>
<section>Introduction Part 1</section>
<h4>339 Functions of the System Governor</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Governance of the aged care system Chapter 5", cleaned)
        self.assertNotIn("Introduction Part 1", cleaned)
        self.assertIn("339 Functions of the System Governor", cleaned)

    def test_html_normalizer_strips_duplicate_section_label_before_matching_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Section 558</p>
<h4>558 Decisions by the Pricing Authority</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>Section 558</p>", cleaned)
        self.assertIn("558 Decisions by the Pricing Authority", cleaned)

    def test_html_normalizer_strips_remaining_bare_section_restart_labels(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>277 Maximum daily amount of resident contribution</h4>
<p>(1) The maximum daily amount is worked out as follows:</p>
<p>Section 278</p>
<p>Method statement</p>
<p>Step 1.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>Section 278</p>", cleaned)
        self.assertIn("<p>Method statement</p>", cleaned)

    def test_html_normalizer_strips_fused_section_prefix_from_clause_continuation(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>5 Objects of this Act</h4>
<p>The objects of this Act are to:</p>
<p>Section 5 (a) protect the rights of older people; and (b) support quality care.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("<p>(a) protect the rights of older people; and (b) support quality care.</p>", cleaned)
        self.assertNotIn("<p>Section 5 (a)", cleaned)

    def test_html_normalizer_strips_fused_section_prefix_using_next_clause_anchor(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>5 Objects of this Act</h4>
<p>Section 6 (g) provide for sustainable funding arrangements.</p>
<h4>6 Simplified outline of this Act</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("<p>(g) provide for sustainable funding arrangements.</p>", cleaned)
        self.assertNotIn("<p>Section 6 (g)", cleaned)

    def test_html_normalizer_strips_marker_and_reordered_breadcrumb_before_clause_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>This Act establishes a charging framework.</p>
<p>[Original Page Number: 284]</p>
<p>Accommodation payments and accommodation contributions Part 4 Charging of accommodation contributions Division 5</p>
<h4>298 Charging accommodation contributions</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("[Original Page Number: 284]", cleaned)
        self.assertNotIn("Accommodation payments and accommodation contributions Part 4", cleaned)

    def test_html_normalizer_rejects_reordered_running_head_as_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Funding of aged care services Chapter 4</p>
<h4>221 Meaning of funded aged care service</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn(">Funding of aged care services Chapter 4</h", cleaned)
        self.assertIn("221 Meaning of funded aged care service", cleaned)

    def test_html_normalizer_rejects_split_statutory_reference_year_as_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Privacy Act 1988.</h2>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">Privacy Act 1988.</a>", nav_block)
        self.assertIn("<h2>Privacy Act 1988.</h2>", cleaned)

    def test_html_normalizer_merges_split_legal_reference_numbered_heading_fragments(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>provider-based subsidy:</p>
<p>(a) for the service group home support-see sections 201 and</p>
<h2>202.</h2>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">202.</a>", nav_block)
        self.assertIn("see sections 201 and 202.", cleaned)

    def test_html_normalizer_strips_reordered_running_head_fragments_from_body(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Funding of aged care services Chapter 4</p>
<h4>335 Notice of decision</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Funding of aged care services Chapter 4", cleaned)
        self.assertIn("335 Notice of decision", cleaned)

    def test_html_normalizer_demotes_fragment_heading_like_division_must(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h3>Division must:</h3>
<p>(a) be with respect to the provision of sickness benefits.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">Division must:</a>", nav_block)
        self.assertIn("<p>Division must:</p>", cleaned)

    def test_html_normalizer_demotes_cross_reference_part_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care.</p>
<p>Note:</p>
<h3>Part 3 of Chapter 5.</h3>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">Part 3 of Chapter 5.</a>", nav_block)
        self.assertIn("<p>Part 3 of Chapter 5.</p>", cleaned)

    def test_html_normalizer_demotes_date_only_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care.</p>
<h3>31 January 2029.</h3>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">31 January 2029.</a>", nav_block)
        self.assertIn("<p>31 January 2029.</p>", cleaned)

    def test_html_normalizer_demotes_truncated_subsidy_cross_reference_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care.</p>
<h3>Part 2 of Chapter 4 that affect the amount of subsidy payable under</h3>
<p>(a) be with respect to implementing Australia's obligations.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">Part 2 of Chapter 4 that affect the amount of subsidy payable under</a>", nav_block)
        self.assertIn("<p>Part 2 of Chapter 4 that affect the amount of subsidy payable under</p>", cleaned)

    def test_html_normalizer_demotes_dot_leader_contents_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care.</p>
<h1>Contents of required action notices ............................................... 426</h1>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">Contents of required action notices ............................................... 426</a>", nav_block)
        self.assertIn("<p>Contents of required action notices ............................................... 426</p>", cleaned)

    def test_html_normalizer_demotes_multi_structure_running_head_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care.</p>
<h1>Governance of the aged care system Chapter 5 Introduction Part 1</h1>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">Governance of the aged care system Chapter 5 Introduction Part 1</a>", nav_block)
        self.assertIn("<p>Governance of the aged care system Chapter 5 Introduction Part 1</p>", cleaned)

    def test_html_normalizer_strips_front_matter_legal_contents_block_before_clause_body(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h1>Aged Care Bill 2024</h1>
<h1>Contents</h1>
<h2>Chapter 1 Introduction</h2>
<h3>Part 1 Preliminary</h3>
<p>Short title ........................................ 1 Commencement ........................................ 2</p>
<h3>Part 2 Definitions and key concepts</h3>
<h4>Division 1 Definitions</h4>
<p>Definitions ........................................ 6</p>
<h4>Division 2 Key concepts</h4>
<p>Aged Care Code of Conduct ........................................ 40</p>
<h3>Part 3 Aged care rights and principles</h3>
<h4>Division 1 Aged care rights</h4>
<p>Statement of Rights ........................................ 47</p>
<h2>Chapter 5 Governance of the aged care system</h2>
<p>Simplified outline of this Chapter ........................................ 330</p>
<h3>Part 2 System Governor</h3>
<p>Functions of the System Governor ........................................ 332</p>
<h3>Part 3 Aged Care Quality and Safety Commission</h3>
<h4>Division 1 Triggering Part 7 of the Regulatory Powers Act</h4>
<p>Enforceable provisions ........................................ 422</p>
<h4>1 Short title</h4>
<p>This Act is the Aged Care Act 2024.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("<h1 id=\"heading-2\">Contents</h1>", cleaned)
        self.assertNotIn(">Chapter 5 Governance of the aged care system</a>", cleaned)
        self.assertNotIn("Simplified outline of this Chapter ........................................ 330", cleaned)
        self.assertIn("<h4>1 Short title</h4>", cleaned)
        self.assertIn("<p>This Act is the Aged Care Act 2024.</p>", cleaned)

    def test_html_normalizer_merges_split_legal_heading_continuation_into_full_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care.</p>
<h2>Chapter 5 Governance of the aged care</h2>
<p>system</p>
<h3>Part 12 System Governor functions assurance</h3>
<p>activities</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertRegex(cleaned, r"<h[1-6][^>]*>Chapter 5 Governance of the aged care system</h[1-6]>")
        self.assertRegex(cleaned, r"<h[1-6][^>]*>Part 12 System Governor functions assurance activities</h[1-6]>")
        self.assertNotIn("<p>system</p>", cleaned)
        self.assertNotIn("<p>activities</p>", cleaned)
        self.assertIn(">Chapter 5 Governance of the aged care system</a>", cleaned)
        self.assertIn(">Part 12 System Governor functions assurance activities</a>", cleaned)

    def test_html_normalizer_dedupes_same_structure_heading_after_continuation_merge(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care.</p>
<h3>Part 7 Application fees and fees for services provided by the System Governor,</h3>
<p>Commissioner and Complaints Commissioner</p>
<h3>Part 7 Application fees and fees for services</h3>
<p>provided by the System Governor, Commissioner and Complaints Commissioner</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        expected = "Part 7 Application fees and fees for services provided by the System Governor, Commissioner and Complaints Commissioner"

        self.assertEqual(cleaned.count(expected), 2)
        self.assertNotIn("<p>provided by the System Governor, Commissioner and Complaints Commissioner</p>", cleaned)

    def test_html_normalizer_demotes_date_only_h1_in_legal_compilation_page(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>The Criminal Code Schedule</p>
<h1>9 January 2025</h1>
<p>Compilation text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn(">9 January 2025</a>", cleaned)
        self.assertIn("<p>9 January 2025</p>", cleaned)

    def test_html_normalizer_splits_inline_legal_subsection_from_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about criminal law.</p>
<h4>104.16 Terms of a confirmed control order (1) If the issuing court confirms the interim control order, the court must make a corresponding order.</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("<h4>104.16 Terms of a confirmed control order</h4>", cleaned)
        self.assertIn("<p>(1) If the issuing court confirms the interim control order, the court must make a corresponding order.</p>", cleaned)

    def test_html_normalizer_strips_three_level_legal_running_head_paragraph(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>The Criminal Code Schedule</p>
<p>The proper administration of Government Chapter 7 Miscellaneous Part 7.20 Miscellaneous Division 261</p>
<h2>Part 7.20 Miscellaneous</h2>
<h4>261.1 Saving of other laws</h4>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("The proper administration of Government Chapter 7 Miscellaneous Part 7.20 Miscellaneous Division 261", cleaned)
        self.assertRegex(cleaned, r"<h[1-6][^>]*>Part 7\.20 Miscellaneous</h[1-6]>")

    def test_html_normalizer_strips_leaked_nested_document_wrappers_after_toc_injection(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<html><head></head><body><main id="content" role="main">
<h1>The Criminal Code Schedule</h1>
<h2>Section 104.16</h2>
<p>Body text.</p>
</main></body></html>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<html><head></head><body>", cleaned)
        self.assertEqual(cleaned.count("<main id=\"content\" role=\"main\">"), 1)

    def test_html_normalizer_strips_compilation_furniture_fused_into_legal_clause(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>The Criminal Code Schedule</p>
<h1>Section 104.16</h1>
<p>Compilation No. 166</p>
<p>Compilation date: 09/01/2025 (a) the relevant interim control order did not begin to be in force when it was served personally on the person.</p>
<p>(b) either of the following events occurs:</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>Compilation No. 166</p>", cleaned)
        self.assertNotIn("Compilation date: 09/01/2025 (a)", cleaned)
        self.assertIn("<p>(a) the relevant interim control order did not begin to be in force when it was served personally on the person.</p>", cleaned)

    def test_html_normalizer_demotes_incomplete_part_heading_ending_with_and(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>A Bill for an Act about aged care.</p>
<h3>Part 14 Authorised Commission officers and</h3>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">Part 14 Authorised Commission officers and</a>", nav_block)
        self.assertIn("<p>Part 14 Authorised Commission officers and</p>", cleaned)

    def test_html_normalizer_repairs_specific_regulatory_powers_heading_continuations(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h3>Part 2 Monitoring under Part 2 of the Regulatory</h3>
<p>Powers Act</p>
<h4>Division 1 Triggering Part 2 of the Regulatory Powers</h4>
<p>Act</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertRegex(cleaned, r"<h[1-6][^>]*>Part 2 Monitoring under Part 2 of the Regulatory Powers Act</h[1-6]>")
        self.assertIn("<h4>Division 1 Triggering Part 2 of the Regulatory Powers Act</h4>", cleaned)
        self.assertNotIn("<p>Powers Act</p>", cleaned)
        self.assertNotIn("<p>Act</p>", cleaned)

    def test_html_normalizer_demotes_specific_incomplete_legal_sentence_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h3>Part 2 of the Regulatory Powers Act creates a framework for</h3>
<p>monitoring whether a provision has been complied with.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)
        nav_block = cleaned.split("</nav>", 1)[0] if "</nav>" in cleaned else cleaned

        self.assertNotIn(">Part 2 of the Regulatory Powers Act creates a framework for</a>", nav_block)
        self.assertIn("<p>Part 2 of the Regulatory Powers Act creates a framework for</p>", cleaned)

    def test_html_normalizer_strips_specific_repeated_legal_running_head_paragraphs(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Monitoring under Part 2 of the Regulatory Powers Act Part 2 Triggering Part 2 of the Regulatory Powers Act Division 1</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Monitoring under Part 2 of the Regulatory Powers Act Part 2 Triggering Part 2 of the Regulatory Powers Act Division 1", cleaned)
        self.assertIn("<p>Body text.</p>", cleaned)

    def test_html_normalizer_strips_specific_reordered_running_head_with_break(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Funding of aged care services Chapter 4<br/>Introduction Part 1</p>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Funding of aged care services Chapter 4", cleaned)
        self.assertIn("<p>Body text.</p>", cleaned)

    def test_html_normalizer_strips_specific_raw_text_reordered_running_head_with_break(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Accommodation payments and accommodation contributions may be paid by daily payments, a lump sum (known as a refundable</p>
Funding of aged care services Chapter 4
Introduction Part 1
<br/>
Section 190
<br/>
deposit) or a combination of refundable deposit and daily accommodation payment.</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Funding of aged care services Chapter 4", cleaned)
        self.assertNotIn("Introduction Part 1", cleaned)
        self.assertNotIn("Section 190", cleaned)
        self.assertIn("deposit) or a combination of refundable deposit and daily accommodation payment.", cleaned)

    def test_html_normalizer_strips_specific_means_testing_running_head_with_breaks(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><title>A Bill for an Act</title></head>
<body>
<main id="content" role="main">
<p>Step 5.</p>
<p>If the individual’s total assessable income exceeds the second income threshold but not the third income threshold, the sum is divided by</p>
<h2>364:</h2>
Funding of aged care services Chapter 4<br/>
Means testing Part 5<br/>
Means testing in approved residential care home Division 2
<ol type="a">
<li>50% of the difference between the total assessable income free area and the first income threshold;</li>
</ol>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Funding of aged care services Chapter 4", cleaned)
        self.assertNotIn("Means testing Part 5", cleaned)
        self.assertNotIn("Means testing in approved residential care home Division 2", cleaned)
        self.assertIn("364:", cleaned)
        self.assertIn("<ol type=\"a\">", cleaned)

    def test_html_normalizer_strips_specific_part_14_running_head_paragraph(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><title>A Bill for an Act</title></head>
<body>
<main id="content" role="main">
<p>(5) A determination made under subsection (4) is not a legislative instrument.</p>
<p>Authorised Commission officers and authorised System Governor officers Part 14 Functions and powers Division 2</p>
<h4>527 Functions and powers of authorised Commission officers</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Authorised Commission officers and authorised System Governor officers Part 14 Functions and powers Division 2", cleaned)
        self.assertIn("<h4>527 Functions and powers of authorised Commission officers</h4>", cleaned)

    def test_html_normalizer_strips_specific_numeric_legal_page_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>An authorised person may be assisted by other persons in exercising powers or performing functions or duties under Part 3 of</p>
<h2>386</h2>
<p>the Regulatory Powers Act in relation to evidential material that</p>
<h2>1</h2>
<p>relates to a provision mentioned in section 412 of this Act.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<h2>386</h2>", cleaned)
        self.assertNotIn("<h2>1</h2>", cleaned)
        self.assertIn("the Regulatory Powers Act in relation to evidential material that", cleaned)

    def test_html_normalizer_merges_specific_split_legal_paragraph_fragments(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Chapter or the Regulatory Powers Act as it applies under this</p>
<p>Chapter.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("<p>Chapter or the Regulatory Powers Act as it applies under this Chapter.</p>", cleaned)
        self.assertNotIn("<p>Chapter.</p>", cleaned)

    def test_html_normalizer_merges_specific_under_this_chapter_continuation(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>assisting (1) An authorised officer is not liable to civil proceedings in the exercise or purported exercise of any power under this</p>
<p>Chapter or the Regulatory Powers Act as it applies under this Chapter.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("any power under this Chapter or the Regulatory Powers Act as it applies under this Chapter.", cleaned)
        self.assertNotIn("<p>Chapter or the Regulatory Powers Act as it applies under this Chapter.</p>", cleaned)

    def test_html_normalizer_merges_specific_division_must_continuation(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>(10) Rules made for the purposes of a provision of Division 4 of Part 2 of Chapter 4 that affect the amount of subsidy payable under that</p>
<p>Division must:</p>
<p>(a) be with respect to the provision of sickness and hospital benefits.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("payable under that Division must:", cleaned)
        self.assertNotIn("<p>Division must:</p>", cleaned)

    def test_html_normalizer_repairs_specific_section_602_subsidy_split_for_divisions_1_to_3(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Constitutional limits for rules made for the purposes of subsidy calculations (9) Rules made for the purposes of a provision of Division 1, 2 or 3 of</p>
<p>Part 2 of Chapter 4 that affect the amount of subsidy payable under</p>
<p>(a) be with respect to implementing Australia's international obligations.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(
            "Constitutional limits for rules made for the purposes of subsidy calculations (9) Rules made for the purposes of a provision of Division 1, 2 or 3 of Part 2 of Chapter 4 that affect the amount of subsidy payable under those Divisions must:",
            cleaned,
        )
        self.assertNotIn("<p>Part 2 of Chapter 4 that affect the amount of subsidy payable under</p>", cleaned)

    def test_html_normalizer_repairs_specific_section_602_division_5_must_continuation(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>(11) Rules made for the purposes of a provision of Division 5 of Part 2 of Chapter 4 that affect the amount of subsidy payable under that</p>
<p>(a) be with respect to implementing Australia's international obligations.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn(
            "(11) Rules made for the purposes of a provision of Division 5 of Part 2 of Chapter 4 that affect the amount of subsidy payable under that Division must:",
            cleaned,
        )
        self.assertNotIn(
            "<p>(11) Rules made for the purposes of a provision of Division 5 of Part 2 of Chapter 4 that affect the amount of subsidy payable under that</p>",
            cleaned,
        )

    def test_html_normalizer_strips_orphan_operators_heading_fragment(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Chapter 3 Registered providers, aged care workers and aged care digital platform</h2>
<p>operators</p>
<h2>Chapter 3 Registered providers, aged care workers and aged care digital platform operators</h2>
<p>Body text.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>operators</p>", cleaned)
        self.assertIn("Chapter 3 Registered providers, aged care workers and aged care digital platform operators", cleaned)

    def test_html_normalizer_repairs_split_registered_providers_heading_sequence(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h2>Chapter 3 Registered providers, aged care workers</h2>
<p>and aged care digital platform operators</p>
<h2>Chapter 3 Registered providers, aged care workers and aged care digital platform</h2>
<h2>Chapter 3 Registered providers, aged care</h2>
<p>workers and aged care digital platform operators</p>
<h1>Registered providers, aged care workers and aged care digital platform operators</h1>
<h2>Chapter 3</h2>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>and aged care digital platform operators</p>", cleaned)
        self.assertNotIn("<p>workers and aged care digital platform operators</p>", cleaned)
        self.assertIn("Chapter 3 Registered providers, aged care workers and aged care digital platform operators", cleaned)
        self.assertNotIn("Chapter 3 Registered providers, aged care workers and aged care digital platform</h2>", cleaned)

    def test_html_normalizer_repairs_split_part_2_home_approval_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h3>Part 2 Provider registration and residential care home</h3>
<p>approval process</p>
<h3>Part 2 Provider registration and residential care</h3>
<p>home approval process</p>
<p>decisions</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("Part 2 Provider registration and residential care home approval process", cleaned)
        self.assertNotIn("<p>approval process</p>", cleaned)
        self.assertNotIn("<p>home approval process</p>", cleaned)
        self.assertNotIn("<p>decisions</p>", cleaned)

    def test_html_normalizer_strips_entry_to_commonwealth_running_head_paragraph(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Entry to the Commonwealth aged care system Chapter 2 Place allocation Part 5 Allocation of places to individuals Division 1</p>
<h4>91 Number of places available for allocation</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Entry to the Commonwealth aged care system Chapter 2 Place allocation Part 5 Allocation of places to individuals Division 1", cleaned)
        self.assertIn("<h4>91 Number of places available for allocation</h4>", cleaned)

    def test_html_normalizer_repairs_truncated_front_matter_headings(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>Division 2 Allocation of a place to registered providers for</h4>
<h2>Chapter 3 Registered providers, aged care workers</h2>
<h3>Part 2 Provider registration and residential care home</h3>
<h4>Division 1 Applications for registration and registration</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("Division 2 Allocation of a place to registered providers for certain specialist aged care programs", cleaned)
        self.assertIn("Chapter 3 Registered providers, aged care workers and aged care digital platform operators", cleaned)
        self.assertIn("Part 2 Provider registration and residential care home approval process", cleaned)
        self.assertIn("Division 1 Applications for registration and registration decisions", cleaned)

    def test_html_normalizer_strips_specific_provider_registration_running_head_paragraph(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>Provider registration and residential care home approval process Part 2 Applications for registration and registration decisions Division 1</p>
<h4>105 Commissioner must decide whether to register the entity</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Provider registration and residential care home approval process Part 2 Applications for registration and registration decisions Division 1", cleaned)
        self.assertIn("<h4>105 Commissioner must decide whether to register the entity</h4>", cleaned)

    def test_html_normalizer_strips_specific_provider_home_approval_running_head_paragraph(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><title>A Bill for an Act</title></head>
<body>
<main id="content" role="main">
<p>Provider registration and residential care home approval process Part 2 Applications for approval of residential care homes Division 2</p>
<h4>111 Approval of residential care homes</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Provider registration and residential care home approval process Part 2 Applications for approval of residential care homes Division 2", cleaned)
        self.assertIn("<h4>111 Approval of residential care homes</h4>", cleaned)

    def test_html_normalizer_strips_specific_provider_notice_decisions_running_head_paragraph(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<head><title>A Bill for an Act</title></head>
<body>
<main id="content" role="main">
<p>Provider registration and residential care home approval process Part 2 Notice of decisions and other provisions Division 3</p>
<h4>114 Notice of decision to register or renew</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("Provider registration and residential care home approval process Part 2 Notice of decisions and other provisions Division 3", cleaned)
        self.assertIn("<h4>114 Notice of decision to register or renew</h4>", cleaned)

    def test_html_normalizer_strips_redundant_specialist_programs_continuation_paragraph(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>Division 2 Allocation of a place to registered providers for certain specialist aged care programs</h4>
<p>certain specialist aged care programs</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>certain specialist aged care programs</p>", cleaned)
        self.assertIn("Division 2 Allocation of a place to registered providers for certain specialist aged care programs", cleaned)

    def test_html_normalizer_strips_redundant_provisions_continuation_paragraph(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>Division 2 General rules about offences and civil penalty provisions</h4>
<p>provisions</p>
<h4>531 Physical elements of offences</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertNotIn("<p>provisions</p>", cleaned)
        self.assertIn("<h4>Division 2 General rules about offences and civil penalty provisions</h4>", cleaned)

    def test_html_normalizer_repairs_split_division_heading_continuations(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>Division 1 Civil penalty provisions for false or misleading</h4>
<p>information or documents</p>
<h4>Division 3 Notices to attend to answer questions or give</h4>
<p>information or documents</p>
<h4>Division 2 General rules about offences and civil penalty</h4>
<p>provisions</p>
<h4>Division 2 Allocation of a place to registered providers</h4>
<p>for certain specialist aged care programs</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("Division 1 Civil penalty provisions for false or misleading information or documents", cleaned)
        self.assertIn("Division 3 Notices to attend to answer questions or give information or documents", cleaned)
        self.assertIn("Division 2 General rules about offences and civil penalty provisions", cleaned)
        self.assertIn("Division 2 Allocation of a place to registered providers for certain specialist aged care programs", cleaned)
        self.assertNotIn("<p>information or documents</p>", cleaned)
        self.assertNotIn("<p>provisions</p>", cleaned)
        self.assertNotIn("<p>for certain specialist aged care programs</p>", cleaned)

    def test_html_normalizer_strips_specific_body_information_or_documents_fragments(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>60 penalty units.</p>
<p>information or documents</p>
<h4>488 Notice to attend to answer questions etc. relevant to</h4>
<p>Commissioner's functions</p>
<h4>Division 1 Civil penalty provisions for false or misleading information or documents</h4>
<p>information or documents</p>
<h4>529 Civil penalty provision for false or misleading information</h4>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertEqual(cleaned.count("<p>information or documents</p>"), 0)
        self.assertIn("<h4>488 Notice to attend to answer questions etc. relevant to</h4>", cleaned)
        self.assertIn("<h4>Division 1 Civil penalty provisions for false or misleading information or documents</h4>", cleaned)

    def test_html_normalizer_merges_under_this_chapter_continuation_after_late_cleanup(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>533 Protection from liability for authorised officers and persons</h4>
<p>assisting (1) An authorised officer is not liable to civil proceedings for loss, damage or injury of any kind suffered by another person as a result of anything done, or omitted to be done, by the officer in good faith in the exercise or purported exercise of any power under this</p>
<p>Chapter or the Regulatory Powers Act as it applies under this Chapter.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("any power under this Chapter or the Regulatory Powers Act as it applies under this Chapter.", cleaned)
        self.assertNotIn("<p>Chapter or the Regulatory Powers Act as it applies under this Chapter.</p>", cleaned)

    def test_html_normalizer_repairs_specific_persons_assisting_heading_body_splice(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h4>533 Protection from liability for authorised officers and persons</h4>
<p>assisting (1) An authorised officer is not liable to civil proceedings for loss, damage or injury of any kind suffered by another person as a result of anything done, or omitted to be done, by the officer in good faith in the exercise or purported exercise of any power under this Chapter or the Regulatory Powers Act as it applies under this Chapter.</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertIn("<h4>533 Protection from liability for authorised officers and persons assisting</h4>", cleaned)
        self.assertIn("<p>(1) An authorised officer is not liable to civil proceedings", cleaned)
        self.assertNotIn("<p>assisting (1)", cleaned)

    def test_html_normalizer_strips_duplicate_split_legal_heading_after_full_heading(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h3>Part 3 Investigating under Part 3 of the Regulatory Powers Act</h3>
<h3>Part 3 Investigating under Part 3 of the</h3>
<p>Regulatory Powers Act</p>
</main>
</body>
</html>"""

        cleaned = normalize_streamed_html_document(raw)

        self.assertEqual(cleaned.count("Part 3 Investigating under Part 3 of the Regulatory Powers Act"), 2)
        self.assertNotIn("<h3>Part 3 Investigating under Part 3 of the</h3>", cleaned)
        self.assertNotIn("<p>Regulatory Powers Act</p>", cleaned)


if __name__ == "__main__":
    unittest.main()
