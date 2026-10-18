# auto-linkedin

A local application assistant using Python, JSON and a static dashboard. Private records stay in an external workspace. No employer submission is enabled by default.

Run `python3 -m unittest discover -s tests -v` and `node --test tests/run-grouping.test.cjs` from this directory. Publication requires `python3 scripts/publication.py --history`; optional local forbidden markers are a JSON array selected with `--forbidden-markers` outside this repository.

Existing workspace layouts can be selected in place; no migration or deletion is required. Do not stage private files or generated dashboards.

Supported baseline: macOS, Python 3.10+ and Node 18+ for tests. Runtime uses Python stdlib and static HTML/CSS/JS. POSIX locking is also usable on Linux; Windows locking and live browsers are unsupported. PDF import optionally needs Poppler and PyMuPDF; routine commands do not.

Set up with `python3 scripts/workspace.py --workspace /tmp/synthetic-workspace init`, then run the same command with `doctor`. For private use choose a persistent external directory. Doctor reports live browser support honestly and does not open or alter authenticated sessions.

To answer questions: export the dashboard, edit the Questions view, click **Export answer changes**, then run `python3 scripts/workspace.py --workspace /tmp/synthetic-workspace import-answers --file /tmp/answer-changes.json`. Refresh the page to confirm persistence. Downloading alone does not save answers. Scope is shown with each answer; review authorization lasts 30 days in this UI.

Run `export` to install/update the static dashboard inside the selected private workspace, then open its `dashboard/index.html`. Set `defer_export: true` in private config to defer repeated updates; explicit `export` repairs/refreshes the view. A successful mutation can report a failed export and remains saved; repeat `export`, not the submission.

Synthetic execution: `run --catalog /tmp/synthetic-catalog.json --batch demo --quota 2 --max-steps 10`. Catalog is a JSON list of fictional jobs with verified structured requirements and semantic form fields. Without a synthetic catalog, the adapter reports `unsupported_live_capability`; there is no live employer adapter. Batch quota is immutable. Unresolved submit intents reserve capacity until evidence reconciliation. Private `budgets` config supports `duration_seconds` (default 900), `max_actions` (100), `max_retries` (3) and optional measured `provider_token_limit`/`provider_cost_limit`. `--deadline` supplies an offset-aware deadline when creating a batch. Deadlines persist across restart; use a new batch for a new time budget.

After fixing and reviewing a login/layout/fact prerequisite, run `resume` (optionally `--id` for one application) to acknowledge it, then rerun the batch. This never clears uncertain submissions, confirmations, exhausted retries or batch budgets. Reconcile an uncertain intent with saved confirmation evidence through `submission.confirm`, or explicit evidence that no submission occurred through `submission.reconcile_not_submitted`; neither automatically retries a click. `metrics` prints a shareable numeric-only measured summary. Missing provider usage remains null.

For the real local browser form smoke, serve this source directory only on loopback and open `fixtures/form.html`. Run its text/select/upload smoke and changed-layout fallback; it never contacts an employer.

Run the full offline scenario with `python3 scripts/smoke.py`. To retain its fictional dashboard and local browser form, add `--workspace /tmp/synthetic-demo` using an empty disposable directory. Open `dashboard/index.html` there for Questions/Run views. The scenario covers shared unknown answers, one batch import, exclusions, form preparation, confirmations, duplicate refusal, interrupted intent reconciliation, export recovery and deadline/quota limits.

Release verification: `python3 scripts/clean_smoke.py` copies only manifest files to a temporary directory, runs both suites and the scenario, then checks fresh init/doctor/dashboard setup. Use `--destination /tmp/synthetic-release` to retain a clean export. The one Git-containment test is skipped in a source archive; all manifest/content/history regressions still run. A local Git checkout runs that containment test too.

Publication is deny-by-default: audit each added path, update `publication.json` and the exact `.gitignore` exceptions, run the publication check (including `--history` and optional external forbidden markers), then stage ordinary paths. History scanning includes all reachable refs and removed ancestors; symlink components cannot escape the release root. Generated data is never part of the release manifest. Keep optional forbidden-marker lists outside the repository. MIT license; notices are preserved in `NOTICE`.
