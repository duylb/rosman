import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from openai import OpenAI
from openai import OpenAIError


class AIRosterAgentError(Exception):
    """Base exception for AI roster generation errors."""


class AIRosterAgentAPIError(AIRosterAgentError):
    """Raised when the OpenAI API call fails."""


class AIRosterAgentInvalidJSONError(AIRosterAgentError):
    """Raised when the model response is not valid JSON."""


logger = logging.getLogger(__name__)


def _parse_iso_date(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _daypart_from_shift(shift: dict[str, Any]) -> str:
    name = str(shift.get("name") or "").lower()
    start_time = str(shift.get("start_time") or "")
    hour = 12
    if ":" in start_time:
        try:
            hour = int(start_time.split(":")[0])
        except ValueError:
            hour = 12
    if "lunch" in name or 9 <= hour < 16:
        return "lunch"
    return "dinner"


def summarize_staff(staff_list: Any) -> dict[str, Any]:
    rows = staff_list if isinstance(staff_list, list) else []
    roles: dict[str, int] = {}
    full_time = 0
    part_time = 0

    for row in rows:
        if not isinstance(row, dict):
            continue

        role = str(row.get("role") or "unknown").strip().lower() or "unknown"
        roles[role] = roles.get(role, 0) + 1

        employment_type = str(row.get("employment_type") or "").strip().lower()
        if employment_type in {"full_time", "full-time", "ft"}:
            full_time += 1
        elif employment_type in {"part_time", "part-time", "pt"}:
            part_time += 1
        elif bool(row.get("full_time") or row.get("is_full_time")):
            full_time += 1
        else:
            part_time += 1

    return {
        "total_staff": len([row for row in rows if isinstance(row, dict)]),
        "roles": roles,
        "full_time": full_time,
        "part_time": part_time,
    }


def summarize_availability(
    availability_records: Any,
    start_date: str,
    end_date: str,
    total_staff: int,
) -> dict[str, int]:
    rows = availability_records if isinstance(availability_records, list) else []
    start_obj = _parse_iso_date(start_date)
    end_obj = _parse_iso_date(end_date)
    if start_obj is None or end_obj is None or end_obj < start_obj:
        return {}

    blocked_by_day: dict[date, set[int]] = {}
    current = start_obj
    while current <= end_obj:
        blocked_by_day[current] = set()
        current += timedelta(days=1)

    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().lower()
        if status not in {"leave", "unavailable", "off"}:
            continue

        staff_id_raw = row.get("staff_id")
        try:
            staff_id = int(staff_id_raw)
        except (TypeError, ValueError):
            continue

        block_start = _parse_iso_date(row.get("start_date")) or start_obj
        block_end = _parse_iso_date(row.get("end_date")) or end_obj
        if block_end < start_obj or block_start > end_obj:
            continue

        day = max(block_start, start_obj)
        last = min(block_end, end_obj)
        while day <= last:
            blocked_by_day[day].add(staff_id)
            day += timedelta(days=1)

    summary: dict[str, int] = {}
    current = start_obj
    while current <= end_obj:
        day_name = current.strftime("%A").lower()
        available = max(total_staff - len(blocked_by_day[current]), 0)
        summary[f"{day_name}_lunch"] = available
        summary[f"{day_name}_dinner"] = available
        current += timedelta(days=1)

    return summary


def summarize_sales(sales_records: Any) -> dict[str, float | int]:
    rows = sales_records if isinstance(sales_records, list) else []
    if not rows:
        return {
            "avg_daily_revenue": 0.0,
            "avg_lunch_revenue": 0.0,
            "avg_dinner_revenue": 0.0,
            "avg_bookings": 0,
            "avg_walkins": 0,
        }

    revenue_total = 0.0
    lunch_total = 0.0
    dinner_total = 0.0
    bookings_total = 0
    walkins_total = 0
    count = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        count += 1
        revenue_total += float(row.get("daily_revenue", row.get("revenue", 0.0)) or 0.0)
        lunch_total += float(row.get("lunch_revenue", 0.0) or 0.0)
        dinner_total += float(row.get("dinner_revenue", 0.0) or 0.0)
        bookings_total += int(row.get("bookings", 0) or 0)
        walkins_total += int(row.get("walkins", 0) or 0)

    if count == 0:
        return {
            "avg_daily_revenue": 0.0,
            "avg_lunch_revenue": 0.0,
            "avg_dinner_revenue": 0.0,
            "avg_bookings": 0,
            "avg_walkins": 0,
        }

    return {
        "avg_daily_revenue": round(revenue_total / count, 2),
        "avg_lunch_revenue": round(lunch_total / count, 2),
        "avg_dinner_revenue": round(dinner_total / count, 2),
        "avg_bookings": int(round(bookings_total / count)),
        "avg_walkins": int(round(walkins_total / count)),
    }


def summarize_shifts(shift_list: Any) -> dict[str, Any]:
    rows = shift_list if isinstance(shift_list, list) else []
    shift_summary: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        shift_summary.append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "start_time": row.get("start_time"),
                "end_time": row.get("end_time"),
                "required_staff": int(row.get("required_staff", 0) or 0),
                "daypart": _daypart_from_shift(row),
            }
        )
    return {
        "total_shift_templates": len(shift_summary),
        "shift_templates": shift_summary,
    }


def _extract_sales_records(shift_data: Any) -> list[dict[str, Any]]:
    if isinstance(shift_data, dict):
        rows = shift_data.get("sales_records", [])
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _build_prompt(
    staff_summary: dict[str, Any],
    availability_summary: dict[str, Any],
    sales_summary: dict[str, Any],
    shift_summary: dict[str, Any],
    start_date: str,
    end_date: str,
) -> str:
    return (
        f"Date range: {start_date} to {end_date}\n\n"
        "Staff summary:\n"
        f"{json.dumps(staff_summary, ensure_ascii=False)}\n\n"
        "Availability summary:\n"
        f"{json.dumps(availability_summary, ensure_ascii=False)}\n\n"
        "Sales forecast summary:\n"
        f"{json.dumps(sales_summary, ensure_ascii=False)}\n\n"
        "Shift summary:\n"
        f"{json.dumps(shift_summary, ensure_ascii=False)}\n\n"
        "Task:\n"
        "Generate a weekly roster demand recommendation.\n"
        "Return JSON with required staff counts per shift.\n\n"
        "Example output format:\n"
        '{\n'
        '  "monday_lunch": {"servers": 4, "bartenders": 1},\n'
        '  "monday_dinner": {"servers": 6, "bartenders": 2}\n'
        "}\n"
    )


def _default_demand_recommendation(
    staff_summary: dict[str, Any],
    shift_summary: dict[str, Any],
    start_date: str,
    end_date: str,
) -> dict[str, dict[str, int]]:
    start_obj = _parse_iso_date(start_date)
    end_obj = _parse_iso_date(end_date)
    if start_obj is None or end_obj is None or end_obj < start_obj:
        return {}

    roles = staff_summary.get("roles", {})
    role_counts = {str(k): int(v) for k, v in roles.items() if isinstance(v, int)}
    total_roles = sum(role_counts.values())
    if total_roles <= 0:
        role_counts = {"servers": 1}
        total_roles = 1

    shift_templates = shift_summary.get("shift_templates", [])
    if not isinstance(shift_templates, list):
        shift_templates = []

    default_by_daypart = {"lunch": 0, "dinner": 0}
    for shift in shift_templates:
        if not isinstance(shift, dict):
            continue
        daypart = str(shift.get("daypart") or "lunch")
        default_by_daypart[daypart] = max(
            default_by_daypart.get(daypart, 0),
            int(shift.get("required_staff", 0) or 0),
        )

    recommendation: dict[str, dict[str, int]] = {}
    current = start_obj
    while current <= end_obj:
        day_name = current.strftime("%A").lower()
        for daypart in ("lunch", "dinner"):
            required = max(default_by_daypart.get(daypart, 0), 1)
            role_alloc: dict[str, int] = {}
            assigned = 0
            role_items = list(role_counts.items())
            for index, (role_name, count) in enumerate(role_items):
                if index == len(role_items) - 1:
                    role_alloc[role_name] = max(required - assigned, 0)
                else:
                    portion = int(round(required * (count / total_roles)))
                    role_alloc[role_name] = portion
                    assigned += portion
            recommendation[f"{day_name}_{daypart}"] = role_alloc
        current += timedelta(days=1)
    return recommendation


def _fallback_result(
    staff_summary: dict[str, Any],
    shift_summary: dict[str, Any],
    start_date: str,
    end_date: str,
    error: str,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "demand_recommendation": _default_demand_recommendation(
            staff_summary=staff_summary,
            shift_summary=shift_summary,
            start_date=start_date,
            end_date=end_date,
        ),
        "roster_suggestions": [],
        "notes": ["Fallback logic used due to AI output failure."],
    }


def _normalize_result(parsed: dict[str, Any]) -> dict[str, Any]:
    if isinstance(parsed.get("roster_suggestions"), list):
        parsed.setdefault("success", True)
        return parsed

    demand_pairs = {
        key: value
        for key, value in parsed.items()
        if isinstance(key, str) and isinstance(value, dict)
    }
    if demand_pairs:
        return {
            "success": True,
            "demand_recommendation": demand_pairs,
            "roster_suggestions": [],
            "notes": parsed.get("notes", []),
        }
    return parsed


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

    staff_summary = summarize_staff(staff_data)
    shift_summary = summarize_shifts(shift_data)
    availability_summary = summarize_availability(
        availability_records=availability_data,
        start_date=start_date,
        end_date=end_date,
        total_staff=int(staff_summary.get("total_staff", 0) or 0),
    )
    sales_summary = summarize_sales(_extract_sales_records(shift_data))
    prompt = _build_prompt(
        staff_summary=staff_summary,
        availability_summary=availability_summary,
        sales_summary=sales_summary,
        shift_summary=shift_summary,
        start_date=start_date,
        end_date=end_date,
    )

    client = OpenAI(
        api_key=api_key,
        timeout=httpx.Timeout(60.0),
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an experienced workforce management planner for restaurants.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
    except OpenAIError as exc:
        logger.error("OpenAI API request failed: %s", str(exc))
        return _fallback_result(
            staff_summary=staff_summary,
            shift_summary=shift_summary,
            start_date=start_date,
            end_date=end_date,
            error="AI service temporarily unavailable",
        )
    except Exception as exc:
        logger.error("Unexpected OpenAI client error: %s", str(exc))
        return _fallback_result(
            staff_summary=staff_summary,
            shift_summary=shift_summary,
            start_date=start_date,
            end_date=end_date,
            error="AI service temporarily unavailable",
        )

    content = response.choices[0].message.content if response.choices else None
    if not content:
        logger.error("OpenAI returned an empty response.")
        return _fallback_result(
            staff_summary=staff_summary,
            shift_summary=shift_summary,
            start_date=start_date,
            end_date=end_date,
            error="AI returned an empty response",
        )

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.error("OpenAI returned invalid JSON.")
        return _fallback_result(
            staff_summary=staff_summary,
            shift_summary=shift_summary,
            start_date=start_date,
            end_date=end_date,
            error="AI returned invalid JSON",
        )

    if not isinstance(parsed, dict):
        logger.error("OpenAI JSON response must be a top-level object.")
        return _fallback_result(
            staff_summary=staff_summary,
            shift_summary=shift_summary,
            start_date=start_date,
            end_date=end_date,
            error="AI response format is invalid",
        )

    return _normalize_result(parsed)
