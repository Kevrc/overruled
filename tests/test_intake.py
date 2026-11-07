"""Scout's chat intake with real file formats. No server needed: the chat is faked."""
import asyncio, datetime, pathlib
import pytest

from overruled import court, law

CONTRACT = pathlib.Path(__file__).parent / "fixtures" / "contract.pdf"


class Chat:
    """Stands in for scout's connection: serves uploads and records what it says."""
    id = "scout"

    def __init__(self, files):
        self.files, self.said, self.http = files, [], self

    async def get(self, url, params):
        self.content = self.files[params["mxc"]]
        return self

    def raise_for_status(self):
        pass

    async def say(self, room, text):
        self.said.append(text)


def intake(chat, renewal):
    c = object.__new__(court.Court)
    c.room, c.intakes, c.bot = "room", {}, lambda name: chat
    message = {"sender_name": "alex", "body": f'@scout intake app="Zephyrdesk" renewal={renewal}',
               "attachments": [{"mxc": name, "filename": name} for name in chat.files]}
    asyncio.run(c.intake(message))
    return c


@pytest.fixture
def renewal(tmp_path, monkeypatch):
    monkeypatch.setattr(law, "CASES", tmp_path)
    return (datetime.date.today() + datetime.timedelta(days=120)).isoformat()


def test_a_pdf_and_an_okta_export_go_through_on_the_real_date(renewal):
    day = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    rows = "".join(f"U{i},u{i}@x.co,u{i},4,x,{day}T15:04:05.000Z\n" for i in range(21))
    okta = "Person,Login,Application username,Logins,Login Date,Login Date_ISO8601\n" + rows
    chat = Chat({"contract.pdf": CONTRACT.read_bytes(), "okta.csv": okta.encode()})
    c = intake(chat, renewal)
    assert "zephyrdesk" in c.intakes
    assert "| 21 |" in chat.said[0] and "Okta Application Usage" in chat.said[0] and "must cover the last 90 days" in chat.said[0]
    f = law.compute_facts("zephyrdesk")
    assert (f["seats"], f["active_seats"], f["uplift_percent"], f["notice_days"]) == (50, 21, 8, 45)
    assert f["days_to_notice"] == 75


def test_a_scan_is_refused_and_opens_nothing(renewal):
    chat = Chat({"scan.pdf": b"not a pdf", "s.csv": b"user,last_login\n"})
    c = intake(chat, renewal)
    assert "can't take this file" in chat.said[0] and not c.intakes and not (law.CASES / "zephyrdesk").exists()
