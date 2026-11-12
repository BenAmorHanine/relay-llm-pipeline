# eval/questions.yaml: format

A YAML list. One mapping per question. Comments (`#`) are allowed anywhere. Pages are the numbers **printed on the page**. For the three pinned PDFs these equal the PDF page index; this was checked in Step 4, and Attention's page 1 has no printed number.

| Field | Type | Required | Rule |
|---|---|---|---|
| `id` | string | yes | `q` + two digits (`q01`…), unique |
| `type` | string | yes | one of `single_fact`, `table_number`, `explanation`, `cross_paper`, `term_trap`, `unanswerable` |
| `question` | string | yes | non-empty; exactly what is sent to the pipeline |
| `should_refuse` | bool | yes | `true` if and only if `type` is `unanswerable` |
| `key_facts` | list of strings | yes | non-empty; what a correct answer must contain (for `unanswerable`: what a correct refusal must say) |
| `gold` | list of mappings | yes | empty if and only if `should_refuse` is `true`; each item is `{paper, section, page}` (below) |
| `note` | string | no | free text: why the question is hard, which pitfall it targets |
| `verified` | bool | yes | `true` once the item has been checked against the PDF by hand |

`gold` item:

| Field | Type | Rule |
|---|---|---|
| `paper` | string | one of `1706.03762v7`, `2410.00037v1`, `2507.07955v2` |
| `section` | string | free text for people, conventionally `"<number> <title>"` with an optional `(sub-part)` or `, Table N`; not used for scoring |
| `page` | int | printed page number, within the paper (1–15, 1–66, 1–39) |

Scoring uses only `paper` + `page`: a retrieved chunk is a gold hit if it is from that paper and its page range covers that page. `section` is checked only as a warning: if it starts with a section number, that number should exist in the clean extraction and contain the page.

Validated by `scripts/validate_questions.py`, which only reads the file and never edits it.
