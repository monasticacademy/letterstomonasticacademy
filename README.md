# Testimonials System

## Flow

1. Visitor submits a testimonial via the embedded form on **truthaboutmonasticacademy.com**
2. The submission lands in [Airtable](https://airtable.com/app3KoZGg1uwP1RZn/tblPhcAnbKSGrDgwn) with `Status = Needs Review` (the field default)
3. You approve or reject it by changing the row's `Status` to `Publish` or `Rejected`
4. A GitHub Action runs every 15 minutes and publishes everything where `Status = Publish`
5. GitHub Pages auto-deploys; the change is live within seconds of the commit

## How to review submissions

Open the [**Testimonials**](https://airtable.com/app3KoZGg1uwP1RZn/tblPhcAnbKSGrDgwn) table in the **Community** base and change a row's `Status` to `Publish` or `Rejected`.

## Pieces

### Airtable

- Base: **Community** (`app3KoZGg1uwP1RZn`)
- Table: **Testimonials** (`tblPhcAnbKSGrDgwn`)
- Fields:
  - `Name` — public attribution shown under the testimonial (e.g. "Rhia"). Blank → renders as "Anonymous".
  - `Testimonial` — the body text
  - `Status` — `Needs Review` (default) / `Publish` / `Rejected`
  - `Related Community Member` — internal-only link to a person; not rendered on the site

### Airtable automation

**Match submitter to community member** — on new row, look up the submitted email against the Community Members table and populate `Related Community Member` if found.

### GitHub

- Repo: **monasticacademy/letterstomonasticacademy**
- Site: `index.html`, `testimonials.html` (plain static HTML, served by GitHub Pages)
- Sync script: `scripts/sync-testimonials.py`
- Tests: `tests/test_sync_testimonials.py`
- Workflows:
  - `sync-testimonials.yml` — cron every 15 min, plus a manual "Run workflow" button
  - `test.yml` — runs on PRs and pushes; shows red/green status checks (advisory, doesn't block)

## When a testimonial doesn't show up

1. Confirm its `Status` is `Publish` (not `Needs Review` or `Rejected`)
2. Wait up to 15 minutes for the next scheduled sync — or force it now: **GitHub → Actions → "Sync testimonials from Airtable" → "Run workflow"**
3. If still missing, check the latest workflow run under Actions for errors

## Safety nets

- Sync refuses to overwrite the testimonials page if Airtable returns zero Publish rows (guards against misconfig)
- HTML-validity tests run **inside** the sync workflow before the commit step; bad content → no commit, workflow fails
- The same tests run on every PR and push to `main`, so style or marker regressions are visible

## Making changes

| Goal | How |
|---|---|
| Edit a testimonial | Edit the row in Airtable; next sync (≤15 min) updates the site |
| Reject something already published | Change `Status` to `Rejected`; next sync removes it |
| Reorder | Currently sorted by Airtable's createdTime (newest first). Reordering would need an `Order` field + a small script tweak |
| Change the site design | Edit `index.html` / `testimonials.html`, push (or PR). The Tests check will appear on the PR |
| Force an immediate sync | GitHub → Actions → "Sync testimonials from Airtable" → "Run workflow" |
