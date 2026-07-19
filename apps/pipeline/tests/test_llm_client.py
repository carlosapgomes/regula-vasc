"""Tests for LLM client protocol."""

from apps.pipeline.llm import (
    LlmClient,
    RecordingLlmClient,
    StaticLlmClient,
    create_openai_llm1_client,
    create_openai_llm2_client,
)


class TestStaticLlmClient:
    def test_returns_fixed_response(self):
        client = StaticLlmClient(response_text='{"fixed": "response"}')
        result = client.complete(system_prompt="sys", user_prompt="user")
        assert result == '{"fixed": "response"}'

    def test_satisfies_protocol(self):
        client = StaticLlmClient("test")
        assert isinstance(client, LlmClient)

    def test_ignores_prompts(self):
        client = StaticLlmClient("always the same")
        r1 = client.complete(system_prompt="a", user_prompt="b")
        r2 = client.complete(system_prompt="c", user_prompt="d")
        assert r1 == r2 == "always the same"


class TestRecordingLlmClient:
    def test_records_calls(self):
        client = RecordingLlmClient(responses=['{"first": 1}', '{"second": 2}'])
        r1 = client.complete(system_prompt="sys1", user_prompt="usr1")
        r2 = client.complete(system_prompt="sys2", user_prompt="usr2")

        assert r1 == '{"first": 1}'
        assert r2 == '{"second": 2}'
        assert len(client.calls) == 2
        assert client.calls[0]["system_prompt"] == "sys1"
        assert client.calls[0]["user_prompt"] == "usr1"
        assert client.calls[1]["system_prompt"] == "sys2"
        assert client.calls[1]["user_prompt"] == "usr2"

    def test_returns_empty_string_when_no_responses(self):
        client = RecordingLlmClient(responses=[])
        result = client.complete(system_prompt="sys", user_prompt="usr")
        assert result == ""

    def test_satisfies_protocol(self):
        client = RecordingLlmClient()
        assert isinstance(client, LlmClient)


class TestCreateOpenAiClient:
    def test_creates_llm1_client(self):
        import os

        os.environ.setdefault("OPENAI_API_KEY", "test-key")
        os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")
        from django.conf import settings

        settings.OPENAI_API_KEY = "test-key"
        settings.OPENAI_MODEL = "gpt-4o-mini"

        client = create_openai_llm1_client()
        assert isinstance(client, LlmClient)
        # Client should have schema configured
        assert hasattr(client, "_schema_name")
        assert client._schema_name == "llm1_vascular_response"

    def test_creates_llm2_client(self):
        import os

        os.environ.setdefault("OPENAI_API_KEY", "test-key")
        from django.conf import settings

        settings.OPENAI_API_KEY = "test-key"
        settings.OPENAI_MODEL = "gpt-4o-mini"

        client = create_openai_llm2_client()
        assert isinstance(client, LlmClient)
        assert hasattr(client, "_schema_name")
        assert client._schema_name == "llm2_vascular_response"
