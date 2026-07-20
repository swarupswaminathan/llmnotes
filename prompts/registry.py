"""Task/prompt registry for the four staged meds cvars."""

from __future__ import annotations

from dataclasses import dataclass, field

import configs.prompt_config as prompt_config


@dataclass(frozen=True)
class StageSchema:
    properties: dict[str, dict[str, str]]
    required: list[str]


@dataclass
class PromptConfig:
    """Everything needed to run one staged cvar without branching in the runner."""

    cvar: str
    bilateral: bool
    target_columns: list[str] | str
    output_keys: list[str]
    prompts: dict[str, str]
    # stage number -> schema (stages 1 and 3 often share)
    stage_schemas: dict[int, StageSchema]
    label_keys: list[str]
    # JSON keys used for citations/reasoning on extract+revise stages
    citation_json_keys: dict[str, str]  # label_key -> json field
    citation_label: str  # e.g. "Citation" or "Citation and Reasoning"
    # Optional separate reasoning field (top_meds_staged only)
    reasoning_json_key: str | None = None
    # Validation-stage reason field suffix / key pattern
    validation_reason_keys: dict[str, str] = field(default_factory=dict)
    # idx logging threshold; None = always log when verbose
    log_idx_limit: int | None = None
    # How task2 input is assembled (field names in the prompt blob)
    t2_includes_reasoning: bool = False

    def schema_for_stage(self, stage: int) -> StageSchema:
        if stage not in self.stage_schemas:
            raise KeyError(f"{self.cvar}: no schema for stage {stage}")
        return self.stage_schemas[stage]

    def failed_labels(self) -> dict[str, str]:
        return {k: "None (failed)" for k in self.label_keys}

    def none_labels(self) -> dict[str, str]:
        return {k: "None" for k in self.label_keys}


def _str_prop() -> dict[str, str]:
    return {"type": "string"}

_TOP_MEDS_EXTRACT = StageSchema(
    properties={
        "OD": _str_prop(),
        "OS": _str_prop(),
        "OD_citation": _str_prop(),
        "OS_citation": _str_prop(),
        "reasoning": _str_prop(),
    },
    required=["OD", "OS", "OD_citation", "OS_citation", "reasoning"],
)
_TOP_MEDS_VALIDATE = StageSchema(
    properties={
        "OD": _str_prop(),
        "OS": _str_prop(),
        "OD_reason": _str_prop(),
        "OS_reason": _str_prop(),
    },
    required=["OD", "OS", "OD_reason", "OS_reason"],
)

_TOP_CHANGE_EXTRACT = StageSchema(
    properties={
        "OD": _str_prop(),
        "OS": _str_prop(),
        "OD_reasoning": _str_prop(),
        "OS_reasoning": _str_prop(),
    },
    required=["OD", "OS", "OD_reasoning", "OS_reasoning"],
)
_TOP_CHANGE_VALIDATE = StageSchema(
    properties={
        "OD": _str_prop(),
        "OS": _str_prop(),
        "OD_reason": _str_prop(),
        "OS_reason": _str_prop(),
    },
    required=["OD", "OS", "OD_reason", "OS_reason"],
)

_ORAL_SCHEMA = StageSchema(
    properties={
        "Oral": _str_prop(),
        "Oral_reasoning": _str_prop(),
    },
    required=["Oral", "Oral_reasoning"],
)


def _build_registry() -> dict[str, PromptConfig]:
    return {
        "top_meds_staged": PromptConfig(
            cvar="top_meds_staged",
            bilateral=True,
            target_columns=["Topical Meds OD", "Topical Meds OS"],
            output_keys=["OD", "OS"],
            prompts=prompt_config.top_meds_staged,
            stage_schemas={1: _TOP_MEDS_EXTRACT, 2: _TOP_MEDS_VALIDATE, 3: _TOP_MEDS_EXTRACT},
            label_keys=["OD", "OS"],
            citation_json_keys={"OD": "OD_citation", "OS": "OS_citation"},
            citation_label="Citation",
            reasoning_json_key="reasoning",
            validation_reason_keys={"OD": "OD_reason", "OS": "OS_reason"},
            log_idx_limit=None,
            t2_includes_reasoning=True,
        ),
        "top_meds_change_staged": PromptConfig(
            cvar="top_meds_change_staged",
            bilateral=True,
            target_columns=["Change in Topical Treatment OD", "Change in Topical Treatment OS"],
            output_keys=["OD", "OS"],
            prompts=prompt_config.top_meds_change_staged,
            stage_schemas={
                1: _TOP_CHANGE_EXTRACT,
                2: _TOP_CHANGE_VALIDATE,
                3: _TOP_CHANGE_EXTRACT,
            },
            label_keys=["OD", "OS"],
            citation_json_keys={"OD": "OD_reasoning", "OS": "OS_reasoning"},
            citation_label="Citation and Reasoning",
            reasoning_json_key=None,
            validation_reason_keys={"OD": "OD_reason", "OS": "OS_reason"},
            log_idx_limit=None,
            t2_includes_reasoning=False,
        ),
        "oral_meds_staged": PromptConfig(
            cvar="oral_meds_staged",
            bilateral=False,
            target_columns="Oral Meds",
            output_keys=["Oral"],
            prompts=prompt_config.oral_meds_staged,
            stage_schemas={1: _ORAL_SCHEMA, 2: _ORAL_SCHEMA, 3: _ORAL_SCHEMA},
            label_keys=["Oral"],
            citation_json_keys={"Oral": "Oral_reasoning"},
            citation_label="Citation and Reasoning",
            reasoning_json_key=None,
            validation_reason_keys={"Oral": "Oral_reasoning"},
            log_idx_limit=None,
            t2_includes_reasoning=False,
        ),
        "oral_meds_change_staged": PromptConfig(
            cvar="oral_meds_change_staged",
            bilateral=False,
            target_columns="Change in Oral Meds",
            output_keys=["Oral"],
            prompts=prompt_config.oral_meds_change_staged,
            stage_schemas={1: _ORAL_SCHEMA, 2: _ORAL_SCHEMA, 3: _ORAL_SCHEMA},
            label_keys=["Oral"],
            citation_json_keys={"Oral": "Oral_reasoning"},
            citation_label="Citation and Reasoning",
            reasoning_json_key=None,
            validation_reason_keys={"Oral": "Oral_reasoning"},
            log_idx_limit=None,
            t2_includes_reasoning=False,
        ),
    }


PROMPT_REGISTRY: dict[str, PromptConfig] = _build_registry()


def get_prompt_config(cvar: str) -> PromptConfig:
    if cvar not in PROMPT_REGISTRY:
        raise ValueError(
            f"Unknown or out-of-scope cvar '{cvar}'. "
            f"Supported: {list(PROMPT_REGISTRY.keys())}"
        )
    return PROMPT_REGISTRY[cvar]


def list_cvars() -> list[str]:
    return list(PROMPT_REGISTRY.keys())
