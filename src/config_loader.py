"""config 파일 로드 및 스키마 검증."""

import json


class ConfigError(Exception):
    """config 로드/검증 실패."""


def load_config(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config 파일을 찾을 수 없습니다: {config_path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"config 파일이 올바른 JSON이 아닙니다: {e}")

    google_sheet = config.get("google_sheet")
    if not google_sheet or not google_sheet.get("spreadsheet_id"):
        raise ConfigError("config에 google_sheet.spreadsheet_id가 없습니다")

    columns = google_sheet.get("columns")
    if not columns or not all(k in columns for k in ("name", "ticker", "exchange")):
        raise ConfigError(
            "config의 google_sheet.columns에 name, ticker, exchange가 모두 필요합니다"
        )

    google_sheet.setdefault("gid", 0)
    google_sheet.setdefault("has_header", True)
    config.setdefault("options", {}).setdefault("timeout_sec", 10)

    return config
