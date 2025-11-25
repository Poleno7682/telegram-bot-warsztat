"""Tests for TranslationService"""

import pytest
from app.services.translation_service import TranslationService


@pytest.mark.asyncio
async def test_translate_same_language():
    """Test that translating to the same language returns original text"""
    service = TranslationService()
    result = await service.translate("Hello", "en", "en")
    assert result == "Hello"


@pytest.mark.asyncio
async def test_translate_caching():
    """Test that translation results are cached"""
    service = TranslationService()
    
    # First translation
    result1 = await service.translate("Hello", "en", "pl", use_cache=True)
    
    # Second translation should use cache
    result2 = await service.translate("Hello", "en", "pl", use_cache=True)
    
    assert result1 == result2


@pytest.mark.asyncio
async def test_translate_to_all_languages():
    """Test translation to all supported languages"""
    service = TranslationService()
    result = await service.translate_to_all_languages(
        "Hello",
        "en",
        ["en", "pl", "ru"]
    )
    
    assert "en" in result
    assert "pl" in result
    assert "ru" in result
    assert result["en"] == "Hello"  # Source language should be unchanged


@pytest.mark.asyncio
async def test_translate_timeout_handling():
    """Test that timeout errors are handled gracefully"""
    service = TranslationService()
    # This should not raise an exception even if translation fails
    result = await service.translate("Test", "en", "pl")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_clear_cache():
    """Test cache clearing"""
    service = TranslationService()
    
    # Translate and cache
    await service.translate("Hello", "en", "pl", use_cache=True)
    
    # Clear cache
    service.clear_cache()
    
    # Cache should be empty
    stats = service.get_cache_stats()
    assert stats["size"] == 0

