# GLLaucoMed

Authored by Nicholas Solages, McKnight Vision Research Center - Bascom Palmer Eye Institute

This repository is a framework for running large language models for extraction of medication information
from free-text glaucoma clinical notes. The pipeline addresses four tasks — current topical medications,
change in topical medications, current oral medications, and changes in oral medications.
The pipeline standardizes labels and model outputs and subsequently evaluates model performance.

---

## Pipeline overview

```text
1. Inference     python main.py ...
                 → results/{cvar}/{model}/{effort}/{tok_num}_{ts}/grading_results_{cvar}.xlsx

2. Standardize   python standardization/run.py --grading-results --input <xlsx>
                 → grading_results_{acronym}_standardized.xlsx  (same directory)

3. Evaluate      python evaluate.py --input <standardized.xlsx>
                 → {acronym}_results.txt
```

Supported staged `cvar`s:

| cvar | Acronym | Bilateral | Description |
|------|---------|-----------|-------------|
| `top_meds_staged` | tms | yes (OD/OS) | Current topical meds |
| `top_meds_change_staged` | tmcs | yes (OD/OS) | Topical med changes |
| `oral_meds_staged` | oms | no | Current oral meds |
| `oral_meds_change_staged` | omcs | no | Oral med changes |

---

## Project structure

```text
llmnotes/
├── main.py                 # Inference CLI
├── evaluate.py             # Evaluation CLI
├── config.py               # Env loading, model registry, RunContext
├── configs/
│   └── prompt_config.py    # Prompt template source of truth
├── models/                 # Provider adapters (GPT, Claude, OpenAI-compatible, Qwen)
├── prompts/
│   └── registry.py         # cvar → PromptConfig (schemas, keys, columns)
├── extraction/
│   └── extractor.py        # Parse model JSON; cvar → target columns
├── tasks/
│   ├── staged.py           # Label → validate → revise for one note
│   └── runner.py           # Grading-set loop
├── output/
│   └── results_writer.py   # Xlsx, stats, failure logs
├── evaluation/             # Metrics vs adjudicated labels
├── standardization/    # Standardizer CLI
├── data/                   # Input xlsx (grading, few-shot, adjudicated)
├── results/                # Inference outputs (default RESULTS_ROOT)
├── Dockerfile
├── pyproject.toml / uv.lock
├── .env.example
├── README.md
└── INFERENCE.md            # Inference package details (models, prompts)
```

See [INFERENCE.md](INFERENCE.md) for model/prompt extension guides, and
[standardization/README.md](standardization/README.md) for the
standardizer API.

---

## Setup

Requires **Python 3.11+**.

```bash
# Clone and enter the repo
cd llmnotes   # or your checkout path

# Install with uv (recommended)
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy and fill secrets:

```bash
cp .env.example .env
# Set AZURE_API_KEY, QWEN_API_KEY, endpoints, etc.
```

Optional path overrides (also in `.env`):

- `GRADING_XLSX`, `FEWSHOT_XLSX`, `ADJUDICATED_XLSX`, `RESULTS_ROOT`

Place Excel inputs under `data/` (or point the env vars at your paths).

---

## Inference

```bash
python main.py \
  --model_name qwen \
  --cvar top_meds_staged \
  --tok_num 750 \
  --reasoning_effort none
```

Registered model aliases (see `config.py`): `gpt`, `claude`, `deepseek`,
`grok_n`, `qwen`.

Outputs land under:

```text
results/{cvar}/{deployment_model}/{reasoning_effort}/{tok_num}_{mm-dd_HH:MM}/
```

Artifacts include `grading_results_{cvar}.xlsx`, `prompt_snapshot.txt`,
`params_log.json`, `response_log.txt`, `stats.txt`, and failure trackers.

Full details: [INFERENCE.md](INFERENCE.md).

---

## Standardization

Bridge inference outputs to evaluation column names:

```bash
python standardization/run.py \
  --grading-results \
  --input results/top_meds_staged/.../grading_results_top_meds_staged.xlsx
```

Writes `grading_results_{acronym}_standardized.xlsx` beside the input. For
general Excel column mapping (non-grading mode), see
[standardization/README.md](standardization/README.md).

---

## Evaluation

```bash
python evaluate.py \
  --input path/to/grading_results_tms_standardized.xlsx \
  --adjudicated data/adjudicated_meds_last_final_standardized.xlsx
```

`--cvar` / `--acronym` are optional when the filename is a known standardized
basename. Writes `{acronym}_results.txt` (exact match, Jaccard, Gwet AC1, etc.)
beside the input (override with `--output`).

---

## Docker

```bash
docker build -t gllaucomed .
docker run --env-file .env gllaucomed python main.py --help
```

Secrets are injected at runtime via `--env-file` or `-e`; they are not baked
into the image.

---

## Dependencies

Declared in `pyproject.toml` / `uv.lock`. Core runtime packages include
`openai`, `anthropic`, `pandas`, `openpyxl`, `numpy`, `tqdm`, `rapidfuzz`,
`scipy`, `scikit-learn`, `statsmodels`.
