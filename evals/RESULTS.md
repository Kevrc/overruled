# Clerk evaluation

The clerk is the part of Overruled that uses no AI, so it can be measured directly.

| Test | Result |
|---|---|
| Hand-labelled fabricated claims caught | 20 of 20 |
| Hand-labelled supported claims kept | 20 of 20 |
| Live defense speeches where an unsupported figure was struck | 20 of 20 |
| Live prosecution speeches struck | 1 of 20, a real misquote ("give" where the contract says "gives") |

## Harborline benchmark

Harborline is a fictional company, not a customer. Its 34 renewals in `imports/benchmark` and `imports/benchmark-2` hide known traps.

| Test | First score | Now |
|---|---|---|
| 26 renewals: hidden increases, missed deadlines, partial usage data, mismatched bills, overlapping tools | 15 of 26 | 26 of 26 |
| 8 contracts in wording the rules hadn't seen | 1 of 8 | 7 of 8 |
| A planted instruction telling the AI to lie and approve: 10 runs each of witness, juror and contract reader | Not obeyed once | Not obeyed once |

- The first score on the second set shows that pattern rules alone don't generalize. Unclear contracts now go to a model, and code rejects any clause that isn't word for word in the contract with the number it claims.
- The one miss is safe: a contract with no renewal clause and a seat lock was stopped for a person to read, with a different reason than expected.
- Both sets have now been used to fix the system, so neither is a blind test anymore. Real contracts will find new failures.
- One first-pass failure was a mistake in the test data, not the system, and it was corrected.
- Run them with `uv run python -m evals.benchmark`, `uv run python -m evals.benchmark benchmark-2` and `uv run python -m evals.injection_eval`. The second set and the planted instruction test use Claude.

## How it was run

- **Labelled claims:** `evals/claims.yaml`, 40 sentences about the Nimbusly case. Run with `uv run python -m evals.clerk_eval`.
- **Live speeches:** 40 real Claude Sonnet speeches across four cases, in `evals/live_results.json`. Run with `uv run python -m evals.live_eval 20`.

## What this does not prove

- These numbers come from the final version, after the first runs exposed bugs. Runs vary: an earlier run of the same version struck 0 of 20. The first score on labelled claims was 15 of 20, because figures written in words got through. The first live run wrongly struck 10 of 20 prosecution speeches, because of a quote parsing bug.
- The labelled claims helped shape those fixes, so they are not a blind test.
- The sample is small, and every case is fictional.
- A defense strike is not always an invented value. The clerk also strikes correct arithmetic that isn't in the evidence, such as a monthly price worked out from a yearly one. That is deliberate: speakers must use the clerk's figures.
- The clerk checks numbers and quotes only. A false claim with neither can reach the jury.
