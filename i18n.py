"""Internationalization (i18n) module for RentWise

Supports: Simplified Chinese (简体中文)

Translations are loaded from JSON files in the locales/ directory.
"""

from typing import Dict, Optional
import os
import json
import streamlit as st

# Default language
DEFAULT_LANG = "zh-cn"

# Supported languages
SUPPORTED_LANGS = ["zh-cn"]

# Cache for loaded translations
_TRANSLATIONS_CACHE: Dict[str, Dict[str, str]] = {}


def _load_translations_from_file(lang: str) -> Dict[str, str]:
    """Load translations from JSON file for a specific language"""
    locales_dir = os.path.join(os.path.dirname(__file__), "locales")
    file_path = os.path.join(locales_dir, f"{lang}.json")

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Remove meta key if present
            if "_meta" in data:
                del data["_meta"]
            return data
    return {}


def _get_translations() -> Dict[str, Dict[str, str]]:
    """Get all translations, loading from files if not cached"""
    global _TRANSLATIONS_CACHE

    if not _TRANSLATIONS_CACHE:
        for lang in SUPPORTED_LANGS:
            _TRANSLATIONS_CACHE[lang] = _load_translations_from_file(lang)

    return _TRANSLATIONS_CACHE


# Translation dictionary (loaded from JSON files)
TRANSLATIONS: Dict[str, Dict[str, str]] = _get_translations()


def get_text(key: str, lang: Optional[str] = None) -> str:
    """Get translated text for a key

    Args:
        key: The translation key
        lang: Language code. If None, uses session state or default.

    Returns:
        Translated string
    """
    if lang is None:
        # Always use zh-cn
        lang = DEFAULT_LANG

    # Return translation or key itself
    if lang in TRANSLATIONS:
        return TRANSLATIONS[lang].get(key, key)
    else:
        return key


def set_language(lang: str) -> None:
    """Set the current language in session state"""
    if lang in TRANSLATIONS:
        st.session_state["language"] = lang


def get_language() -> str:
    """Get the current language"""
    return DEFAULT_LANG


# Shorthand function for easier usage
def t(key: str) -> str:
    """Shorthand for get_text()"""
    return get_text(key)
