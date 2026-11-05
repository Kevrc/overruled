"""Scores the clerk on hand-labelled claims. No model involved. Usage: python -m evals.clerk_eval"""
import pathlib, yaml
from overruled import law

data = yaml.safe_load((pathlib.Path(__file__).parent / "claims.yaml").read_text())
docs, facts = law.evidence("nimbusly"), law.compute_facts("nimbusly")


def score() -> dict:
    wrong_strikes = [c for c in data["supported"] if law.audit(c, docs, facts)[1]]
    missed = [c for c in data["fabricated"] if not law.audit(c, docs, facts)[1]]
    return {"supported": len(data["supported"]), "fabricated": len(data["fabricated"]), "wrong_strikes": wrong_strikes, "missed": missed}


if __name__ == "__main__":
    r = score()
    print(f"Fabricated claims caught: {r['fabricated'] - len(r['missed'])} of {r['fabricated']}")
    print(f"Supported claims kept: {r['supported'] - len(r['wrong_strikes'])} of {r['supported']}")
    for c in r["missed"]:
        print("  MISSED:", c)
    for c in r["wrong_strikes"]:
        print("  WRONG STRIKE:", c)
