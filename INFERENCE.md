# Staged medication inference

Config-driven CLI for three-stage medication extraction from clinical notes
(label → validate → revise). Entry point: `main.py`.

**In scope:** only these four staged `cvar`s:

| cvar | Bilateral | Notes |
|------|-----------|-------|
| `top_meds_staged` | yes (OD/OS) | Current topical meds |
| `top_meds_change_staged` | yes (OD/OS) | Topical change |
| `oral_meds_staged` | no | Current oral meds |
| `oral_meds_change_staged` | no | Oral change |

## Quick start

```bash
cp .env.example .env   # fill in API keys and endpoints
python main.py --model_name qwen --cvar top_meds_staged --tok_num 750 --reasoning_effort none
```

Artifacts land under:

```text
results/{cvar}/{deployment_model_name}/{reasoning_effort}/{tok_num}_{mm-dd_HH:MM}/
```

Override the root with `RESULTS_ROOT` or `--results_root`. Each run writes:

- `prompt_snapshot.txt` — prompts used for the cvar
- `params_log.json` — model call parameters (once per run)
- `response_log.txt` — verbose per-note logs
- `server_failures.txt` — note indices that hit retriable server errors
- `stats.txt` — summary accuracy / drought metrics
- `max_count_tracker.txt` — token/max-count tracker
- `grading_results_{cvar}.xlsx` — full grading frame with AI columns

## Package layout

```text
config.py                 # env + model registry + RunContext
main.py                   # argparse → resolve → run
models/                   # provider adapters (shared BaseAdapter interface)
  base.py
  gpt_client.py           # Azure OpenAI Responses API
  anthropic_client.py     # Claude via AnthropicFoundry
  openai_compatible.py    # Grok / DeepSeek / Qwen chat completions
  registry.py             # create_adapter / create_client
prompts/registry.py       # cvar → PromptConfig (four entries)
extraction/extractor.py   # JSON parse helpers + column/key maps
tasks/staged.py           # generalized staged-meds routine
tasks/runner.py           # grading-set loop
output/results_writer.py  # result artifacts
configs/prompt_config.py  # prompt template source of truth
```

## How a note is processed

For each held-out note (`UsedinExamples` is false):

1. **Task 1 (label)** — extract medication labels + citations as JSON
2. **Task 2 (validate)** — check labels; reasons recorded per eye/field
3. **Task 3 (revise)** — only if validation failed; otherwise skipped

`tasks/staged.py` formats citations/reasoning from the `PromptConfig` field
maps. `extraction/extractor.py` parses the final JSON (direct parse → last
`{...}` block → field regex → failed sentinel).

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

## CLI flags

| Flag | Default | Meaning |
|------|---------|---------|
| `--model_name` | required | Registry alias (`gpt`, `claude`, `deepseek`, `grok_n`, `qwen`) |
| `--cvar` | required | One of the four staged cvars |
| `--tok_num` | 750 | Max tokens for the provider path |
| `--reasoning_effort` | `none` | Validated against the model's allowed set |
| `--grading_xlsx` | from env / `data/` | Grading labels workbook |
| `--fewshot_xlsx` | from env / `data/` | UsedinExamples workbook |
| `--results_root` | `results/` | Output root |

## Downstream steps

After inference, standardize then evaluate (see [README.md](README.md)):

```bash
python med_standardization/run.py --grading-results --input <grading_results_{cvar}.xlsx>
python evaluate.py --input <grading_results_{acronym}_standardized.xlsx>
```

## Dependencies

Runtime needs packages from `pyproject.toml` (`openai`, `anthropic`, `pandas`,
`openpyxl`, `tqdm`, …). Prompt templates live in `configs/prompt_config.py`.
