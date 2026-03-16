from app.config import Settings, parse_origins


def test_parse_origins_from_json_list_string() -> None:
    value = '["https://a.example","https://b.example"]'
    assert parse_origins(value) == ["https://a.example", "https://b.example"]


def test_parse_origins_from_comma_separated_string() -> None:
    value = "https://a.example, https://b.example ,,"
    assert parse_origins(value) == ["https://a.example", "https://b.example"]


def test_parse_origins_from_single_origin_string() -> None:
    assert parse_origins("https://single.example") == ["https://single.example"]


def test_settings_builds_database_url_from_postgres_parts_with_encoding() -> None:
    settings = Settings(
        _env_file=None,
        database_url=None,
        postgres_user="user+name",
        postgres_password="p@ss word",
        postgres_host="db",
        postgres_port=5432,
        postgres_db="expense",
    )

    assert (
        settings.database_url
        == "postgresql+psycopg://user%2Bname:p%40ss+word@db:5432/expense"
    )


def test_settings_prefers_explicit_database_url() -> None:
    explicit_dsn = "postgresql+psycopg://custom:secret@db:5432/expense"
    settings = Settings(
        _env_file=None,
        database_url=explicit_dsn,
        postgres_user="ignored",
        postgres_password="ignored",
        postgres_host="ignored",
        postgres_port=5432,
        postgres_db="ignored",
    )

    assert settings.database_url == explicit_dsn
