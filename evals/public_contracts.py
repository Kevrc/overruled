"""Reads real public contracts and compares the result with hand labels. Needs Claude and internet.

Usage: python -m evals.public_contracts [--blind]
A safe stop is a contract the labels say could be read, which went to a person instead. A wrong read is the failure that matters.
"""
import pathlib, sys, tempfile, urllib.request
import yaml
from overruled import importer

CASES = yaml.safe_load((pathlib.Path(__file__).parent / "public_contracts.yaml").read_text())


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as r:
        return r.read()


def score(want: dict, read: tuple | None) -> str:
    if read is None:
        return "correct" if "stop" in want else "safe stop"
    if "stop" in want:
        return "wrong"
    uplift, _, notice, _ = read
    return "correct" if (notice, uplift) == (want["read"]["notice"], want["read"]["uplift"]) else "wrong"


def main() -> None:
    totals: dict[str, int] = {}
    only_blind = "--blind" in sys.argv
    for key, want in CASES.items():
        if want.get("blind", False) != only_blind:
            continue
        text = importer.contract_text("contract.pdf", fetch(want["url"]))
        try:
            read, why = importer.read_terms(text), ""
        except ValueError as e:
            read, why = None, str(e)
        result = score(want, read)
        totals[result] = totals.get(result, 0) + 1
        print(f"{key}: {result} | read {read[2] if read else '-'} days, {read[0] if read else '-'}% | {why[:90]}", flush=True)
    print(totals)
    sys.exit(1 if totals.get("wrong") else 0)


if __name__ == "__main__":
    main()
