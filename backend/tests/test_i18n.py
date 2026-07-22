"""Tests for the gettext-backed i18n loader (app/core/i18n/loader.py).

This locks down the public API (I18nLoader.get/get_available_languages,
get_text, get_text_bilingual) that stayed unchanged when the storage engine
was swapped from hand-rolled JSON to gettext catalogs under locales/ (see
locales/README.md) - every `_("dotted.key")` call site elsewhere in the app
relies on this behavior without knowing the storage format underneath.
"""

from app.core.i18n import I18nLoader, get_i18n_loader, get_text, get_text_bilingual


def test_get_returns_translated_text_for_known_key():
    assert get_text("booking.actions.accept", "ru") == "✅ Принять"
    assert get_text("booking.actions.accept", "pl") == "✅ Akceptuj"


def test_get_falls_back_to_default_locale_for_unknown_language():
    assert get_text("booking.actions.accept", "de") == get_text("booking.actions.accept", "pl")


def test_get_falls_back_to_the_key_itself_for_unknown_key():
    assert get_text("this.key.does.not.exist", "ru") == "this.key.does.not.exist"


def test_get_formats_placeholders():
    result = get_text("booking.notification.accepted", "ru", mechanic_name="Иван", details="X")
    assert "Иван" in result
    assert "X" in result


def test_get_available_languages_includes_pl_and_ru():
    languages = get_i18n_loader().get_available_languages()
    assert set(languages) == {"pl", "ru"}


def test_get_text_bilingual_includes_both_languages():
    result = get_text_bilingual("start.unauthorized")
    assert get_text("start.unauthorized", "pl") in result
    assert get_text("start.unauthorized", "ru") in result


def test_i18n_loader_raises_for_missing_locales_dir(tmp_path):
    empty_dir = tmp_path / "does-not-exist"
    try:
        I18nLoader(locales_dir=str(empty_dir))
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
