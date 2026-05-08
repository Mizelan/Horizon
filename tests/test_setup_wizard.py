from __future__ import annotations

from src.models import AIProvider
from src.setup.presets import _source_unique_key
from src.setup import wizard


def test_configure_ai_skips_api_key_prompt_for_llm_runner(monkeypatch):
    prompts = []
    answers = {
        "AI provider": "llm_runner",
        "Model name": "gpt-5.5",
        "Base URL (leave empty for default)": "",
        "LLM runner provider": "codex",
    }

    def fake_ask(prompt, **kwargs):
        prompts.append(prompt)
        return answers[prompt]

    monkeypatch.setattr(wizard.Prompt, "ask", fake_ask)

    config = wizard.configure_ai()

    assert config.provider == AIProvider.LLM_RUNNER
    assert config.api_key_env is None
    assert config.llm_runner_provider == "codex"
    assert "Output languages (comma-separated)" not in prompts
    assert "API key environment variable name" not in prompts


def test_llm_runner_recommendations_do_not_depend_on_horizon_api_key():
    config = wizard.AIConfig(
        provider=AIProvider.LLM_RUNNER,
        model="gpt-5.5",
        llm_runner_provider="codex",
    )

    assert wizard._ai_recommendations_available(config) is True


def test_sdk_recommendations_still_require_configured_env(monkeypatch):
    config = wizard.AIConfig(
        provider=AIProvider.OPENAI,
        model="gpt-5.5",
        api_key_env="OPENAI_API_KEY",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert wizard._ai_recommendations_available(config) is False

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert wizard._ai_recommendations_available(config) is True


def test_build_config_adds_youtube_recommendations():
    ai_config = wizard.AIConfig(
        provider=AIProvider.LLM_RUNNER,
        model="gpt-5.5",
        llm_runner_provider="codex",
    )

    config = wizard.build_config(
        ai_config,
        [
            {
                "type": "youtube",
                "description": "The Diary Of A CEO interviews",
                "config": {
                    "name": "The Diary Of A CEO",
                    "url": "https://www.youtube.com/@TheDiaryOfACEO",
                    "fetch_limit": 12,
                    "category": "interviews",
                },
            }
        ],
    )

    assert config.sources.youtube.enabled is True
    assert len(config.sources.youtube.channels) == 1
    channel = config.sources.youtube.channels[0]
    assert channel.name == "The Diary Of A CEO"
    assert str(channel.url).rstrip("/") == "https://www.youtube.com/@TheDiaryOfACEO"
    assert channel.fetch_limit == 12
    assert channel.category == "interviews"


def test_merge_configs_dedupes_youtube_by_url_and_preserves_enabled_state():
    ai_config = wizard.AIConfig(
        provider=AIProvider.LLM_RUNNER,
        model="gpt-5.5",
        llm_runner_provider="codex",
    )
    selected = [
        {
            "type": "youtube",
            "config": {
                "name": "The Diary Of A CEO",
                "url": "https://www.youtube.com/@TheDiaryOfACEO",
                "fetch_limit": 12,
            },
        }
    ]
    new_config = wizard.build_config(ai_config, selected)
    existing_config = wizard.build_config(ai_config, selected)
    existing_config.sources.youtube.channels[0].enabled = False

    merged = wizard.merge_configs(new_config, existing_config)

    assert len(merged.sources.youtube.channels) == 1
    assert merged.sources.youtube.channels[0].enabled is False
    assert merged.sources.youtube.channels[0].fetch_limit == 12


def test_count_sources_includes_enabled_youtube_channels_only():
    ai_config = wizard.AIConfig(
        provider=AIProvider.LLM_RUNNER,
        model="gpt-5.5",
        llm_runner_provider="codex",
    )
    config = wizard.build_config(
        ai_config,
        [
            {
                "type": "youtube",
                "config": {
                    "name": "The Diary Of A CEO",
                    "url": "https://www.youtube.com/@TheDiaryOfACEO",
                },
            }
        ],
    )

    assert wizard._count_sources(config) == 2

    config.sources.youtube.channels[0].enabled = False
    assert wizard._count_sources(config) == 1

    config.sources.youtube.channels[0].enabled = True
    config.sources.youtube.enabled = False
    assert wizard._count_sources(config) == 1


def test_youtube_source_unique_key_uses_channel_url():
    assert _source_unique_key(
        {
            "type": "youtube",
            "config": {
                "name": "The Diary Of A CEO",
                "url": "https://www.youtube.com/@TheDiaryOfACEO",
            },
        }
    ) == "youtube:https://www.youtube.com/@TheDiaryOfACEO"
