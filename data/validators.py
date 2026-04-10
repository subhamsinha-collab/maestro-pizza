"""
Input validators.
Checks uploaded files for column structure and branch name matching.
Returns warnings (not errors) so the user can decide whether to proceed.
"""
import pandas as pd
from typing import List, Tuple, Set


def validate_branch_names(uploaded_names: Set[str],
                          system_names: Set[str]) -> List[Tuple[str, str]]:
    """
    Check if uploaded branch names match system names.

    Returns:
        list of (uploaded_name, closest_system_name) for mismatches.
        Empty list = all names match.
    """
    mismatches = []
    for uname in uploaded_names:
        if uname not in system_names:
            # Find closest match
            best_match = None
            best_score = 0
            uname_clean = uname.lower().replace(" ", "").replace("-", "")
            for sname in system_names:
                sname_clean = sname.lower().replace(" ", "").replace("-", "")
                # Simple containment score
                if uname_clean in sname_clean or sname_clean in uname_clean:
                    score = len(set(uname_clean) & set(sname_clean))
                    if score > best_score:
                        best_score = score
                        best_match = sname
            if best_match is None:
                best_match = "no match found"
            mismatches.append((uname, best_match))
    return mismatches


def validate_columns(df: pd.DataFrame, required: List[str],
                     file_desc: str = "file") -> Tuple[bool, str]:
    """
    Check if DataFrame has required columns.

    Returns:
        (is_valid, message)
    """
    df_cols = [str(c).strip().lower() for c in df.columns]
    missing = []
    for req in required:
        if req.lower() not in df_cols:
            # Check partial match
            found = False
            for dc in df_cols:
                if req.lower() in dc:
                    found = True
                    break
            if not found:
                missing.append(req)

    if missing:
        return False, (
            f"{file_desc}: Missing columns: {', '.join(missing)}. "
            f"Found: {', '.join(str(c) for c in df.columns[:10])}"
        )
    return True, "OK"


def load_and_validate_cars(file_or_path, system_branches: Set[str] = None):
    """Load cars restriction with validation."""
    import numpy as np
    df = pd.read_excel(file_or_path)
    df.columns = [str(c).strip() for c in df.columns]

    # Expect: Branch, Hr, 1, 2, 3, 4, 5, 6, 7
    if len(df.columns) < 9:
        # Try renaming
        df.columns = ["Branch", "Hr"] + [str(d) for d in range(1, 8)][:len(df.columns) - 2]

    branch_col = df.columns[0]
    hour_col = df.columns[1]
    df[branch_col] = df[branch_col].astype(str).str.strip()

    cars = {}
    for branch in df[branch_col].unique():
        bdata = df[df[branch_col] == branch]
        mat = np.zeros((24, 7), dtype=int)
        for _, row in bdata.iterrows():
            h = int(row[hour_col])
            if 0 <= h < 24:
                for d in range(7):
                    col = str(d + 1)
                    if col in df.columns:
                        mat[h, d] = int(row[col])
        cars[str(branch)] = mat

    # Validate branch names
    warnings = []
    if system_branches:
        mismatches = validate_branch_names(set(cars.keys()), system_branches)
        if mismatches:
            warnings = mismatches

    return cars, warnings


def load_restricted_branches(file_or_path) -> Set[str]:
    """Load restricted branches list."""
    df = pd.read_excel(file_or_path)
    return set(df.iloc[:, 0].astype(str).str.strip())
