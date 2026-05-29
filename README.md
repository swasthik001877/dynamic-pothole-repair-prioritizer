# 🚧 PotholeFix – Dynamic Pothole Repair Prioritizer
Desktop application · PyQt6 + SQLite3

## Quick Start
```bash
pip install PyQt6 matplotlib pillow
python main.py
```

### Demo Credentials
| Role | Email | Password |
|---|---|---|
| Admin | admin@potholefix.gov | admin123 |
| Repair Crew | ravi@crew.gov | crew123 |
| Citizen | arjun@citizen.com | pass123 |

## Features by Role

### Citizen
- Submit pothole report with road name, location, severity
- Pick location on map (OpenStreetMap / Nominatim geocoder, no API key needed)
- Upload up to 5 photos per report
- ML Severity Analysis — click "Analyse with ML" to auto-detect severity from photos
- Live priority score preview before submitting
- View own reports with status and ML severity

### Admin
- Dashboard: live stats, priority bar chart, status pie chart, monthly trend
- View/search/filter all reports; update status; delete reports
- Assign repair crew with scheduled date and notes
- Add Repair Crew members (citizens self-register; admin cannot add citizens)
- Deactivate/reactivate users for serious faults (soft-delete, reports preserved)
- Full assignments view with proof photo counts
- Priority queue with ML severity column
- Export reports and assignments to CSV

### Repair Crew
- View own assignments only
- Double-click to update progress: Assigned → Started → Completed
- Add progress notes describing work done
- Upload proof photographs as completion evidence
- Open pothole location directly in OpenStreetMap browser
- Stats panel: Total / Completed / Active counts

## Priority Algorithm
Score = 0.5 × Normalize(Severity 1-10) + 0.5 × Normalize(Avg Daily Traffic)
Result: 0-100 | Critical ≥75 | High ≥50 | Medium ≥25 | Low <25

## ML Severity Analysis
Uses Pillow locally (no internet). Analyses brightness variance and dark patch ratio
as proxies for surface damage. Replace MLAnalyser._analyse() with real CNN/ONNX inference.

## Map System
- Address search via Nominatim (free, no API key)
- Reverse geocoding from coordinates
- One-click Open in Browser → live OpenStreetMap at exact pin

## Project Structure
main.py              - Full PyQt6 app (all views, dialogs, ML thread)
database.py          - SQLite3 CRUD layer
priority_engine.py   - Scoring algorithm
requirements.txt     - PyQt6, matplotlib, pillow
pothole.db           - Auto-created SQLite database
uploads/potholes/    - Citizen pothole photos
uploads/proof/       - Crew proof photographs
tests/               - 38 unit + integration tests

## Run Tests
python -m pytest tests/ -v
