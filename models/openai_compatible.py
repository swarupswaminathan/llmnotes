"""OpenAI-compatible chat adapters (Grok, DeepSeek, Qwen)."""

from __future__ import annotations

import json
from typing import Any

from openai import APIStatusError

from config import SERVER_ERROR_CODES, ServerFailureError
from models.base import BaseAdapter


class OpenAICompatibleAdapter(BaseAdapter):
    """Chat Completions path used by Grok / DeepSeek (and Qwen subclass)."""

    extra_body: dict[str, Any] | None = None

    def generate(
        self,
        note: str,
        cfg: str,
        *,
        schema_properties: dict,
        schema_required: list[str],
        stage: int | None = None,
        verbose: bool = False,
        max_count: int = 0,
        prompt_count: int = 0,
    ) -> dict:
        reasoning_effort = self.ctx.reasoning_effort
        tok_num = self.ctx.tok_num
        is_thinking = reasoning_effort != "none"

        self._maybe_log_params(
            {
                "model": self.ctx.model_name,
                "reasoning_effort": reasoning_effort,
                "is_thinking": is_thinking,
                "temperature": 0.4,
                "max_tokens": tok_num,
                "schema_properties": schema_properties,
                "schema_required": schema_required,
                "stage": stage,
            }
        )

        response_format = self._build_response_format(schema_properties, schema_required)
        create_kwargs: dict[str, Any] = {
            "model": self.ctx.model_name,
            "temperature": 0.4,
            "top_p": 0.9,
            "max_completion_tokens": tok_num,
            "messages": [
                {"role": "system", "content": cfg},
                {"role": "user", "content": note},
            ],
            "response_format": response_format,
        }
        if self.spec.pass_reasoning_effort:
            create_kwargs["reasoning_effort"] = reasoning_effort
        if self.extra_body is not None:
            create_kwargs["extra_body"] = self.extra_body

        try:
            completion = self.client.chat.completions.create(**create_kwargs)
        except APIStatusError as e:
            if e.status_code in SERVER_ERROR_CODES:
                with open(self.ctx.logger_path, "a") as f:
                    f.write(f"{e}\n")
                raise ServerFailureError(f"Server error {e.status_code}: {e}") from e
            raise

        print(f"Raw completion output: {completion}")
        response = completion.choices[0].message.content
        inc_det = completion.choices[0].finish_reason

        explanation = None
        if inc_det == "length":
            print(f"Incomplete — max_tokens hit. Response: {response}")
            print(f"Raw completion output: {completion}")
            if response is not None and response != "" and response != {}:
                print("Attempting to parse incomplete response...")
                response += '"}'
            max_count += 1
            self.ctx.global_max_count += 1
        else:
            try:
                explanation = json.loads(response).get("reasoning", None) if response else None
            except (json.JSONDecodeError, TypeError, AttributeError):
                explanation = None

        if verbose:
            msg = (
                f"model: {self.ctx.model_name}, max_token_hit: {inc_det} "
                f"{max_count} times and {self.ctx.global_max_count} global times, "
                f"Text Response: {response}, Reasoning effort: {reasoning_effort}, "
                f"Thinking: {is_thinking}"
            )
            self._log_verbose(
                f"max_token_hit: {inc_det} {max_count} times and "
                f"{self.ctx.global_max_count} global times, Text Response: {response}"
            )
            print(msg)

        return {
            "response": response,
            "explanation": explanation,
            "selected_notes_indices": None,
            "max_count": max_count,
            "prompt_count": prompt_count,
        }

    def _build_response_format(self, properties: dict, required: list[str]) -> dict:
        schema = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }
        style = self.spec.response_format_style
        if style == "json_object":
            return {
                "type": "json_object",
                "json_object": {
                    "name": "base_schema",
                    "schema": schema,
                    "strict": True,
                },
            }
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "base_schema",
                "schema": schema,
                "strict": True,
            },
        }


class QwenAdapter(OpenAICompatibleAdapter):
    """Qwen always disables thinking via extra_body (never at call sites)."""

    extra_body = {
        "chat_template_kwargs": {
            "enable_thinking": False,
        }
    }
