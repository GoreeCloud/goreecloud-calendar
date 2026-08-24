from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "glaze.css").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


class GlazeUIFormFactorTests(unittest.TestCase):
    def test_current_glaze_contract_is_recorded(self) -> None:
        self.assertIn("Glaze UI 1.4", CSS)
        self.assertIn("Glaze UI 1.4", README)

    def test_all_supported_form_factor_ranges_are_explicit(self) -> None:
        required_queries = (
            "@media (max-width: 719px)",
            "@media (min-width: 720px) and (max-width: 1023px)",
            "@media (min-width: 1024px) and (max-width: 1439px)",
            "@media (min-width: 1440px)",
        )
        for query in required_queries:
            self.assertIn(query, CSS)

    def test_accessibility_and_resilience_contract_remains_present(self) -> None:
        for requirement in (
            "prefers-reduced-transparency",
            "prefers-reduced-motion",
            "prefers-contrast: more",
            "forced-colors: active",
            ":focus-visible",
            ":focus-within",
            "safe-area-inset-bottom",
        ):
            self.assertIn(requirement, CSS)


if __name__ == "__main__":
    unittest.main()
