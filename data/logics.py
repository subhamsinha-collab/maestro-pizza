"""
Logics loader.
Reads the OUTCOME (DB Table) sheet from the Simulation Model Excel.
Structure: DRIVERS | DEMAND | CAPACITY | PROFIT | Utilization % | Internal % | Actual Capacity

The OUTCOME MODEL sheet has 3 admin-editable variables:
  3P Cost / order, Staff Cost / hr., V. Cost/order
Changing these regenerates the DB Table.

For the app: admin uploads the full Excel, we read the DB Table directly.
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, List, Optional


def load_logics_from_simulation(file_or_path, sheet_name: str = "OUTCOME (DB Table)") -> Tuple[
    Dict[Tuple[int, int, float], dict], List[float], List[int]
]:
    """
    Load logics lookup table from Simulation Model Excel.

    Args:
        file_or_path: Excel file with OUTCOME (DB Table) sheet
        sheet_name: sheet to read (default: "OUTCOME (DB Table)")

    Returns:
        logics: {(drivers, demand, capacity) -> {p: profit, u: utilization}}
        capacity_levels: sorted list of capacity values [1.0, 1.5, 2.0, ...]
        demand_levels: sorted list of demand values [0, 1, 2, ..., 12]
    """
    df = pd.read_excel(file_or_path, sheet_name=sheet_name, header=None)

    # Find the header row (contains DRIVERS, DEMAND, etc.)
    header_row = None
    for i in range(min(10, len(df))):
        row_vals = [str(v).strip().upper() for v in df.iloc[i] if pd.notna(v)]
        if "DRIVERS" in row_vals and "DEMAND" in row_vals:
            header_row = i
            break

    if header_row is None:
        raise ValueError(
            "Could not find header row with DRIVERS/DEMAND columns. "
            "Expected sheet 'OUTCOME (DB Table)' with columns: "
            "DRIVERS | DEMAND | CAPACITY | PROFIT | Utilization % | Internal % | Actual Capacity"
        )

    df.columns = [str(c).strip() for c in df.iloc[header_row]]
    df = df.iloc[header_row + 1:].reset_index(drop=True)

    # Normalize column names
    col_map = {}
    for c in df.columns:
        cl = str(c).lower()
        if "driver" in cl:
            col_map["drivers"] = c
        elif "demand" in cl:
            col_map["demand"] = c
        elif "capacity" in cl and "actual" not in cl:
            col_map["capacity"] = c
        elif "profit" in cl:
            col_map["profit"] = c
        elif "utilization" in cl or "util" in cl:
            col_map["util"] = c
        elif "internal" in cl:
            col_map["internal"] = c
        elif "actual" in cl:
            col_map["actual_cap"] = c

    required = ["drivers", "demand", "capacity", "profit"]
    missing = [r for r in required if r not in col_map]
    if missing:
        raise ValueError(
            f"Missing columns: {missing}. Found: {list(df.columns)}. "
            f"Expected: DRIVERS | DEMAND | CAPACITY | PROFIT | Utilization % | Internal % | Actual Capacity"
        )

    # Parse
    logics = {}
    for _, row in df.iterrows():
        try:
            k = int(float(row[col_map["drivers"]]))
            d = int(float(row[col_map["demand"]]))
            c = float(row[col_map["capacity"]])
            p = float(row[col_map["profit"]])
            u = float(row.get(col_map.get("util", ""), 0) or 0)
        except (ValueError, TypeError):
            continue

        if 1 <= k <= 9:
            logics[(k, d, c)] = {"p": p, "u": u}

    capacity_levels = sorted({float(c) for (_, _, c) in logics.keys()})
    demand_levels = sorted({int(d) for (_, d, _) in logics.keys()})

    return logics, capacity_levels, demand_levels


def load_logics_cost_params(file_or_path) -> Dict[str, float]:
    """Read the 3 cost parameters from OUTCOME MODEL sheet."""
    df = pd.read_excel(file_or_path, sheet_name="OUTCOME MODEL", header=None)
    params = {}
    for i in range(min(20, len(df))):
        label = str(df.iloc[i, 0]).strip().lower() if pd.notna(df.iloc[i, 0]) else ""
        val = df.iloc[i, 1] if len(df.columns) > 1 else None
        if "3p cost" in label and pd.notna(val):
            params["cost_3p_per_order"] = float(val)
        elif "staff cost" in label and pd.notna(val):
            params["cost_staff_per_hour"] = float(val)
        elif "v. cost" in label and pd.notna(val):
            params["cost_variable_per_order"] = float(val)
    return params


def bucket_capacity(c: float, capacity_levels: List[float]) -> float:
    """Snap a capacity value to the nearest level in the logics table."""
    if not capacity_levels:
        return float(c)
    return min(capacity_levels, key=lambda x: abs(x - float(c)))


def bucket_demand(d: int, demand_levels: List[int]) -> int:
    """Snap a demand value to the nearest level (capped at max)."""
    if not demand_levels:
        return int(d)
    d = max(0, min(int(d), max(demand_levels)))
    return min(demand_levels, key=lambda x: abs(x - d))


def profit_lookup(k: int, d: int, cap: float,
                  logics: dict, capacity_levels: list, demand_levels: list) -> float:
    """Look up profit for given drivers/demand/capacity."""
    if k <= 0:
        return 0.0
    k = max(1, min(9, int(k)))
    d_b = bucket_demand(int(d), demand_levels)
    c_b = bucket_capacity(float(cap), capacity_levels)
    entry = logics.get((k, d_b, c_b))
    return float(entry["p"]) if entry else 0.0
