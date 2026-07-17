import json
import subprocess
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "public" / "js" / "api-errors.js"


class RegistrationErrorMessageTests(unittest.TestCase):
    def format_error(self, payload: object, fallback: str = "注册失败，请稍后重试。") -> str:
        script = """
const fs = require('fs');
const vm = require('vm');

const helperPath = process.argv[1];
const payload = JSON.parse(process.argv[2]);
const fallback = process.argv[3];
const sandbox = { window: {} };

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(helperPath, 'utf8'), sandbox, { filename: helperPath });

const result = sandbox.window.formatApiError(payload, fallback);
if (typeof result !== 'string') {
  throw new Error('formatApiError must return a string');
}
process.stdout.write(result);
"""
        result = subprocess.run(
            ["node", "-e", script, str(HELPER), json.dumps(payload), fallback],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_formats_fastapi_password_minimum_length_error(self) -> None:
        message = self.format_error(
            {
                "detail": [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "password"],
                        "msg": "String should have at least 8 characters",
                        "ctx": {"min_length": 8},
                    }
                ]
            }
        )

        self.assertIn("密码", message)
        self.assertIn("至少 8 位", message)

    def test_formats_fastapi_username_pattern_error(self) -> None:
        message = self.format_error(
            {
                "detail": [
                    {
                        "type": "string_pattern_mismatch",
                        "loc": ["body", "username"],
                        "msg": "String should match pattern",
                    }
                ]
            }
        )

        self.assertEqual(message, "用户名仅可使用中文、英文、数字、下划线或短横线。")

    def test_preserves_safe_registration_string_detail(self) -> None:
        self.assertEqual(self.format_error({"detail": "验证码已过期。"}), "验证码已过期。")

    def test_uses_fallback_for_unknown_string_detail(self) -> None:
        self.assertEqual(
            self.format_error({"detail": "Internal diagnostic: database unavailable"}),
            "注册失败，请稍后重试。",
        )

    def test_uses_fallback_for_unknown_payload(self) -> None:
        self.assertEqual(
            self.format_error({"detail": [{"type": "unexpected_error"}]}),
            "注册失败，请稍后重试。",
        )

    def test_register_pages_load_and_use_error_helper(self) -> None:
        pages = {
            ROOT / "public" / "register.html": 'src="js/api-errors.js"',
            ROOT / "register.html": 'src="public/js/api-errors.js"',
        }

        for page, helper_reference in pages.items():
            content = page.read_text(encoding="utf-8")

            self.assertIn(helper_reference, content, page)
            self.assertLess(content.index(helper_reference), content.index("<script>"), page)
            self.assertEqual(content.count("formatApiError(data,"), 2, page)


if __name__ == "__main__":
    unittest.main()
