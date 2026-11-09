"""Support ticket tag hygiene audit CLI.

Reads a support ticket CSV export and audits every ticket for tag
hygiene: tickets with no tags at all, near-duplicate tags that
differ only by case, separator, or plural (refund, Refund,
refunds), tags used only once, tickets carrying too many tags,
generic tags that say nothing (question, customer), tags with
characters Zendesk drops, and tags missing from an approved
dictionary file.

Each problem is a finding with a ticket id, a tag, a rule name, a
severity (error or warning), and a message. Errors are the ones
that break reporting, routing, or automations; warnings are
hygiene issues worth fixing. --check exits 1 when any error is
found, and --strict also fails on warnings.

Tag character rule, enforced as the invalid-characters error:
Zendesk allows only alphanumeric characters plus dash, underscore,
colon, and forward slash in a tag, and anything else disappears
when the ticket is updated (Zendesk help, "Working with ticket
tags", support.zendesk.com, updated 2026-10-09). Tags are also
expected to be lowercase, so an uppercase tag is a warning, not
an error. This tool enforces exactly that: a tag is valid when,
after lowercasing, every character is a letter or digit, or one
of - _ : /.

Zero dependencies, Python 3.10 or newer, standard library only.

Usage:
    python3 ticket_tag_doctor.py examples/tickets.csv
    python3 ticket_tag_doctor.py tickets.csv --json --check
    python3 ticket_tag_doctor.py tickets.csv --dictionary approved.txt
"""

import argparse
import csv
import json
import re
import sys

__version__ = "1.0.0"

ALLOWED_PUNCTUATION = "-_:/"

GENERIC_TAGS = {
    "question", "customer", "ticket", "support", "help", "issue",
    "problem", "general", "misc", "other", "enquiry", "inquiry",
    "request", "feedback", "info", "unknown", "todo", "test",
    "default", "new",
}

DEFAULT_MAX_TAGS = 10
DEFAULT_MIN_USES = 2


class Finding:
    """One audit finding for one ticket, one tag, or the tag set."""

    def __init__(self, ticket, tag, rule, severity, message):
        self.ticket = ticket
        self.tag = tag
        self.rule = rule
        self.severity = severity
        self.message = message

    def as_dict(self):
        """Return the finding as a plain dict."""
        return {"ticket": self.ticket, "tag": self.tag,
                "rule": self.rule, "severity": self.severity,
                "message": self.message}

    def __str__(self):
        target = self.ticket
        if self.tag is not None:
            target = "%s [%s]" % (self.ticket, self.tag)
        return "%s [%s] %s: %s" % (self.severity.upper(), self.rule,
                                   target, self.message)


def split_tags(field):
    """Split one tags field into a list of tags.

    Tags separated by commas or semicolons are split on those
    separators, so a comma separated export works as-is. When the
    field has neither, it is split on whitespace, which is how
    Zendesk itself separates tags in its own exports. Empty
    segments are dropped.
    """
    if field is None:
        return []
    if "," in field or ";" in field:
        parts = re.split(r"[,;]", field)
    else:
        parts = field.split()
    return [part.strip() for part in parts if part.strip()]


def invalid_characters(tag):
    """Return the bad characters in a tag, or an empty list.

    A tag is valid when, after lowercasing, every character is a
    letter or digit, or one of - _ : /. Anything else is a
    character Zendesk drops when the ticket is updated.
    """
    return [ch for ch in tag
            if not (ch.isalnum() or ch in ALLOWED_PUNCTUATION)]


def normalize_tag(tag):
    """Return the canonical form of a tag for duplicate grouping.

    Lowercases, unifies the separators - _ / into one underscore,
    and strips one trailing "s" (refund and refunds group
    together). Short tags and words ending in "ss" keep their
    final "s", so "rma" stays "rma" and "class" stays "class".
    """
    lowered = tag.lower()
    unified = re.sub(r"[-_/]+", "_", lowered).strip("_")
    if len(unified) > 3 and unified.endswith("s") \
            and not unified.endswith("ss"):
        unified = unified[:-1]
    return unified


def parse_csv(path, id_column, tags_column):
    """Parse a ticket CSV export.

    Returns (tickets, findings). Each ticket is a dict with "id"
    and "tags" (a list). Rows with the wrong number of fields are
    reported as malformed-row errors and skipped, never a crash.
    A UTF-8 BOM header is handled. Extra columns are ignored.
    """
    findings = []
    tickets = []
    try:
        handle = open(path, newline="", encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError("cannot read %s: %s" % (path, exc))
    with handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("%s is empty, no header row found" % path)
        except csv.Error as exc:
            raise ValueError("%s is not a readable CSV file: %s"
                             % (path, exc))
        header = [name.strip() for name in header]
        if tags_column not in header:
            raise ValueError(
                "%s has no %r column (header is: %s)"
                % (path, tags_column, ", ".join(header)))
        id_index = None
        if id_column is not None:
            if id_column not in header:
                raise ValueError(
                    "%s has no %r column (header is: %s)"
                    % (path, id_column, ", ".join(header)))
            id_index = header.index(id_column)
        elif "id" in header:
            id_index = header.index("id")
        elif "ticket_id" in header:
            id_index = header.index("ticket_id")
        tags_index = header.index(tags_column)
        for line_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) != len(header):
                findings.append(Finding(
                    "row %d" % line_number, None, "malformed-row",
                    "error",
                    "row has %d fields but the header has %d, "
                    "so the row was skipped" % (len(row), len(header))))
                continue
            if id_index is None:
                ticket_id = "row %d" % line_number
            else:
                ticket_id = row[id_index].strip() or "row %d" % line_number
            tickets.append({"id": ticket_id,
                            "tags": split_tags(row[tags_index])})
    return tickets, findings


def load_dictionary(path):
    """Load an approved-tags dictionary file.

    One tag per line, blank lines and lines starting with # are
    ignored. Matching is case-insensitive, so "Refund" in the
    export matches "refund" in the dictionary.
    """
    try:
        with open(path, encoding="utf-8-sig") as handle:
            lines = handle.read().splitlines()
    except OSError as exc:
        raise ValueError("cannot read dictionary %s: %s" % (path, exc))
    approved = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        approved.add(stripped.lower())
    return approved


def audit(tickets, max_tags=DEFAULT_MAX_TAGS,
          min_uses=DEFAULT_MIN_USES, dictionary=None):
    """Audit a parsed ticket list and return a list of findings."""
    findings = []
    tag_ticket_count = {}
    tag_variants = {}

    for ticket in tickets:
        tags = ticket["tags"]
        if not tags:
            findings.append(Finding(
                ticket["id"], None, "untagged-ticket", "error",
                "ticket has no tags, so it cannot be routed, "
                "reported on, or found by tag"))
            continue
        if len(tags) > max_tags:
            findings.append(Finding(
                ticket["id"], None, "too-many-tags", "warning",
                "ticket carries %d tags, over the limit of %d, "
                "so the tag list is noise rather than signal"
                % (len(tags), max_tags)))
        lowered_counts = {}
        for tag in tags:
            lowered_counts[tag.lower()] = \
                lowered_counts.get(tag.lower(), 0) + 1
        for lowered, count in lowered_counts.items():
            if count > 1:
                findings.append(Finding(
                    ticket["id"], lowered, "duplicate-tag-on-ticket",
                    "warning",
                    "tag appears %d times on this ticket" % count))
        seen = set()
        for tag in tags:
            if tag in seen:
                continue
            seen.add(tag)
            bad = invalid_characters(tag)
            if bad:
                findings.append(Finding(
                    ticket["id"], tag, "invalid-characters", "error",
                    "tag contains %s, which Zendesk drops when the "
                    "ticket is updated (allowed: letters, digits, "
                    "-, _, :, /)" % ", ".join(repr(ch) for ch in bad)))
                continue
            if any(ch.isupper() for ch in tag):
                findings.append(Finding(
                    ticket["id"], tag, "uppercase-tag", "warning",
                    "tag has uppercase letters; Zendesk treats tags "
                    "as lowercase, so this splits reporting from %s"
                    % tag.lower()))
            if tag.lower() in GENERIC_TAGS:
                findings.append(Finding(
                    ticket["id"], tag, "generic-tag", "warning",
                    "tag says nothing about the ticket, so it adds "
                    "noise to reports and views"))
            if dictionary is not None and tag.lower() not in dictionary:
                findings.append(Finding(
                    ticket["id"], tag, "unapproved-tag", "warning",
                    "tag is not in the approved dictionary"))
            tag_ticket_count[tag] = tag_ticket_count.get(tag, 0) + 1
            tag_variants.setdefault(normalize_tag(tag), set()).add(tag)

    for tag, count in sorted(tag_ticket_count.items()):
        if count < min_uses:
            findings.append(Finding(
                "(tag set)", tag, "single-use-tag", "warning",
                "tag is used on only %d ticket%s, so it is a "
                "one-off rather than a category"
                % (count, "" if count == 1 else "s")))
    for canonical, variants in sorted(tag_variants.items()):
        if len(variants) > 1:
            ordered = sorted(variants)
            findings.append(Finding(
                "(tag set)", canonical, "near-duplicate-tags",
                "warning",
                "tags %s all mean the same thing and should be "
                "merged into one tag"
                % ", ".join(repr(variant) for variant in ordered)))
    return findings


def summarize(tickets, findings):
    """Return the summary counts for a ticket list and findings."""
    total_tags = sum(len(ticket["tags"]) for ticket in tickets)
    errors = sum(1 for item in findings if item.severity == "error")
    warnings = sum(1 for item in findings if item.severity == "warning")
    return {"tickets": len(tickets), "tags": total_tags,
            "findings": len(findings), "errors": errors,
            "warnings": warnings}


def render_text(tickets, findings, summary):
    """Render the text report."""
    lines = [str(item) for item in findings]
    lines.append("")
    lines.append("Tickets: %(tickets)d, tags: %(tags)d, "
                 "findings: %(findings)d, errors: %(errors)d, "
                 "warnings: %(warnings)d" % summary)
    if summary["findings"] == 0:
        lines.append("All tickets clean.")
    return "\n".join(lines) + "\n"


def render_json(tickets, findings, summary):
    """Render the JSON report."""
    report = dict(summary)
    report["findings"] = [item.as_dict() for item in findings]
    return json.dumps(report, indent=2) + "\n"


def build_parser():
    """Build the command line parser."""
    parser = argparse.ArgumentParser(
        prog="ticket-tag-doctor",
        description="Audit a support ticket CSV export for tag hygiene.")
    parser.add_argument("csv_file", help="ticket CSV export to audit")
    parser.add_argument("--tags-column", default="tags",
                        help="name of the tags column (default: tags)")
    parser.add_argument("--id-column", default=None,
                        help="name of the ticket id column "
                        "(default: id, else ticket_id, else row number)")
    parser.add_argument("--dictionary", default=None,
                        help="file of approved tags, one per line")
    parser.add_argument("--max-tags", type=int,
                        default=DEFAULT_MAX_TAGS,
                        help="most tags allowed per ticket "
                        "(default: %d)" % DEFAULT_MAX_TAGS)
    parser.add_argument("--min-uses", type=int, default=DEFAULT_MIN_USES,
                        help="a tag used fewer times than this is "
                        "flagged single-use (default: %d)"
                        % DEFAULT_MIN_USES)
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of text")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if any error is found")
    parser.add_argument("--strict", action="store_true",
                        help="with --check, also exit 1 on warnings")
    parser.add_argument("--out", default=None,
                        help="write the report to a file")
    return parser


def main(argv=None):
    """Run the CLI and return the exit code."""
    args = build_parser().parse_args(argv)
    if args.max_tags < 1:
        print("error: --max-tags must be at least 1", file=sys.stderr)
        return 2
    if args.min_uses < 1:
        print("error: --min-uses must be at least 1", file=sys.stderr)
        return 2
    dictionary = None
    if args.dictionary is not None:
        try:
            dictionary = load_dictionary(args.dictionary)
        except ValueError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
    try:
        tickets, findings = parse_csv(args.csv_file, args.id_column,
                                      args.tags_column)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    findings.extend(audit(tickets, max_tags=args.max_tags,
                          min_uses=args.min_uses,
                          dictionary=dictionary))
    summary = summarize(tickets, findings)
    if args.json:
        report = render_json(tickets, findings, summary)
    else:
        report = render_text(tickets, findings, summary)
    if args.out is not None:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(report)
        except OSError as exc:
            print("error: cannot write %s: %s" % (args.out, exc),
                  file=sys.stderr)
            return 2
    else:
        sys.stdout.write(report)
    if args.check:
        if summary["errors"] > 0:
            return 1
        if args.strict and summary["warnings"] > 0:
            return 1
    return 0


def main_entry():
    """Console script entry point."""
    sys.exit(main())


if __name__ == "__main__":
    main_entry()
