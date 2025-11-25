"""Translation Service using googletrans"""

import asyncio
from typing import Dict, Optional
from functools import lru_cache
from deep_translator import GoogleTranslator

from app.config.settings import get_settings


class TranslationService:
    """Service for translating text between languages (SRP)"""
    
    # Cache for translations to reduce API calls
    _cache: Dict[str, str] = {}
    
    @staticmethod
    def _get_cache_key(text: str, source_lang: str, target_lang: str) -> str:
        """Generate cache key"""
        return f"{source_lang}:{target_lang}:{text[:100]}"
    
    @staticmethod
    async def translate(
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """
        Translate text from source language to target language
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated text
        """
        # Skip if same language
        if source_lang == target_lang:
            return text
        
        # Check cache
        cache_key = TranslationService._get_cache_key(text, source_lang, target_lang)
        if cache_key in TranslationService._cache:
            return TranslationService._cache[cache_key]
        
        try:
            # Use deep-translator (more reliable than googletrans)
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            
            # Run in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            translated = await loop.run_in_executor(
                None,
                translator.translate,
                text
            )
            
            # Cache result
            TranslationService._cache[cache_key] = translated
            
            return translated
            
        except Exception as e:
            # Fallback: return original text if translation fails
            print(f"Translation error: {e}")
            return text
    
    @staticmethod
    async def translate_to_all_languages(
        text: str,
        source_lang: str,
        target_languages: list[str] = None
    ) -> Dict[str, str]:
        """
        Translate text to all supported languages
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_languages: List of target language codes (default: from settings)
            
        Returns:
            Dictionary with language codes as keys and translations as values
        """
        if target_languages is None:
            settings = get_settings()
            target_languages = settings.supported_languages_list
        
        translations = {}
        
        # Add source language
        translations[source_lang] = text
        
        # Translate to other languages
        for target_lang in target_languages:
            if target_lang != source_lang:
                translations[target_lang] = await TranslationService.translate(
                    text, source_lang, target_lang
                )
            else:
                translations[target_lang] = text
        
        return translations
    
    @staticmethod
    def clear_cache():
        """Clear translation cache"""
        TranslationService._cache.clear()

