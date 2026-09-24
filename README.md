# Vaccination Project

This repository contains code and data for vaccination analysis and ETL.

Structure
- `clean_data.py`, `build_db.py`, and other scripts
- `data/` raw data
- `cleaned_data/` processed outputs
- `sql/` schema and SQL queries

To set up:

1. Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Build the database:

```powershell
python build_db.py
```
