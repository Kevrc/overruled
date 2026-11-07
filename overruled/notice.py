"""Drafts what a ruling needs next. Templates, not AI: a notice to a vendor must say exactly what was ruled."""
import csv, datetime, io

from overruled import law

REMINDERS = (14, 7, 1, -1)  # days before the deadline, and -1 for the day after it passes


def draft(case: dict, facts: dict, ruling: str, slug: str) -> str:
    money = lambda n: f"${n:,.0f}"
    docs = law.evidence(slug)
    source = law.cite(docs, case["notice_quote"]) if case.get("notice_quote") else None
    action = (f"reduce our subscription from {facts['seats']} to {facts['recommended_seats']} seats"
              if ruling == "condition" else "not renew this subscription")
    outcome = f" The renewal fee becomes {money(facts['right_sized_cost'])}." if ruling == "condition" else ""
    return (f"To: {case.get('vendor', 'the vendor')}\nSubject: Notice regarding {case['name']}\n\n"
            f"This is written notice that we will {action}, effective at the renewal on {facts['renewal_date']}.{outcome}\n"
            f"Under the agreement, notice is due by {facts['notice_deadline']}"
            + (f" (\"{case['notice_quote']}\", {source}).\n" if source else ".\n")
            + "Please confirm in writing.\n")


def calendar(case: dict, facts: dict) -> bytes:
    day = facts["notice_deadline"].replace("-", "")
    end = (datetime.date.fromisoformat(facts["notice_deadline"]) + datetime.timedelta(days=1)).strftime("%Y%m%d")
    stamp = law.case_today(case).strftime("%Y%m%dT000000Z")
    return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Overruled//Court//EN", "BEGIN:VEVENT",
                        f"UID:{day}-{law_slug(case)}@overruled.local", f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{day}", f"DTEND;VALUE=DATE:{end}",
                        f"SUMMARY:Last day to send notice: {case['name']}", "END:VEVENT", "END:VCALENDAR", ""]).encode()


def release_list(slug: str, facts: dict, today: datetime.date) -> tuple[bytes, int, int]:
    """The idle seats to free after a conditional ruling, longest idle first. Returns the CSV, how many it names, and how many it can't."""
    with (law.CASES / slug / "usage.csv").open() as f:
        idle = [r for r in csv.DictReader(f) if not law.is_active(r["last_active"], today)]
    release = facts["seats"] - facts["recommended_seats"]
    names = sorted(idle, key=lambda r: r["last_active"])[:release]  # blank means no activity, so it sorts first
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["user", "last_active"])
    w.writerows([law.csv_safe(r["user"]), r["last_active"] or "never"] for r in names)
    return out.getvalue().encode(), len(names), release - len(names)


def report(cases: dict[str, dict], ledger: list[dict], followups: dict) -> str:
    """A summary for finance. `cases` maps each slug to its facts. Code only: every figure comes from the files and the ledger."""
    money = lambda n: f"${n:,.0f}"
    ruled, sent = {}, set()
    for e in ledger:  # in order, so a later ruling replaces an earlier one and needs its own notice
        if e.get("event") == "notice_sent":
            sent.add(e["case"])
        elif "ruling" in e:
            ruled[e["case"]] = e
            sent.discard(e["case"])
    waiting = {s: f for s, f in cases.items() if s not in ruled}
    upcoming = [f for f in waiting.values() if f["notice_open"] and f["days_to_notice"] <= 90]
    missed = [f for f in waiting.values() if not f["notice_open"]]
    saved = sum(e["saved"] for e in ruled.values())
    confirmed = sum(e["saved"] for s, e in ruled.items() if s in sent)
    return f"""📊 **Scout.** Renewal summary.

| | |
|---|---|
| Renewals with notice due in 90 days | {len(upcoming)} |
| Their cost as written | {money(sum(f['renewal_as_written'] for f in upcoming))} |
| Calculated saving still available | {money(sum(f['calculated_saving'] for f in upcoming))} |
| Notice dates missed with no ruling | {len(missed)}, {money(sum(f['missed_saving'] for f in missed))} lost this term |
| Decisions made | {len(ruled)} |
| Saving decided | {money(saved)} |
| Saving with the notice confirmed | {money(confirmed)} |
| Notices waiting for confirmation | {len(followups)} |

Savings are calculated, not guaranteed. A saving is only real once the vendor accepts the notice."""


def passed_reminders(deadline: str, today: datetime.date) -> list[int]:
    days = (datetime.date.fromisoformat(deadline) - today).days
    return [m for m in REMINDERS if days <= m]


def next_reminder(deadline: str, reminded: list[int], today: datetime.date) -> int | None:
    """The most urgent reminder due now and not sent yet."""
    due = [m for m in passed_reminders(deadline, today) if m not in reminded]
    return min(due) if due else None


def law_slug(case: dict) -> str:
    return case["keywords"][0]
