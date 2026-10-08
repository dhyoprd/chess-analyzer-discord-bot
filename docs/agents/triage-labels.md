# Triage Labels

The five canonical triage **state** roles, mapped to the label strings used in this repo's issue tracker.

| Canonical role | Label string in this repo |
|----------------|---------------------------|
| `needs-triage` | `needs-triage` |
| `needs-info` | `needs-info` |
| `ready-for-agent` | `ready-for-agent` |
| `ready-for-human` | `ready-for-human` |
| `wontfix` | `wontfix` |

The two **category** roles use the tracker's standard labels: `bug` and `enhancement`.

Every triaged issue carries exactly one category role and one state role. If state roles conflict, flag it and ask the maintainer before proceeding.

`/triage` reads this file to apply labels. If your tracker already uses different
strings (e.g. `bug:triage` for `needs-triage`), edit the right-hand column so
`triage` applies existing labels instead of creating duplicates.
