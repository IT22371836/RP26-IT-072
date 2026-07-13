from app.core.config import Settings


def test_cors_origins_are_parsed() -> None:
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test_database",
        cors_origins="http://localhost:5173, https://example.com ",
    )

    assert settings.cors_origin_list == ["http://localhost:5173", "https://example.com"]
