# auto-linkedin

A local application assistant using Python, JSON and a static dashboard. Private records stay in an external workspace. No employer submission is enabled by default.

Run `python3 -m unittest discover -s tests -v` and `node --test tests/run-grouping.test.cjs` from this directory. Publication requires `python3 scripts/publication.py --history`; optional local forbidden markers are a JSON array selected with `--forbidden-markers` outside this repository.

Existing workspace layouts can be selected in place; no migration or deletion is required. Do not stage private files or generated dashboards.

Supported baseline: macOS, Python 3.10+ and Node 18+ for tests. Runtime uses Python stdlib and static HTML/CSS/JS. POSIX locking is also usable on Linux; Windows locking and live browsers are unsupported. PDF import optionally needs Poppler and PyMuPDF; routine commands do not.

Set up with `python3 scripts/workspace.py --workspace /tmp/synthetic-workspace init`, then run the same command with `doctor`. For private use choose a persistent external directory. Doctor reports live browser support honestly and does not open or alter authenticated sessions.

To answer questions: export the dashboard, edit the Questions view, click **Export answer changes**, then run `python3 scripts/workspace.py --workspace /tmp/synthetic-workspace import-answers --file /tmp/answer-changes.json`. Refresh the page to confirm persistence. Downloading alone does not save answers. Scope is shown with each answer; review authorization lasts 30 days in this UI.

Run `export` to install/update the static dashboard inside the selected private workspace, then open its `dashboard/index.html`. Set `defer_export: true` in private config to defer repeated updates; explicit `export` repairs/refreshes the view. A successful mutation can report a failed export and remains saved; repeat `export`, not the submission.

Synthetic execution: `run --catalog /tmp/synthetic-catalog.json --batch demo --quota 2 --max-steps 10`. Catalog is a JSON list of fictional jobs with verified structured requirements and semantic form fields. Without a synthetic catalog, the adapter reports `unsupported_live_capability`; there is no live employer adapter. Batch quota is immutable. Unresolved submit intents reserve capacity until evidence reconciliation. Private `budgets` config supports `duration_seconds` (default 900), `max_actions` (100), `max_retries` (3) and optional measured `provider_token_limit`/`provider_cost_limit`. `--deadline` supplies an offset-aware deadline when creating a batch. Deadlines persist across restart; use a new batch for a new time budget.
