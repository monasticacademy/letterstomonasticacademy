"""Tests for the testimonials sync pipeline and the published HTML.

Run from repo root:  python -m unittest discover -s tests -v
"""
import importlib.util
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# scripts/sync-testimonials.py has a hyphen, so we load it via importlib.
_spec = importlib.util.spec_from_file_location(
    "sync_testimonials", ROOT / "scripts" / "sync-testimonials.py"
)
sync = importlib.util.module_from_spec(_spec)
sys.modules["sync_testimonials"] = sync
_spec.loader.exec_module(sync)


# ---------- HTML well-formedness validator (stdlib only) ----------

VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class StrictHTMLValidator(HTMLParser):
    """Tracks tag balance and reports mismatches/unclosed tags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # list of (tag, (line, col))
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_ELEMENTS:
            self.stack.append((tag, self.getpos()))

    def handle_startendtag(self, tag, attrs):
        # self-closing like <br/> — treat as void
        pass

    def handle_endtag(self, tag):
        if not self.stack:
            self.errors.append(f"unexpected </{tag}> at {self.getpos()}")
            return
        opened_tag, opened_pos = self.stack.pop()
        if opened_tag != tag:
            self.errors.append(
                f"mismatched tag: opened <{opened_tag}> at line {opened_pos[0]}, "
                f"closed </{tag}> at line {self.getpos()[0]}"
            )

    def finish(self):
        for tag, pos in self.stack:
            self.errors.append(f"unclosed <{tag}> opened at line {pos[0]}")
        return self.errors


def validate_html_file(path):
    parser = StrictHTMLValidator()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.finish()


# ---------- render_block tests ----------


class RenderBlockTests(unittest.TestCase):
    def test_body_and_attribution(self):
        out = sync.render_block({
            "fields": {"Testimonial": "Hello world.", "Name": "Anonymous"}
        })
        self.assertIn('class="testimonial"', out)
        self.assertIn("Hello world.", out)
        self.assertIn("<em>— Anonymous</em>", out)

    def test_body_only_no_attribution(self):
        out = sync.render_block({"fields": {"Testimonial": "Just a body."}})
        self.assertIn("Just a body.", out)
        self.assertNotIn("<em>", out)

    def test_attribution_blank_string_omitted(self):
        out = sync.render_block({
            "fields": {"Testimonial": "Body.", "Name": "   "}
        })
        self.assertNotIn("<em>", out)

    def test_empty_body_returns_none(self):
        self.assertIsNone(sync.render_block({"fields": {"Testimonial": "   "}}))
        self.assertIsNone(sync.render_block({"fields": {}}))

    def test_body_html_is_escaped(self):
        out = sync.render_block({
            "fields": {"Testimonial": "<script>alert(1)</script>", "Name": "x"}
        })
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_attribution_html_is_escaped(self):
        out = sync.render_block({
            "fields": {"Testimonial": "ok", "Name": "<b>name</b>"}
        })
        self.assertIn("&lt;b&gt;name&lt;/b&gt;", out)
        self.assertNotIn("<b>name</b>", out)

    def test_strips_surrounding_whitespace(self):
        out = sync.render_block({
            "fields": {"Testimonial": "  text  \n", "Name": "  Rhia  "}
        })
        self.assertIn(">text<", out)
        self.assertIn("— Rhia<", out)


# ---------- sort + render_all tests ----------


class RenderAllTests(unittest.TestCase):
    def test_sorts_by_created_time_ascending(self):
        records = [
            {"fields": {"Testimonial": "C"}, "createdTime": "2025-01-03"},
            {"fields": {"Testimonial": "A"}, "createdTime": "2025-01-01"},
            {"fields": {"Testimonial": "B"}, "createdTime": "2025-01-02"},
        ]
        out = sync.render_all(records)
        joined = "\n".join(out)
        self.assertLess(joined.index(">A<"), joined.index(">B<"))
        self.assertLess(joined.index(">B<"), joined.index(">C<"))

    def test_skips_empty_bodies(self):
        records = [
            {"fields": {"Testimonial": "kept"}},
            {"fields": {"Testimonial": ""}},
            {"fields": {}},
        ]
        out = sync.render_all(records)
        self.assertEqual(len(out), 1)


# ---------- marker substitution tests ----------


class ReplaceBetweenMarkersTests(unittest.TestCase):
    HTML = (
        "<html><body>\n"
        "  <h1>Testimonials</h1>\n"
        "  <!-- TESTIMONIALS:START -->\n"
        "  <div>old</div>\n"
        "  <!-- TESTIMONIALS:END -->\n"
        "  <footer>x</footer>\n"
        "</body></html>"
    )

    def test_replaces_content_between_markers(self):
        new = sync.replace_between_markers(self.HTML, ['    <div class="testimonial">new</div>'])
        self.assertIn('<div class="testimonial">new</div>', new)
        self.assertNotIn("<div>old</div>", new)
        self.assertIn("<footer>x</footer>", new)
        self.assertIn("<h1>Testimonials</h1>", new)

    def test_keeps_markers_intact(self):
        new = sync.replace_between_markers(self.HTML, ["    <div>x</div>"])
        self.assertEqual(new.count("<!-- TESTIMONIALS:START -->"), 1)
        self.assertEqual(new.count("<!-- TESTIMONIALS:END -->"), 1)

    def test_missing_markers_raise(self):
        with self.assertRaises(ValueError):
            sync.replace_between_markers("<html><body></body></html>", ["x"])


# ---------- HTML validity tests on the actual repo files ----------


class PublishedHtmlValidityTests(unittest.TestCase):
    def test_index_html_is_well_formed(self):
        errors = validate_html_file(ROOT / "index.html")
        self.assertEqual(errors, [], f"index.html has errors: {errors}")

    def test_testimonials_html_is_well_formed(self):
        errors = validate_html_file(ROOT / "testimonials.html")
        self.assertEqual(errors, [], f"testimonials.html has errors: {errors}")

    def test_testimonials_has_markers(self):
        text = (ROOT / "testimonials.html").read_text(encoding="utf-8")
        self.assertEqual(text.count(sync.START_MARKER), 1)
        self.assertEqual(text.count(sync.END_MARKER), 1)
        self.assertLess(
            text.index(sync.START_MARKER),
            text.index(sync.END_MARKER),
            "START marker must precede END marker",
        )

    def test_testimonials_has_at_least_one_testimonial(self):
        text = (ROOT / "testimonials.html").read_text(encoding="utf-8")
        self.assertIn('class="testimonial"', text)


# ---------- end-to-end: synthetic Airtable -> rendered file is still valid ----------


class EndToEndRenderTests(unittest.TestCase):
    def test_synthetic_render_produces_valid_html(self):
        records = [
            {"fields": {"Testimonial": "Plain testimonial.", "Name": "Anonymous"}, "createdTime": "2025-01-01"},
            {"fields": {"Testimonial": "Has <chars> & \"quotes\".", "Name": "Rhia"}, "createdTime": "2025-01-02"},
            {"fields": {"Testimonial": "Multi-paragraph.\n\nSecond para."}, "createdTime": "2025-01-03"},
        ]
        blocks = sync.render_all(records)
        current = (ROOT / "testimonials.html").read_text(encoding="utf-8")
        new = sync.replace_between_markers(current, blocks)

        parser = StrictHTMLValidator()
        parser.feed(new)
        errors = parser.finish()
        self.assertEqual(errors, [], f"rendered html has errors: {errors}")

        # All three bodies appear (escaped where needed)
        self.assertIn("Plain testimonial.", new)
        self.assertIn("&lt;chars&gt;", new)
        self.assertIn("Multi-paragraph.", new)


if __name__ == "__main__":
    unittest.main()
