"""Append-only ruling ledger. Each entry carries the hash of the one before it, so edits show up."""
import csv, hashlib, io, json, sys

from overruled import law
from overruled.client import STATE

LEDGER = STATE / "ledger.jsonl"
GENESIS = "0" * 64


def entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def read() -> list[dict]:
    return [json.loads(line) for line in LEDGER.read_text().splitlines()] if LEDGER.exists() else []


def append(record: dict) -> dict:
    rows = read()
    entry = {**record, "prev": rows[-1]["hash"] if rows else GENESIS}
    entry["hash"] = entry_hash(entry)
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify(rows: list[dict] | None = None) -> tuple[bool, str]:
    rows = read() if rows is None else rows
    prev = GENESIS
    for n, entry in enumerate(rows, 1):
        if entry["prev"] != prev or entry["hash"] != entry_hash(entry):
            return False, f"Entry {n} ({entry.get('case')}) does not match its hash."
        prev = entry["hash"]
    return True, f"{len(rows)} rulings verified."


def decisions_csv(rows: list[dict]) -> bytes:
    """One line per ruling, with its notice confirmation, for people who don't use the chat."""
    fields = ["date", "case", "name", "requester", "ruled_by", "ruling", "jury", "asked", "saved", "notice_deadline", "evidence_sha256", "hash"]
    rulings, last = [], {}
    for e in rows:
        if e.get("event") == "notice_sent":
            if e["case"] in last:
                last[e["case"]] |= {"notice_sent_on": e["date"], "notice_confirmed_by": e["by"]}
        elif "ruling" in e:
            last[e["case"]] = {k: e.get(k, "") for k in fields}
            rulings.append(last[e["case"]])
    out = io.StringIO()
    w = csv.DictWriter(out, [*fields, "notice_sent_on", "notice_confirmed_by"])
    w.writeheader()
    w.writerows({k: law.csv_safe(v) for k, v in r.items()} for r in rulings)
    return out.getvalue().encode()


if __name__ == "__main__":
    ok, message = verify()
    print(message)
    sys.exit(0 if ok else 1)
