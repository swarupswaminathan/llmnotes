# Medication Label Standardization
Authored by Janet Kang, University of Miami Miller School of Medicine

This repository standardizes free-text topical and oral glaucoma medication labels into a consistent format for downstream review and analysis.

It includes:

* a script for **current medication** labels
* a script for **medication change** labels
* a **combined wrapper** that routes to the correct standardizer
* a **command-line Excel runner** for batch processing
* **pytest test files** for current and change standardization

## Repository structure

```text
med_standardization/
├── src/
│   ├── current_med_standardization.py
│   ├── change_med_standardization.py
│   ├── combined_med_standardization.py
│   ├── constants.py
│   ├── fda_lookup.py
│   ├── matching.py
│   ├── models.py
│   ├── parser.py
│   ├── utils.py
│   └── __init__.py
├── run.py
├── tests/
│   ├── test_med_current.py
│   └── test_med_change.py
└── README.md
```

## What each script does

### `src/current_med_standardization.py`

Standardizes **current medication lists**.

Use this when the input is a list of medications the patient is currently taking, for example:

* `Lumigan QHS, Cosopt PF 2x daily`
* `Diamox BID, methazolamide 50 three times a day`

Main function:

```python
standardize_medication_list(med_list: str, med_list_type: str) -> dict
```

Accepted `med_list_type` values:

* `"OD"`
* `"OS"`
* `"oral"`

Example:

```python
from src.current_med_standardization import standardize_medication_list

result = standardize_medication_list("Lumigan QHS, Cosopt PF 2x daily", "OD")
print(result["standardized_medication_list"])
```

This script can be run from the directory root.
Example:

```
python -m src.current_med_standardization
```

### `src/change_med_standardization.py`

Standardizes **medication change labels**.

Use this when the input describes medication actions such as:

* Start
* Stop
* Increase
* Decrease
* synonyms such as Add, Begin, Discontinue, Reduce, etc.

Examples:

* `Start Lumigan nightly, Stop Alphagan, Increase Cosopt to 3x daily`
* `Switch timolol BID to Cosopt BID`
* `Add Diamox 250 BID and Neptazane 50 BID`

Main function:

```python
standardize_medication_change_list(med_list: str, med_list_type: str) -> dict
```

Accepted `med_list_type` values:

* `"OD"`
* `"OS"`
* `"oral"`

Example:

```python
from src.change_med_standardization import standardize_medication_change_list

result = standardize_medication_change_list(
    "Start Lumigan nightly, Stop Alphagan, Increase Cosopt to 3x daily",
    "OD",
)
print(result["standardized_medication_change_list"])
```

This script can be run from the directory root.
Example:

```
python -m src.change_med_standardization
```

### `src/combined_med_standardization.py`

Provides a **unified interface** for current and change labels.

Main function:

```python
standardize_medication_label(
    medication_string: str,
    medication_type: str,
    label_type: str,
) -> dict
```

Accepted `medication_type` values:

* `"OD"`
* `"OS"`
* `"oral"`

Accepted `label_type` values:

* `"current"`
* `"change"`

Example:

```python
from src.combined_med_standardization import standardize_medication_label

result = standardize_medication_label(
    medication_string="Diamox BID",
    medication_type="oral",
    label_type="current",
)
print(result)
```

Use the combined wrapper when you want one entry point and do not want to manually decide whether to call the current or change script.

### `run.py`

Reads an Excel file, standardizes one or more medication columns, and writes the results to a new Excel workbook.

This is the main script to use for **batch processing**.

## Returned output format

### Current medication script

`standardize_medication_list(...)` returns a dictionary like:

```python
{
  "input_type": "OD",
  "raw_input": "Lumigan QHS, Cosopt PF 2x daily",
  "standardized_medication_list": "bimatoprost QHS, dorzolamide/timolol PF BID",
  "parsed_items": [...],
  "manual_review_required": False,
}
```

### Change medication script

`standardize_medication_change_list(...)` returns a dictionary like:

```python
{
  "input_type": "OD",
  "raw_input": "Start Lumigan nightly, Stop Alphagan",
  "standardized_medication_change_list": "Start bimatoprost QHS, Stop brimonidine",
  "parsed_items": [...],
  "manual_review_required": False,
}
```

## Batch Excel processing

## What `run.py` expects

The script accepts:

* an input Excel file
* an output Excel file
* one or more command-line arguments telling it which columns contain medication labels

You can run it with only one column or with multiple columns.

Supported column arguments:

* `--current-od-col`
* `--current-os-col`
* `--current-oral-col`
* `--change-od-col`
* `--change-os-col`
* `--change-oral-col`
* `--current_topical_col_json`
* `--current_oral_col_json`
* `--change_topical_col_json`
* `--change_oral_col_json`

Optional:

* `--sheet-name` to choose a sheet by name or index
* `--use-combined-wrapper` to route all processing through `standardize_medication_label(...)`

## Example commands

### Example 1: current oral medications only

```bash
python run.py \
  --input train_data.xlsx \
  --output train_data_standardized.xlsx \
  --current-oral-col "Current Oral Meds"
```

### Example 2: current topical OD only

```bash
python run.py \
  --input train_data.xlsx \
  --output train_data_standardized.xlsx \
  --current-od-col "Topical Meds OD"
```

### Example 3: change topical OD and OS

```bash
python run.py \
  --input val_data.xlsx \
  --output val_data_standardized.xlsx \
  --change-od-col "Change in Topical Treatment OD" \
  --change-os-col "Change in Topical Treatment OS"
```

### Example 4: multiple current and change columns together

```bash
python run.py \
  --input val_data.xlsx \
  --output val_data_standardized.xlsx \
  --current-od-col "Topical Meds OD" \
  --current-os-col "Topical Meds OS" \
  --current-oral-col "Oral Meds" \
  --change-od-col "Change in Topical Treatment OD" \
  --change-os-col "Change in Topical Treatment OS" \
  --change-oral-col "Change in Oral Meds"
```

## Output columns created by `run.py`

For each input column, the script appends four output columns:

* `<input_col>__standardized_<label_type>_<med_type>_output`
* `<input_col>__standardized_<label_type>_<med_type>_manual_review_required`
* `<input_col>__standardized_<label_type>_<med_type>_parsed_items`
* `<input_col>__standardized_<label_type>_<med_type>_error`

Example:

If you pass:

```bash
--current-od-col "Topical Meds OD"
```

then the output workbook will contain columns similar to:

```text
Topical Meds OD__standardized_current_od_output
Topical Meds OD__standardized_current_od_manual_review_required
Topical Meds OD__standardized_current_od_parsed_items
Topical Meds OD__standardized_current_od_error
```

## When to use each script

### Use `current_med_standardization.py` when:

* the text describes the patient’s current medication list
* there is no action phrase like Start, Stop, Increase, or Decrease

### Use `change_med_standardization.py` when:

* the text describes medication changes
* the text includes action phrases such as Start, Stop, Increase, Decrease, Switch, or synonyms

### Use `combined_med_standardization.py` when:

* you want one interface for both current and change labels
* you already know the medication type and the label type

### Use `run.py` when:

* you want to process an entire Excel sheet
* you want to standardize one or more columns at once
* you want a new Excel file containing both the original inputs and the standardized outputs


## Tests

The repository includes two pytest files:

* `tests/test_med_current.py`
* `tests/test_med_change.py`

### `tests/test_med_current.py`

Tests the current-medication standardization logic.

It covers cases such as:

* brand to generic conversion
* frequency normalization
* prostaglandin QHS conversion
* PF suffix placement
* percentage removal for prednisolone
* oral medication normalization
* exclusion of artificial tears
* error and manual-review cases

Run it with:

```bash
python -m pytest tests/test_med_current.py
```

### `tests/test_med_change.py`

Tests the medication-change standardization logic.

It covers cases such as:

* typo correction
* removal of extra verbiage
* laterality unknown placeholder handling
* brand to generic conversion
* XE/XR handling
* combination drop ordering
* PF suffix placement
* autologous serum tears normalization
* prostaglandin frequency rules
* oral change standardization
* synonym handling for change phrases
* split rules for `and`
* `switch` phrase handling

Run it with:

```bash
python -m pytest tests/test_med_change.py
```

### Run all tests

```bash
python -m pytest tests/
```

## Test logging

Both test files use Python logging.

They print useful input and output information to the console and also write persistent logs to file.

Common log files:

* `test_med_standardizer.log`
* `test_med_change_standardizer.log`

