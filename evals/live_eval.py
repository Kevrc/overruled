"""Runs real prosecution and defense speeches through the clerk. Usage: python -m evals.live_eval [rounds]"""
import asyncio, json, pathlib, re, sys

from overruled import court, law
from overruled.llm import ask

OUT = pathlib.Path(__file__).parent / "live_results.json"
CASES = ["nimbusly", "pipewave-crm", "slidehive", "helpline"]


async def speech(role, slug, gate):
    c = law.load_case(slug)
    t = court.Trial(slug, c["name"], c["requested_by"], law.compute_facts(slug), law.evidence(slug))
    system = f"{court.DEFENSE}\n{court.ADVOCATE}" if role == "defense" else f"{court.PROSECUTION}\n{court.LAW}"
    async with gate:
        reply, cost = await ask(system, f"{court.briefing(t)}\n\nRECORD SO FAR:\n(nothing yet)", "sonnet", "")
    kept, struck = law.audit(reply, court.Court.court_evidence(t), t.facts)
    return {"case": slug, "role": role, "speech": reply, "kept": kept, "struck": struck, "cost": cost}


async def main(rounds):
    gate = asyncio.Semaphore(4)
    jobs = [speech(r, CASES[i % len(CASES)], gate) for i in range(rounds) for r in ("defense", "prosecution")]
    rows = await asyncio.gather(*jobs)
    OUT.write_text(json.dumps(rows, indent=1))
    d = [r for r in rows if r["role"] == "defense"]; p = [r for r in rows if r["role"] == "prosecution"]
    print(f"defense speeches with a strike: {sum(bool(r['struck']) for r in d)} of {len(d)}")
    print(f"prosecution speeches with a strike: {sum(bool(r['struck']) for r in p)} of {len(p)}")
    print("cost", round(sum(r["cost"] for r in rows), 2))


asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20))
