# Imaginary prices in USD per million tokens: (input, output).
DEFAULT_PRICE = (1.0, 2.0)
MODEL_PRICES = {
    "qwen3:4b": (0.5, 1.0),
    "qwen3:8b": (1.0, 2.0),
}


def cost_usd(input_tokens: int, output_tokens: int, model: str | None = None) -> float:
    input_price, output_price = MODEL_PRICES.get(model or "", DEFAULT_PRICE)
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
