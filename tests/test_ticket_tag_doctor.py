"""Tests for ticket-tag-doctor."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ticket_tag_doctor as ttd

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "examples")


def write_csv(content):
    """Write content to a temp CSV file and return its path."""
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".csv", delete=False, encoding="utf-8")
    handle.write(content)
    handle.close()
    return handle.name


def rules(findings):
    """Return the sorted rule names of a findings list."""
    return sorted(item.rule for item in findings)


def by_rule(findings, rule):
    """Return the findings with one rule name."""
    return [item for item in findings if item.rule == rule]


class TestSplitTags(unittest.TestCase):
    def test_comma_separated(self):
        self.assertEqual(ttd.split_tags("refund, billing"),
                         ["refund", "billing"])

    def test_semicolon_separated(self):
        self.assertEqual(ttd.split_tags("refund;billing"),
                         ["refund", "billing"])

    def test_space_separated(self):
        self.assertEqual(ttd.split_tags("refund billing"),
                         ["refund", "billing"])

    def test_empty_segments_dropped(self):
        self.assertEqual(ttd.split_tags("refund,, billing "),
                         ["refund", "billing"])

    def test_empty_field(self):
        self.assertEqual(ttd.split_tags(""), [])
        self.assertEqual(ttd.split_tags(None), [])


class TestInvalidCharacters(unittest.TestCase):
    def test_plain_tag_valid(self):
        self.assertEqual(ttd.invalid_characters("refund"), [])

    def test_allowed_punctuation(self):
        self.assertEqual(ttd.invalid_characters("a-b_c:d/e"), [])

    def test_hash_at_bang_are_invalid(self):
        self.assertEqual(ttd.invalid_characters("crash!"), ["!"])
        self.assertEqual(ttd.invalid_characters("vip#1"), ["#"])
        self.assertEqual(ttd.invalid_characters("hi@there"), ["@"])

    def test_dot_is_invalid(self):
        self.assertEqual(ttd.invalid_characters("v2.0"), ["."])

    def test_space_inside_comma_tag_is_invalid(self):
        self.assertEqual(ttd.invalid_characters("tech support"), [" "])

    def test_unicode_letters_allowed(self):
        self.assertEqual(ttd.invalid_characters("rendez-vous"), [])
        self.assertEqual(ttd.invalid_characters("café"), [])


class TestNormalizeTag(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(ttd.normalize_tag("Refund"), "refund")

    def test_unifies_separators(self):
        self.assertEqual(ttd.normalize_tag("date-change"), "date_change")
        self.assertEqual(ttd.normalize_tag("date/change"), "date_change")

    def test_strips_plural(self):
        self.assertEqual(ttd.normalize_tag("refunds"), "refund")

    def test_short_tag_keeps_s(self):
        self.assertEqual(ttd.normalize_tag("rma"), "rma")

    def test_double_s_keeps_s(self):
        self.assertEqual(ttd.normalize_tag("class"), "class")


class TestParseCsv(unittest.TestCase):
    def test_basic_parse(self):
        path = write_csv("id,subject,tags\nT-1,Hi,refund; billing\n")
        try:
            tickets, findings = ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)
        self.assertEqual(findings, [])
        self.assertEqual(tickets, [{"id": "T-1",
                                    "tags": ["refund", "billing"]}])

    def test_ticket_id_column_fallback(self):
        path = write_csv("ticket_id,tags\nT-9,refund\n")
        try:
            tickets, _ = ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)
        self.assertEqual(tickets[0]["id"], "T-9")

    def test_no_id_column_uses_row_number(self):
        path = write_csv("subject,tags\nHi,refund\n")
        try:
            tickets, _ = ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)
        self.assertEqual(tickets[0]["id"], "row 2")

    def test_bom_header_handled(self):
        path = write_csv("\ufeffid,tags\nT-1,refund\n")
        try:
            tickets, findings = ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)
        self.assertEqual(findings, [])
        self.assertEqual(tickets[0]["id"], "T-1")

    def test_extra_columns_ignored(self):
        path = write_csv("id,subject,priority,tags\nT-1,Hi,high,refund\n")
        try:
            tickets, findings = ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)
        self.assertEqual(findings, [])
        self.assertEqual(tickets[0]["tags"], ["refund"])

    def test_malformed_row_is_error_not_crash(self):
        path = write_csv("id,tags\nT-1,refund\nT-2,billing,extra\n"
                         "T-3,delivery\n")
        try:
            tickets, findings = ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)
        self.assertEqual([t["id"] for t in tickets], ["T-1", "T-3"])
        self.assertEqual(rules(findings), ["malformed-row"])
        self.assertEqual(findings[0].severity, "error")
        self.assertEqual(findings[0].ticket, "row 3")

    def test_short_row_is_malformed(self):
        path = write_csv("id,subject,tags\nT-1,Hi\n")
        try:
            tickets, findings = ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)
        self.assertEqual(tickets, [])
        self.assertEqual(rules(findings), ["malformed-row"])

    def test_missing_tags_column(self):
        path = write_csv("id,subject\nT-1,Hi\n")
        try:
            with self.assertRaises(ValueError):
                ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)

    def test_missing_file(self):
        with self.assertRaises(ValueError):
            ttd.parse_csv("/nonexistent/tickets.csv", None, "tags")

    def test_empty_file(self):
        path = write_csv("")
        try:
            with self.assertRaises(ValueError):
                ttd.parse_csv(path, None, "tags")
        finally:
            os.unlink(path)


class TestAudit(unittest.TestCase):
    def audit(self, tickets, **kwargs):
        return ttd.audit(tickets, **kwargs)

    def test_untagged_is_error(self):
        findings = self.audit([{"id": "T-1", "tags": []}])
        self.assertEqual(rules(findings), ["untagged-ticket"])
        self.assertEqual(findings[0].severity, "error")

    def test_invalid_characters_is_error(self):
        findings = self.audit([{"id": "T-1", "tags": ["crash!"]}])
        self.assertEqual(rules(findings), ["invalid-characters"])
        self.assertEqual(findings[0].severity, "error")

    def test_invalid_tag_skips_single_use(self):
        findings = self.audit([{"id": "T-1", "tags": ["crash!"]}])
        self.assertNotIn("single-use-tag", rules(findings))

    def test_uppercase_is_warning(self):
        findings = self.audit([{"id": "T-1", "tags": ["Refund"]},
                               {"id": "T-2", "tags": ["Refund"]}])
        self.assertEqual(rules(findings), ["uppercase-tag",
                                           "uppercase-tag"])

    def test_generic_tag_is_warning(self):
        findings = self.audit([{"id": "T-1", "tags": ["question"]},
                               {"id": "T-2", "tags": ["question"]}])
        self.assertEqual(rules(findings), ["generic-tag",
                                           "generic-tag"])

    def test_single_use_tag(self):
        findings = self.audit([{"id": "T-1", "tags": ["refund"]},
                               {"id": "T-2", "tags": ["billing"]}])
        self.assertEqual(rules(findings), ["single-use-tag",
                                           "single-use-tag"])

    def test_tag_used_twice_is_not_single_use(self):
        findings = self.audit([{"id": "T-1", "tags": ["refund"]},
                               {"id": "T-2", "tags": ["refund"]}])
        self.assertEqual(findings, [])

    def test_min_uses_threshold(self):
        tickets = [{"id": "T-1", "tags": ["refund"]},
                   {"id": "T-2", "tags": ["refund"]}]
        findings = self.audit(tickets, min_uses=3)
        self.assertEqual(rules(findings), ["single-use-tag"])

    def test_too_many_tags(self):
        tags = ["tag%d" % number for number in range(11)]
        findings = self.audit([{"id": "T-1", "tags": tags}])
        self.assertIn("too-many-tags", rules(findings))

    def test_max_tags_option(self):
        tags = ["tag%d" % number for number in range(11)]
        findings = self.audit([{"id": "T-1", "tags": tags}],
                              max_tags=15)
        self.assertNotIn("too-many-tags", rules(findings))

    def test_ten_tags_is_allowed_by_default(self):
        tags = ["tag%d" % number for number in range(10)]
        findings = self.audit([{"id": "T-1", "tags": tags}])
        self.assertNotIn("too-many-tags", rules(findings))

    def test_duplicate_tag_on_ticket(self):
        findings = self.audit([{"id": "T-1", "tags": ["refund", "Refund"]},
                               {"id": "T-2", "tags": ["refund"]}])
        dupes = by_rule(findings, "duplicate-tag-on-ticket")
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0].severity, "warning")

    def test_near_duplicate_case_variant(self):
        findings = self.audit([{"id": "T-1", "tags": ["refund"]},
                               {"id": "T-2", "tags": ["Refund"]}])
        groups = by_rule(findings, "near-duplicate-tags")
        self.assertEqual(len(groups), 1)
        self.assertIn("refund", groups[0].message)
        self.assertIn("Refund", groups[0].message)

    def test_near_duplicate_separator_and_plural(self):
        findings = self.audit(
            [{"id": "T-1", "tags": ["date_change"]},
             {"id": "T-2", "tags": ["date-change"]},
             {"id": "T-3", "tags": ["refunds"]},
             {"id": "T-4", "tags": ["refund"]}])
        groups = by_rule(findings, "near-duplicate-tags")
        self.assertEqual(len(groups), 2)

    def test_distinct_tags_are_not_near_duplicates(self):
        findings = self.audit([{"id": "T-1", "tags": ["refund"]},
                               {"id": "T-2", "tags": ["billing"]}])
        self.assertNotIn("near-duplicate-tags", rules(findings))

    def test_dictionary_approved(self):
        findings = self.audit([{"id": "T-1", "tags": ["refund"]},
                               {"id": "T-2", "tags": ["refund"]}],
                              dictionary={"refund"})
        self.assertEqual(findings, [])

    def test_dictionary_unapproved(self):
        findings = self.audit([{"id": "T-1", "tags": ["refund"]},
                               {"id": "T-2", "tags": ["refund"]}],
                              dictionary={"billing"})
        self.assertEqual(rules(findings), ["unapproved-tag",
                                           "unapproved-tag"])

    def test_dictionary_match_is_case_insensitive(self):
        findings = self.audit([{"id": "T-1", "tags": ["RMA"]},
                               {"id": "T-2", "tags": ["RMA"]}],
                              dictionary={"rma"})
        self.assertNotIn("unapproved-tag", rules(findings))

    def test_summary_counts(self):
        tickets = [{"id": "T-1", "tags": []},
                   {"id": "T-2", "tags": ["question"]}]
        findings = self.audit(tickets)
        summary = ttd.summarize(tickets, findings)
        self.assertEqual(summary["tickets"], 2)
        self.assertEqual(summary["tags"], 1)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["warnings"], 2)


class TestDictionaryFile(unittest.TestCase):
    def test_comments_and_blanks_ignored(self):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8")
        handle.write("# comment\n\nrefund\n  billing  \n# other\n")
        handle.close()
        try:
            approved = ttd.load_dictionary(handle.name)
        finally:
            os.unlink(handle.name)
        self.assertEqual(approved, {"refund", "billing"})

    def test_missing_dictionary_file(self):
        with self.assertRaises(ValueError):
            ttd.load_dictionary("/nonexistent/dictionary.txt")


class TestCli(unittest.TestCase):
    def run_cli(self, *argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = ttd.main(list(argv))
        return code, buffer.getvalue()

    def test_sample_file_counts(self):
        path = os.path.join(EXAMPLES, "tickets.csv")
        code, output = self.run_cli(path)
        self.assertEqual(code, 0)
        self.assertIn("Tickets: 12, tags: 25, findings: 29, "
                      "errors: 3, warnings: 26", output)

    def test_check_fails_on_errors(self):
        path = os.path.join(EXAMPLES, "tickets.csv")
        code, _ = self.run_cli(path, "--check")
        self.assertEqual(code, 1)

    def test_clean_file_passes_check(self):
        path = os.path.join(EXAMPLES, "clean.csv")
        code, output = self.run_cli(path, "--check")
        self.assertEqual(code, 0)
        self.assertIn("All tickets clean.", output)

    def test_strict_fails_on_warnings_only(self):
        path = write_csv("id,tags\nT-1,question\nT-2,question\n")
        try:
            code, _ = self.run_cli(path, "--check")
            self.assertEqual(code, 0)
            code, _ = self.run_cli(path, "--check", "--strict")
            self.assertEqual(code, 1)
        finally:
            os.unlink(path)

    def test_json_output_shape(self):
        path = os.path.join(EXAMPLES, "clean.csv")
        code, output = self.run_cli(path, "--json")
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertEqual(report["tickets"], 3)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["errors"], 0)

    def test_json_finding_fields(self):
        path = os.path.join(EXAMPLES, "tickets.csv")
        _, output = self.run_cli(path, "--json")
        report = json.loads(output)
        untagged = [item for item in report["findings"]
                    if item["rule"] == "untagged-ticket"]
        self.assertEqual(len(untagged), 1)
        self.assertEqual(untagged[0]["ticket"], "T-112")
        self.assertEqual(untagged[0]["severity"], "error")

    def test_dictionary_flag(self):
        path = os.path.join(EXAMPLES, "tickets.csv")
        dictionary = os.path.join(EXAMPLES, "dictionary.txt")
        _, output = self.run_cli(path, "--dictionary", dictionary)
        self.assertIn("findings: 39, errors: 3, warnings: 36", output)

    def test_missing_file_exits_2(self):
        code, _ = self.run_cli("/nonexistent/tickets.csv")
        self.assertEqual(code, 2)

    def test_out_writes_file(self):
        path = os.path.join(EXAMPLES, "clean.csv")
        out = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False)
        out.close()
        try:
            code, output = self.run_cli(path, "--out", out.name)
            self.assertEqual(code, 0)
            self.assertEqual(output, "")
            with open(out.name, encoding="utf-8") as handle:
                self.assertIn("All tickets clean.", handle.read())
        finally:
            os.unlink(out.name)

    def test_max_tags_flag(self):
        path = write_csv("id,tags\nT-1,a,b,c,d,e,f,g,h,i,j,k\n")
        try:
            _, output = self.run_cli(path, "--max-tags", "12")
            self.assertNotIn("too-many-tags", output)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
