# 🍕 Maestro Pizza — Delivery Capacity Engine

Unified application for driver hiring, scheduling, MC optimization, and polygon routing.

## Quick Start

```bash
# Clone
git clone https://github.com/your-org/maestro-pizza.git
cd maestro-pizza

# Install
pip install -r requirements.txt

# Run
streamlit run app.py
```

Opens at `http://localhost:8501`

## Modules

| Module | Status | Description |
|--------|--------|-------------|
| SFT Hiring | ✅ Complete | Saudi driver allocation (GA + greedy marginal) |
| EFT Hiring | 🔲 Placeholder | Expat hiring (depends on SFT remaining) |
| Scheduling | 🔲 Placeholder | SFT+EFT scheduling with employee restrictions |
| MC Optimizer | 🔲 Placeholder | Maestro Captain dual-threshold optimizer |
| Capacity Model | 🔲 Placeholder | Auto-assembled final output |
| Polygon | 🔲 Placeholder | MP-to-branch routing optimizer |

## Data Inputs

| Input | Source | Format |
|-------|--------|--------|
| Demand forecast | QuickSight CSV | branch_name, order_hour, Weekday, Forecast |
| Capacity | MCP (compute in-app) | branch_name, Weekday, TTCL, SD_TTCL → Adj.m |
| Logics | Simulation Model Excel | OUTCOME (DB Table) sheet |
| Cars restriction | Manual upload | Branch, Hr, 1-7 |
| Branch 5D/6D | Upload | Branch, Schedule |
| Restricted branches | Manual upload | Branch (list) |
| Employee restriction | Manual upload | Branch, Coming, Going, Gap, Weekoff, Type |
| MC restriction | Manual upload | Branch, Max team size |
| 3P Preference | Manual upload | Branch, Priority 1-3 (H/C/Y) |
| Current deployment | ERP | Branch, Drivers (for comparison) |

## Architecture

```
maestro-pizza/
├── app.py              # Streamlit main app (all pages)
├── config.py           # System parameters (admin-editable, persisted)
├── data/
│   ├── demand.py       # QuickSight CSV → demand matrix
│   ├── capacity.py     # TTCL → Adj.m computation
│   ├── logics.py       # Simulation Model → logics lookup
│   ├── validators.py   # Branch name matching, column validation
│   └── templates.py    # Sample file generation for downloads
├── engines/
│   └── sft_hiring.py   # SFT GA optimizer + greedy + attribution
├── requirements.txt
└── README.md
```

## Key Parameters

| Parameter | Value | Where |
|-----------|-------|-------|
| 5D idle penalty | -26.44 SAR | From Logics_5D row (1,0,*) |
| 6D idle penalty | -22.04 SAR | From Logics_6D row (1,0,*) |
| GA population | 100 | Admin settings |
| GA generations | 60 | Admin settings |
| MC threshold 1 | 0.8 orders/hr | Per-run configurable |
| MC threshold 2 | 0.6 orders/hr | Per-run configurable |

## SFT Hiring Output (4 sheets)

1. **Branch_Summary**: Branch | Schedule_Type | Allocated_Drivers | Profit
2. **Employee_Details**: Branch | Type | Employee | Profit | Cum_Profit | Hours | Num_Orders | Productivity | Schedule
3. **Coverage_Analysis**: Branch | Hour | 1-7 (active branches only)
4. **Comparison**: Branch | Current_Drivers | Model_Drivers | Delta | Action
