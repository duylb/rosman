from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import session

SUPPORTED_LANGS = {"en", "vi"}
BASE_DIR = Path(__file__).resolve().parents[1]
LOCALES_DIR = BASE_DIR / "locales"


@lru_cache(maxsize=None)
def _load_locale(lang: str) -> dict[str, Any]:
    locale_path = LOCALES_DIR / f"{lang}.json"
    if not locale_path.exists():
        return {}
    with locale_path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    return data if isinstance(data, dict) else {}


def get_lang() -> str:
    lang = (session.get("lang") or "en").strip().lower()
    return lang if lang in SUPPORTED_LANGS else "en"


def set_lang(lang: str) -> None:
    normalized = (lang or "").strip().lower()
    if normalized in SUPPORTED_LANGS:
        session["lang"] = normalized


def t(key: str) -> str:
    current_lang = get_lang()
    current_locale = _load_locale(current_lang)
    if key in current_locale:
        return str(current_locale[key])

    english_locale = _load_locale("en")
    if key in english_locale:
        return str(english_locale[key])

    return key
