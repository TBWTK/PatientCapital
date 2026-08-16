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

    assert database_url.path.removeprefix("/") == example["POSTGRES_DB"]
    assert test_database_url.path.removeprefix("/") == f"{example['POSTGRES_DB']}_test"

    assert example["GIGACHAT_ENABLED"] == "false"
    assert example["GIGACHAT_API_KEY"] == ""
    assert example["GIGACHAT_CLIENT_ID"] == ""
    assert example["MOEX_ISS_BASE_URL"] == "https://iss.moex.com/iss"
    assert 0 < int(example["MOEX_TIMEOUT_SECONDS"]) <= 30
    assert 0 < int(example["MOEX_MAX_AGE_SECONDS"]) <= 604_800
    assert 0 < int(example["UPLOAD_MAX_BYTES"]) <= 10 * 1024 * 1024
    assert 0 < int(example["UPLOAD_MAX_PIXELS"]) <= 25_000_000
    assert 0 < int(example["OCR_TIMEOUT_SECONDS"]) <= 30
    assert example["UPLOAD_TEMP_DIRECTORY"] == "/tmp"
    ca_bundle = Path(example["GIGACHAT_CA_BUNDLE"])
    assert not ca_bundle.is_absolute()
    assert (PROJECT_ROOT / ca_bundle).is_file()
