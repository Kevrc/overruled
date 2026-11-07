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

## Real public contracts

These are real software contracts published by US cities, counties and school districts. The links and hand labels are in `evals/public_contracts.yaml`. A contract is scored correct when the notice period and price increase match, or when it's stopped for a person because the terms have no fixed answer.

| Test | Result |
|---|---|
| 11 contracts, first run | 7 correct, 4 stopped for a person, 0 wrong |
| The same 11 after fixes | 10 correct, 1 stopped for a person, 0 wrong |
| 6 new contracts, blind | **5 correct, 1 wrong** |

- The blind labels were fixed before the single run, and no code changed in between. The blind result wasn't tuned afterwards.
- The first run exposed real problems: PDF text splits words and uses curly quotes, so exact quotes failed to match. The model also denied an auto-renewal that the contract stated, so code now checks that.
- Three of my hand labels on the first 11 were wrong, and the reader was right: two contracts let the county change pricing, and one had a 3% increase I had missed. I corrected them after reading those clauses. The first-run score above uses the corrected labels.
- The blind miss is Carroll County. The master agreement gives 90 days, and a county addendum requires written notice 30 days before the fiscal year ends. The label says 90, the reader said 30. Both clauses exist, so a person would have to decide, but it counts as wrong.
- Four more contracts were left out before running them, because their terms had no clear single answer or several contracts were mixed in one packet. Four others couldn't be downloaded as PDFs.
- 17 contracts is a small sample. Two share a template, and they're public-sector contracts, so they may not reflect private company terms.
- Run it with `uv run python -m evals.public_contracts` or `--blind`. It needs Claude and internet. Results can vary between runs.

## How it was run

- **Labelled claims:** `evals/claims.yaml`, 40 sentences about the Nimbusly case. Run with `uv run python -m evals.clerk_eval`.
- **Live speeches:** 40 real Claude Sonnet speeches across four cases, in `evals/live_results.json`. Run with `uv run python -m evals.live_eval 20`.

## What this does not prove

- These numbers come from the final version, after the first runs exposed bugs. Runs vary: an earlier run of the same version struck 0 of 20. The first score on labelled claims was 15 of 20, because figures written in words got through. The first live run wrongly struck 10 of 20 prosecution speeches, because of a quote parsing bug.
- The labelled claims helped shape those fixes, so they are not a blind test.
- The sample is small, and every case is fictional.
- A defense strike is not always an invented value. The clerk also strikes correct arithmetic that isn't in the evidence, such as a monthly price worked out from a yearly one. That is deliberate: speakers must use the clerk's figures.
- The clerk checks numbers and quotes only. A false claim with neither can reach the jury.
