import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from tests.integration.conftest import TEST_DATABASE_URL


def test_head_migration_creates_required_authorities() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    inspector = inspect(engine)

    assert {
        "alembic_version",
        "profile_versions",
        "asset_versions",
        "price_snapshots",
        "transactions",
        "recommendation_runs",
    }.issubset(set(inspector.get_table_names()))
    assert inspector.get_unique_constraints("transactions")
    assert inspector.get_check_constraints("asset_versions")
    engine.dispose()


def test_database_rejects_mutation_of_append_only_facts() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    with (
        pytest.raises(DBAPIError, match="immutable table profile_versions"),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                """
                INSERT INTO profile_versions (
                  version, base_currency, investment_horizon_years, risk_level,
                  cash_buffer, broker_name, fee_rate, minimum_fee
                ) VALUES (1, 'RUB', 15, 'balanced', 0, 'Test', 0.001, 1)
                """
            )
        )
        connection.execute(text("UPDATE profile_versions SET broker_name = 'Mutated'"))
    engine.dispose()
