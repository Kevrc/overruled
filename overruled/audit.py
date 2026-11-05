"""Append-only ruling ledger. Each entry carries the hash of the one before it, so edits show up."""
import hashlib, json, sys

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


if __name__ == "__main__":
    ok, message = verify()
    print(message)
    sys.exit(0 if ok else 1)
