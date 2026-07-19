"""GPT / Azure OpenAI Responses API adapter."""

from __future__ import annotations

from openai import APIStatusError
from openai.types.responses import ResponseReasoningItem

from config import SERVER_ERROR_CODES, ServerFailureError
from models.base import BaseAdapter


class GptAdapter(BaseAdapter):
    """GPT Responses API path (Cell 20), with stage schemas from task config."""

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
                "thinking_param": "adaptive" if is_thinking else "disabled",
                "temperature": 1.0 if is_thinking else 0.4,
                "max_tokens": tok_num,
                "prompt_count": prompt_count,
                "schema_properties": schema_properties,
                "schema_required": schema_required,
                "stage": stage,
            }
        )

        create_kwargs = {
            "model": self.ctx.model_name,
            "temperature": 0.4 if reasoning_effort == "none" else None,
            "top_p": 0.9 if reasoning_effort == "none" else None,
            "max_output_tokens": tok_num,
            "reasoning": {
                "effort": reasoning_effort,
                "summary": "concise",
            },
            "input": [
                {"role": "developer", "content": cfg},
                {"role": "user", "content": note},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "base_schema",
                    "schema": {
                        "type": "object",
                        "properties": schema_properties,
                        "required": schema_required,
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            },
        }

        try:
            completion = self.client.responses.create(**create_kwargs)
        except APIStatusError as e:
            if e.status_code in SERVER_ERROR_CODES:
                with open(self.ctx.logger_path, "a") as f:
                    f.write(f"{e}\n")
                raise ServerFailureError(f"Server error {e.status_code}: {e}") from e
            raise

        explanation = None
        print(f"Raw completion output: {completion}")
        if completion.output:
            try:
                if len(completion.output) > 0 and isinstance(
                    completion.output[0], ResponseReasoningItem
                ):
                    explanation = (
                        completion.output[0].summary[0].text
                        or completion.output[0].content
                    )
            except Exception:
                explanation = None

        response = completion.output_text
        inc_det = completion.incomplete_details
        if inc_det:
            print(f"Incomplete details: {inc_det}, Response: {response}")
            if inc_det.reason == "max_prompt_tokens":
                prompt_count += 1
            if inc_det.reason == "max_output_tokens":
                print(f"Incomplete details: {inc_det}")
                max_count += 1
                self.ctx.global_max_count += 1

        if verbose:
            print(
                f"model: {self.ctx.model_name}, max_token_hit: {max_count}, "
                f"Text Response: {response}, Explantion: {explanation}, "
                f"Reasoning effort: {reasoning_effort}, Thinking: {is_thinking}"
            )
            with open(self.ctx.logger_path, "a") as f:
                f.write(
                    f"max_token_hit: {inc_det} {max_count} times, Text Response: {response}\n"
                )

        return {
            "response": response,
            "explanation": explanation,
            "selected_notes_indices": None,
            "max_count": max_count,
            "prompt_count": prompt_count,
        }
