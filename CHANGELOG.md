# Changelog

## 1.0.0 - 2026-11-09

Initial release.

* Tag hygiene audit over a support ticket CSV export: untagged
  tickets, near-duplicate tags (case, separator, and plural
  variants), tags used only once, tickets carrying too many
  tags, generic tags, duplicate tags on one ticket, and tags
  with characters Zendesk drops.
* Zendesk tag character rule enforced as the invalid-characters
  error: letters and digits plus dash, underscore, colon, and
  forward slash only, per Zendesk help "Working with ticket
  tags" (updated 2026-10-09). Uppercase tags are warnings,
  since Zendesk treats tags as lowercase.
* Malformed CSV rows are reported as data errors and skipped,
  never a crash. UTF-8 BOM headers and extra columns handled.
* Optional --dictionary file of approved tags, with
  case-insensitive matching. Blank lines and # comments ignored.
* Findings carry a ticket id, a tag, a rule name, a severity
  (error or warning), and a message; errors and warnings are
  counted in the summary.
* Text and --json output, --out file output, --max-tags and
  --min-uses thresholds, --tags-column and --id-column
  overrides, and a --check CI gate that exits 1 on errors
  (and on warnings with --strict).
* Zero dependencies, Python 3.10 or newer.
