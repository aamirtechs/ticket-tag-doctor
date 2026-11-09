# ticket-tag-doctor
**Live tool:** https://aamirtechs.github.io/ticket-tag-doctor/ (runs in your browser, no install)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/aamirtechs/ticket-tag-doctor/blob/main/LICENSE) [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/aamirtechs/ticket-tag-doctor/issues)

A zero-dependency Python CLI that audits a support ticket CSV
export for tag hygiene: untagged tickets, near-duplicate tags that
differ only by case, separator, or plural (refund, Refund,
refunds), tags used only once, tickets carrying too many tags,
generic tags that say nothing, and tags with characters Zendesk
drops.

Zendesk and Freshdesk show only the 100 most-used tags and offer
no offline audit of the tag set, and AI auto-taggers add tags
without cleaning up the existing ones. Manual tagging drifts over
time into hundreds of near-duplicates that split reports, break
trigger conditions, and make routing views unreliable. This tool
is the offline audit before any cleanup: it reads the exported
CSV, flags every problem with a rule name and a severity, and
never touches your helpdesk.

## Install

Requires Python 3.10 or newer. No dependencies beyond the standard
library.

```bash
pip install ticket-tag-doctor
```

Or run it straight from the source checkout:

```bash
python3 ticket_tag_doctor.py examples/tickets.csv
```

## Input format

A CSV export with a header row. Columns used: `id` (or
`ticket_id` when there is no `id` column) and `tags`. Extra
columns are ignored, so a full ticket export works as-is. A
UTF-8 BOM header is handled.

The tags field is split on commas or semicolons when either is
present, and on whitespace otherwise, which is how Zendesk itself
separates tags in its own exports. A tag with a space inside it
can therefore only appear in a comma or semicolon separated
field, and it is flagged, because Zendesk would split it into
two tags.

```csv
id,subject,tags
T-101,Refund not received,refund
T-102,Refund status check,Refund
T-103,Double charge on card,refunds;billing
T-104,Where is my order?,question
T-105,Login fails on mobile,"login, password_reset, mobile_app, urgent, vip, billing, account, security, 2fa, ios, android"
T-107,Order arrived damaged,"damaged, RMA"
T-108,Can I change delivery date?,"delivery, date_change, date-change"
T-110,App crashes on checkout,crash!
T-112,Printer not connecting,
```

## The tag character rule

Zendesk allows only alphanumeric characters plus dash,
underscore, colon, and forward slash in a tag. Any other
character disappears when the ticket is updated. Source: Zendesk
help, "Working with ticket tags",
support.zendesk.com/hc/en-us/articles/4408835059482, updated
2026-10-09: "You can use only alphanumeric, dash, underscore,
colon, and the forward slash characters. You can't use other
special characters, such as #, @, or !. If you try to add tags
with characters that are not allowed, they disappear when the
ticket is updated." Tags are also expected to be lowercase, so
an uppercase tag is a warning, not an error. This tool enforces
exactly that rule: a tag is valid when, after lowercasing, every
character is a letter or digit, or one of `-`, `_`, `:`, `/`.

## What it checks

Errors, the ones that break routing, reporting, or automations:

* `untagged-ticket`: a ticket with no tags at all, so it cannot
  be routed, reported on, or found by tag.
* `invalid-characters`: a tag with a character Zendesk drops
  (for example `!`, `#`, `@`, `.`, or a space), so the tag
  silently vanishes from the ticket.
* `malformed-row`: a row with the wrong number of fields. The
  row is skipped and reported, never a crash.

Warnings, hygiene issues worth fixing:

* `near-duplicate-tags`: distinct tags that normalize to the
  same form (lowercased, separators unified, one trailing "s"
  stripped), so `refund`, `Refund`, and `refunds` are one tag
  split three ways across reports.
* `single-use-tag`: a tag used on fewer tickets than
  `--min-uses` (default 2), so it is a one-off rather than a
  category.
* `too-many-tags`: a ticket carrying more tags than
  `--max-tags` (default 10).
* `generic-tag`: a tag from the built-in generic list
  (question, customer, ticket, support, help, issue, problem,
  general, misc, other, enquiry, inquiry, request, feedback,
  info, unknown, todo, test, default, new) that says nothing
  about the ticket.
* `uppercase-tag`: a tag with uppercase letters. Zendesk
  treats tags as lowercase, so mixed case splits reporting.
* `duplicate-tag-on-ticket`: the same tag twice on one ticket,
  ignoring case.
* `unapproved-tag`: with `--dictionary`, a tag that is not in
  the approved-tags file.

## Usage

```bash
python3 ticket_tag_doctor.py examples/tickets.csv
```

Captured output:

```
ERROR [malformed-row] row 14: row has 4 fields but the header has 3, so the row was skipped
WARNING [uppercase-tag] T-102 [Refund]: tag has uppercase letters; Zendesk treats tags as lowercase, so this splits reporting from refund
WARNING [generic-tag] T-104 [question]: tag says nothing about the ticket, so it adds noise to reports and views
WARNING [too-many-tags] T-105: ticket carries 11 tags, over the limit of 10, so the tag list is noise rather than signal
WARNING [uppercase-tag] T-107 [RMA]: tag has uppercase letters; Zendesk treats tags as lowercase, so this splits reporting from rma
ERROR [invalid-characters] T-110 [crash!]: tag contains '!', which Zendesk drops when the ticket is updated (allowed: letters, digits, -, _, :, /)
ERROR [untagged-ticket] T-112: ticket has no tags, so it cannot be routed, reported on, or found by tag
WARNING [single-use-tag] (tag set) [2fa]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [RMA]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [Refund]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [account]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [address_change]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [android]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [cancel]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [damaged]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [date-change]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [date_change]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [delivery]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [ios]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [login]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [mobile_app]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [question]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [refund]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [refunds]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [security]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [urgent]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [single-use-tag] (tag set) [vip]: tag is used on only 1 ticket, so it is a one-off rather than a category
WARNING [near-duplicate-tags] (tag set) [date_change]: tags 'date-change', 'date_change' all mean the same thing and should be merged into one tag
WARNING [near-duplicate-tags] (tag set) [refund]: tags 'Refund', 'refund', 'refunds' all mean the same thing and should be merged into one tag

Tickets: 12, tags: 25, findings: 29, errors: 3, warnings: 26
```

The sample has 12 tickets (the malformed row 14 is skipped) and
25 tag assignments. Only two tags survive the single-use check:
`billing` (T-103, T-105) and `password_reset` (T-105, T-111).
The near-duplicate groups catch both the case and plural drift
on `refund` and the separator drift on `date_change`.

Use it as a CI gate: `--check` exits 1 when any error is found,
and 0 otherwise. On the sample above it exits 1:

```bash
python3 ticket_tag_doctor.py examples/tickets.csv --check
```

On `examples/clean.csv`, three clean tickets, it exits 0:

```
Tickets: 3, tags: 6, findings: 0, errors: 0, warnings: 0
All tickets clean.
```

With `--strict`, `--check` also fails on warnings.
`examples/warnings-only.csv` has two tickets tagged only
`question`, so it passes `--check` (exit 0) and fails
`--check --strict` (exit 1).

An approved-tags dictionary adds one warning per tag that is
not listed. `examples/dictionary.txt` approves 11 tags,
including `refund` and `rma`:

```bash
python3 ticket_tag_doctor.py examples/tickets.csv --dictionary examples/dictionary.txt
```

Captured summary:

```
Tickets: 12, tags: 25, findings: 39, errors: 3, warnings: 36
```

The 10 extra warnings are the unapproved tags: `mobile_app`,
`urgent`, `vip`, `account`, `security`, `2fa`, `ios`, and
`android` on T-105, plus `date-change` on T-108 and `refunds`
on T-103. Note that `refunds` is flagged even though `refund`
is approved, because dictionary matching is exact after
lowercasing, so a plural variant still needs a decision.
`RMA` passes because matching is case-insensitive. `--json`
emits the summary and findings as JSON, and `--out` writes the
report to a file.

## Options

| Flag | Meaning |
| --- | --- |
| `--tags-column` | Name of the tags column (default: tags) |
| `--id-column` | Name of the ticket id column (default: id, else ticket_id, else row number) |
| `--dictionary` | File of approved tags, one per line |
| `--max-tags` | Most tags allowed per ticket (default: 10) |
| `--min-uses` | A tag used fewer times than this is flagged single-use (default: 2) |
| `--json` | Emit JSON instead of text |
| `--check` | Exit 1 if any error is found |
| `--strict` | With --check, also exit 1 on warnings |
| `--out` | Write the report to a file |

## Edge cases

* A tag with invalid characters is reported once as an error
  and is left out of the single-use, near-duplicate, generic,
  and dictionary checks, so one bad tag does not pile up five
  findings.
* Near-duplicate grouping lowercases, unifies `-`, `_`, and
  `/` into one separator, and strips one trailing "s", except
  on tags of 3 characters or fewer and words ending in "ss",
  so `rma` stays `rma` and `class` stays `class`.
* A row with too many or too few fields is a malformed-row
  error and is skipped; the rest of the file is still audited.
* A blank tags field is an untagged ticket, not a malformed
  row. A blank line in the file is skipped silently.
* Tag usage is counted per ticket, not per occurrence, so a
  tag listed twice on one ticket counts once toward
  `--min-uses`.
* Dictionary matching is case-insensitive but exact otherwise,
  so `refunds` does not match an approved `refund`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

57 tests, all passing: tag splitting, the character rule,
normalization, near-duplicate grouping, single-use and
min-uses thresholds, too-many-tags, generic and uppercase tags,
duplicate tags on a ticket, dictionary loading and matching,
malformed rows, BOM headers, id column fallbacks, summary
counts, JSON output shape, and `--check` and `--strict` exit
codes.

## License

MIT. See [LICENSE](LICENSE).
