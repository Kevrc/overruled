"""Drafts what a ruling needs next. Templates, not AI: a notice to a vendor must say exactly what was ruled."""
import datetime

from overruled import law


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
    stamp = law.TODAY.strftime("%Y%m%dT000000Z")
    return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Overruled//Court//EN", "BEGIN:VEVENT",
                        f"UID:{day}-{law_slug(case)}@overruled.local", f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{day}", f"DTEND;VALUE=DATE:{end}",
                        f"SUMMARY:Last day to send notice: {case['name']}", "END:VEVENT", "END:VCALENDAR", ""]).encode()


def law_slug(case: dict) -> str:
    return case["keywords"][0]
