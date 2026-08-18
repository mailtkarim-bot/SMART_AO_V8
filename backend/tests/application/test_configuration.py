from app.bootstrap.configuration import Settings


def test_runtime_settings_keep_safe_defaults_and_require_database_url():
    database_url = "postgresql://" + "smart_ao:smart_ao@localhost/smart_ao"
    settings = Settings(smart_ao_database_url=database_url)
    assert settings.smart_ao_env == "development"
    assert settings.smart_ao_log_level == "INFO"
    assert settings.smart_ao_database_url.endswith("/smart_ao")
