# Modeling Plan

The current repository builds a corpus. A judgment-prediction model needs an additional supervised-label layer before training.

## Target Labels

Define labels in a separate table, for example `labels/cases.csv`, rather than embedding them in the raw collection output.

Candidate labels:

- Judgment direction: petitioner win, respondent win, mixed, dismissed, vacated/remanded, or other
- Lower-court disposition: affirmed, reversed, vacated, remanded, dismissed, or mixed
- Vote split: for example `9-0`, `6-3`, `5-4`
- Majority author
- Joining coalitions by justice
- Issue area
- Ideological direction, if using an external coding scheme

Keep each label's source explicit. Some labels can be parsed from opinions, but many should be audited manually or imported from a trusted structured source.

## Feature Layers

Recommended feature groups:

- Questions presented
- Merits briefs
- Amicus brief counts and text
- Oral argument transcript text
- Lower court
- Term and argument timing
- Parties and petitioner/respondent posture
- Opinion text for retrospective analysis only

For prospective judgment prediction, avoid leakage. Do not use slip-opinion text, final vote splits, or post-decision metadata as model inputs.

## Suggested Pipeline

1. Build raw corpus with `scotus_corpus_builder.build_corpus`.
2. Extract and normalize text into a stable feature table.
3. Create a reviewed label table with source citations.
4. Split train/test by term, not by random case row, to better approximate future prediction.
5. Start with a simple baseline model before using larger language-model features.
6. Save model inputs, labels, prompts, and evaluation outputs with versioned filenames.

## Evaluation Notes

Report accuracy against simple baselines, such as always predicting petitioner win or lower-court reversal. For small modern-term datasets, also report confidence intervals or use leave-one-term-out evaluation.

Supreme Court merits cases are a small dataset. Treat model output as experimental research, not legal advice.
