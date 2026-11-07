"""Runs a whole simulated company through scout: every bill, sign-in and installed app at once.

Usage: python -m evals.company
"""
import csv, pathlib, tempfile
from overruled import importer, law

SOURCE = pathlib.Path(__file__).parent.parent / "imports" / "benchmark"


def rows(name: str) -> int:
    with (SOURCE / name).open(newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def run() -> dict:
    real_cases = law.CASES
    with tempfile.TemporaryDirectory() as d:
        law.CASES = pathlib.Path(d)
        try:
            result = importer.run(SOURCE)
            due, passed = importer.docket(result, set())
            spend = sum(law.compute_facts(r["slug"])["renewal_as_written"] for r in due)
        finally:
            law.CASES = real_cases
    return {"renewals": rows("bills.csv"), "signins": rows("signins.csv"), "installs": rows("software_inventory.csv"),
            "trials": len(due), "spend": spend, "saving": sum(r["saving"] for r in due), "held": len(result["skipped"]),
            "passed": len(passed), "overlaps": len(result["overlaps"])}


if __name__ == "__main__":
    r = run()
    print(f"{r['renewals']} renewals, {r['signins']:,} sign-in records, {r['installs']:,} installed apps")
    print(f"{r['trials']} sent to trial: ${r['spend']:,} as written, ${r['saving']:,} calculated saving")
    print(f"{r['held']} stopped for a person, {r['passed']} not worth a trial, {r['overlaps']} overlapping tools")
