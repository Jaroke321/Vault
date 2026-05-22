def seed_test_db(db) -> None:
    """Populate an in-memory DB with realistic dummy data for interactive test mode."""

    # --- Categories ---
    db.add_category("savings")
    db.add_category("debt")
    db.add_category("metals")
    db.set_category_unit("metals", "oz")

    # --- Fields ---
    db.add_field("checking",  "savings")
    db.add_field("brokerage", "savings")
    db.add_field("401k",      "savings")
    db.add_field("mortgage",  "debt")
    db.add_field("car_loan",  "debt")
    db.add_field("gold",      "metals")
    db.add_field("silver",    "metals")

    # --- Savings snapshots (upward trend) ---
    months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]

    checking_values  = [4_800, 5_000, 5_200, 5_150, 5_400, 5_600]
    brokerage_values = [18_000, 18_500, 17_800, 19_200, 20_100, 21_300]
    k401_values      = [42_000, 43_100, 44_200, 43_500, 45_800, 47_200]

    for month, v in zip(months, checking_values):
        db.record_value("checking", month, float(v))
    for month, v in zip(months, brokerage_values):
        db.record_value("brokerage", month, float(v))
    for month, v in zip(months, k401_values):
        db.record_value("401k", month, float(v))

    # --- Debt snapshots (declining balances, mortgage has asset value) ---
    mortgage_balances = [312_000, 311_400, 310_800, 310_200, 309_600, 309_000]
    house_values      = [385_000, 387_000, 390_000, 392_000, 393_500, 395_000]
    car_balances      = [14_200, 13_800, 13_400, 13_000, 12_600, 12_200]

    for month, bal, asset in zip(months, mortgage_balances, house_values):
        db.record_value("mortgage", month, float(bal))
        db.record_asset_value("mortgage", month, float(asset))
    for month, bal in zip(months, car_balances):
        db.record_value("car_loan", month, float(bal))

    # --- Metals snapshots (oz holdings, flat/slowly growing) ---
    gold_oz   = [10.0, 10.0, 10.5, 10.5, 11.0, 11.0]
    silver_oz = [150.0, 150.0, 175.0, 175.0, 200.0, 200.0]

    for month, v in zip(months, gold_oz):
        db.record_value("gold", month, v)
    for month, v in zip(months, silver_oz):
        db.record_value("silver", month, v)

    # --- Commodity tags + override prices (no live fetch needed) ---
    db.set_commodity("gold", "XAU")
    db.set_commodity_override("gold", 3_300.00)
    db.set_commodity("silver", "XAG")
    db.set_commodity_override("silver", 33.00)
