import pytest
from pathlib import Path

from Vault.db_handler import DBHandler
from Vault.logger import Logger
from Vault.cli import CLI


@pytest.fixture
def db():
    return DBHandler(db_path=Path(":memory:"))


@pytest.fixture
def logger(tmp_path):
    return Logger(log_file=str(tmp_path / "test.log"))


@pytest.fixture
def cli(db, logger):
    return CLI(logger, db, price_fetcher=None)


def seed_db(db):
    """Insert representative data for tests that need an existing state."""
    db.add_category("savings")
    db.add_field("checking", "savings")
    db.add_field("brokerage", "savings")
    db.record_value("checking", "2026-01", 5000.0)
    db.record_value("checking", "2026-02", 5200.0)
    db.record_value("brokerage", "2026-01", 12000.0)


@pytest.fixture
def seeded_db(db):
    seed_db(db)
    return db
