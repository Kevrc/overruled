"""Turns exports from inventory, identity and accounting tools into trial cases.

Usage: python -m overruled.importer imports/sample

The folder import uses this project's own sample format. Chat intake also reads the real sign-in exports listed in EXPORTS.
shortcut: reads files only, a live version would call each vendor's API with the same mapping.
"""
import csv, datetime, io, pathlib, re, sys
import pypdf, pypdf.errors, yaml

from overruled import law, reader

COLUMNS = {"bills.csv": {"app", "vendor", "seats", "price_per_seat", "renewal_date", "contract_file", "owner_team"},
           "signins.csv": {"app", "user", "last_login"},
           "software_inventory.csv": {"device", "name", "publisher", "version"}}
NOTICE = re.compile(r"[^.\n]*written notice[^.\n]*", re.I)
SENTENCE = re.compile(r"(?<=\.)\s+|\n+")
INDEXED = re.compile(r"\b(cpi|index|inflation)\b", re.I)
SYSTEM_PUBLISHERS = {"microsoft", "apple"}
BUFFER_PERCENT = 5
SEATS = re.compile(r"(\d[\d,]*)\s+(?:[\w-]+\s+){0,3}seats?\s+at\s+\$(\d[\d,]*(?:\.\d+)?)(\s+per\s+seat\s+per\s+month)?", re.I)
SEATS_ES = re.compile(r"(\d[\d.,]*)\s+(?:[\w-]+\s+){0,3}(?:licencias?|usuarios?|puestos?)(?:\s+[\w-]+){0,2}\s+a\s+(?:USD\s?|US)?\$\s?(\d[\d.,]*)((?:\s+\w+){1,4}\s+(?:al|por)\s+mes|\s+mensual\w*)?", re.I)
# shortcut: only US dollars, because every total and notice is in dollars. A plain $ can still mean pesos, so a person confirms the price.
FOREIGN = re.compile(r"[€£]\s?\d|\d\s?(?:[€£]|(?:EUR|GBP|MXN|COP|PEN|CLP|ARS|BRL)\b)|\b(?:euros?|pesos|soles|reales)\b", re.I)
MIN_SIGNIN_COVERAGE = 0.5
RENEWAL_WINDOW_DAYS = 90
MIN_SAVING = 1000
MAX_PDF_PAGES = 300
# name: (user column, date column), checked against each vendor's documentation.
EXPORTS = {"Overruled": ("user", "last_login"),
           "Okta Application Usage": ("Login", "Login Date_ISO8601"),
           "Microsoft 365 Apps usage": ("User Principal Name", "Last Activity Date")}


def read(folder: pathlib.Path, name: str) -> list[dict]:
    with (folder / name).open(newline="") as f:
        reader = csv.DictReader(f)
        missing = COLUMNS[name] - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{name} is missing columns: {sorted(missing)}")
        return list(reader)


def spanish_number(text: str) -> float:
    """1.200,50 in Spanish is 1200.5, while the English pattern would read 1.2."""
    text = text.rstrip(".,")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?|\d+,\d{1,2}", text):
        return float(text.replace(".", "").replace(",", "."))
    return float(text.replace(",", ""))


def contract_terms(contract: str) -> tuple[int, float] | None:
    """Seats and yearly price per seat, when the contract states them."""
    es = SEATS_ES.search(contract)
    if es:
        price = spanish_number(es.group(2))
        return int(spanish_number(es.group(1))), price * 12 if es.group(3) else price
    m = SEATS.search(contract)
    if not m:
        return None
    price = float(m.group(2).replace(",", ""))
    return int(m.group(1).replace(",", "")), price * 12 if m.group(3) else price


def percent_in(sentence: str) -> float | None:
    digits = re.search(r"(\d+(?:\.\d+)?)\s?(?:%|percent)", sentence, re.I)
    if digits:
        return float(digits.group(1))
    words = [v for text, v in law.word_numbers(sentence) if text.lower().endswith("percent")]
    return words[0] if words else None


def read_uplift(contract: str) -> tuple[float, str]:
    """The increase that applies at renewal, or none. Raises rather than guess at an indexed price."""
    clauses = [s.strip() for s in SENTENCE.split(contract) if re.search(r"increase|uplift", s, re.I) and (percent_in(s) is not None or INDEXED.search(s))]
    if not clauses:
        return 0, ""
    clause = next((c for c in clauses if "renew" in c.lower()), clauses[0])
    if INDEXED.search(clause):
        raise ValueError("the price increase is tied to an index, so a person must read it")
    return percent_in(clause), clause


def read_notice(contract: str) -> tuple[int, str]:
    m = NOTICE.search(contract)
    if not m:
        return 0, ""
    clause = m.group(0).strip()
    number = re.search(r"\((\d+)\)|(\d+) days", clause)
    words = [v for text, v in law.word_numbers(clause)] + [v for w, v in law.UNITS.items() if re.search(rf"\b{w} days", clause, re.I)]
    days = int(number.group(1) or number.group(2)) if number else int(words[0]) if words else None
    if days is None:
        raise ValueError("the notice clause gives no number of days, so a person must read it")
    return days, clause


def slugify(app: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", app.lower()).strip("-")


def build_case(bill: dict, signins: list[dict], installs: int, contracts: pathlib.Path, target: pathlib.Path,
               live: bool = False, signed_in_only: bool = False) -> str:
    """Writes one case folder and returns its slug. Raises ValueError rather than guess."""
    app = bill["app"].strip()
    seats, price = int(bill["seats"]), float(bill["price_per_seat"])
    if seats <= 0 or price <= 0:
        raise ValueError("seats and price must be positive")
    # basename only: a bills file must not read outside the contracts folder
    contract_path = contracts / pathlib.Path(bill["contract_file"]).name
    if not contract_path.exists():
        raise ValueError(f"contract {contract_path.name} not found")
    # No sign-in data would read as zero use and invent a huge saving, so it stops the import.
    rows = [r for r in signins if r["app"].strip() == app]
    if not rows:
        raise ValueError("no sign-in data")
    datetime.date.fromisoformat(bill["renewal_date"])
    today = datetime.date.today() if live else law.TODAY
    active = sum(law.is_active(r["last_login"], today) for r in rows)
    if active > seats:
        raise ValueError(f"{active} active users but only {seats} seats, check the export")
    # Seats missing from a partial export would read as idle and invent a saving.
    if not signed_in_only and len(rows) < seats * MIN_SIGNIN_COVERAGE:
        raise ValueError(f"sign-ins cover only {len(rows)} of {seats} seats")

    contract = contract_path.read_text()
    if FOREIGN.search(contract):
        raise ValueError("the contract isn't priced in US dollars, and Overruled only calculates in dollars, so a person must read it")
    terms = contract_terms(contract)
    if terms and terms != (seats, price):
        raise ValueError(f"the contract says {terms[0]} seats at ${terms[1]:g} a year, but the bill says {seats} at ${price:g}")
    if not NOTICE.search(contract) or reader.UNCLEAR.search(contract):
        uplift, uplift_quote, notice_days, notice_quote = reader.read(contract)
    else:
        uplift, uplift_quote = read_uplift(contract)
        notice_days, notice_quote = read_notice(contract)
    slug = slugify(app)
    folder = target / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "contract.md").write_text(contract)
    with (folder / "usage.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["user", "last_active"])
        w.writerows([r["user"], r["last_login"]] for r in rows)
    (folder / "request.md").write_text(
        f"# Renewal of {app}\n\nImported from company systems. {bill['owner_team']} owns this tool, billed by {bill['vendor']}.\n"
        f"It renews on {bill['renewal_date']}" + (f" and is installed on {installs} devices.\n" if installs else ".\n"))
    (folder / "case.yaml").write_text(yaml.safe_dump({
        "name": f"{app} renewal", "vendor": bill["vendor"], "renewal_date": bill["renewal_date"], "keywords": [slug.split("-")[0]], "requested_by": bill["owner_team"], "seats": seats,
        "price_per_seat": price, "uplift_percent": uplift, "buffer_percent": BUFFER_PERCENT,
        "uplift_quote": uplift_quote, "notice_quote": notice_quote, "notice_days": notice_days, "live": live}))
    return slug


def run(folder: pathlib.Path, target: pathlib.Path | None = None, live: bool = False) -> dict:
    target = target or law.CASES
    bills, signins = read(folder, "bills.csv"), read(folder, "signins.csv")
    inventory = read(folder, "software_inventory.csv")
    result = {"imported": [], "skipped": [], "unbilled": [], "overlaps": []}
    for bill in bills:
        app = bill["app"].strip()
        installs = len({i["device"] for i in inventory if i["name"].strip() == app})
        try:
            slug = build_case(bill, signins, installs, folder / "contracts", target, live)
            law.compute_facts(slug) if target == law.CASES else None
            result["imported"].append(slug)
        except (ValueError, KeyError) as e:
            result["skipped"].append((app, str(e)))
    categories: dict[str, list[str]] = {}
    for bill in bills:
        if bill.get("category", "").strip():
            categories.setdefault(bill["category"].strip(), []).append(slugify(bill["app"]))
    result["overlaps"] = [group for group in categories.values() if len(group) > 1]
    billed = {b["app"].strip() for b in bills}
    result["unbilled"] = sorted({i["name"].strip() for i in inventory
                                 if i["name"].strip() not in billed and i["publisher"].strip().lower() not in SYSTEM_PUBLISHERS})
    return result


def parse_intake(message: str, contract: str) -> dict:
    """Reads the fields a person typed, and fills seats and price from the contract when it states them."""
    # Slack turns straight quotes into curly ones.
    args = {k.lower(): (a or b) for k, a, b in re.findall(r'(\w+)=(?:"([^"]+)"|(\S+))', re.sub("[“”]", '"', message))}
    terms = contract_terms(contract)
    seats = args.get("seats") or (terms[0] if terms else None)
    price = args.get("price") or (terms[1] if terms else None)
    missing = [k for k, v in {"app": args.get("app"), "renewal": args.get("renewal"), "seats": seats, "price": price}.items() if not v]
    if missing:
        raise ValueError(f"I still need {', '.join(missing)}")
    return {"app": args["app"], "vendor": args.get("vendor", args["app"]), "seats": seats, "price_per_seat": price,
            "renewal_date": args["renewal"], "contract_file": "contract.md", "owner_team": args.get("team", "the requester")}


def contract_text(filename: str, data: bytes) -> str:
    """The text of an uploaded contract. Raises rather than pass on a contract nobody can check."""
    if not filename.lower().endswith(".pdf"):
        return data.decode("utf-8-sig")
    try:
        pages = pypdf.PdfReader(io.BytesIO(data)).pages
        if len(pages) > MAX_PDF_PAGES:
            raise ValueError(f"the PDF has over {MAX_PDF_PAGES} pages")
        text = "\n".join(page.extract_text() or "" for page in pages)
    except pypdf.errors.PyPdfError as e:
        raise ValueError("the PDF can't be opened, it may be damaged or locked") from e
    text = "\n".join(line.rstrip() for line in text.splitlines())
    if not text.strip():
        raise ValueError("the PDF has no readable text, it may be a scan, so a person must read it")
    # shortcut: page headers and footers stay in the text, clauses split by one won't be found and go to a person.
    return re.sub(r"(?<![.:;!?\n])\n(?=\S)", " ", text)  # PDFs break lines mid-sentence, and clauses are read line by line


def read_signins(text: str, app: str) -> tuple[str, list[dict]]:
    """The export's name and its rows. Dates may be blank, which means no recorded activity."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    fields = set(reader.fieldnames or [])
    source = next((name for name, columns in EXPORTS.items() if set(columns) <= fields), None)
    if not source:
        raise ValueError("the sign-in file needs user and last_login columns, or a real export: " + ", ".join(list(EXPORTS)[1:]))
    user, date = EXPORTS[source]
    rows = list(reader)
    # A shorter report can't tell who was active in the whole window, so it could invent a saving.
    if "Report Period" in fields and any(int(r["Report Period"] or 0) < law.ACTIVE_DAYS for r in rows):
        raise ValueError(f"the report must cover at least {law.ACTIVE_DAYS} days")
    return source, [{"app": app, "user": r[user], "last_login": r[date].strip()[:10]} for r in rows]


def docket(result: dict, tried: set[str]) -> tuple[list[dict], list[dict]]:
    """Splits imported cases into those worth a trial now, biggest saving first, and the rest with why."""
    due, passed = [], []
    for slug in result["imported"]:
        case, f = law.load_case(slug), law.compute_facts(slug)
        days = f["days_to_notice"]  # the notice date is what can be missed, not the renewal itself
        row = {"slug": slug, "app": case["name"], "keyword": case["keywords"][0], "days": days, "saving": f["calculated_saving"],
               "active": f["active_seats"], "seats": f["seats"], "notice_deadline": f["notice_deadline"], "days_to_notice": f["days_to_notice"]}
        if slug in tried:
            passed.append({**row, "why": "already ruled"})
        elif not f["notice_open"]:
            passed.append({**row, "why": f"notice deadline missed, {'$' + format(f['missed_saving'], ',')} is gone for this term"})
        elif not 0 <= days <= RENEWAL_WINDOW_DAYS:
            passed.append({**row, "why": f"notice is due in {days} days"})
        elif f["calculated_saving"] < MIN_SAVING:
            passed.append({**row, "why": "saving too small for a trial"})
        else:
            due.append(row)
    return sorted(due, key=lambda r: -r["saving"]), passed


def main() -> None:
    r = run(pathlib.Path(sys.argv[1]))
    for slug in r["imported"]:
        f = law.compute_facts(slug)
        print(f"Ready for trial: {law.load_case(slug)['name']}. {f['active_seats']} of {f['seats']} seats active, ${f['calculated_saving']:,} calculated saving.")
    for app, why in r["skipped"]:
        print(f"Skipped {app}: {why}")
    for app in r["unbilled"]:
        print(f"Installed with no bill on file: {app}")


if __name__ == "__main__":
    main()
