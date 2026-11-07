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
    c.bot = lambda name: chat
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
