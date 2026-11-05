"""The clerk's rules. No AI here: everything that reaches the jury passes through this file."""
import csv, datetime, hashlib, json, math, pathlib, re
import yaml

ROOT = pathlib.Path(__file__).parent.parent
CASES = ROOT / "cases"
EVIDENCE_FILES = ("contract.md", "request.md", "usage.csv")
ACTIVE_DAYS = 90
TODAY = datetime.date(2026, 11, 4)  # shortcut: fixed so the sample data stays reproducible, use date.today() with live data
NUMBER = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s?(?:%|k\b|K\b|percent\b|million\b)?")
QUOTE = re.compile(r"[\"“]([^\"”]+)[\"”]")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
MIN_QUOTE = 8  # shorter quotes like "48%" are emphasis, and their numbers are checked anyway
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: (i + 2) * 10 for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9}
NUMBER_WORD = "|".join([*UNITS, *TENS, "hundred", *SCALES])
WORD_NUMBER = re.compile(rf"\b(?:(half) an? |an? )?((?:{NUMBER_WORD})(?:(?:[ -]| and )(?:{NUMBER_WORD}))*)\b(\s+(?:times|percent|x)\b)?", re.I)
SMALL = 13  # small words like "three jurors" are ordinary speech, unless they claim a multiple or a percentage


def find_case(text: str) -> str | None:
    lower = text.lower()
    for path in sorted(CASES.iterdir()):
        if (path / "case.yaml").exists() and any(k in lower for k in load_case(path.name)["keywords"]):
            return path.name
    return None


def load_case(slug: str) -> dict:
    return yaml.safe_load((CASES / slug / "case.yaml").read_text())


def evidence(slug: str) -> dict[str, str]:
    return {name: (CASES / slug / name).read_text() for name in EVIDENCE_FILES}


def squeeze(text: str) -> str:
    return " ".join(text.lower().split())


def compute_facts(slug: str, today: datetime.date = TODAY) -> dict:
    """The money figures of a case, calculated from its files."""
    case, docs = load_case(slug), evidence(slug)
    for key in ("uplift_quote", "notice_quote"):
        if case[key] and squeeze(case[key]) not in squeeze(docs["contract.md"]):
            raise ValueError(f"{key} is not in the contract")
    renewal = datetime.date.fromisoformat(str(case["renewal_date"]))
    notice = re.search(r"\((\d+)\)|(\d+) days", case["notice_quote"] or "")
    notice_days = case.get("notice_days", int(notice.group(1) or notice.group(2)) if notice else 0)
    deadline = renewal - datetime.timedelta(days=notice_days)
    rows = list(csv.DictReader((CASES / slug / "usage.csv").open()))
    cutoff = today - datetime.timedelta(days=ACTIVE_DAYS)
    active = sum(datetime.date.fromisoformat(r["last_active"]) >= cutoff for r in rows)
    seats, price = case["seats"], case["price_per_seat"]
    uplift = 1 + case["uplift_percent"] / 100
    recommended = min(seats, math.ceil(active * (1 + case["buffer_percent"] / 100)))
    as_written = round(seats * price * uplift)
    right_sized = round(recommended * price * uplift)
    open_window = deadline >= today
    # A saving nobody can claim this term is not a saving: the contract already renews as written.
    saving = as_written - right_sized if open_window else 0
    return {"seats": seats, "price_per_seat": price, "active_seats": active, "inactive_seats": seats - active,
            "adoption_percent": round(100 * active / seats), "uplift_percent": case["uplift_percent"],
            "current_cost": seats * price, "renewal_as_written": as_written, "recommended_seats": recommended,
            "right_sized_cost": right_sized, "calculated_saving": saving, "missed_saving": as_written - right_sized - saving,
            "notice_days": notice_days, "days_to_notice": (deadline - today).days, "renewal_date": renewal.isoformat(),
            "notice_deadline": deadline.isoformat(), "notice_open": open_window}


def cite(docs: dict[str, str], quote: str) -> str | None:
    """Where a quote lives, so a reader can open the file and check it."""
    want = squeeze(quote).rstrip(".,;:")
    for name, text in docs.items():
        for number, line in enumerate(text.splitlines(), 1):
            if want and want in squeeze(line):
                return f"{name} line {number}"
    return None


def fingerprint(docs: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(docs, sort_keys=True).encode()).hexdigest()


def approver_for(amount: float, policy: dict) -> dict | None:
    """The delegated approver for this amount, or None when only the final approver may rule."""
    for rule in sorted(policy["approvals"], key=lambda r: r["up_to"]):
        if amount <= rule["up_to"]:
            return rule
    return None


def norm_number(token: str) -> float | None:
    t = token.lower().replace("$", "").replace(",", "").strip()
    scale = 1.0
    if t.endswith("k"):
        scale, t = 1000.0, t[:-1]
    elif t.endswith("million"):
        scale, t = 1_000_000.0, t[:-7]
    t = t.replace("percent", "").replace("%", "").strip()
    try:
        return float(t) * scale
    except ValueError:
        return None


def word_numbers(sentence: str) -> list[tuple[str, float]]:
    """Finds figures written in words, so "sixty thousand dollars" can't slip past the digit check."""
    found = []
    for m in WORD_NUMBER.finditer(sentence):
        total, current = 0.0, 0.0
        for w in re.findall(r"[a-z]+", m.group(2).lower()):
            if w in UNITS:
                current += UNITS[w]
            elif w in TENS:
                current += TENS[w]
            elif w == "hundred":
                current = max(current, 1) * 100
            elif w in SCALES:
                total += max(current, 1) * SCALES[w]
                current = 0
        value = (total + current) * (.5 if m.group(1) else 1)
        if value >= SMALL or m.group(3):
            found.append((m.group(0).strip(), value))
    return found


def known_numbers(docs: dict[str, str], facts: dict) -> set[float]:
    text = docs["contract.md"] + docs["request.md"]
    found = {norm_number(m) for m in NUMBER.findall(text)} | {float(ACTIVE_DAYS)}
    found |= {float(v) for v in facts.values() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return found - {None}


def audit(speech: str, docs: dict[str, str], facts: dict) -> tuple[str, list[dict]]:
    """Returns the speech as it enters the record, and each sentence the clerk struck with why."""
    corpus = squeeze("\n".join(docs.values()))
    allowed = known_numbers(docs, facts)
    kept, struck = [], []
    for sentence in filter(None, (s.strip() for s in SENTENCE.split(speech))):
        reason = None
        for quote in QUOTE.findall(sentence):
            if len(quote) >= MIN_QUOTE and squeeze(quote).rstrip(".,;:") not in corpus:
                reason = "that quote is not in the evidence"
        for token in NUMBER.findall(ISO_DATE.sub("", sentence)):
            if norm_number(token) not in allowed:
                reason = f"{token.strip()} is not in evidence"
        for text, value in word_numbers(sentence):
            multiple = re.search(r"\b(times|x)$", text, re.I)
            if multiple or value not in allowed:
                reason = f"{text} is not in evidence"
        if reason:
            struck.append({"sentence": sentence, "reason": reason})
        else:
            kept.append(sentence)
    return " ".join(kept), struck


def tally(votes: dict[str, dict]) -> str:
    counts = {"approve": 0, "condition": 0, "reject": 0}
    for v in votes.values():
        counts[v["vote"]] += 1
    top = max(counts.values())
    leaders = [k for k, n in counts.items() if n == top]
    return leaders[0] if len(leaders) == 1 else "hung jury"
