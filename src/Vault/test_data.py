def seed_test_db(db) -> None:
    """Populate an in-memory DB with realistic dummy data for interactive test mode."""

    # --- Records (fixed categories: cash, retirement, asset, debt, investment) ---
    db.add_field("checking",  "cash")
    db.add_field("savings",   "cash")
    db.add_field("401k",      "retirement")
    db.add_field("house",     "asset")
    db.add_field("mortgage",  "debt")
    db.add_field("car_loan",  "debt")
    db.add_field("gold",      "investment")
    db.add_field("silver",    "investment")
    db.add_field("aapl",      "investment")

    # --- Debt attributes: mortgage backed by the house, with an interest rate ---
    db.set_apr("mortgage", 6.25)
    db.set_apr("car_loan", 4.9)
    db.set_backing("mortgage", "house")

    # --- Notes (exercise * marker across categories in summary/show) ---
    db.set_note("checking", "Primary checking account")
    db.set_note("house", "Primary residence")
    db.set_note("mortgage", "30-year fixed")
    db.set_note("gold", "Physical bullion in safe deposit box")

    # --- Investment symbols + unit derivation (gold/silver in troy oz, aapl in shares) ---
    db.set_investment_symbol("gold", "gold")
    db.set_investment_symbol("silver", "silver")
    db.set_investment_symbol("aapl", "AAPL")

    # --- Override prices so summary/investment work with no live fetch needed ---
    db.set_override("gold", 3_300.00)
    db.set_override("silver", 33.00)
    db.set_override("aapl", 210.50)

    # --- Snapshots ---
    months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]

    checking_values  = [4_800, 5_000, 5_200, 5_150, 5_400, 5_600]
    savings_values   = [10_000, 10_200, 10_500, 10_800, 11_000, 11_300]
    k401_values      = [42_000, 43_100, 44_200, 43_500, 45_800, 47_200]
    house_values     = [385_000, 387_000, 390_000, 392_000, 393_500, 395_000]
    mortgage_values  = [312_000, 311_400, 310_800, 310_200, 309_600, 309_000]
    car_loan_values  = [14_200, 13_800, 13_400, 13_000, 12_600, 12_200]
    gold_oz          = [10.0, 10.0, 10.5, 10.5, 11.0, 11.0]
    silver_oz        = [150.0, 150.0, 175.0, 175.0, 200.0, 200.0]
    aapl_shares      = [10.0, 10.0, 12.0, 12.0, 15.0, 15.0]

    for name, series in [
        ("checking", checking_values),
        ("savings", savings_values),
        ("401k", k401_values),
        ("house", house_values),
        ("mortgage", mortgage_values),
        ("car_loan", car_loan_values),
        ("gold", gold_oz),
        ("silver", silver_oz),
        ("aapl", aapl_shares),
    ]:
        for month, amount in zip(months, series):
            db.record_value(name, month, float(amount))
