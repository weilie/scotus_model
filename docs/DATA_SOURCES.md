# Data Sources

This project collects publicly available Supreme Court materials from `https://www.supremecourt.gov`.

## Current Sources

- Slip opinion term pages: `https://www.supremecourt.gov/opinions/slipopinion/<term>`
- Oral argument transcript term pages: `https://www.supremecourt.gov/oral_arguments/argument_transcript/<term>`
- Oral argument audio pages: `https://www.supremecourt.gov/oral_arguments/audio/<term>/<docket>`
- Public docket pages: `https://www.supremecourt.gov/search.aspx?filename=/docket/docketfiles/html/public/<docket>.html`
- Case-specific docket PDFs under `/DocketPDF/`
- Questions-presented PDFs under `/qp/`

## Collection Boundaries

The collector stores public source URLs and local file paths for auditability. It filters docket links to avoid site-wide public-information PDFs that are not case-specific filings, such as media guides or general public-information documents.

The corpus builder does not currently collect:

- Non-Supreme-Court lower-court records
- Commercial legal databases
- SCDB labels
- Oyez metadata
- News, commentary, or prediction-market data

Those sources may be useful for modeling, but they should be integrated as separate, documented data layers with their own provenance and licensing notes.

## Reproducibility

Each downloaded file is recorded in `manifest.jsonl` with:

- Document type
- Source URL
- Local path
- Download status
- SHA-256 hash when downloaded
- Error message when collection fails

Per-case `metadata.json` files preserve the source document references that were discovered during the run.

## Public-Repo Caution

Supreme Court materials are public, but downloaded PDFs and audio can make a repository large and slow to clone. For a public GitHub repository, prefer committing source code, tests, and documentation while excluding generated `data/` output. Publish derived datasets separately if needed.
