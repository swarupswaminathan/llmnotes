# Staged EHR / SLM meds inference

Config-driven CLI that replaces the duplicated `get_model_response` /
`run_staged_meds` cells in `scripts/gemma_refactored copy 2.ipynb`.

**In scope:** only these four staged `cvar`s:

| cvar | bilateral | notes |
|------|-----------|-------|
| `top_meds_staged` | yes (OD/OS) | topical meds |
| `top_meds_change_staged` | yes (OD/OS) | topical change |
| `oral_meds_staged` | no | oral meds |
| `oral_meds_change_staged` | no | oral change |

## Quick start

```bash
cp .env.example .env   # fill in API keys
python main.py --model_name qwen --cvar top_meds_staged --tok_num 750 --reasoning_effort none
```

Artifacts land under:

```text
final_results/{cvar}/{deployment_model_name}/{reasoning_effort}/{tok_num}_{mm-dd_HH:MM}/
```

Same subdirectory shape as the notebook (`final_results/` root; override with
`RESULTS_ROOT` or `--results_root`). Writes `prompt_snapshot.txt`,
`params_log.json`, `response_log.txt`, `server_failures.txt`, `stats.txt`,
`max_count_tracker.txt`, and `grading_results_{cvar}.xlsx`.

## Layout

```text
config.py                 # env + model registry metadata
main.py                   # argparse → resolve → run
models/                   # provider adapters (one interface)
prompts/registry.py       # cvar → PromptConfig (four entries)
extraction/extractor.py   # Cell 24 extractor (four cvars)
tasks/staged.py           # one generalized staged-meds routine
tasks/runner.py           # grading loop (Cell 28)
output/results_writer.py  # result artifacts
configs/prompt_config.py  # prompt template source of truth
```

## How to add a model

1. Add a `ModelSpec` in `config.py` (`MODEL_REGISTRY`) with alias, provider type,
   adapter name, deployment string, allowed `reasoning_effort` values, and env
   var names for key/endpoint.
2. If the provider needs new SDK quirks, add an adapter under `models/` that
   implements `generate(...)` and register it in `models/registry.py`
   `_ADAPTER_CLASSES`. Do **not** add `if model == ...` branches in the runner.

## How to add a staged prompt

1. Add the staged prompt dict (`task1_label` / `task2_validate` / `task3_revise`)
   to `configs/prompt_config.py`.
2. Add one `PromptConfig` entry in `prompts/registry.py` (schemas, label keys,
   citation field maps, target columns).
3. Add matching entries in `extraction/extractor.py` (`CONFIG_TO_COLUMN`,
   `CVAR_OUTPUT_KEYS`) if the output keys / columns are new.

No changes to `tasks/staged.py` or `main.py` dispatch logic should be required.

## Dependencies

Runtime needs `openai`, `anthropic`, `pandas`, `openpyxl`, `tqdm` (already used
by the notebook environment). Prompt templates live in `configs/prompt_config.py`.
