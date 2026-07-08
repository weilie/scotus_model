# SCOTUS Jackson Court Corpus Builder

Build a public-source corpus for Supreme Court argued merits cases from the Jackson Court period, defaulting to October Term 2022 onward. The corpus is intended to support downstream modeling work, including judgment-outcome prediction, while keeping the raw data collection step reproducible and auditable.

Primary source: supremecourt.gov. Optional text extraction uses `pypdf`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Test

```bash
python -m pytest -q
```

## Smoke test on a few real Jackson Court cases

This downloads documents for the first 3 cases discovered from the OT2022 slip-opinion page, enriched with transcript, audio, docket, filing, and questions-presented links where available:

```bash
python -m scotus_corpus_builder.build_corpus --terms 2022 --limit 3 --out data/scotus-jackson-court --extract-text
```

To avoid downloading PDFs/audio and only build metadata:

```bash
python -m scotus_corpus_builder.build_corpus --terms 2022 --limit 3 --out data/scotus-jackson-court --metadata-only
```

`--limit` preserves discovery order from the Supreme Court term pages, so small smoke tests are easier to inspect.

## Full run

```bash
python -m scotus_corpus_builder.build_corpus --terms 2022 2023 2024 2025 2026 --out data/scotus-jackson-court --extract-text
```

The job is resume-safe: existing files with matching manifest entries are skipped unless `--force` is used.

## Output layout

```text
scotus-jackson-court/
  cases.csv
  manifest.jsonl
  cases/
    2022/
      21-476_303-creative-llc-v-elenis/
        metadata.json
        docket.html
        case_metadata/*.pdf
        briefs_and_filings/*.pdf
        oral_argument/transcript.pdf
        oral_argument/audio.mp3
        opinions/slip_opinion.pdf
        extracted_text/*.txt
```

## Outputs

- `cases.csv`: one row per discovered case, including docket, case name, term, decision date, argument date, source URLs, lower court, and questions-presented URL when available.
- `manifest.jsonl`: one row per discovered document, including document type, source URL, local path, download status, hash, and error details.
- `cases/<term>/<docket_slug>/metadata.json`: full per-case metadata and document references.
- `docket.html`: saved docket page for auditability.
- `extracted_text/*.txt`: optional text extracted from downloaded PDFs.

## Data Scope

The collector currently targets public materials hosted by the Supreme Court:

- Slip opinions
- Oral argument transcripts
- Oral argument audio
- Docket pages
- Questions-presented PDFs
- Case-specific docket PDFs, including briefs, appendices, motions, certificates, and proofs of service

It intentionally ignores site-wide public-information PDFs that may be linked from docket pages but are not case filings.

More detail is in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Modeling Status

This repository currently builds the corpus. It does not yet create supervised judgment labels or train a model. Recommended next steps are documented in [docs/MODELING_PLAN.md](docs/MODELING_PLAN.md).

## Public Repository Notes

Before publishing, review [docs/PUBLIC_RELEASE_CHECKLIST.md](docs/PUBLIC_RELEASE_CHECKLIST.md). In particular, choose a license, avoid committing downloaded PDFs/audio unless you intentionally want a large data repository, and document any generated datasets separately from the source code.
