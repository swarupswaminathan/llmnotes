# fda_lookup.py

import requests

from .utils import normalize_whitespace


def lookup_openfda_name(token: str) -> str | None:
    token = normalize_whitespace(token.lower())
    if not token:
        return None

    searches = [
        f'openfda.generic_name:"{token}"',
        f'openfda.brand_name:"{token}"',
        f'openfda.substance_name:"{token}"',
    ]

    for search in searches:
        try:
            resp = requests.get(
                "https://api.fda.gov/drug/drugsfda.json",
                params={"search": search, "limit": 1},
                timeout=2,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                continue

            openfda = results[0].get("openfda", {}) or {}

            generic_names = openfda.get("generic_name") or []
            if generic_names:
                return normalize_whitespace(generic_names[0].lower())

            substance_names = openfda.get("substance_name") or []
            if substance_names:
                val = substance_names[0].lower().replace(";", "/")
                return normalize_whitespace(val)

        except Exception:
            return None

    return None