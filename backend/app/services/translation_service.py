"""Translation Service with LRU cache and fallback strategy"""

import asyncio
from typing import Dict, Optional
from functools import lru_cache
from collections import OrderedDict
from deep_translator import GoogleTranslator

from app.config.settings import get_settings
from app.core.rate_limiter import get_translation_rate_limiter
from app.core.logging_config import get_logger
from app.core.metrics import get_metrics_collector


logger = get_logger(__name__)


class LRUCache:
    """Simple LRU cache implementation"""
    
    def __init__(self, maxsize: int = 1000):
        """
        Initialize LRU cache
        
        Args:
            maxsize: Maximum number of cached items
        """
        self.maxsize = maxsize
        self.cache: OrderedDict[str, str] = OrderedDict()
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def set(self, key: str, value: str) -> None:
        """Set value in cache"""
        if key in self.cache:
            # Update existing
            self.cache.move_to_end(key)
            self.cache[key] = value
        else:
            # Add new
            self.cache[key] = value
            # Remove oldest if cache is full
            if len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)  # Remove oldest (first item)
    
    def clear(self) -> None:
        """Clear cache"""
        self.cache.clear()
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)


class TranslationService:
    """Service for translating text between languages with LRU cache and fallback strategy"""
    
    _instance: Optional["TranslationService"] = None
    _default_cache_size: int = 1000
    _translation_timeout: float = 10.0  # seconds
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        # Initialize cache in __new__ to ensure it's always set
        settings = get_settings()
        cache_size = getattr(settings, "translation_cache_size", cls._default_cache_size)
        cls._instance._cache = LRUCache(maxsize=cache_size)
        cls._instance._rate_limiter = get_translation_rate_limiter()
        return cls._instance
    
    def __init__(self):
        """Initialize translation service"""
        # Cache is initialized in __new__, just ensure it exists
        if not hasattr(self, "_cache") or self._cache is None:
            settings = get_settings()
            cache_size = getattr(settings, "translation_cache_size", self._default_cache_size)
            self._cache = LRUCache(maxsize=cache_size)
        if not hasattr(self, "_rate_limiter"):
            self._rate_limiter = get_translation_rate_limiter()
    
    @staticmethod
    def _get_cache_key(text: str, source_lang: str, target_lang: str) -> str:
        """Generate cache key"""
        # Use first 200 chars to avoid too long keys
        text_hash = hash(text[:200])
        return f"{source_lang}:{target_lang}:{text_hash}"
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        use_cache: bool = True
    ) -> str:
        """
        Translate text from source language to target language
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Translated text (or original text on error)
        """
        # Skip if same language
        if source_lang == target_lang:
            return text
        
        # Check cache
        cache_key: Optional[str] = None
        if use_cache:
            cache_key = self._get_cache_key(text, source_lang, target_lang)
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Translation cache hit: {source_lang} -> {target_lang}")
                return cached
        
        # Try translation with timeout
        try:
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            
            # Run in thread pool with timeout
            loop = asyncio.get_event_loop()
            translated = await asyncio.wait_for(
                loop.run_in_executor(None, translator.translate, text),
                timeout=self._translation_timeout
            )
            
            # Cache result
            if use_cache and cache_key is not None:
                self._cache.set(cache_key, translated)
            
            # Record metrics
            metrics = get_metrics_collector()
            await metrics.increment("translations.success")
            await metrics.increment(f"translations.{source_lang}.{target_lang}")
            
            logger.debug("Translation successful", source_lang=source_lang, target_lang=target_lang)
            return translated
            
        except asyncio.TimeoutError:
            # Record metrics
            metrics = get_metrics_collector()
            await metrics.increment("translations.timeout")
            
            logger.warning("Translation timeout", source_lang=source_lang, target_lang=target_lang)
            # Fallback: return original text
            return text
        except Exception as e:
            # Record metrics
            metrics = get_metrics_collector()
            await metrics.increment("translations.error")
            
            # Rate limit error logging to prevent spam
            # Use a dummy chat_id (0) for global translation error rate limiting
            if await self._rate_limiter.is_allowed(0):
                logger.error("Translation error", source_lang=source_lang, target_lang=target_lang, error=str(e), exc_info=True)
                await self._rate_limiter.record_message(0)
            # Fallback: return original text
            return text
    
    async def translate_to_all_languages(
        self,
        text: str,
        source_lang: str,
        target_languages: Optional[list[str]] = None,
        use_cache: bool = True
    ) -> Dict[str, str]:
        """
        Translate text to all supported languages
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_languages: List of target language codes (default: from settings)
            use_cache: Whether to use cache (default: True)
            
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
                translations[target_lang] = await self.translate(
                    text, source_lang, target_lang, use_cache=use_cache
                )
            else:
                translations[target_lang] = text
        
        return translations
    
    def clear_cache(self) -> None:
        """Clear translation cache"""
        self._cache.clear()
        logger.info("Translation cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "size": self._cache.size(),
            "maxsize": self._cache.maxsize
        }


# Global singleton instance
_translation_service: Optional[TranslationService] = None


def get_translation_service() -> TranslationService:
    """Get singleton translation service instance"""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service


# Backward compatibility: static methods that use singleton
async def translate(text: str, source_lang: str, target_lang: str) -> str:
    """Static method for backward compatibility"""
    service = get_translation_service()
    return await service.translate(text, source_lang, target_lang)


async def translate_to_all_languages(
    text: str,
    source_lang: str,
    target_languages: Optional[list[str]] = None
) -> Dict[str, str]:
    """Static method for backward compatibility"""
    service = get_translation_service()
    return await service.translate_to_all_languages(text, source_lang, target_languages)

