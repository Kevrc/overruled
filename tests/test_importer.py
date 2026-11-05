import pathlib, shutil
import pytest

from overruled import importer, law

SAMPLE = pathlib.Path(__file__).parent.parent / "imports" / "sample"


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
