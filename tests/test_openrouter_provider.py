import os
import pytest
from unittest.mock import patch, MagicMock

from gpt_researcher.config.config import Config
from gpt_researcher.llm_provider.generic.base import GenericLLMProvider
from gpt_researcher.memory.embeddings import Memory


def test_openrouter_llm_provider_model_normalization():
    """Test that openrouter normalizes non-namespaced models to openai/<model> and keeps namespaced models."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123", "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1"}):
        # Bare OpenAI-style model name
        provider_instance = GenericLLMProvider.from_provider(
            "openrouter",
            model="gpt-4o-mini",
            temperature=0.7,
        )
        assert provider_instance.llm.model_name == "openai/gpt-4o-mini"
        assert str(provider_instance.llm.openai_api_base) == "https://openrouter.ai/api/v1"

        # Explicitly namespaced model
        provider_claude = GenericLLMProvider.from_provider(
            "openrouter",
            model="anthropic/claude-3.5-sonnet",
        )
        assert provider_claude.llm.model_name == "anthropic/claude-3.5-sonnet"

        # Bare claude model
        provider_bare_claude = GenericLLMProvider.from_provider(
            "openrouter",
            model="claude-3-haiku",
        )
        assert provider_bare_claude.llm.model_name == "anthropic/claude-3-haiku"


def test_config_openrouter_fallback_when_openai_key_missing():
    """Test that Config automatically falls back to OpenRouter when OPENAI_API_KEY is missing and OPENROUTER_API_KEY is present."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test-12345"}, clear=True):
        cfg = Config()
        assert cfg.fast_llm_provider == "openrouter"
        assert cfg.fast_llm_model == "openai/gpt-4o-mini"
        assert cfg.smart_llm_provider == "openrouter"
        assert cfg.strategic_llm_provider == "openrouter"
        assert cfg.embedding_provider == "openrouter"
        assert cfg.embedding_model == "openai/text-embedding-3-small"


def test_config_openai_used_when_openai_key_present():
    """Test that Config defaults to OpenAI when OPENAI_API_KEY is present."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}, clear=True):
        cfg = Config()
        assert cfg.fast_llm_provider == "openai"
        assert cfg.fast_llm_model == "gpt-4o-mini"
        assert cfg.smart_llm_provider == "openai"
        assert cfg.embedding_provider == "openai"


def test_openrouter_embeddings_initialization():
    """Test that openrouter embedding provider is configured properly."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123", "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1"}):
        mem = Memory("openrouter", "text-embedding-3-small")
        embeddings = mem.get_embeddings()
        assert embeddings.model == "openai/text-embedding-3-small"
        assert str(embeddings.openai_api_base) == "https://openrouter.ai/api/v1"
