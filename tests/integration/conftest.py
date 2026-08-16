import os
import re
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from patientcapital.api.app import create_app
from patientcapital.config import Settings


def _validate_test_database_url(value: str) -> str:
    database_name = make_url(value).database
    if database_name is None or not re.fullmatch(r"[A-Za-z0-9_]+_test", database_name):
        raise RuntimeError(
            "TEST_DATABASE_URL must target a dedicated database whose name ends with '_test'"
        )
    return value


TEST_DATABASE_URL = _validate_test_database_url(
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://patientcapital:patientcapital@localhost:55432/patientcapital_test",
    )
)


def _ensure_test_database() -> None:
    test_url = make_url(TEST_DATABASE_URL)
    database_name = test_url.database
    if database_name is None:  # pragma: no cover - guarded by _validate_test_database_url
        raise RuntimeError("TEST_DATABASE_URL has no database name")

    admin_engine = create_engine(test_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
            {"database_name": database_name},
        ).scalar_one_or_none()
        if exists is None:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Generator[None]:
    _ensure_test_database()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_database(migrated_database: None) -> Generator[None]:
    del migrated_database
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE monitor_alert_acknowledgements, monitor_alerts, monitor_runs, "
                "transaction_draft_decisions, transaction_drafts, proposal_sets, "
                "recommendation_runs, transactions, price_snapshots, "
                "asset_versions, assets, profile_versions RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()
    yield


@pytest.fixture
def client() -> Generator[TestClient]:
    app = create_app(Settings(database_url=TEST_DATABASE_URL, app_env="test"))
    with TestClient(app) as test_client:
        yield test_client
