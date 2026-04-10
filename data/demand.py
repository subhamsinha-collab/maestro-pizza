"""
Demand loader — converts QuickSight forecast CSV into Branch x Hour x Day matrices.
Input CSV columns: branch_name | order_hour | Weekday | Forecast PRE_FILTER (CUSTOM)
Output: dict { branch: (demand_dict, branch_list) }
  demand_dict: {(branch, hour, day_1indexed) -> int}
  branch_list: sorted list of branch names
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, List

DAY_MAP = {
    "sun": 1, "sunday": 1,
    "mon": 2, "monday": 2,
    "tue": 3, "tuesday": 3,
    "wed": 4, "wednesday": 4,
    "thu": 5, "thursday": 5,
    "fri": 6, "friday": 6,
    "sat": 7, "saturday": 7,
}


def load_demand_from_csv(file_or_path) -> Tuple[Dict[Tuple[str, int, int], int], List[str]]:
    """
    Load forecasted demand from QuickSight export CSV.

    Args:
        file_or_path: file path string or file-like object (Streamlit UploadedFile)

    Returns:
        demand: dict {(branch_name, hour, day_1to7) -> rounded_demand}
        branches: sorted list of unique branch names
    """
    df = pd.read_csv(file_or_path)
    df.columns = [str(c).strip() for c in df.columns]

    # Identify columns flexibly
    branch_col = _find_col(df, ["branch_name", "branch", "branchname"])
    hour_col = _find_col(df, ["order_hour", "hour", "hr", "hr."])
    day_col = _find_col(df, ["weekday", "day", "dayweek", "day_of_week"])
    forecast_col = _find_col(df, ["forecast", "forecast pre_filter", "n. orders", "orders", "demand"])

    if not all([branch_col, hour_col, day_col, forecast_col]):
        missing = []
        if not branch_col: missing.append("branch_name")
        if not hour_col: missing.append("order_hour")
        if not day_col: missing.append("Weekday")
        if not forecast_col: missing.append("Forecast")
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    df[branch_col] = df[branch_col].astype(str).str.strip()
    df[hour_col] = pd.to_numeric(df[hour_col], errors="coerce").fillna(0).astype(int)
    df[forecast_col] = pd.to_numeric(df[forecast_col], errors="coerce").fillna(0.0)

    # Convert day names to 1-7
    df["_day_idx"] = df[day_col].astype(str).str.strip().str.lower().map(DAY_MAP)
    # If day names didn't map, try numeric
    unmapped = df["_day_idx"].isna()
    if unmapped.any():
        df.loc[unmapped, "_day_idx"] = pd.to_numeric(
            df.loc[unmapped, day_col], errors="coerce"
        )
    df["_day_idx"] = df["_day_idx"].fillna(1).astype(int)

    demand = {}
    for _, row in df.iterrows():
        b = row[branch_col]
        h = int(row[hour_col])
        d = int(row["_day_idx"])
        v = float(row[forecast_col])
        if 0 <= h <= 23 and 1 <= d <= 7:
            demand[(b, h, d)] = int(round(v))

    branches = sorted(df[branch_col].unique())
    return demand, branches


def demand_to_matrix(demand: Dict, branch: str) -> np.ndarray:
    """Convert demand dict to 24x7 numpy array for a single branch."""
    mat = np.zeros((24, 7), dtype=float)
    for h in range(24):
        for d in range(1, 8):
            mat[h, d - 1] = demand.get((branch, h, d), 0)
    return mat


def _find_col(df: pd.DataFrame, candidates: List[str]):
    """Find a column by matching against candidate names (case-insensitive, partial)."""
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        cand_l = cand.lower()
        # Exact match
        if cand_l in cols_lower:
            return cols_lower[cand_l]
        # Partial match
        for col_l, col_orig in cols_lower.items():
            if cand_l in col_l:
                return col_orig
    return None
