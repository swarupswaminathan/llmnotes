# SLM\_SWARUP

This repository contains a framework for experimenting with small language models (SLMs) applied to electronic health records (EHR) classification and labeling tasks.

It was adapted from the original [slm\_ehr](https://github.com/bpei-vip/slm_ehr) repository.

---

## Staged meds inference (CLI)

Config-driven replacement for the duplicated staged-meds cells in
`scripts/gemma_refactored copy 2.ipynb`. Only these `cvar`s are supported:
`top_meds_staged`, `top_meds_change_staged`, `oral_meds_staged`,
`oral_meds_change_staged`.

```bash
cp .env.example .env   # set AZURE_API_KEY / QWEN_API_KEY / etc.
python main.py --model_name qwen --cvar top_meds_staged --tok_num 750 --reasoning_effort none
```

Outputs go to `final_results/{cvar}/{model}/{reasoning_effort}/{tok_num}_{timestamp}/`
(same shape as the notebook). See [INFERENCE.md](INFERENCE.md) for package layout
and how to add a model or staged prompt.

---

## 📂 Project Structure

```
SLM_SWARUP/
├── __pycache__/
├── .venv/                   # Python virtual environment
├── labels/                  # Ground-truth labels for evaluation
├── prompts/                 # Prompt templates for inference
├── results/                 # Output results from inference runs
├── .gitignore
├── .python-version
├── config.py                # Configuration for running experiments
├── gemma.ipynb              # Notebook for running Gemma LLM inference
├── git_login.txt            # Git login info (personal use, ignore for public deployment)
├── metrics.ipynb            # Notebook for calculating evaluation metrics
├── pyproject.toml
├── README.md
├── requirements.txt         # Python dependencies
└── uv.lock                  # Lockfile for Python environment reproducibility
```

---

## 🛠️ Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/bpei-vip/slm_ehr.git
cd slm_ehr
```

Or clone your own fork (if working on SLM\_SWARUP locally).

---

### 2. Set up Python Environment (Recommended: Python 3.10+)

If using `uv`:

```bash
uv pip install -r requirements.txt
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 3. Configure Your OpenAI / LLM Provider API Keys

For OpenAI API:

```bash
export OPENAI_API_KEY=your_api_key
```

For Hugging Face models like Gemma (locally or via API), authenticate using your Hugging Face token.

---

## ✅ Running Inference

**Main Notebook for Inference:**

* `gemma.ipynb`

This notebook runs prompts from the `/prompts` folder on your chosen SLM (like Gemma, GPT, etc.), using text data from your `/labels` folder or external source.

**What it does:**

* Loads prompts from config.
* Calls the LLM with each prompt.
* Saves the LLM-generated responses to `/results/`.

---

## ✅ Running Evaluation Metrics

**Metrics Notebook:**

* `metrics.ipynb`

What it calculates:

* Accuracy
* Sensitivity
* Specificity
* Confidence intervals
* Per-class performance
* Confusion matrix

It compares the LLM output (`/results/`) with ground truth (`/labels/`).

---

## ✅ Configuration

The `config.py` file stores:

* Prompt file locations
* Model configurations
* System prompts
* Class labels for each task

You can extend it as needed.

---

## 📊 Tasks Supported

* Disease classification (e.g., Glaucoma staging)
* Multi-label extraction from clinical notes
* Eye-specific diagnosis labeling (OD / OS split)

---

## ✅ Prompts

All prompt templates are inside `/prompts/`.

Each `.txt` file contains instructions given to the LLM (like "Summarize disease severity", "Extract ICD codes", etc.).

---

## 📈 Labels & Results

| Folder      | Purpose                   |
| ----------- | ------------------------- |
| `/labels/`  | Ground truth annotations  |
| `/results/` | LLM-generated predictions |

---

## ✅ Dependencies

Core Python packages:

* `transformers`
* `openai`
* `pandas`
* `numpy`
* `scikit-learn`
* `matplotlib`
* `statsmodels`
* `tqdm`

Full list: see `requirements.txt`.

---

## ✏️ Example Usage Flow

1. **Generate Predictions:**

Run `gemma.ipynb`.

2. **Evaluate Metrics:**

Run `metrics.ipynb`.

3. **Tune Prompts:**

Edit files inside `/prompts/` or modify config.py.

---

## ✅ Future Work
* Fine-tuning small models
---
