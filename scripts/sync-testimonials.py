#!/usr/bin/env python3
"""Sync testimonials from Airtable into testimonials.html.

Reads rows from the Airtable table where Status = "Publish" and replaces the
content between the START/END markers in testimonials.html.

Required env vars:
  AIRTABLE_TOKEN     Personal Access Token with data.records:read on the base
  AIRTABLE_BASE_ID   e.g. appXXXXXXXXXXXXXX
Optional:
  AIRTABLE_TABLE_NAME  defaults to "Testimonials"
  HTML_PATH            defaults to "testimonials.html"

Expected Airtable schema (table "Testimonials"):
  Testimonial   Long text       (the testimonial body)
  Name          Single line     (public attribution, e.g. "Anonymous", "Rhia")
  Status        Single select   (Needs Review / Publish / Rejected — only "Publish" renders)
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

START_MARKER = "<!-- TESTIMONIALS:START -->"
END_MARKER = "<!-- TESTIMONIALS:END -->"


def fetch_records(token, base_id, table):
    base_url = f"https://api.airtable.com/v0/{base_id}/{urllib.parse.quote(table)}"
    records = []
    offset = None
    while True:
        params = {
            "filterByFormula": "{Status}='Publish'",
            "pageSize": "100",
        }
        if offset:
            params["offset"] = offset
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Airtable API HTTP {e.code}: {body}") from e
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


def render_block(record):
    fields = record.get("fields", {})
    body = (fields.get("Testimonial") or "").strip()
    attribution = (fields.get("Name") or "").strip()
    if not body:
        return None
    # quote=False because we're inserting into element text, not attribute values;
    # quotes don't need escaping there and the source is uglier with &#x27;.
    body_html = html.escape(body, quote=False)
    if attribution:
        attr_html = f"<em>— {html.escape(attribution, quote=False)}</em>"
        return f'    <div class="testimonial">{body_html}{attr_html}</div>'
    return f'    <div class="testimonial">{body_html}</div>'


def sort_records(records):
    # Oldest first — matches the existing page's natural order of arrival.
    return sorted(records, key=lambda r: r.get("createdTime", ""))


def render_all(records):
    """Return a list of rendered block strings (skipping records with empty bodies)."""
    return [b for b in (render_block(r) for r in sort_records(records)) if b]


def replace_between_markers(current_html, rendered_blocks):
    """Return the HTML with the region between markers replaced by the rendered blocks.

    Raises ValueError if the markers are missing.
    """
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
    )
    if not pattern.search(current_html):
        raise ValueError(f"markers not found: {START_MARKER} ... {END_MARKER}")
    body = "\n\n".join(rendered_blocks)
    replacement = f"{START_MARKER}\n{body}\n    {END_MARKER}"
    return pattern.sub(replacement, current_html)


def main():
    token = os.environ["AIRTABLE_TOKEN"]
    base_id = os.environ["AIRTABLE_BASE_ID"]
    table = os.environ.get("AIRTABLE_TABLE_NAME") or "Testimonials"
    html_path = os.environ.get("HTML_PATH") or "testimonials.html"

    records = fetch_records(token, base_id, table)
    blocks = render_all(records)

    if not blocks:
        # Guard against wiping the file when Airtable is empty/misconfigured.
        print("No Publish records found; leaving testimonials.html unchanged.")
        return

    with open(html_path, encoding="utf-8") as f:
        current = f.read()

    new = replace_between_markers(current, blocks)

    if new == current:
        print("No changes")
        return

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"Updated {html_path} with {len(blocks)} testimonial(s)")


if __name__ == "__main__":
    main()
