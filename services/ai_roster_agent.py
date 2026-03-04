import json
import os
from typing import Any

from openai import OpenAI
from openai import OpenAIError


class AIRosterAgentError(Exception):
    """Base exception for AI roster generation errors."""


class AIRosterAgentAPIError(AIRosterAgentError):
    """Raised when the OpenAI API call fails."""


class AIRosterAgentInvalidJSONError(AIRosterAgentError):
    """Raised when the model response is not valid JSON."""


def generate_roster(
    staff_data: Any,
    shift_data: Any,
    availability_data: Any,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """
    Generate roster suggestions using OpenAI.

    This function does not write to the database. It only returns suggested roster data.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AIRosterAgentAPIError("Missing OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=api_key)

    prompt = (
        "You are a workforce scheduling assistant. "
        "Create roster suggestions for the requested date range based on the given data. "
        "Return JSON only with no markdown or extra text.\\n\\n"
        f"Date range: {start_date} to {end_date}\\n\\n"
        "Staff data:\\n"
        f"{json.dumps(staff_data, ensure_ascii=False)}\\n\\n"
        "Shift data:\\n"
        f"{json.dumps(shift_data, ensure_ascii=False)}\\n\\n"
        "Availability data:\\n"
        f"{json.dumps(availability_data, ensure_ascii=False)}\\n\\n"
        "Output requirements:\\n"
        "- Return a top-level JSON object.\\n"
        "- Include a key named 'roster_suggestions' containing an array of assignments.\\n"
        "- Each assignment should include staff identifier, shift identifier, date, and a short rationale.\\n"
        "- Include a key named 'notes' containing an array of constraints or assumptions."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You generate valid JSON only.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={"type": "json_object"},
        )
    except OpenAIError as exc:
        raise AIRosterAgentAPIError(f"OpenAI API request failed: {exc}") from exc
    except Exception as exc:
        raise AIRosterAgentAPIError(f"Unexpected OpenAI client error: {exc}") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise AIRosterAgentInvalidJSONError("OpenAI returned an empty response.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIRosterAgentInvalidJSONError(
            f"OpenAI returned invalid JSON: {exc.msg}"
        ) from exc

    if not isinstance(parsed, dict):
        raise AIRosterAgentInvalidJSONError(
            "OpenAI JSON response must be a top-level object."
        )

    return parsed
