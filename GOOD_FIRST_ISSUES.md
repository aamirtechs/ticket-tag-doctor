# Good first issues

Seeded issues for new contributors. File each one on GitHub with
the `good first issue` and `help wanted` labels.

## 1. Add a merge plan export

Title: Export a CSV of near-duplicate tags to merge

Description: Add a --merge-out flag that writes a CSV of the
near-duplicate groups (canonical tag, variant tags, ticket count
per variant), so a support lead can review the list and merge
exactly those tags in Zendesk. The tool itself must never change
anything in the helpdesk.

Difficulty: Easy

Acceptance criteria: the export lists both groups from the
sample file (refund and date_change); a test round-trips the
export; README documents the flag.

## 2. Add a most-used tags table

Title: Show the most-used tags in the summary

Description: After the findings, print a short table of the five
most-used tags (tag, ticket count), so a support lead can see
which tags actually carry the reporting load.

Difficulty: Easy

Acceptance criteria: the table appears in text output with the
correct top five for the sample file (billing and password_reset
first, both used on 2 tickets); JSON output is unchanged; a test
checks the table rows.

## 3. Support a custom generic tags file

Title: Let teams supply their own generic tags list

Description: Add a --generic-tags flag that reads a file of
generic tags (one per line, same format as --dictionary) and
uses it instead of the built-in list, so a team can flag its
own noise words like "followup" or "escalated".

Difficulty: Easy

Acceptance criteria: a file containing "followup" flags a
followup tag and does not flag question; without the flag the
built-in list still applies; a test covers both cases; README
documents the flag.

## 4. Add a tag count histogram

Title: Show how tag usage is distributed

Description: Add a --histogram flag that prints, after the
summary, how many tags are used on exactly 1 ticket, 2 tickets,
3 to 5 tickets, and more than 5 tickets, so a team can see at a
glance whether the tag set is mostly one-offs or mostly shared
categories.

Difficulty: Medium

Acceptance criteria: the histogram for the sample file shows 20
tags used once, 2 tags used twice, and 0 in the higher buckets;
a test checks the counts; README documents the flag.
