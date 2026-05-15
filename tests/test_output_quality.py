import unittest

from chronicle_app.services.output_quality import analyze_output_quality, build_run_health_summary


class OutputQualityTest(unittest.TestCase):
    def test_analyze_output_quality_flags_html_artifacts(self):
        report = analyze_output_quality(
            "<html><body><h2></h2><p>IMAGE_PLACEHOLDER</p><img src=''></body></html>",
            fmt="html",
            doc_profile="magazine",
        )

        self.assertFalse(report["ok"])
        self.assertIn("empty heading", report["warnings"])
        self.assertIn("image placeholder token", report["warnings"])
        self.assertIn("empty image source", report["warnings"])

    def test_analyze_output_quality_flags_legal_false_headings(self):
        report = analyze_output_quality(
            "<html><body><h3>31 January 2029.</h3></body></html>",
            fmt="html",
            doc_profile="legal",
        )

        self.assertFalse(report["ok"])
        self.assertIn("date-only legal heading", report["warnings"])

    def test_analyze_output_quality_flags_html_leak_in_text(self):
        report = analyze_output_quality("<figure>chart</figure>", fmt="txt")

        self.assertFalse(report["ok"])
        self.assertIn("HTML tag leaked into non-HTML output", report["warnings"])

    def test_build_run_health_summary_includes_qa_summary(self):
        summary = build_run_health_summary(
            file_name="source.pdf",
            output_path="/tmp/source.html",
            fmt="html",
            doc_profile="magazine",
            engine_label="gemini-2.5-pro",
            total_units=12,
            resumed_units=3,
            qa_report={"summary": "Output QA passed."},
        )

        self.assertIn("File: source.pdf", summary)
        self.assertIn("Recovered from previous session: 3", summary)
        self.assertIn("Output QA passed.", summary)


if __name__ == "__main__":
    unittest.main()
