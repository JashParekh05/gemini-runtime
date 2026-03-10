"""Token cost estimator. Prices in USD per 1M tokens."""

from __future__ import annotations

# Gemini pricing (approximate, update as needed)
_PRICE_TABLE: dict[str, dict[str, float]] = {
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
}

_DEFAULT_PRICE = {"input": 1.25, "output": 10.0}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = _PRICE_TABLE.get(model, _DEFAULT_PRICE)
    input_cost = (prompt_tokens / 1_000_000) * prices["input"]
    output_cost = (completion_tokens / 1_000_000) * prices["output"]
    return round(input_cost + output_cost, 8)
