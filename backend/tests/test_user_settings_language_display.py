"""Regression test for item 2.4.7 in docs/REFACTORING_PLAN_2026-07.md:
get_language_display_name() used to return a hardcoded bilingual literal
("❌ Не установлен / Nie ustawiono") for the unset-language case instead of
going through the i18n catalogs like every other user-facing string in this
file - and that branch was actually unreachable in practice, since both
call sites already guarded against passing an unset language.
"""

from app.bot.handlers.user_settings import get_language_display_name
from app.models.user import LANGUAGE_UNSET


def translate(key: str, **kwargs) -> str:
    # Stand-in i18n getter: returns the key itself so the test can assert
    # the right *key* was used, without depending on catalog content.
    return key


class TestGetLanguageDisplayName:
    def test_known_language_returns_native_name(self):
        assert get_language_display_name("pl", translate) == "Polski 🇵🇱"
        assert get_language_display_name("ru", translate) == "Русский 🇷🇺"

    def test_none_goes_through_i18n_key(self):
        assert get_language_display_name(None, translate) == "user_settings.language_not_set"

    def test_unset_sentinel_goes_through_i18n_key(self):
        assert get_language_display_name(LANGUAGE_UNSET, translate) == "user_settings.language_not_set"
