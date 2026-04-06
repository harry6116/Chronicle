import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.local_benchmark_pack_accessibility import (
    Case,
    audit_html_output,
    build_markdown_summary,
    build_config,
    grade_from_score,
    run_case_with_watchdog,
    score_html_checks,
    summarize_report,
)


class BenchmarkScorecardTest(unittest.TestCase):
    def test_build_config_inherits_profile_defaults(self):
        case = Case(
            key="legal_case",
            relative_path="sample.pdf",
            profile="legal",
            model="gemini-2.5-pro",
        )

        cfg = build_config(case, output_dir="out")

        self.assertTrue(cfg["preserve_original_page_numbers"])
        self.assertEqual(cfg["doc_profile"], "legal")
        self.assertEqual(cfg["model_name"], "gemini-2.5-pro")

    def test_a_plus_requires_perfect_score(self):
        self.assertEqual(grade_from_score(100.0, True), "A+")
        self.assertEqual(grade_from_score(100.0, False), "A")

    def test_newspaper_scorecard_rewards_full_semantic_pass(self):
        checks = {
            "has_lang_dir_root": True,
            "has_main_landmark": True,
            "has_page_header_cite": True,
            "has_source_footer_cite": True,
            "has_h1": True,
            "has_h2": True,
            "has_image_description": True,
            "has_nested_doctype": False,
            "has_nested_html_tag": False,
            "has_fence_wrappers": False,
            "has_synthetic_page_filename_heading": False,
        }

        scorecard = score_html_checks("newspaper", checks)

        self.assertEqual(scorecard["score"], 100.0)
        self.assertEqual(scorecard["grade"], "A+")
        self.assertTrue(scorecard["perfect_score"])

    def test_newspaper_scorecard_drops_below_a_plus_on_missed_factor(self):
        checks = {
            "has_lang_dir_root": True,
            "has_main_landmark": True,
            "has_page_header_cite": False,
            "has_source_footer_cite": True,
            "has_h1": True,
            "has_h2": True,
            "has_image_description": True,
            "has_nested_doctype": False,
            "has_nested_html_tag": False,
            "has_fence_wrappers": False,
            "has_synthetic_page_filename_heading": False,
        }

        scorecard = score_html_checks("newspaper", checks)

        self.assertEqual(scorecard["score"], 80.0)
        self.assertEqual(scorecard["grade"], "B-")
        self.assertFalse(scorecard["perfect_score"])

    def test_html_audit_counts_del_tag_as_strikethrough_recovery(self):
        raw = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<h1>7th Division</h1>
<h2>91st Infantry Brigade</h2>
<p>January 1916 - <del>August 1918</del></p>
</main>
</body>
</html>"""

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "war-diary.html"
            path.write_text(raw, encoding="utf-8")
            checks = audit_html_output(path)

        self.assertTrue(checks["has_strikethrough_recovery"])

    def test_military_scorecard_does_not_require_strikethrough_when_absent(self):
        checks = {
            "has_lang_dir_root": True,
            "has_main_landmark": True,
            "has_h1": True,
            "has_h2": True,
            "has_strikethrough_recovery": False,
            "has_nested_doctype": False,
            "has_nested_html_tag": False,
            "has_fence_wrappers": False,
            "has_synthetic_page_filename_heading": False,
            "has_leading_content_before_doctype": False,
        }

        scorecard = score_html_checks("military", checks)

        self.assertEqual(scorecard["score"], 100.0)
        self.assertEqual(scorecard["grade"], "A+")
        self.assertTrue(scorecard["perfect_score"])

    def test_military_scorecard_rewards_present_strikethrough_recovery(self):
        checks = {
            "has_lang_dir_root": True,
            "has_main_landmark": True,
            "has_h1": True,
            "has_h2": True,
            "has_strikethrough_recovery": True,
            "has_nested_doctype": False,
            "has_nested_html_tag": False,
            "has_fence_wrappers": False,
            "has_synthetic_page_filename_heading": False,
            "has_leading_content_before_doctype": False,
        }

        scorecard = score_html_checks("military", checks)

        self.assertEqual(scorecard["score"], 100.0)
        self.assertEqual(scorecard["grade"], "A+")
        self.assertTrue(scorecard["perfect_score"])

    def test_manual_scorecard_does_not_require_form_semantics_when_absent(self):
        checks = {
            "has_lang_dir_root": True,
            "has_main_landmark": True,
            "has_h1": True,
            "has_h2": True,
            "has_checkbox_markup": False,
            "has_radio_markup": False,
            "has_text_field_markup": False,
            "has_nested_doctype": False,
            "has_nested_html_tag": False,
            "has_fence_wrappers": False,
            "has_synthetic_page_filename_heading": False,
            "has_leading_content_before_doctype": False,
        }

        scorecard = score_html_checks("manual", checks)

        self.assertEqual(scorecard["score"], 100.0)
        self.assertEqual(scorecard["grade"], "A+")
        self.assertTrue(scorecard["perfect_score"])

    def test_run_case_with_watchdog_returns_worker_output_path(self):
        class FakeQueue:
            def __init__(self):
                self.items = []

            def empty(self):
                return not self.items

            def get_nowait(self):
                return self.items.pop(0)

            def put(self, value):
                self.items.append(value)

            def close(self):
                pass

            def join_thread(self):
                pass

        class FakeProcess:
            def __init__(self, target, args, daemon):
                self._target = target
                self._args = args
                self.exitcode = None
                self._alive = False

            def start(self):
                self._alive = True
                self._target(*self._args)
                self.exitcode = 0
                self._alive = False

            def is_alive(self):
                return self._alive

            def join(self, timeout=None):
                self._alive = False

            def terminate(self):
                self._alive = False
                self.exitcode = -15

        def fake_worker(queue, source_path_str, case_payload, output_root_str):
            queue.put({"status": "ok", "output_path": str(Path(output_root_str) / "sample.html")})

        original_worker = __import__("tools.local_benchmark_pack_accessibility", fromlist=["_run_case_worker"])._run_case_worker
        import tools.local_benchmark_pack_accessibility as benchmark_tool
        benchmark_tool._run_case_worker = fake_worker
        try:
            case = Case(key="sample", relative_path="sample.pdf", profile="legal", model="gemini-2.5-pro")
            result = run_case_with_watchdog(
                Path("sample.pdf"),
                case,
                Path("out"),
                case_timeout_sec=30,
                idle_timeout_sec=10,
                process_cls=FakeProcess,
                queue_cls=FakeQueue,
            )
        finally:
            benchmark_tool._run_case_worker = original_worker

        self.assertEqual(result, Path("out/sample.html"))

    def test_run_case_with_watchdog_times_out_when_idle(self):
        class FakeQueue:
            def empty(self):
                return True

            def close(self):
                pass

            def join_thread(self):
                pass

        class FakeProcess:
            def __init__(self, target, args, daemon):
                self.exitcode = None
                self._alive = False

            def start(self):
                self._alive = True

            def is_alive(self):
                return self._alive

            def join(self, timeout=None):
                self._alive = False

            def terminate(self):
                self._alive = False
                self.exitcode = -15

        with TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            tmp_out = output_root / "sample.html.tmp"
            tmp_out.write_text("seed", encoding="utf-8")
            size_calls = {"count": 0}
            original_stat = Path.stat

            def fake_stat(path_obj):
                if path_obj == tmp_out:
                    size_calls["count"] += 1
                    class Result:
                        st_size = 10 if size_calls["count"] == 1 else 11
                    return Result()
                return original_stat(path_obj)

            ticks = iter([0.0, 0.0, 2.0, 6.5])
            case = Case(key="sample", relative_path="sample.pdf", profile="legal", model="gemini-2.5-pro")
            try:
                Path.stat = fake_stat
                with self.assertRaises(TimeoutError):
                    run_case_with_watchdog(
                        Path("sample.pdf"),
                        case,
                        output_root,
                        case_timeout_sec=30,
                        idle_timeout_sec=3,
                        poll_sec=0.1,
                        process_cls=FakeProcess,
                        queue_cls=FakeQueue,
                        time_fn=lambda: next(ticks),
                        sleep_fn=lambda _: None,
                    )
            finally:
                Path.stat = original_stat

    def test_run_case_with_watchdog_allows_longer_startup_before_first_growth(self):
        class FakeQueue:
            def empty(self):
                return True

            def close(self):
                pass

            def join_thread(self):
                pass

        class FakeProcess:
            def __init__(self, target, args, daemon):
                self.exitcode = None
                self._alive = False

            def start(self):
                self._alive = True

            def is_alive(self):
                return self._alive

            def join(self, timeout=None):
                self._alive = False

            def terminate(self):
                self._alive = False
                self.exitcode = -15

        ticks = iter([0.0, 0.0, 90.0, 181.5])
        case = Case(key="sample", relative_path="sample.pdf", profile="legal", model="gemini-2.5-pro")
        with self.assertRaises(TimeoutError) as ctx:
            run_case_with_watchdog(
                Path("sample.pdf"),
                case,
                Path("out"),
                case_timeout_sec=600,
                idle_timeout_sec=60,
                poll_sec=0.1,
                process_cls=FakeProcess,
                queue_cls=FakeQueue,
                time_fn=lambda: next(ticks),
                sleep_fn=lambda _: None,
            )

        self.assertIn("180s", str(ctx.exception))

    def test_report_summary_and_markdown_include_grade(self):
        report = {
            "generated_at": "2026-03-15 09:00:00",
            "results": [
                {
                    "case": {"key": "trove_age"},
                    "status": "ok",
                    "output_path": "out/trove.html",
                    "issues": [],
                    "scorecard": {
                        "grade": "A+",
                        "score": 100.0,
                        "points_earned": 100,
                        "points_possible": 100,
                        "perfect_score": True,
                        "breakdown": [
                            {
                                "label": "Publication/page metadata is wrapped in <header><cite>",
                                "passed": True,
                                "points_earned": 20,
                                "points_possible": 20,
                            }
                        ],
                    },
                }
            ],
        }

        summary = summarize_report(report)
        markdown = build_markdown_summary({**report, "summary": summary})

        self.assertEqual(summary["overall_grade"], "A+")
        self.assertIn("Average score: 100.0/100", markdown)
        self.assertIn("Overall grade: A+", markdown)
        self.assertIn("## trove_age", markdown)


if __name__ == "__main__":
    unittest.main()
