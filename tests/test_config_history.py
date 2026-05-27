from ccbackup_bot.config_history import config_sha256, generate_config_diff, normalize_config_text


def test_normalize_config_text_normalizes_line_endings_and_trailing_whitespace():
    config = "interface Gi1/0/1   \r\n description Uplink   \r\n!\r\n"

    assert normalize_config_text(config) == "interface Gi1/0/1\n description Uplink\n!\n"


def test_config_sha256_ignores_line_endings_and_trailing_whitespace():
    first = "hostname core-sw-01\r\ninterface Gi1/0/1   \r\n"
    second = "hostname core-sw-01\ninterface Gi1/0/1\n"

    assert config_sha256(first) == config_sha256(second)


def test_generate_config_diff_shows_config_changes():
    old_config = "hostname core-sw-01\ninterface Gi1/0/1\n description Old\n"
    new_config = "hostname core-sw-01\ninterface Gi1/0/1\n description New\n"

    diff_text = generate_config_diff(old_config, new_config, "old", "new")

    assert "--- old" in diff_text
    assert "+++ new" in diff_text
    assert "- description Old" in diff_text
    assert "+ description New" in diff_text
