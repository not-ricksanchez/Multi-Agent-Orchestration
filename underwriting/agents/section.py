import json

from underwriting.models import ModelResult


def schema_instructions(schema) -> str:
    rendered = json.dumps(schema.model_json_schema(), indent=2)
    return (
        "Respond with one JSON object and no other text. "
        "This schema is the required response:\n"
        f"{rendered}"
    )


def write_section(case: dict, result: ModelResult, schema, key: str) -> dict:
    case["_last_usage"] = {
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }
    parsed = schema.model_validate(result.content)
    case[key] = parsed.model_dump()
    return case
