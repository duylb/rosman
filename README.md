# RosMan - Rostering Management (Local Python App)

A lightweight Flask + SQLite app for managing:
- Staff members
- Shift templates
- Daily roster assignments
- Leave/availability windows
- Weekly auto-scheduling
- CSV import/export

## Quick Start

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python app.py
```

4. Open in browser:

`http://127.0.0.1:5000`

## Core Features

- `Staff`: add members and enable/disable them.
- `Shifts`: define shift templates and required headcount.
- `Availability`: record leave/unavailable date ranges and preferred shifts per date range.
- `Roster`: assign manually or auto-generate a week.
- `Data I/O`: import/export CSV by dataset.

## CSV Datasets

- `staff`: `name, role, email, active`
- `shifts`: `name, start_time, end_time, required_staff`
- `assignments`: `roster_date, staff_id, shift_id, notes`
- `availability`: `staff_id, start_date, end_date, status, notes`

Date format is `YYYY-MM-DD`.

## Notes

- Database file is `roster.db` in the project root.
- To reset all data, stop app and delete `roster.db`.
- This is intended for local/internal use.
