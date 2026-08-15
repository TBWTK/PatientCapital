from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_env_example() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator, f"malformed .env.example line for {key}"
        result[key] = value
    return result


def test_env_example_is_coherent_and_secret_free() -> None:
    example = _read_env_example()
    database_url = urlparse(example["DATABASE_URL"])
    test_database_url = urlparse(example["TEST_DATABASE_URL"])

    for parsed in (database_url, test_database_url):
        assert parsed.scheme == "postgresql+psycopg"
        assert parsed.hostname == "localhost"
        assert parsed.port == int(example["POSTGRES_PORT"])
        assert parsed.username == example["POSTGRES_USER"]
        assert parsed.password == example["POSTGRES_PASSWORD"]
        assert parsed.path.removeprefix("/") == example["POSTGRES_DB"]

    assert example["GIGACHAT_ENABLED"] == "false"
    assert example["GIGACHAT_API_KEY"] == ""
    assert example["GIGACHAT_CLIENT_ID"] == ""
    ca_bundle = Path(example["GIGACHAT_CA_BUNDLE"])
    assert not ca_bundle.is_absolute()
    assert (PROJECT_ROOT / ca_bundle).is_file()
