"""I18n Loader - loads translations from gettext catalogs (locales/<lang>/LC_MESSAGES/messages.mo)

Backed by aiogram's own gettext-based I18n engine (aiogram.utils.i18n), the
same one used for this pattern in our other Telegram-Cars project, instead of
the hand-rolled JSON loader this replaced. The public API (I18nLoader.get(),
get_text(), get_text_bilingual()) is kept identical on purpose so nothing
else in the app - I18nMiddleware, every `_("some.dotted.key")` call site -
needed to change: translation keys are still dot-paths like
"booking.notification.accepted", they're just gettext msgids now instead of
JSON dict paths. See locales/README.md for the edit/compile workflow.
"""

from pathlib import Path
from typing import Optional

from aiogram.utils.i18n import I18n

DEFAULT_LOCALE = "pl"


class I18nLoader:
    """Loader for internationalization translations"""

    def __init__(self, locales_dir: Optional[str] = None):
        """
        Initialize I18n Loader

        Args:
            locales_dir: Directory containing <lang>/LC_MESSAGES/messages.mo catalogs
        """
        if locales_dir is None:
            # Repo layout: backend/locales/<lang>/LC_MESSAGES/messages.mo
            self.locales_dir = Path(__file__).resolve().parent.parent.parent.parent / "locales"
        else:
            self.locales_dir = Path(locales_dir)

        if not self.locales_dir.exists():
            raise FileNotFoundError(f"Locales directory not found: {self.locales_dir}")

        self._i18n = I18n(path=self.locales_dir, default_locale=DEFAULT_LOCALE, domain="messages")
        self.available_languages: list[str] = list(self._i18n.available_locales)

        if not self.available_languages:
            raise ValueError(
                f"No compiled translations found in {self.locales_dir} - "
                f"run `pybabel compile -d locales -D messages` (see locales/README.md)"
            )

    def get(self, key: str, lang: str = DEFAULT_LOCALE, **kwargs) -> str:
        """
        Get translation by key

        Args:
            key: Translation key (gettext msgid, dot notation e.g. "menu.main.title")
            lang: Language code
            **kwargs: Variables for string formatting

        Returns:
            Translated string (falls back to the key itself if not found, same
            as gettext's own behavior for an unknown msgid)
        """
        if lang not in self._i18n.locales:
            lang = DEFAULT_LOCALE

        value = self._i18n.gettext(key, locale=lang)

        if kwargs:
            try:
                value = value.format(**kwargs)
            except KeyError:
                pass

        return value

    def get_available_languages(self) -> list[str]:
        """Get list of available language codes"""
        return self.available_languages.copy()


# Global instance
_i18n_loader: Optional[I18nLoader] = None


def get_i18n_loader() -> I18nLoader:
    """Get global I18n loader instance"""
    global _i18n_loader
    if _i18n_loader is None:
        _i18n_loader = I18nLoader()
    return _i18n_loader


def get_text(key: str, lang: str = DEFAULT_LOCALE, **kwargs) -> str:
    """
    Convenience function to get translation

    Args:
        key: Translation key
        lang: Language code
        **kwargs: Variables for string formatting

    Returns:
        Translated string
    """
    return get_i18n_loader().get(key, lang, **kwargs)


def get_text_bilingual(key: str, **kwargs) -> str:
    """
    Get translation in both Polish and Russian with flags

    Args:
        key: Translation key
        **kwargs: Variables for string formatting

    Returns:
        Formatted string with both languages separated by newline and flags
    """
    loader = get_i18n_loader()
    text_pl = loader.get(key, "pl", **kwargs)
    text_ru = loader.get(key, "ru", **kwargs)

    # Special formatting for welcome message
    if key == "start.welcome":
        select_pl = loader.get("start.select_language", "pl")
        select_ru = loader.get("start.select_language", "ru")
        # Extract language texts (before "/" for PL, after "/" for RU)
        select_pl_text = select_pl.split(" / ")[0] if " / " in select_pl else select_pl
        select_ru_text = select_ru.split(" / ")[1] if " / " in select_ru else select_ru
        return f"🇵🇱 {text_pl}\n\n🇷🇺 {text_ru}\n\n🇷🇺 {select_ru_text}:\n\n🇵🇱 {select_pl_text}:"

    return f"🇵🇱 {text_pl}\n\n🇷🇺 {text_ru}"
