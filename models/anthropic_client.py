"""Anthropic (Claude via AnthropicFoundry) adapter."""

from __future__ import annotations

import json

from models.base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    """Claude messages.create path with optional adaptive thinking.

    ``reasoning_effort="none"`` disables thinking:
      - temperature 0.4 (else 1.0)
      - thinking ``{"type": "disabled"}`` (else ``"adaptive"``)
      - ``output_config.effort`` forced to ``"high"`` — ``"none"`` is never sent
    Params log still records the requested reasoning_effort and is_thinking.
    With thinking off, explanation falls back to the JSON body's ``reasoning`` field.
    """

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
        # Effort remains "high" if is_thinking = False
        effort_level = reasoning_effort if is_thinking else "high"
        temperature = 1.0 if is_thinking else 0.4
        thinking_param = "adaptive" if is_thinking else "disabled"

        self._maybe_log_params(
            {
                "model": self.ctx.model_name,
                "reasoning_effort": reasoning_effort,
                "is_thinking": is_thinking,
                "thinking_param": thinking_param,
                "effort_level": effort_level,
                "temperature": temperature,
                "max_tokens": tok_num,
                "prompt_count": prompt_count,
                "schema_properties": schema_properties,
                "schema_required": schema_required,
            }
        )

        label_required = [k for k in schema_required if k in ("OD", "OS", "Oral")]
        if not label_required:
            label_required = list(schema_required)

        completion = self.client.messages.create(
            model=self.ctx.model_name,
            temperature=temperature,
            max_tokens=tok_num,
            system=cfg,
            thinking={"type": thinking_param},
            messages=[{"role": "user", "content": note}],
            output_config={
                "effort": effort_level,
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
        inc_det = completion.stop_reason == "max_tokens"
        explanation = None
        if inc_det:
            print(f"Incomplete — max_tokens hit. Response: {text_response}")
            max_count += 1
            self.ctx.global_max_count += 1
        else:
            # Thinking off → thinking_response is usually None; use JSON "reasoning".
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
