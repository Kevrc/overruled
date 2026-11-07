"""What happens after a ruling: the seats to release and the notice follow-up. The chat is faked."""
import asyncio, csv, datetime, io, types
import pytest

from overruled import audit, court, law, notice

DAY = datetime.date(2026, 11, 4)


class Chat:
    id = "paralegal"

    def __init__(self):
        self.said, self.files, self.http = [], {}, self

    async def say(self, room, text):
        self.said.append(text)

    async def op(self, operation, **args):
        return {}

    async def post(self, url, files, data):
        name, content, _ = files["file"]
        self.files[name] = (content, data["caption"])
        return types.SimpleNamespace(status_code=200)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "LEDGER", tmp_path / "ledger.jsonl")
    c, chat = object.__new__(court.Court), Chat()
    c.room, c.queue, c.trial, c.agents = "room", [], None, {"gavel": chat}
    c.followups_file, c.bot = tmp_path / "followups.json", lambda name: chat
    return c, chat


def rule(c, ruling):
    facts = law.compute_facts("pipewave-crm")
    t = types.SimpleNamespace(slug="pipewave-crm", name="Pipewave CRM renewal", facts=facts)
    c.closed = {"trial": t, "ruling": ruling, "person": "cfo"}
    asyncio.run(c.prepare_notice())
    return facts


def test_release_list_names_only_the_seats_to_free_longest_idle_first(setup):
    c, chat = setup
    f = rule(c, "condition")
    data, caption = chat.files["seats-to-release-pipewave-crm.csv"]
    rows = list(csv.DictReader(io.StringIO(data.decode())))
    assert len(rows) == f["seats"] - f["recommended_seats"] or "doesn't name" in caption
    assert [r["last_active"] for r in rows] == sorted(r["last_active"] for r in rows)
    assert all(not law.is_active(r["last_active"], DAY) for r in rows)
    assert "Nothing was removed" in caption


def test_release_list_says_how_many_seats_it_cannot_name(tmp_path, monkeypatch):
    monkeypatch.setattr(law, "CASES", tmp_path)
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "usage.csv").write_text("user,last_active\n=cmd,\nb,2026-10-20\n")
    data, named, unnamed = notice.release_list("x", {"seats": 10, "recommended_seats": 2}, DAY)
    assert (named, unnamed) == (1, 7) and "'=cmd,never" in data.decode()


def test_a_rejected_renewal_has_no_seat_list(setup):
    c, chat = setup
    rule(c, "reject")
    assert not any(name.startswith("seats-to-release") for name in chat.files)


def test_each_reminder_comes_once_and_late_cases_skip_to_the_urgent_one():
    deadline = "2026-12-01"
    assert notice.next_reminder(deadline, [], datetime.date(2026, 11, 1)) is None
    assert notice.next_reminder(deadline, [], datetime.date(2026, 11, 17)) == 14
    assert notice.next_reminder(deadline, [14], datetime.date(2026, 11, 17)) is None
    assert notice.next_reminder(deadline, [14], datetime.date(2026, 11, 30)) == 1
    assert notice.next_reminder(deadline, [14, 7, 1], datetime.date(2026, 12, 2)) == -1
    assert notice.next_reminder(deadline, [14, 7, 1, -1], datetime.date(2026, 12, 9)) is None


def test_reminders_stop_once_a_person_confirms_and_the_ledger_records_it(setup):
    c, chat = setup
    rule(c, "condition")
    keyword = law.load_case("pipewave-crm")["keywords"][0]
    followups = c.followups()
    followups["pipewave-crm"] |= {"reminded": [], "deadline": "2026-11-10"}  # six days away, so one reminder is due
    c.save_followups(followups)
    before = len(chat.said)
    asyncio.run(c.check_followups())
    asyncio.run(c.check_followups())
    assert len(chat.said) == before + 1 and "@cfo" in chat.said[-1]
    asyncio.run(c.paralegal("room", {"sender_name": "maya", "body": f"@paralegal sent {keyword}"}))
    entry = audit.read()[-1]
    assert (entry["event"], entry["by"], entry["case"]) == ("notice_sent", "maya", "pipewave-crm") and audit.verify()[0]
    assert "on time" in chat.said[-1] and not c.followups()


def test_a_bot_cannot_confirm_a_notice(setup):
    c, chat = setup
    rule(c, "condition")
    asyncio.run(c.paralegal("room", {"sender_name": "gavel", "body": "@paralegal sent pipewave"}))
    assert c.followups() and not audit.read()


def test_an_unknown_name_confirms_nothing(setup):
    c, chat = setup
    rule(c, "condition")
    asyncio.run(c.paralegal("room", {"sender_name": "cfo", "body": "@paralegal sent nothing-here"}))
    assert c.followups() and "No notice is waiting" in chat.said[-1]


def test_a_new_ruling_replaces_the_follow_up(setup, tmp_path):
    c, chat = setup
    rule(c, "condition")
    assert c.followups()["pipewave-crm"]["owner"] == "cfo"
    c.saved_file, c.tried_file = tmp_path / "saved", tmp_path / "tried"
    async def log_ruling(line, total): pass
    async def next_case(): pass
    c.log_ruling, c.next_case = log_ruling, next_case
    f = law.compute_facts("pipewave-crm")
    t = types.SimpleNamespace(slug="pipewave-crm", name="x", facts=f, requester="alex", verdict="approve", votes=[], models=[], docs={}, record=[], strikes=0, cost=0, transcript=[])
    asyncio.run(c.rule(t, "approve", "cfo"))
    assert not c.followups()


def facts(**extra):
    return {"notice_open": True, "days_to_notice": 30, "renewal_as_written": 1000, "calculated_saving": 400, "missed_saving": 0, **extra}


def test_report_counts_only_what_is_still_open_and_real():
    cases = {"a": facts(), "b": facts(days_to_notice=200), "c": facts(notice_open=False, missed_saving=300), "d": facts(), "e": facts()}
    ledger = [{"case": "d", "ruling": "condition", "saved": 500}, {"case": "d", "event": "notice_sent"}, {"case": "e", "ruling": "reject", "saved": 700}]
    text = notice.report(cases, ledger, {"e": {}})
    assert "90 days | 1 |" in text and "as written | $1,000 |" in text and "available | $400 |" in text
    assert "1, $300 lost" in text and "decided | $1,200 |" in text and "confirmed | $500 |" in text and "confirmation | 1 |" in text


def test_a_new_ruling_needs_its_own_confirmed_notice():
    ledger = [{"case": "d", "ruling": "condition", "saved": 500}, {"case": "d", "event": "notice_sent"}, {"case": "d", "ruling": "reject", "saved": 900}]
    text = notice.report({"d": facts()}, ledger, {})
    assert "decided | $900 |" in text and "confirmed | $0 |" in text and "Decisions made | 1 |" in text


def test_scout_answers_report(setup, tmp_path, monkeypatch):
    c, chat = setup
    c.agents = {"gavel": chat}
    asyncio.run(c.scout("room", {"sender_name": "cfo", "body": "@scout report"}))
    assert "Renewal summary" in chat.said[-1]


def test_export_has_one_line_per_ruling_with_its_confirmation():
    ledger = [{"case": "a", "date": "2026-11-01", "ruling": "condition", "ruled_by": "=cfo", "saved": 5, "transcript": ["x"]},
              {"case": "a", "date": "2026-11-02", "event": "notice_sent", "by": "maya"}, {"case": "a", "date": "2026-11-03", "ruling": "reject", "saved": 9}]
    rows = list(csv.DictReader(io.StringIO(audit.decisions_csv(ledger).decode())))
    assert [r["ruling"] for r in rows] == ["condition", "reject"] and rows[0]["ruled_by"] == "'=cfo"
    assert rows[0]["notice_confirmed_by"] == "maya" and not rows[1]["notice_confirmed_by"] and "transcript" not in rows[0]


def test_a_person_can_ask_for_the_export(setup):
    c, chat = setup
    audit.append({"case": "a", "date": "2026-11-01", "ruling": "reject", "saved": 9})
    asyncio.run(c.paralegal("room", {"sender_name": "cfo", "body": "@paralegal export"}))
    data, caption = chat.files["decisions.csv"]
    assert b"reject" in data and "1 rulings verified" in caption
