import datetime, io, pathlib, shutil
import pypdf, pytest

from overruled import importer, law

SAMPLE = pathlib.Path(__file__).parent.parent / "imports" / "sample"
FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(law, "CASES", tmp_path / "cases")
    (tmp_path / "cases").mkdir()
    src = tmp_path / "in"
    shutil.copytree(SAMPLE, src)
    return src


def edit(path, old, new):
    path.write_text(path.read_text().replace(old, new))


def test_sample_import(world):
    r = importer.run(world)
    assert r["imported"] == ["pipewave-crm", "docuvault", "slidehive", "formly"]
    f = law.compute_facts("pipewave-crm")
    assert f["seats"] == 50 and f["active_seats"] == 21 and f["uplift_percent"] == 8
    assert f["renewal_as_written"] == 32400
    assert f["recommended_seats"] == 23 and f["calculated_saving"] == 17496
    assert law.find_case("put the pipewave renewal on trial") == "pipewave-crm"


def test_a_case_without_inventory_data_does_not_claim_zero_devices(tmp_path):
    (tmp_path / "contract.md").write_text("Customer gives written notice at least thirty (30) days before the term ends.")
    bill = {"app": "Acme", "vendor": "Acme", "seats": "1", "price_per_seat": "10", "renewal_date": "2027-03-01", "contract_file": "contract.md", "owner_team": "Ops"}
    importer.build_case(bill, [{"app": "Acme", "user": "a", "last_login": "2026-10-01"}], 0, tmp_path, tmp_path)
    assert "devices" not in (tmp_path / "acme" / "request.md").read_text()


def test_no_uplift_clause_means_no_uplift(world):
    importer.run(world)
    f = law.compute_facts("docuvault")
    assert f["uplift_percent"] == 0 and f["renewal_as_written"] == 6000


def test_missing_contract_is_skipped_with_a_reason(world):
    r = importer.run(world)
    assert r["skipped"] == [("Meetfast", "contract missing.md not found")]


def test_app_without_signins_is_not_treated_as_unused(world):
    (world / "contracts" / "missing.md").write_text("A contract.")
    r = importer.run(world)
    assert ("Meetfast", "no sign-in data") in r["skipped"]


def test_more_active_users_than_seats_stops_that_app(world):
    edit(world / "bills.csv", "Pipewave CRM,Pipewave Inc,50", "Pipewave CRM,Pipewave Inc,10")
    r = importer.run(world)
    assert "pipewave-crm" not in r["imported"]
    assert "21 active users" in r["skipped"][0][1]


def test_contract_path_cannot_leave_the_contracts_folder(world):
    (world / "secret.md").write_text("secret")
    edit(world / "bills.csv", "pipewave.md", "../secret.md")
    r = importer.run(world)
    assert ("Pipewave CRM", "contract secret.md not found") in r["skipped"]


def test_bad_numbers_and_dates_are_skipped(world):
    edit(world / "bills.csv", "Pipewave CRM,Pipewave Inc,50,600", "Pipewave CRM,Pipewave Inc,fifty,600")
    edit(world / "signins.csv", "docuvault01@example.com,2", "docuvault01@example.com,not-a-date-2")
    assert importer.run(world)["imported"] == ["slidehive", "formly"]


def test_missing_column_stops_the_import(world):
    edit(world / "bills.csv", "price_per_seat", "cost")
    with pytest.raises(ValueError, match="price_per_seat"):
        importer.run(world)


def test_installed_software_with_no_bill_is_reported(world):
    assert importer.run(world)["unbilled"] == ["Sketchly"]


def test_docket_picks_due_renewals_by_saving(world):
    due, passed = importer.docket(importer.run(world), set())
    assert [r["slug"] for r in due] == ["pipewave-crm", "slidehive"]
    why = {r["slug"]: r["why"] for r in passed}
    assert why["docuvault"] == "saving too small for a trial"
    assert why["formly"].startswith("notice deadline missed")


def test_a_missed_notice_deadline_means_no_claimable_saving(world):
    importer.run(world)
    f = law.compute_facts("formly")
    assert f["calculated_saving"] == 0 and f["missed_saving"] > 0 and not f["notice_open"]
    assert f["notice_deadline"] == "2026-10-21"


def test_docket_skips_ruled_and_distant_renewals(world):
    edit(world / "bills.csv", "2026-12-20", "2028-01-01")
    due, passed = importer.docket(importer.run(world), {"pipewave-crm"})
    assert due == []
    assert {r["slug"]: r["why"] for r in passed}["pipewave-crm"] == "already ruled"
    assert "notice is due in" in {r["slug"]: r["why"] for r in passed}["slidehive"]


def test_a_bad_renewal_date_is_skipped(world):
    edit(world / "bills.csv", "2027-01-20", "soon")
    r = importer.run(world)
    assert "pipewave-crm" not in r["imported"]


def test_intake_reads_seats_and_price_from_the_contract():
    bill = importer.parse_intake('@scout intake app="Acme Sign" renewal=2027-03-01', "Customer buys 25 Named User seats at $300 per seat.")
    assert bill["seats"] == 25 and bill["price_per_seat"] == 300 and bill["app"] == "Acme Sign"


def test_intake_asks_for_what_is_missing():
    with pytest.raises(ValueError, match="renewal, seats, price"):
        importer.parse_intake("@scout intake app=Acme", "No terms here.")


def test_a_wrapped_pdf_reads_like_the_text_contract():
    text = importer.contract_text("contract.PDF", (FIXTURES / "contract.pdf").read_bytes())
    assert importer.read_uplift(text)[0] == 8
    assert importer.read_notice(text)[0] == 45
    assert importer.contract_terms(text) == (50, 600)


def test_a_pdf_without_text_stops_the_intake():
    w = pypdf.PdfWriter()
    w.add_blank_page(200, 200)
    out = io.BytesIO()
    w.write(out)
    with pytest.raises(ValueError, match="scan"):
        importer.contract_text("scan.pdf", out.getvalue())


def test_a_locked_or_broken_pdf_stops_the_intake():
    w = pypdf.PdfWriter()
    w.add_blank_page(200, 200)
    w.encrypt("secret")
    out = io.BytesIO()
    w.write(out)
    for data in (out.getvalue(), b"not a pdf"):
        with pytest.raises(ValueError, match="can't be opened"):
            importer.contract_text("x.pdf", data)


def test_okta_export_with_its_real_columns():
    text = "Person,Login,Application username,Logins,Login Date,Login Date_ISO8601\nAna,ana@x.co,ana,3,\"Oct 1, 2026\",2026-10-01T15:04:05.000Z\n"
    source, rows = importer.read_signins(text, "Acme")
    assert source.startswith("Okta") and rows == [{"app": "Acme", "user": "ana@x.co", "last_login": "2026-10-01"}]


M365 = "\ufeffReport Refresh Date,User Principal Name,Last Activation Date,Last Activity Date,Report Period\n"


def test_microsoft_export_keeps_people_with_no_activity():
    text = M365 + "2026-11-01,ana@x.co,2026-01-01,2026-10-20,90\n2026-11-01,leo@x.co,,,90\n"
    source, rows = importer.read_signins(text, "Acme")
    assert source.startswith("Microsoft") and [r["last_login"] for r in rows] == ["2026-10-20", ""]
    assert not law.is_active("", law.TODAY) and law.is_active("2026-10-20", law.TODAY)


def test_a_microsoft_report_shorter_than_the_active_window_stops():
    with pytest.raises(ValueError, match="at least 90 days"):
        importer.read_signins(M365 + "2026-11-01,ana@x.co,,2026-10-20,30\n", "Acme")


def bill(**extra):
    return {"app": "Acme", "vendor": "Acme", "seats": "10", "price_per_seat": "100", "renewal_date": "2030-01-01", "contract_file": "c.md", "owner_team": "IT", **extra}


def live_case(tmp_path, signins, **kwargs):
    (tmp_path / "c.md").write_text("Customer must give written notice at least 30 days before renewal.")
    return importer.build_case(bill(), signins, 0, tmp_path, law.CASES, **kwargs)


def test_okta_rows_can_be_fewer_than_half_the_seats(world, tmp_path):
    rows = [{"app": "Acme", "user": "a", "last_login": law.TODAY.isoformat()}]
    with pytest.raises(ValueError, match="cover only"):
        live_case(tmp_path, rows)
    assert law.compute_facts(live_case(tmp_path, rows, signed_in_only=True))["active_seats"] == 1


def test_a_live_case_uses_the_real_date_and_a_sample_does_not(world, tmp_path):
    fresh = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    rows = [{"app": "Acme", "user": str(i), "last_login": fresh} for i in range(6)]
    case = law.load_case(live_case(tmp_path, rows, live=True))
    assert law.case_today(case) == datetime.date.today() and law.case_today({}) == law.TODAY
    assert law.compute_facts("acme")["active_seats"] == 6


def test_intake_rejects_a_signin_file_without_the_columns():
    with pytest.raises(ValueError, match="last_login"):
        importer.read_signins("name,date\na,b\n", "Acme")


def test_intake_accepts_the_curly_quotes_slack_sends():
    bill = importer.parse_intake('@scout intake app=“Acme Sign” renewal=2027-03-01', "Customer buys 25 seats at $300 per seat.")
    assert bill["app"] == "Acme Sign"


def test_harborline_benchmark():
    from evals.benchmark import score
    bad = [r for r in score() if r["problems"]]
    assert not bad, bad
