import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SECURITY_SCAN_ROOTS = [
    PROJECT_ROOT / "chronicle_app",
    PROJECT_ROOT / "chronicle_core.py",
    PROJECT_ROOT / "chronicle_gui.py",
    PROJECT_ROOT / "chronicle_runtime.py",
]


def _python_files():
    for root in PYTHON_SECURITY_SCAN_ROOTS:
        if root.is_file():
            yield root
        else:
            yield from root.rglob("*.py")


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


class StaticSecurityTest(unittest.TestCase):
    def test_subprocess_calls_do_not_use_shell_true(self):
        offenders = []
        for path in _python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if _call_name(node.func) not in {"subprocess.run", "subprocess.Popen"}:
                    continue
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

        self.assertEqual(offenders, [], "subprocess shell=True is not allowed")

    def test_no_command_line_secret_headers_for_subprocess_calls(self):
        offenders = []
        for path in _python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if _call_name(node.func) not in {"subprocess.run", "subprocess.Popen"}:
                    continue
                rendered = ast.unparse(node)
                lowered = rendered.lower()
                if "x-goog-api-key" in lowered or "authorization: bearer" in lowered:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

        self.assertEqual(offenders, [], "API keys must not be passed in subprocess command arguments")

    def test_gemini_rest_fallback_uses_fixed_https_endpoints(self):
        source = (PROJECT_ROOT / "chronicle_app/services/pdf_processor.py").read_text(encoding="utf-8")

        self.assertIn("https://generativelanguage.googleapis.com/v1beta/models/{model_key}:generateContent", source)
        self.assertIn(
            "https://generativelanguage.googleapis.com/v1beta/models/{model_key}:streamGenerateContent?alt=sse",
            source,
        )
        self.assertNotIn("file://", source)

    def test_no_eval_exec_or_os_system_in_runtime_code(self):
        offenders = []
        banned_calls = {"eval", "exec", "os.system"}
        for path in _python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node.func) in banned_calls:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:{_call_name(node.func)}")

        self.assertEqual(offenders, [], "Dynamic execution and os.system are not allowed in runtime code")


if __name__ == "__main__":
    unittest.main()
