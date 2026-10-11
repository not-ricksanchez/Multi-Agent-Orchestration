def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * 1 + output_tokens * 2) / 1_000_000
