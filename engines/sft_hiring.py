"""
SFT Hiring Engine — Saudi Driver Allocation Optimizer
=====================================================
Phase 1: Build profit lookup per branch (GA optimizer for team sizes 1-6)
Phase 2: Greedy allocate N Saudi drivers by best marginal profit
Phase 3: Employee attribution (incremental profit, orders, productivity)

Car constraint: SOFT PENALTY
  - Only min(drivers, cars) contribute to logics profit
  - Excess drivers incur idle cost: 5D=-26.44, 6D=-22.04 per hour-slot
  - GA can schedule beyond car limits if peak revenue > idle penalty
"""
import numpy as np
import pandas as pd
import random
import copy
import io
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Callable

from config import cfg
from data.logics import profit_lookup, bucket_capacity, bucket_demand


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class DriverShift:
    start_hour: int
    is_working: bool
    def get_hours(self) -> List[int]:
        if not self.is_working or self.start_hour == -1:
            return []
        return [(self.start_hour + i) % 24 for i in range(8)]


@dataclass
class DriverSchedule:
    shifts: List[DriverShift]
    employee_id: int = 0
    def get_work_days(self) -> int:
        return sum(1 for s in self.shifts if s.is_working)


# ============================================================
# CASE GENERATION
# ============================================================

def generate_cases(branches, demand, capacity, logics, cap_levels, dem_levels,
                   branch_types, target_type, driver_cost_per_hour=0.0):
    """
    Build profit matrices (Case1-6) per branch.
    Case[n] = 24x7 matrix of NET profit/hr with n drivers.
    NET = Simulation_Gross_Profit - (n_drivers * driver_cost_per_hour)
    For SFT 5D: driver_cost = 26.44, for 6D: 22.04
    """
    cases = {}
    for b in branches:
        if branch_types.get(b) != target_type:
            continue
        branch_cases = []
        for n_drivers in range(1, 7):
            mat = np.zeros((24, 7))
            for h in range(24):
                for d in range(1, 8):
                    dm = min(demand.get((b, h, d), 0), max(dem_levels) if dem_levels else 12)
                    cp = capacity.get((b, d), 2.0)
                    gross_p = profit_lookup(n_drivers, dm, cp, logics, cap_levels, dem_levels)
                    net_p = gross_p - n_drivers * driver_cost_per_hour
                    mat[h, d - 1] = net_p
            branch_cases.append(mat)
        cases[b] = branch_cases
    return cases


# ============================================================
# GA SCHEDULE OPTIMIZER WITH SOFT CAR PENALTY
# ============================================================

def _create_random_schedule(schedule_type):
    start = random.randint(0, 23)
    if schedule_type == "5D":
        off1 = random.randint(0, 6)
        offs = {off1, (off1 + 1) % 7}
    else:
        offs = {random.randint(0, 6)}
    shifts = []
    for d in range(7):
        if d in offs:
            shifts.append(DriverShift(-1, False))
        else:
            s = (start + random.randint(-2, 2)) % 24
            shifts.append(DriverShift(s, True))
    return DriverSchedule(shifts)


def _create_staggered_schedule(schedule_type, driver_idx, num_drivers):
    bands = [[16, 17, 18], [19, 20, 21], [8, 9, 10], [11, 12, 13], [14, 15], [22, 23, 0]]
    band = bands[driver_idx % len(bands)]
    start = random.choice(band)
    if schedule_type == "5D":
        off1 = (driver_idx * 2) % 7
        offs = {off1, (off1 + 1) % 7}
    else:
        offs = {(driver_idx * 2) % 7}
    shifts = []
    for d in range(7):
        if d in offs:
            shifts.append(DriverShift(-1, False))
        else:
            s = (start + random.randint(-1, 1)) % 24
            shifts.append(DriverShift(s, True))
    return DriverSchedule(shifts)


def _calc_profit_soft_penalty(schedules, case_matrices, car_matrix, schedule_type="5D"):
    """Profit with soft car penalty."""
    penalty_rate = cfg.penalty_5d if schedule_type == "5D" else cfg.penalty_6d
    cov = np.zeros((24, 7), int)
    for sc in schedules:
        for di, sh in enumerate(sc.shifts):
            if sh.is_working:
                for h in sh.get_hours():
                    cov[h, di] += 1

    total = 0.0
    for h in range(24):
        for d in range(7):
            n = cov[h, d]
            if n > 0:
                max_cars = int(car_matrix[h, d])
                eff = min(n, max_cars) if max_cars > 0 else n
                if eff > 0:
                    ci = min(eff - 1, len(case_matrices) - 1)
                    total += case_matrices[ci][h, d]
                if n > max_cars and max_cars > 0:
                    total -= (n - max_cars) * penalty_rate
    return total


def _optimize_team_size(num_drivers, schedule_type, cases, car_mat,
                        pop_size=None, gens=None):
    """GA optimizer for a given team size at one branch."""
    if num_drivers == 0:
        return 0.0, []
    if pop_size is None:
        pop_size = cfg.ga_population
    if gens is None:
        gens = cfg.ga_generations

    max_cars = int(car_mat.max())
    constrained = num_drivers > max_cars
    if constrained:
        pop_size = max(pop_size, 200)
        gens = max(gens, 100)

    pop = []
    for p_idx in range(pop_size):
        if constrained and p_idx < pop_size // 2:
            team = [_create_staggered_schedule(schedule_type, i, num_drivers)
                    for i in range(num_drivers)]
        else:
            team = [_create_random_schedule(schedule_type) for _ in range(num_drivers)]
        pop.append((team, _calc_profit_soft_penalty(team, cases, car_mat, schedule_type)))

    for _ in range(gens):
        pop.sort(key=lambda x: x[1], reverse=True)
        el = max(1, int(pop_size * 0.2))
        new = pop[:el]
        while len(new) < pop_size:
            par = random.choice(pop[:el])
            child = [copy.deepcopy(s) for s in par[0]]
            idx = random.randint(0, num_drivers - 1)
            if random.random() < 0.3:
                if constrained and random.random() < 0.5:
                    child[idx] = _create_staggered_schedule(schedule_type, idx, num_drivers)
                else:
                    child[idx] = _create_random_schedule(schedule_type)
            else:
                for i, sh in enumerate(child[idx].shifts):
                    if sh.is_working:
                        child[idx].shifts[i] = DriverShift(
                            (sh.start_hour + random.choice([-2, -1, 0, 1, 2])) % 24, True
                        )
                        break
            new.append((child, _calc_profit_soft_penalty(child, cases, car_mat, schedule_type)))
        pop = new

    best = max(pop, key=lambda x: x[1])
    return best[1], best[0]


# ============================================================
# GREEDY REORDER FOR MONOTONIC ATTRIBUTION
# ============================================================

def _reorder_greedy(schedules, case_matrices, car_matrix, schedule_type="5D"):
    """Reorder schedules so that marginal attribution is monotonic."""
    if not schedules or len(schedules) <= 1:
        return list(schedules)

    penalty_rate = cfg.penalty_5d if schedule_type == "5D" else cfg.penalty_6d
    n = len(schedules)
    remaining = list(range(n))
    ordered = []
    profit_before = 0.0

    for step in range(n):
        best_idx = None
        best_marginal = -float("inf")
        best_profit = 0.0

        for cand in remaining:
            test_team = [schedules[i] for i in ordered] + [schedules[cand]]
            cov = np.zeros((24, 7), int)
            for sc in test_team:
                for di, sh in enumerate(sc.shifts):
                    if sh.is_working:
                        for h in sh.get_hours():
                            cov[h, di] += 1
            profit = 0.0
            for h in range(24):
                for d in range(7):
                    nc = cov[h, d]
                    if nc > 0:
                        mc = int(car_matrix[h, d])
                        eff = min(nc, mc) if mc > 0 else nc
                        if eff > 0:
                            ci = min(eff - 1, len(case_matrices) - 1)
                            profit += case_matrices[ci][h, d]
                        if nc > mc and mc > 0:
                            profit -= (nc - mc) * penalty_rate
            marginal = profit if step == 0 else profit - profit_before
            if marginal > best_marginal:
                best_marginal = marginal
                best_idx = cand
                best_profit = profit

        ordered.append(best_idx)
        remaining.remove(best_idx)
        profit_before = best_profit

    return [schedules[i] for i in ordered]


# ============================================================
# EMPLOYEE ATTRIBUTION (Profit + Orders + Productivity)
# ============================================================

def _calculate_attribution(branch, schedules, case_matrices, demand, capacity,
                           logics, cap_levels, dem_levels, car_matrix,
                           schedule_type="5D"):
    """
    Incremental attribution per employee.
    Returns: list of dicts with Branch, Employee, Profit, Cum_Profit,
             Hours, Num_Orders, Productivity, Schedule
    """
    if not schedules or not case_matrices:
        return []

    penalty_rate = cfg.penalty_5d if schedule_type == "5D" else cfg.penalty_6d

    # Greedy reorder
    schedules = _reorder_greedy(schedules, case_matrices, car_matrix, schedule_type)

    results = []
    cum_profit = 0.0
    cum_orders = 0
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    for emp_idx in range(len(schedules)):
        # Build cumulative coverage up to this employee
        cov = np.zeros((24, 7), int)
        for e in range(emp_idx + 1):
            for di, sh in enumerate(schedules[e].shifts):
                if sh.is_working:
                    for h in sh.get_hours():
                        cov[h, di] += 1

        # Compute profit with N employees
        profit_n = 0.0
        for h in range(24):
            for d in range(7):
                n = cov[h, d]
                if n > 0:
                    mc = int(car_matrix[h, d])
                    eff = min(n, mc) if mc > 0 else n
                    if eff > 0:
                        ci = min(eff - 1, len(case_matrices) - 1)
                        profit_n += case_matrices[ci][h, d]
                    if n > mc and mc > 0:
                        profit_n -= (n - mc) * penalty_rate

        # Compute orders served with N employees
        orders_n = 0
        for h in range(24):
            for dy in range(1, 8):
                n = int(cov[h, dy - 1])
                dm = demand.get((branch, h, dy), 0)
                if n == 0 or dm == 0:
                    continue
                cp = capacity.get((branch, dy), 2.0)
                entry = logics.get((
                    n,
                    bucket_demand(min(dm, max(dem_levels) if dem_levels else 12), dem_levels),
                    bucket_capacity(cp, cap_levels)
                ))
                if entry:
                    u = min(float(entry["u"]), 1.0)
                    served = round(min(u * cp * n, dm))
                    orders_n += served

        emp_profit = profit_n - cum_profit
        emp_orders = orders_n - cum_orders
        cum_profit = profit_n
        cum_orders = orders_n

        # Build schedule string
        parts = []
        total_hours = 0
        for di, sh in enumerate(schedules[emp_idx].shifts):
            dn = day_names[di]
            if sh.is_working:
                s = sh.start_hour
                e = (s + 8) % 24
                parts.append(f"{dn} {s:02d}:00-{e:02d}:00")
                total_hours += 8
            else:
                parts.append(f"{dn} OFF")

        productivity = round(emp_orders / total_hours, 2) if total_hours > 0 else 0

        results.append({
            "Branch": branch,
            "Schedule_Type": schedule_type,
            "Employee": f"E{emp_idx + 1}",
            "Employee_Profit": round(emp_profit, 2),
            "Cumulative_Profit": round(cum_profit, 2),
            "Weekly_Hours": total_hours,
            "Num_Orders": emp_orders,
            "Productivity": productivity,
            "Schedule": " | ".join(parts),
        })

    return results


# ============================================================
# MAIN ENGINE CLASS
# ============================================================

class SFTHiringEngine:
    """
    End-to-end SFT hiring optimizer.

    Usage:
        engine = SFTHiringEngine(demand, capacity, logics, cap_levels, dem_levels,
                                 branch_types, cars, restricted)
        engine.run(target_drivers=207, progress_callback=fn)
        results = engine.get_results()
        excel_bytes = engine.export_excel()
    """

    def __init__(self, demand, capacity, logics, cap_levels, dem_levels,
                 branch_types, branches, cars=None, restricted=None,
                 current_deployment=None):
        self.demand = demand
        self.capacity = capacity
        self.logics = logics
        self.cap_levels = cap_levels
        self.dem_levels = dem_levels
        self.branch_types = branch_types
        self.branches = branches
        self.cars = cars or {}
        self.restricted = restricted or set()
        self.current_deployment = current_deployment or {}

        # Results
        self.allocation = {}
        self.lookup = {}
        self.total_profit = 0.0
        self.cases_5d = {}
        self.cases_6d = {}
        self.attribution = []

    def run(self, target_drivers: int,
            progress_callback: Optional[Callable] = None):
        """Run the full optimizer pipeline."""

        # Phase 0: Generate cases
        if progress_callback:
            progress_callback(0, "Generating profit cases...")

        self.cases_5d = generate_cases(
            self.branches, self.demand, self.capacity,
            self.logics, self.cap_levels, self.dem_levels,
            self.branch_types, "5D", driver_cost_per_hour=cfg.penalty_5d
        )
        self.cases_6d = generate_cases(
            self.branches, self.demand, self.capacity,
            self.logics, self.cap_levels, self.dem_levels,
            self.branch_types, "6D", driver_cost_per_hour=cfg.penalty_6d
        )

        # Phase 1: Build profit lookup via GA
        eligible = [b for b in self.branches if b not in self.restricted]
        self.lookup = {}
        total = len(eligible)

        for idx, branch in enumerate(eligible):
            stype = self.branch_types.get(branch, "5D")
            cases = self.cases_5d.get(branch, []) if stype == "5D" else self.cases_6d.get(branch, [])
            car_mat = self.cars.get(branch, np.full((24, 7), 6))

            if not cases:
                continue

            max_size = min(6, len(cases))
            self.lookup[branch] = {0: (0.0, [])}

            if progress_callback:
                pct = int(5 + 75 * (idx + 1) / max(total, 1))
                progress_callback(pct, f"Lookup {idx + 1}/{total}: {branch}")

            for size in range(1, max_size + 1):
                p, scheds = _optimize_team_size(size, stype, cases, car_mat)
                self.lookup[branch][size] = (p, scheds)

                # Early stop: 2 consecutive very negative marginals
                if size >= 2:
                    m1 = p - self.lookup[branch][size - 1][0]
                    m0 = self.lookup[branch][size - 1][0] - self.lookup[branch][size - 2][0]
                    if m1 < -500 and m0 < -500:
                        for s in range(size + 1, max_size + 1):
                            self.lookup[branch][s] = (p - 999999, [])
                        break

        # Phase 2: Greedy allocation
        if progress_callback:
            progress_callback(82, "Greedy allocation...")

        alloc = {b: 0 for b in self.lookup}
        for _ in range(target_drivers):
            best_branch = None
            best_marginal = -float("inf")
            for b in self.lookup:
                ns = alloc[b] + 1
                if ns not in self.lookup[b]:
                    continue
                pn = self.lookup[b][ns][0]
                if pn <= -999000:
                    continue
                m = pn - self.lookup[b][alloc[b]][0]
                if m > best_marginal:
                    best_marginal = m
                    best_branch = b
            if best_branch:
                alloc[best_branch] += 1
            else:
                break

        self.allocation = {b: n for b, n in alloc.items() if n > 0}
        self.total_profit = sum(
            self.lookup[b][n][0] for b, n in self.allocation.items()
        )

        # Phase 3: Attribution
        if progress_callback:
            progress_callback(90, "Employee attribution...")

        self.attribution = []
        for branch, n in self.allocation.items():
            _, scheds = self.lookup[branch][n]
            if not scheds:
                continue
            stype = self.branch_types.get(branch, "5D")
            cases = self.cases_5d.get(branch, []) if stype == "5D" else self.cases_6d.get(branch, [])
            car_mat = self.cars.get(branch, np.full((24, 7), 99))
            if cases:
                attr = _calculate_attribution(
                    branch, scheds, cases, self.demand, self.capacity,
                    self.logics, self.cap_levels, self.dem_levels,
                    car_mat, stype
                )
                self.attribution.extend(attr)

        if progress_callback:
            progress_callback(100, "Complete!")

    def get_results(self) -> dict:
        """Return structured results for the UI."""
        return {
            "total_drivers": sum(self.allocation.values()),
            "total_profit": round(self.total_profit, 2),
            "active_branches": len(self.allocation),
            "total_branches": len(self.branches),
            "allocation": self.allocation,
        }

    def export_excel(self) -> bytes:
        """
        Export 4 sheets:
          1. Branch_Summary (all branches, incl. 0-driver)
          2. Employee_Details (with Orders + Productivity)
          3. Coverage_Analysis (active branches only)
          4. Comparison (current vs model)
        """
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

        # 1. Branch_Summary
        alloc_rows = []
        for b in sorted(set(list(self.allocation.keys()) + list(self.branch_types.keys()))):
            n = self.allocation.get(b, 0)
            p = self.lookup.get(b, {}).get(n, (0.0, []))[0] if b in self.lookup else 0.0
            alloc_rows.append({
                "Branch": b,
                "Schedule_Type": self.branch_types.get(b, "N/A"),
                "Allocated_Drivers": n,
                "Profit": round(p, 2),
            })
        df_branch = pd.DataFrame(alloc_rows).sort_values("Profit", ascending=False)

        # 2. Employee_Details
        df_emp = pd.DataFrame(self.attribution) if self.attribution else pd.DataFrame()

        # 3. Coverage_Analysis (active branches only)
        cov_rows = []
        for branch, n in self.allocation.items():
            _, scheds = self.lookup[branch][n]
            if not scheds:
                continue
            stype = self.branch_types.get(branch, "5D")
            car_mat = self.cars.get(branch, np.full((24, 7), 99))
            cases = self.cases_5d.get(branch, []) if stype == "5D" else self.cases_6d.get(branch, [])
            scheds = _reorder_greedy(scheds, cases, car_mat, stype) if cases else scheds

            cov = np.zeros((24, 7), int)
            for sc in scheds:
                for di, sh in enumerate(sc.shifts):
                    if sh.is_working:
                        for h in sh.get_hours():
                            cov[h, di] += 1
            for h in range(24):
                row = {"Branch": branch, "Hour": h}
                for d in range(7):
                    row[str(d + 1)] = int(cov[h, d])
                cov_rows.append(row)

        df_cov = pd.DataFrame(cov_rows)
        if not df_cov.empty:
            df_cov = df_cov[["Branch", "Hour"] + [str(d) for d in range(1, 8)]]

        # 4. Comparison
        comp_rows = []
        all_branches = set(list(self.allocation.keys()) + list(self.current_deployment.keys()))
        for b in sorted(all_branches):
            current = self.current_deployment.get(b, 0)
            model = self.allocation.get(b, 0)
            delta = model - current
            if delta > 0:
                action = "Hire / move in"
            elif delta < 0:
                action = "Redeploy"
            else:
                action = "No change"
            comp_rows.append({
                "Branch": b,
                "Current_Drivers": current,
                "Model_Drivers": model,
                "Delta": delta,
                "Action": action,
            })
        df_comp = pd.DataFrame(comp_rows).sort_values("Delta", ascending=False)

        # Write Excel
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df_branch.to_excel(w, sheet_name="Branch_Summary", index=False)
            if not df_emp.empty:
                df_emp.to_excel(w, sheet_name="Employee_Details", index=False)
            if not df_cov.empty:
                df_cov.to_excel(w, sheet_name="Coverage_Analysis", index=False)
            if comp_rows:
                df_comp.to_excel(w, sheet_name="Comparison", index=False)
        return buf.getvalue()
