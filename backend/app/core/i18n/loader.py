"""I18n Loader - loads translations from JSON files"""

import json
import os
from pathlib import Path
from typing import Dict, Optional


class I18nLoader:
    """Loader for internationalization translations"""
    
    def __init__(self, locales_dir: str = None):
        """
        Initialize I18n Loader
        
        Args:
            locales_dir: Directory with locale JSON files
        """
        if locales_dir is None:
            locales_dir = Path(__file__).parent / "locales"
        
        self.locales_dir = Path(locales_dir)
        self.translations: Dict[str, Dict[str, str]] = {}
        self.available_languages: list[str] = []
        
        self._load_translations()
    
    def _load_translations(self) -> None:
        """Load all translation files from locales directory"""
        if not self.locales_dir.exists():
            raise FileNotFoundError(f"Locales directory not found: {self.locales_dir}")
        
        for file_path in self.locales_dir.glob("*.json"):
            lang_code = file_path.stem
            
            with open(file_path, "r", encoding="utf-8") as f:
                self.translations[lang_code] = json.load(f)
                self.available_languages.append(lang_code)
        
        if not self.translations:
            raise ValueError(f"No translation files found in {self.locales_dir}")
    
    def get(self, key: str, lang: str = "pl", **kwargs) -> str:
        """
        Get translation by key
        
        Args:
            key: Translation key (supports dot notation: "menu.main.title")
            lang: Language code
            **kwargs: Variables for string formatting
            
        Returns:
            Translated string
        """
        if lang not in self.translations:
            lang = "pl"  # Fallback to Polish
        
        # Support for nested keys (e.g., "menu.main.title")
        keys = key.split(".")
        value = self.translations[lang]
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, key)
            else:
                return key
        
        # Format string with kwargs if provided
        if kwargs and isinstance(value, str):
            try:
                value = value.format(**kwargs)
            except KeyError:
                pass
        
        return value if isinstance(value, str) else key
    
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


def get_text(key: str, lang: str = "pl", **kwargs) -> str:
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

