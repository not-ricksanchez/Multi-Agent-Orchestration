from underwriting.pricing import cost_usd


def test_one_million_input_tokens_cost_one_dollar():
    assert cost_usd(1_000_000, 0) == 1.0


def test_one_million_output_tokens_cost_two_dollars():
    assert cost_usd(0, 1_000_000) == 2.0


def test_qwen3_4b_costs_half_a_dollar_in_and_one_dollar_out_per_million():
    assert cost_usd(1_000_000, 0, "qwen3:4b") == 0.5
    assert cost_usd(0, 1_000_000, "qwen3:4b") == 1.0


def test_other_models_keep_the_default_price():
    assert cost_usd(1_000_000, 0, "qwen3:8b") == 1.0
    assert cost_usd(0, 1_000_000, "scripted") == 2.0
