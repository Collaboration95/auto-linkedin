# auto-linkedin

A local application assistant using Python, JSON and a static dashboard. Private records stay in an external workspace. No employer submission is enabled by default.

Run `python3 -m unittest discover -s tests -v` and `node --test tests/run-grouping.test.cjs` from this directory. Publication requires `python3 scripts/publication.py --history`; optional local forbidden markers are a JSON array selected with `--forbidden-markers` outside this repository.

Existing workspace layouts can be selected in place; no migration or deletion is required. Do not stage private files or generated dashboards.
