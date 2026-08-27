"""ratios.yml content overlay (SPEC 10.3): the owner's descriptions win,
TODOs render as "description coming soon", and a mid-edit typo never takes a
page down."""
from __future__ import annotations

import pytest

from app import views
from pipelines.ratios import FISCAL_RATIO_KEYS, RATIO_META, RATIO_META_BY_KEY


@pytest.fixture
def content_dir(tmp_path, monkeypatch):
    """Point ratio_content() at a scratch ratios.yml and reset its cache."""
    monkeypatch.setattr(views, "RATIOS_YML", tmp_path / "ratios.yml")
    monkeypatch.setattr(views, "_ratio_content", None)
    monkeypatch.setattr(views, "_ratio_content_mtime", None)
    yield tmp_path
    views._ratio_content = None
    views._ratio_content_mtime = None


class TestShippedFile:
    """Assertions about the real data/content/ratios.yml in the repo."""

    def test_every_computed_ratio_has_an_entry(self):
        entries = views.ratio_content()
        for key in FISCAL_RATIO_KEYS:
            assert key in entries, f"{key} missing from ratios.yml"

    def test_entries_carry_the_fields_claude_was_asked_to_fill(self):
        for key, entry in views.ratio_content().items():
            for field in ("display_name", "category", "formula_display", "better_when"):
                assert entry.get(field), f"{key}.{field} is empty"
            assert entry["better_when"] in ("higher", "lower", "depends")

    def test_descriptions_are_reserved_for_the_owner(self):
        # SPEC 10.3: Claude Code leaves every description as TODO(owner).
        descriptions = {e.get("description") for e in views.ratio_content().values()}
        assert descriptions == {"TODO(owner)"}

    def test_yaml_keys_match_the_engine(self):
        assert set(views.ratio_content()) == {m.key for m in RATIO_META}


class TestOverlayBehavior:
    def test_todo_description_renders_as_coming_soon(self, content_dir):
        (content_dir / "ratios.yml").write_text(
            "- key: roe\n  description: TODO(owner)\n")
        meta = views._ratio_display_meta("roe")
        assert meta["description"] == ""  # template shows "description coming soon."
        assert meta["display_name"] == RATIO_META_BY_KEY["roe"].display_name

    def test_owner_wording_overrides_the_code_defaults(self, content_dir):
        (content_dir / "ratios.yml").write_text(
            "- key: roe\n"
            "  display_name: Return on Equity (my version)\n"
            "  description: What the business earns on shareholder money.\n"
            "  caveats:\n"
            "    - Buybacks can shrink equity and flatter this.\n"
        )
        meta = views._ratio_display_meta("roe")
        assert meta["display_name"] == "Return on Equity (my version)"
        assert meta["description"].startswith("What the business earns")
        assert meta["caveats"] == ["Buybacks can shrink equity and flatter this."]

    def test_edits_are_picked_up_without_a_restart(self, content_dir):
        path = content_dir / "ratios.yml"
        path.write_text("- key: roe\n  description: TODO(owner)\n")
        assert views._ratio_display_meta("roe")["description"] == ""

        # Same process, file rewritten — the owner's new words must show up.
        import os
        import time

        path.write_text("- key: roe\n  description: Earnings on shareholder capital.\n")
        os.utime(path, (time.time() + 1, time.time() + 1))
        assert views._ratio_display_meta("roe")["description"] == (
            "Earnings on shareholder capital.")

    def test_broken_yaml_does_not_take_the_page_down(self, content_dir):
        path = content_dir / "ratios.yml"
        path.write_text("- key: roe\n  description: fine\n")
        assert views._ratio_display_meta("roe")["description"] == "fine"

        import os
        import time

        path.write_text("- key: roe\n   bad indent: [unclosed\n")
        os.utime(path, (time.time() + 1, time.time() + 1))
        meta = views._ratio_display_meta("roe")  # must not raise
        assert meta["display_name"]  # falls back to code metadata

    def test_missing_file_falls_back_to_code_metadata(self, content_dir):
        meta = views._ratio_display_meta("current_ratio")
        assert meta["display_name"] == "Current Ratio"
        assert meta["formula"] == "current assets / current liabilities"
        assert meta["description"] == ""
