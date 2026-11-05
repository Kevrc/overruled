"""Scores scout and the clerk's calculations on the Harborline traps. No model involved. Usage: python -m evals.benchmark"""
import pathlib, sys, tempfile
import yaml
from overruled import importer, law

IMPORTS = pathlib.Path(__file__).parent.parent / "imports"


def score(source: pathlib.Path = IMPORTS / "benchmark") -> list[dict]:
    expected = yaml.safe_load((source / "expected.yaml").read_text())
    real_cases = law.CASES
    with tempfile.TemporaryDirectory() as d:
        law.CASES = pathlib.Path(d)
        result = importer.run(source)
        due, passed = importer.docket(result, set())
        found = {r["slug"]: ("due", "") for r in due} | {r["slug"]: ("passed", r["why"]) for r in passed}
        found |= {importer.slugify(a): ("skipped", w) for a, w in result["skipped"]}
        overlaps = {s for group in result.get("overlaps", []) for s in group}
        rows = []
        for slug, want in expected.items():
            status, why = found.get(slug, ("missing", ""))
            problems = []
            if status != want["status"]:
                problems.append(f"expected {want['status']}, got {status} {why}".strip())
            elif want.get("why") and want["why"] not in why.lower():
                problems.append(f"expected a reason about {want['why']}, got: {why}")
            if status in ("due", "passed") and status == want["status"]:
                f = law.compute_facts(slug)
                if "uplift" in want and f["uplift_percent"] != want["uplift"]:
                    problems.append(f"uplift {f['uplift_percent']}, expected {want['uplift']}")
                if "notice" in want and f["notice_days"] != want["notice"]:
                    problems.append(f"notice {f['notice_days']}, expected {want['notice']}")
            if want.get("overlap") and slug not in overlaps:
                problems.append("overlap not reported")
            rows.append({"slug": slug, "trap": want.get("trap", "ordinary renewal"), "problems": problems})
    law.CASES = real_cases
    return rows


if __name__ == "__main__":
    rows = score(IMPORTS / sys.argv[1]) if len(sys.argv) > 1 else score()
    bad = [r for r in rows if r["problems"]]
    print(f"{len(rows) - len(bad)} of {len(rows)} renewals handled correctly")
    for r in bad:
        print(f"  {r['slug']} ({r['trap']}): {'; '.join(r['problems'])}")
    sys.exit(0)
