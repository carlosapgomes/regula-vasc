"""Tests for JSON parser."""

from apps.pipeline.json_parser import LlmJsonParseError, decode_llm_json_object


class TestDecodeJsonObject:
    def test_parses_plain_json(self):
        result = decode_llm_json_object('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extracts_from_markdown_code_block(self):
        response = '```json\n{"suggestion": "accept"}\n```'
        result = decode_llm_json_object(response)
        assert result == {"suggestion": "accept"}

    def test_handles_trailing_commas(self):
        response = '{"items": [1, 2, 3,], "flag": true,}'
        result = decode_llm_json_object(response)
        assert result == {"items": [1, 2, 3], "flag": True}

    def test_extracts_embedded_json_from_text(self):
        response = 'Here is some text before {"key": "embedded"} and some text after'
        result = decode_llm_json_object(response)
        assert result == {"key": "embedded"}

    def test_raises_on_unparseable_text(self):
        try:
            decode_llm_json_object("no json here at all")
            assert False, "Should have raised"
        except LlmJsonParseError:
            pass

    def test_parses_nested_structures(self):
        response = '{"outer": {"inner": [1, 2, 3]}}'
        result = decode_llm_json_object(response)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_handles_multiple_markdown_blocks(self):
        response = '```\n{"first": 1}\n```\nExtra text\n```json\n{"second": 2}\n```'
        result = decode_llm_json_object(response)
        assert result == {"first": 1}
