from overruled import law

DOCS = law.evidence("nimbusly")
FACTS = law.compute_facts("nimbusly")


def test_facts_come_from_the_files():
    assert FACTS["active_seats"] == 58
    assert FACTS["adoption_percent"] == 48
    assert FACTS["renewal_as_written"] == 53760
    assert FACTS["recommended_seats"] == 61
    assert FACTS["right_sized_cost"] == 27328
    assert FACTS["calculated_saving"] == 26432


def test_healthy_tool_saves_little():
    f = law.compute_facts("helpline")
    assert f["recommended_seats"] == 40 and f["calculated_saving"] == 0


def test_a_case_with_a_quote_missing_from_the_contract_fails(tmp_path, monkeypatch):
    src = law.CASES / "helpline"
    dst = tmp_path / "helpline"
    dst.mkdir()
    for f in src.iterdir():
        dst.joinpath(f.name).write_text(f.read_text())
    dst.joinpath("contract.md").write_text("Nothing useful.")
    monkeypatch.setattr(law, "CASES", tmp_path)
    try:
        law.compute_facts("helpline")
        assert False
    except ValueError:
        pass


def test_real_number_survives():
    kept, struck = law.audit("Only 58 seats were active, and the renewal costs $53,760.", DOCS, FACTS)
    assert not struck and "$53,760" in kept


def test_invented_money_is_struck():
    kept, struck = law.audit("It works well. Nimbusly saves us $210,000 a year.", DOCS, FACTS)
    assert kept == "It works well."
    assert "$210,000" in struck[0]["reason"]


def test_invented_percentage_is_struck():
    _, struck = law.audit("Adoption is at 94%.", DOCS, FACTS)
    assert len(struck) == 1


def test_real_quote_survives_and_fake_quote_is_struck():
    good = 'The contract says "the Annual Fee shall increase by twelve percent (12%) on each Renewal Term".'
    assert not law.audit(good, DOCS, FACTS)[1]
    assert law.audit('The contract says "Customer may cancel at any time with no penalty".', DOCS, FACTS)[1]


def test_round_rewrites_of_figures_are_struck():
    assert law.audit("The renewal is about $54,000.", DOCS, FACTS)[1]


def test_votes():
    a, c, r = {"vote": "approve"}, {"vote": "condition"}, {"vote": "reject"}
    assert law.tally({"1": c, "2": c, "3": r}) == "condition"
    assert law.tally({"1": a, "2": c, "3": r}) == "hung jury"


def test_figures_in_words_are_struck():
    for claim in ("It saves two hundred thousand dollars a year.", "It is worth sixty thousand dollars.",
                  "It pays for itself ten times over.", "Losing it would cost half a million dollars.", "That is a hundred thousand dollars."):
        assert law.audit(claim, DOCS, FACTS)[1], claim


def test_ordinary_words_are_not_figures():
    for claim in ("The price goes up twelve percent at renewal.", "Notice is due sixty days before the term ends.",
                  "Three jurors agree with one of the two teams.", "The initial term is twelve months."):
        assert not law.audit(claim, DOCS, FACTS)[1], claim


def test_short_emphasis_quotes_do_not_break_the_next_quote():
    s = 'Adoption is "48%," and the contract says "the Annual Fee shall increase by twelve percent (12%) on each Renewal Term".'
    assert not law.audit(s, DOCS, FACTS)[1]


def test_notice_deadline_comes_from_the_contract():
    assert FACTS["notice_days"] == 60 and FACTS["notice_deadline"] == "2026-12-02" and FACTS["days_to_notice"] == 28


def test_quotes_are_cited_to_a_line():
    assert law.cite(DOCS, "the Annual Fee shall increase by twelve percent (12%)") == "contract.md line 12"
    assert law.cite(DOCS, "nothing like this exists") is None


def test_evidence_fingerprint_changes_with_the_evidence():
    assert law.fingerprint(DOCS) != law.fingerprint({**DOCS, "offer.md": "10% off"})


def test_approval_limits():
    p = {"approvals": [{"up_to": 15000, "approver": "maya"}]}
    assert law.approver_for(12000, p)["approver"] == "maya"
    assert law.approver_for(32400, p) is None


def test_ledger_detects_tampering(tmp_path, monkeypatch):
    from overruled import audit
    monkeypatch.setattr(audit, "LEDGER", tmp_path / "ledger.jsonl")
    audit.append({"case": "a", "saved": 100})
    audit.append({"case": "b", "saved": 200})
    assert audit.verify()[0]
    rows = audit.read()
    rows[0]["saved"] = 999999
    assert not audit.verify(rows)[0]


def test_notice_says_exactly_what_was_ruled():
    from overruled import notice
    case = law.load_case("nimbusly")
    cut = notice.draft(case, FACTS, "condition", "nimbusly")
    assert "reduce our subscription from 120 to 61 seats" in cut and "$27,328" in cut and "2026-12-02" in cut and "contract.md line 11" in cut
    assert "not renew" in notice.draft(case, FACTS, "reject", "nimbusly")
    ics = notice.calendar(case, FACTS).decode()
    assert "DTSTART;VALUE=DATE:20261202" in ics


def test_a_local_juror_falls_back_and_says_so(monkeypatch):
    import asyncio
    from overruled import llm
    monkeypatch.setattr(llm, "OFFLINE", False)
    async def down(*a):
        raise llm.httpx.ConnectError("refused")
    async def claude(system, prompt, model, offline):
        return "{}", 0.01
    monkeypatch.setattr(llm, "ask_local", down)
    monkeypatch.setattr(llm, "ask", claude)
    reply, cost, used = asyncio.run(llm.ask_juror("s", "p", "ollama:qwen3:4b", ""))
    assert reply == "{}" and used == "haiku (Ollama unavailable)"


def test_tables_become_lines_for_slack():
    from overruled.client import tables_to_lines
    text = "Intro\n\n| Juror | Vote | Why |\n|---|---|---|\n| jury-1 | **condition** | Too many seats. |\n\n| | |\n|---|---|\n| Asked to pay | $10 |\nEnd"
    assert tables_to_lines(text) == "Intro\n\n• Juror: Vote · Why\n• jury-1: **condition** · Too many seats.\n\n• Asked to pay: $10\nEnd"


def test_contract_reader_only_trusts_what_is_in_the_contract():
    import pytest
    from overruled import reader
    contract = "Fees rise 6% at each renewal.\nCustomer must notify the vendor not less than 45 days before the term ends."
    good = {"uplift_percent": 6, "uplift_quote": "Fees rise 6% at each renewal", "uplift_stated": True, "notice_days": 45,
            "notice_quote": "not less than 45 days before the term ends", "auto_renews": True, "can_reduce_seats": True}
    assert reader.verify(contract, good)[0] == 6 and reader.verify(contract, good)[2] == 45
    for change in ({"uplift_percent": 2}, {"notice_days": 10}, {"uplift_quote": "Fees rise 2% at each renewal"}, {"notice_quote": "made up"},
                   {"auto_renews": False}, {"can_reduce_seats": False}, {"uplift_percent": None}):
        with pytest.raises(ValueError):
            reader.verify(contract, good | change)


def test_simulated_company_totals_match_the_readme():
    from evals import company
    r = company.run()
    assert (r["renewals"], r["trials"], r["held"]) == (26, 15, 9)
    assert r["saving"] > 0 and r["saving"] <= r["spend"]


def test_the_public_audit_case_uses_the_audited_figures_at_the_audit_date():
    f = law.compute_facts("toronto-pda")
    assert (f["seats"], f["active_seats"], f["recommended_seats"]) == (800000, 15331, 16098)
    assert f["renewal_as_written"] == 740928 and f["calculated_saving"] == 726019 and f["notice_open"]
    assert f["days_to_notice"] == 76
    docs = law.evidence("toronto-pda")["contract.md"]
    for figure in ("800,000", "15,331", "$648,312", "$657,177"):
        assert figure in docs
