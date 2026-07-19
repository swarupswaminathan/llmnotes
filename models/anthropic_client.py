"""Anthropic (Claude via AnthropicFoundry) adapter."""

from __future__ import annotations

import json

from models.base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    """Claude messages.create path (Cells 21–23)."""

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
                "effort_level": reasoning_effort if is_thinking else "high",
                "temperature": 1.0 if is_thinking else 0.4,
                "max_tokens": tok_num,
                "prompt_count": prompt_count,
                "schema_properties": schema_properties,
                "schema_required": schema_required,
                "stage": stage,
            }
        )

        # Notebook Claude cells only require primary label keys (OD/OS or Oral).
        label_required = [k for k in schema_required if k in ("OD", "OS", "Oral")]
        if not label_required:
            label_required = list(schema_required)

        completion = self.client.messages.create(
            model=self.ctx.model_name,
            temperature=1.0 if is_thinking else 0.4,
            max_tokens=tok_num,
            system=cfg,
            thinking={"type": "adaptive"} if is_thinking else {"type": "disabled"},
            messages=[{"role": "user", "content": note}],
            output_config={
                "effort": reasoning_effort if is_thinking else "high",
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": schema_properties,
                        "required": label_required,
                        "additionalProperties": False,
                    },
                },
            },
        )
        print(f"Raw completion output: {completion}")

        text_response = next((b.text for b in completion.content if b.type == "text"), None)
        thinking_response = next(
            (b.thinking for b in completion.content if b.type == "thinking"), None
        )

        explanation = None
        if completion.stop_reason == "max_tokens":
            print(f"Incomplete — max_tokens hit. Response: {text_response}")
            max_count += 1
            self.ctx.global_max_count += 1
        else:
            if thinking_response:
                explanation = thinking_response
            elif text_response:
                try:
                    explanation = json.loads(text_response).get("reasoning")
                except (json.JSONDecodeError, TypeError, AttributeError):
                    explanation = None

        response = text_response or thinking_response

        if verbose:
            print(
                f"model: {self.ctx.model_name}, max_token_hit: {completion.stop_reason}, "
                f"Text Response: {text_response}, Thinking Response: {thinking_response}, "
                f"Reasoning effort: {reasoning_effort}, Thinking: {is_thinking}"
            )

        return {
            "response": response,
            "explanation": explanation,
            "selected_notes_indices": None,
            "max_count": max_count,
            "prompt_count": prompt_count,
        }
