"""
Capacity computation.
Input: branch_name, Weekday (shift), N.Orders, Orders SL%, PT, TDQ, TTCL, SD TTCL
Output: Adj.m per branch per weekday (discrete: 1.0, 1.5, 2.0, 2.5, 3.0, 3.5)

Formulas:
  CVm = SD_TTCL / TTCL
  m   = 1 / ((TTCL * 2) + (5 / 60))
  Adj.m = Round(m / 0.5, 0) * 0.5
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple


def compute_capacity(file_or_path) -> Dict[Tuple[str, int], float]:
    """
    Compute Adj.m capacity from raw capacity data.

    Args:
        file_or_path: Excel/CSV with columns:
            branch_name, Weekday (shift), TTCL, SD TTCL
            (N. Orders, Orders SL%, PT, TDQ are informational)

    Returns:
        capacity: {(branch_name, weekday_1to7) -> Adj_m}
    """
    if str(file_or_path).endswith(".csv"):
        df = pd.read_csv(file_or_path)
    else:
        df = pd.read_excel(file_or_path)

    df.columns = [str(c).strip() for c in df.columns]

    # Find columns
    branch_col = _find(df, ["branch_name", "branch"])
    weekday_col = _find(df, ["weekday (shift)", "weekday", "shift", "day"])
    ttcl_col = _find(df, ["ttcl"])
    sd_ttcl_col = _find(df, ["sd ttcl", "sd_ttcl", "sdttcl"])

    if not all([branch_col, weekday_col, ttcl_col, sd_ttcl_col]):
        raise ValueError(
            f"Missing columns. Need: branch_name, Weekday (shift), TTCL, SD TTCL. "
            f"Found: {list(df.columns)}"
        )

    df[branch_col] = df[branch_col].astype(str).str.strip()
    df[weekday_col] = pd.to_numeric(df[weekday_col], errors="coerce").astype(int)
    df[ttcl_col] = pd.to_numeric(df[ttcl_col], errors="coerce")
    df[sd_ttcl_col] = pd.to_numeric(df[sd_ttcl_col], errors="coerce")

    capacity = {}
    for _, row in df.dropna(subset=[branch_col, ttcl_col]).iterrows():
        branch = row[branch_col]
        weekday = int(row[weekday_col])
        ttcl = float(row[ttcl_col])
        sd_ttcl = float(row[sd_ttcl_col]) if pd.notna(row[sd_ttcl_col]) else 0.0

        if ttcl <= 0:
            adj_m = 2.0  # default
        else:
            # CVm = SD_TTCL / TTCL (informational only)
            # m = 1 / ((TTCL * 2) + (5/60))
            m = 1.0 / ((ttcl * 2) + (5.0 / 60.0))
            # Adj.m = Round(m / 0.5, 0) * 0.5
            adj_m = round(m / 0.5) * 0.5
            adj_m = max(1.0, min(adj_m, 3.5))  # clamp to valid range

        if 1 <= weekday <= 7:
            capacity[(branch, weekday)] = adj_m

    return capacity


def _find(df, candidates):
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        cl = cand.lower()
        if cl in cols_lower:
            return cols_lower[cl]
        for k, v in cols_lower.items():
            if cl in k:
                return v
    return None
