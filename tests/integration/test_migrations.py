import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from tests.integration.conftest import TEST_DATABASE_URL, _validate_test_database_url


def test_destructive_fixture_rejects_non_test_database() -> None:
    with pytest.raises(RuntimeError, match="dedicated database"):
        _validate_test_database_url(
            "postgresql+psycopg://patientcapital:patientcapital@localhost:55432/patientcapital"
        )


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
        "proposal_sets",
    }.issubset(set(inspector.get_table_names()))
    assert inspector.get_unique_constraints("transactions")
    transaction_columns = {item["name"]: item for item in inspector.get_columns("transactions")}
    assert transaction_columns["accrued_interest_total"]["nullable"] is False
    assert inspector.get_check_constraints("asset_versions")
    assert any(
        "accrued_interest_total" in str(item.get("sqltext"))
        for item in inspector.get_check_constraints("transactions")
    )
    assert inspector.get_foreign_keys("proposal_sets")
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


def test_database_rejects_mutation_of_proposal_sets() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    with (
        pytest.raises(DBAPIError, match="immutable table proposal_sets"),
        engine.begin() as connection,
    ):
        connection.execute(
            text(
                """
                INSERT INTO profile_versions (
                  version, base_currency, investment_horizon_years, risk_level,
                  cash_buffer, broker_name, fee_rate, minimum_fee
                ) VALUES (1, 'RUB', 5, 'growth', 0, 'Test', 0.001, 0)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO proposal_sets (
                  id, contribution, currency, profile_version,
                  recommended_strategy_id, strategies
                ) VALUES (
                  '00000000-0000-0000-0000-000000000010', 8000, 'RUB', 1,
                  'five_year_core', '[]'::jsonb
                )
                """
            )
        )
        connection.execute(
            text("UPDATE proposal_sets SET recommended_strategy_id = 'mutated'")
        )
    engine.dispose()
