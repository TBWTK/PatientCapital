import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from patientcapital.api.app import create_app
from patientcapital.config import Settings

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://patientcapital:patientcapital@localhost:55432/patientcapital",
)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Generator[None]:
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
                "TRUNCATE recommendation_runs, transactions, price_snapshots, "
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
