from pathlib import Path
import pytest
from Vault.db_handler import DBHandler


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def test_add_category_returns_id(db):
    cat_id = db.add_category("savings")
    assert isinstance(cat_id, int)
    assert cat_id > 0


def test_add_category_idempotent(db):
    id1 = db.add_category("savings")
    id2 = db.add_category("savings")
    assert id1 == id2


def test_add_category_lowercases(db):
    db.add_category("SAVINGS")
    assert "savings" in db.get_categories()


def test_get_categories_empty(db):
    assert db.get_categories() == []


def test_get_categories_returns_all(db):
    db.add_category("savings")
    db.add_category("debt")
    cats = db.get_categories()
    assert "savings" in cats
    assert "debt" in cats


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------

def test_add_field_success(db):
    result = db.add_field("checking", "savings")
    assert result is True


def test_add_field_creates_category(db):
    db.add_field("checking", "savings")
    assert "savings" in db.get_categories()


def test_add_field_duplicate_returns_false(db):
    db.add_field("checking", "savings")
    result = db.add_field("checking", "savings")
    assert result is False


def test_add_field_lowercases(db):
    db.add_field("Checking", "Savings")
    fields = [row[0] for row in db.get_active_fields()]
    assert "checking" in fields


def test_get_active_fields_empty(db):
    assert db.get_active_fields() == []


def test_get_active_fields_returns_name_category_unit(db):
    db.add_field("checking", "savings")
    rows = db.get_active_fields()
    assert len(rows) == 1
    name, category, unit = rows[0]
    assert name == "checking"
    assert category == "savings"
    assert unit == "$"


def test_deactivate_field(db):
    db.add_field("checking", "savings")
    result = db.deactivate_field("checking")
    assert result is True
    assert db.get_active_fields() == []


def test_deactivate_nonexistent_field(db):
    result = db.deactivate_field("ghost")
    assert result is False


def test_reactivate_deactivated_field(db):
    db.add_field("checking", "savings")
    db.deactivate_field("checking")
    result = db.add_field("checking", "savings")
    assert result is True
    assert len(db.get_active_fields()) == 1


def test_get_fields_by_category(db):
    db.add_field("checking", "savings")
    db.add_field("brokerage", "savings")
    db.add_field("mortgage", "debt")
    fields = db.get_fields_by_category("savings")
    assert "checking" in fields
    assert "brokerage" in fields
    assert "mortgage" not in fields


# ---------------------------------------------------------------------------
# Category units
# ---------------------------------------------------------------------------

def test_set_category_unit(db):
    db.add_category("metals")
    result = db.set_category_unit("metals", "oz")
    assert result is True


def test_set_category_unit_nonexistent(db):
    result = db.set_category_unit("ghost", "oz")
    assert result is False


def test_get_field_unit_default(db):
    db.add_field("checking", "savings")
    assert db.get_field_unit("checking") == "$"


def test_get_field_unit_custom(db):
    db.add_field("gold", "metals")
    db.set_category_unit("metals", "oz")
    assert db.get_field_unit("gold") == "oz"


def test_get_field_unit_missing_returns_default(db):
    assert db.get_field_unit("nonexistent") == "$"


# ---------------------------------------------------------------------------
# Snapshots / record_value
# ---------------------------------------------------------------------------

def test_record_value_success(db):
    db.add_field("checking", "savings")
    result = db.record_value("checking", "2026-01", 5000.0)
    assert result is True


def test_record_value_unknown_field(db):
    result = db.record_value("ghost", "2026-01", 999.0)
    assert result is False


def test_record_value_upserts(db):
    db.add_field("checking", "savings")
    db.record_value("checking", "2026-01", 5000.0)
    db.record_value("checking", "2026-01", 6000.0)
    history = db.get_history("checking")
    assert len(history) == 1
    assert history[0][1] == 6000.0


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def test_get_history_single_field(db):
    db.add_field("checking", "savings")
    db.record_value("checking", "2026-01", 1000.0)
    db.record_value("checking", "2026-02", 2000.0)
    rows = db.get_history("checking")
    assert len(rows) == 2
    assert rows[0] == ("2026-01", 1000.0)
    assert rows[1] == ("2026-02", 2000.0)


def test_get_history_empty(db):
    assert db.get_history("ghost") == []


def test_get_history_all_fields_empty(db):
    months, fields, data = db.get_history()
    assert months == []
    assert fields == []
    assert data == {}


def test_get_history_all_fields(db):
    db.add_field("checking", "savings")
    db.add_field("brokerage", "savings")
    db.record_value("checking", "2026-01", 1000.0)
    db.record_value("brokerage", "2026-01", 5000.0)
    months, fields, data = db.get_history()
    assert "2026-01" in months
    assert data["checking"]["2026-01"] == 1000.0
    assert data["brokerage"]["2026-01"] == 5000.0


# ---------------------------------------------------------------------------
# Latest values
# ---------------------------------------------------------------------------

def test_get_latest_values_empty(db):
    assert db.get_latest_values() == []


def test_get_latest_values_returns_most_recent(db):
    db.add_field("checking", "savings")
    db.record_value("checking", "2026-01", 1000.0)
    db.record_value("checking", "2026-02", 2000.0)
    rows = db.get_latest_values()
    assert len(rows) == 1
    assert rows[0][3] == 2000.0  # value column


# ---------------------------------------------------------------------------
# Commodity prices
# ---------------------------------------------------------------------------

def test_set_commodity_success(db):
    db.add_field("gold", "metals")
    result = db.set_commodity("gold", "xau")
    assert result is True


def test_set_commodity_unknown_field(db):
    result = db.set_commodity("ghost", "XAU")
    assert result is False


def test_get_commodity_fields(db):
    db.add_field("gold", "metals")
    db.set_commodity("gold", "XAU")
    rows = db.get_commodity_fields()
    assert len(rows) == 1
    assert rows[0][1] == "gold"
    assert rows[0][2] == "XAU"


def test_remove_commodity(db):
    db.add_field("gold", "metals")
    db.set_commodity("gold", "XAU")
    result = db.remove_commodity("gold")
    assert result is True
    assert db.get_commodity_fields() == []


def test_remove_commodity_nonexistent(db):
    result = db.remove_commodity("ghost")
    assert result is False


def test_set_commodity_override(db):
    db.add_field("gold", "metals")
    db.set_commodity("gold", "XAU")
    result = db.set_commodity_override("gold", 2500.0)
    assert result is True


def test_set_commodity_override_no_commodity(db):
    db.add_field("gold", "metals")
    result = db.set_commodity_override("gold", 2500.0)
    assert result is False


def test_update_cached_price(db):
    db.add_field("gold", "metals")
    db.set_commodity("gold", "XAU")
    field_id = db.get_commodity_fields()[0][0]
    db.update_cached_price(field_id, 2450.0, "2026-04-17T10:00:00")
    rows = db.get_commodity_fields()
    assert rows[0][4] == 2450.0
    assert rows[0][5] == "2026-04-17T10:00:00"


# ---------------------------------------------------------------------------
# record_asset_value
# ---------------------------------------------------------------------------

def test_record_asset_value_debt_field(db):
    db.add_field("mortgage", "debt")
    result = db.record_asset_value("mortgage", "2026-01", 250000.0)
    assert result is True


def test_record_asset_value_non_debt_field(db):
    db.add_field("checking", "savings")
    result = db.record_asset_value("checking", "2026-01", 5000.0)
    assert result is False
