# Public Release Checklist

Use this before making the repository public on GitHub.

## Repository Hygiene

- Choose and add a license.
- Keep generated `data/` outputs out of Git unless you intentionally want to publish a data repository.
- Do not commit `.venv/`, caches, logs, or local environment files.
- Run `python -m pytest -q`.
- Run a small metadata-only smoke test against supremecourt.gov.

## Data and Provenance

- Document every external data source.
- Keep raw source URLs in generated outputs.
- Record download hashes in `manifest.jsonl`.
- Separate raw collected data from derived features and labels.
- Include notes for any manually reviewed labels.

## Public Communication

- Describe the project as an experimental corpus and modeling tool.
- Avoid claiming predictive reliability until the model has a documented evaluation.
- State that outputs are not legal advice.
- Explain whether generated datasets are included, excluded, or published elsewhere.

## Suggested First GitHub Push

Commit source code, tests, and docs first. Generate the corpus locally after cloning:

```bash
python -m scotus_corpus_builder.build_corpus --terms 2022 --limit 3 --out data/scotus-jackson-court --metadata-only
```
