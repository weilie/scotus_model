# Test Status

Local parser tests pass:

```text
5 passed
```

Live metadata-only smoke test against supremecourt.gov also passed on July 8, 2026:

```bash
python -m scotus_corpus_builder.build_corpus --terms 2022 --limit 2 --out /tmp/scotus-smoke-20260708 --metadata-only
```

Result:

```text
Wrote 2 cases and 424 document records to /tmp/scotus-smoke-20260708
```

The smoke test verified:

- `--limit 2` starts with `21-476` and `22-535`, matching OT2022 slip-opinion discovery order.
- Docket parsing excludes site-wide `publicinfo` PDFs.
- Questions-presented PDFs are captured in `case_metadata`.
- Certificate and proof-of-service attachments are not mislabeled as the main petition or brief.

Parser fixtures are based on actual Supreme Court pages:

- No. 21-476, 303 Creative LLC v. Elenis docket page
- OT2022 slip-opinion term page
- OT2022 oral-argument transcript/audio pages
- No. 22-174, Groff v. DeJoy docket/audio/opinion pages
- No. 21-1333, Gonzalez v. Google audio/opinion pages

Run this on your machine for the live smoke test:

```bash
python -m scotus_corpus_builder.build_corpus --terms 2022 --limit 3 --out data/scotus-jackson-court --extract-text
```
