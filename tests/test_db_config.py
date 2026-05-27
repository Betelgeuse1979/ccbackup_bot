from ccbackup_bot.db import DB_SKIP_MESSAGE, database_config_from_env, store_successful_backups_and_write_report


def test_database_config_from_env_returns_none_when_missing():
    assert database_config_from_env({}) is None


def test_store_successful_backups_skips_cleanly_without_config(tmp_path):
    messages = store_successful_backups_and_write_report([], tmp_path, env={})

    assert messages == [DB_SKIP_MESSAGE]
