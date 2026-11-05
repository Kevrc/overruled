"""Writes contracts in wording the rules were not written against. Scored before any fix, to see how they generalize."""
import csv, datetime, pathlib, random, shutil
import yaml

OUT = pathlib.Path(__file__).parent.parent / "imports" / "benchmark-2"
TODAY = datetime.date(2026, 11, 4)
C = [
 ("Fernway", 40, 300, 120, 15, "Customer licenses 40 seats at $300 per seat per year.\nThe term renews each year unless Customer gives written notice at least sixty (60) days before renewal.\nFees rise 6% at each renewal.\n", {"status": "due", "uplift": 6, "trap": "'rise' instead of 'increase'"}),
 ("Quillbox", 30, 400, 120, 12, "Customer licenses 30 seats at $400 per seat per year.\nCancellation requires written notice sixty (60) days before renewal.\nRenewal pricing: list price +7%.\n", {"status": "due", "uplift": 7, "trap": "uplift written as +7%"}),
 ("Orchardly", 50, 200, 120, 20, "Customer licenses 50 seats at $200 per seat per year.\nCustomer must notify the vendor not less than 45 days before the term ends.\nPrices increase 5% each renewal.\n", {"status": "due", "notice": 45, "trap": "notice without the words 'written notice'"}),
 ("Tallyhall", 25, 480, 120, 9, "Customer licenses 25 seats at $480 per seat per year.\nTo stop renewal, email billing 30 days prior to the anniversary.\n", {"status": "due", "notice": 30, "trap": "notice by email, different wording"}),
 ("Marrowgate", 60, 100, 120, 20, "Annual price is $100 for each of the 60 users.\nCustomer gives written notice at least sixty (60) days before the end of the term.\n", {"status": "due", "trap": "seats and price in a different order"}),
 ("Pinewheel", 45, 250, 120, 15, "Customer licenses 45 seats at $250 per seat per year.\nThis Agreement does not renew automatically and ends on its end date.\n", {"status": "skipped", "why": "renew", "trap": "contract does not auto-renew"}),
 ("Ostler", 35, 300, 120, 12, "Customer licenses 35 seats at $300 per seat per year for a three (3) year term.\nCustomer may not reduce seats during the term.\nCustomer gives written notice at least sixty (60) days before the end of the term.\n", {"status": "skipped", "why": "reduce", "trap": "seats cannot be reduced"}),
 ("Lanternia", 55, 220, 120, 22, "Customer licenses 55 seats at $220 per seat per year.\nCustomer gives written notice at least sixty (60) days before the end of the term.\nAny price change will be notified by the vendor.\n", {"status": "skipped", "why": "price", "trap": "price change with no figure"}),
]


def main() -> None:
    random.seed(33)
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "contracts").mkdir(parents=True)
    bills, signins, inventory, expected = [], [], [], {}
    for app, seats, price, days, active, body, want in C:
        slug = app.lower()
        bills.append([app, f"{app} Inc", seats, price, (TODAY + datetime.timedelta(days=days)).isoformat(), f"{slug}.md", "Operations", ""])
        (OUT / "contracts" / f"{slug}.md").write_text(f"# {app} agreement (fictional)\n\n{body}")
        for i in range(seats):
            age = random.randint(1, 80) if i < active else random.randint(100, 500)
            signins.append([app, f"{slug}{i:03}@example.com", (TODAY - datetime.timedelta(days=age)).isoformat()])
        expected[slug] = want
    with (OUT / "bills.csv").open("w", newline="") as f:
        csv.writer(f).writerows([["app", "vendor", "seats", "price_per_seat", "renewal_date", "contract_file", "owner_team", "category"], *bills])
    with (OUT / "signins.csv").open("w", newline="") as f:
        csv.writer(f).writerows([["app", "user", "last_login"], *signins])
    with (OUT / "software_inventory.csv").open("w", newline="") as f:
        csv.writer(f).writerows([["device", "name", "publisher", "version"]])
    (OUT / "expected.yaml").write_text(yaml.safe_dump(expected, sort_keys=False))


if __name__ == "__main__":
    main()
