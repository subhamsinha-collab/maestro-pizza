"""
Maestro Pizza - Delivery Capacity Engine v4
"""
import streamlit as st
import pandas as pd
import numpy as np
import time, os

st.set_page_config(page_title="Maestro Pizza", page_icon=":pizza:", layout="wide")

st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#f5f7f5 0%,#fff 100%)}
[data-testid="stSidebar"]{background:#1B5E20}
[data-testid="stSidebar"] label,[data-testid="stSidebar"] .stMarkdown p,[data-testid="stSidebar"] .stRadio label span{color:#fff!important}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:#66BB6A!important}
.stButton>button{background:#2E7D32!important;color:#fff!important;border:none;font-weight:600;border-radius:8px}
.stButton>button:hover{background:#1B5E20!important}
div[data-testid="stMetric"]{background:#E8F5E9;border-radius:12px;padding:16px;border-left:4px solid #2E7D32}
h1,h2,h3{color:#1B5E20!important}
</style>""", unsafe_allow_html=True)

USERS = {"admin": {"password": "DailyFood@2026", "role": "admin"},
         "subham": {"password": "delivery123", "role": "admin"},
         "user": {"password": "maestro2026", "role": "user"}}

def find_data_dir():
    for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_files"),
              os.path.join(os.getcwd(), "data_files"),
              "/mount/src/maestro-pizza/data_files"]:
        if os.path.exists(p):
            return p
    return None

def check_login():
    if st.session_state.get("auth"):
        return True
    st.markdown("<h1 style='text-align:center'>Maestro Pizza</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;color:#666!important'>Delivery Capacity Engine</h3>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state["auth"] = True
                st.session_state["user"] = u
                st.session_state["role"] = USERS[u]["role"]
                st.rerun()
            else:
                st.error("Invalid credentials")
    return False

def is_admin():
    return st.session_state.get("role") == "admin"

@st.cache_data(show_spinner="Loading demand data...")
def load_demand(path):
    from data.demand import load_demand_from_csv
    return load_demand_from_csv(path)

@st.cache_data(show_spinner="Loading logics...")
def load_logics(path):
    from data.logics import load_logics_from_simulation
    return load_logics_from_simulation(path)

@st.cache_data(show_spinner="Loading capacity...")
def load_capacity(path):
    df = pd.read_excel(path, header=0)
    df.columns = [str(c).strip() for c in df.columns]
    cap = {}
    for _, r in df.iterrows():
        b = str(r["branch_name"]).strip()
        d = int(r["Weekday (shift)"])
        adj = float(r["Adj.m"])
        if 1 <= d <= 7:
            cap[(b, d)] = adj
    return cap

def ensure_data():
    if st.session_state.get("data_loaded"):
        return True
    dd = find_data_dir()
    if dd is None:
        st.error("data_files/ folder not found!")
        return False
    try:
        dem, brs = load_demand(os.path.join(dd, "demand_forecast.csv"))
        logics, cl, dl = load_logics(os.path.join(dd, "simulation_model.xlsx"))
        cap = load_capacity(os.path.join(dd, "capacity.xlsx"))
        st.session_state["demand"] = dem
        st.session_state["branches"] = brs
        st.session_state["branch_types"] = {b: "5D" for b in brs}
        st.session_state["logics"] = logics
        st.session_state["cap_levels"] = cl
        st.session_state["dem_levels"] = dl
        st.session_state["capacity"] = cap
        st.session_state["data_loaded"] = True
        return True
    except Exception as e:
        st.error("Data load error: " + str(e))
        return False

from data.templates import TEMPLATES, generate_template

# === PAGES ===

def page_home():
    st.title("Dashboard")
    stages = [("SFT Hiring", st.session_state.get("sft_done", False)), ("EFT Hiring", False),
              ("Scheduling", False), ("MC Optimizer", False), ("Capacity Model", False)]
    cols = st.columns(len(stages))
    for i, (name, done) in enumerate(stages):
        with cols[i]:
            if done:
                st.success("**" + str(i+1) + ". " + name + "**\n\nComplete")
            elif i == 0 or stages[i-1][1]:
                st.info("**" + str(i+1) + ". " + name + "**\n\nReady")
            else:
                st.container().markdown("**" + str(i+1) + ". " + name + "**\n\nLocked")
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    eng = st.session_state.get("sft_engine")
    if eng:
        res = eng.get_results()
        c1.metric("Saudi Drivers", res["total_drivers"])
        c2.metric("Active Branches", res["active_branches"])
        c3.metric("Profit (SAR)", "{:,.2f}".format(res["total_profit"]))
    else:
        c1.metric("Saudi Drivers", "--")
        c2.metric("Active Branches", "--")
        c3.metric("Profit", "--")
    c4.metric("Total Branches", len(st.session_state.get("branches", [])))
    st.markdown("---")
    st.markdown("### Data sources (auto-loaded)")
    dem = st.session_state.get("demand")
    lg = st.session_state.get("logics")
    cap = st.session_state.get("capacity")
    if dem:
        st.markdown("[OK] **Demand** -- {:,} slots, {} branches".format(len(dem), len(st.session_state.get("branches", []))))
    else:
        st.markdown("[  ] **Demand** -- not loaded")
    if lg:
        st.markdown("[OK] **Logics** -- {} entries".format(len(lg)))
    else:
        st.markdown("[  ] **Logics** -- not loaded")
    if cap:
        st.markdown("[OK] **Capacity** -- {:,} entries".format(len(cap)))
    else:
        st.markdown("[  ] **Capacity** -- not loaded")


def page_sft():
    st.title("SFT Hiring (Saudi)")
    branches = st.session_state.get("branches", [])
    demand_raw = st.session_state.get("demand", {})
    if not branches or not demand_raw:
        st.error("Data not loaded")
        return
    from config import cfg

    c1, c2, c3 = st.columns(3)
    c1.metric("Branches", len(branches))
    n5d = sum(1 for b in branches if st.session_state.get("branch_types", {}).get(b) == "5D")
    c2.metric("5D / 6D", "{} / {}".format(n5d, len(branches) - n5d))
    c3.metric("Car penalty", "5D: -{} | 6D: -{}".format(cfg.penalty_5d, cfg.penalty_6d))
    st.markdown("---")

    # === QUICKSIGHT-STYLE DEMAND SCALING ===
    st.markdown("### Step 1 -- Demand forecast")
    st.markdown("Historical pattern loaded from backend. Enter W. Forecast to scale.")

    historical_total = sum(v for v in demand_raw.values())

    qs_col1, qs_col2, qs_col3, qs_col4 = st.columns(4)
    with qs_col1:
        w_forecast = st.number_input("W. Forecast (total weekly orders)", min_value=1, value=int(historical_total), step=100, key="w_forecast")
    with qs_col2:
        branch_filter = st.selectbox("Branch", ["All"] + sorted(branches), key="branch_filter")
    with qs_col3:
        country_filter = st.selectbox("Country", ["Saudi Arabia"], key="country_filter")
    with qs_col4:
        order_type = st.selectbox("Order Type", ["Delivery", "All"], key="order_type")

    # Compute scaling factor
    if historical_total > 0:
        scale_factor = w_forecast / historical_total
    else:
        scale_factor = 1.0

    # Scale demand
    demand = {}
    for (b, h, d), v in demand_raw.items():
        if branch_filter != "All" and b != branch_filter:
            continue
        demand[(b, h, d)] = int(round(v * scale_factor))

    # Filter branches if needed
    if branch_filter != "All":
        active_branches = [branch_filter]
    else:
        active_branches = branches

    scaled_total = sum(v for v in demand.values())

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Historical total", "{:,}".format(int(historical_total)))
    sc2.metric("W. Forecast", "{:,}".format(w_forecast))
    sc3.metric("Scale factor", "{:.4f}".format(scale_factor))

    with st.expander("Demand preview (scaled)", expanded=False):
        days_list = ["", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        rows = []
        for (b, h, d), v in list(demand.items())[:200]:
            if v > 0:
                rows.append({"Branch": b, "Hour": h, "Day": days_list[d], "Demand": v})
        if rows:
            st.dataframe(pd.DataFrame(rows).head(20), use_container_width=True, height=200)
        st.info("{:,} scaled slots, {:,} total orders across {} branches".format(len(demand), scaled_total, len(active_branches)))

    # === CAPACITY PREVIEW ===
    with st.expander("Capacity preview (Adj.m -- auto-loaded)", expanded=False):
        cap = st.session_state.get("capacity", {})
        if cap:
            cap_rows = []
            days_h = ["", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            seen = set()
            for (b, d), v in sorted(cap.items()):
                if b not in seen and len(cap_rows) < 30:
                    row = {"Branch": b}
                    for dd in range(1, 8):
                        row[days_h[dd]] = cap.get((b, dd), 2.0)
                    cap_rows.append(row)
                    seen.add(b)
            st.dataframe(pd.DataFrame(cap_rows), use_container_width=True, height=200)
            st.info("{:,} entries, {} branches".format(len(cap), len(seen)))

    # === SFT LOGICS SUMMARY ===
    with st.expander("SFT Logics (read-only for user, editable in Admin)", expanded=False):
        from config import cfg as _cfg
        lg = st.session_state.get("logics", {})
        lc1, lc2, lc3 = st.columns(3)
        lc1.metric("5D idle penalty", "-{} SAR".format(_cfg.penalty_5d))
        lc2.metric("6D idle penalty", "-{} SAR".format(_cfg.penalty_6d))
        lc3.metric("Logics entries", len(lg))
        st.markdown("**Cost variables:** 3P Cost/order = {} | Staff Cost/hr = {} | V. Cost/order = {}".format(
            _cfg.cost_3p_per_order, _cfg.cost_staff_per_hour, _cfg.cost_variable_per_order))
        st.markdown("**Car penalty:** Soft -- excess drivers pay idle cost per hour-slot")
        if lg:
            sample = []
            for (k, d, c), v in sorted(lg.items())[:8]:
                sample.append({"Drivers": k, "Demand": d, "Capacity": c, "Profit/hr": round(v["p"], 2), "Utilization": round(v["u"], 2)})
            st.dataframe(pd.DataFrame(sample), use_container_width=True)

    # === CONFIGURE ===
    st.markdown("---")
    st.markdown("### Step 2 -- Configure")
    test_mode = st.checkbox("Test mode (10 branches -- for cloud pilot)", value=True)
    col1, col2 = st.columns(2)
    with col1:
        target = st.number_input("Target Saudi drivers", 1, 500, 10 if test_mode else 150)
    with col2:
        bt_f = st.file_uploader("Branch 5D/6D (optional)", type=["xlsx"], key="sft_bt")
        if bt_f:
            df_bt = pd.read_excel(bt_f)
            bt = {}
            for _, r in df_bt.iterrows():
                bname = str(r.iloc[0]).strip()
                stype = "6D" if str(r.iloc[1]).strip().upper() == "6D" else "5D"
                bt[bname] = stype
            st.session_state["branch_types"] = bt
            n5 = sum(1 for v in bt.values() if v == "5D")
            n6 = sum(1 for v in bt.values() if v == "6D")
            st.success("5D: {}, 6D: {}".format(n5, n6))

    from data.validators import load_and_validate_cars, load_restricted_branches
    system_branches = set(active_branches)
    cars_f = st.file_uploader("Cars restriction", type=["xlsx", "xls"], key="sft_cars")
    if cars_f:
        cars, warns = load_and_validate_cars(cars_f, system_branches)
        st.session_state["cars"] = cars
        if warns:
            parts = ["`{}`->`{}`".format(u, s) for u, s in warns[:5]]
            st.warning("**Mismatches:** " + ", ".join(parts))
        else:
            st.success("Cars: {} branches".format(len(cars)))

    restr_f = st.file_uploader("Restricted branches", type=["xlsx"], key="sft_restr")
    if restr_f:
        st.session_state["restricted"] = load_restricted_branches(restr_f)
        st.success("Excluded: {} branches".format(len(st.session_state["restricted"])))

    with st.expander("Current deployment (comparison)"):
        dep_f = st.file_uploader("Branch | Drivers", type=["xlsx"], key="sft_dep")
        if dep_f:
            df_d = pd.read_excel(dep_f)
            dep = {}
            for _, r in df_d.iterrows():
                dep[str(r.iloc[0]).strip()] = int(r.iloc[1])
            st.session_state["current_deploy"] = dep
            st.success("Loaded: {} branches".format(len(dep)))

    # === RUN ===
    st.markdown("---")
    if st.button("Run SFT Hiring Optimizer", type="primary", use_container_width=True):
        from engines.sft_hiring import SFTHiringEngine
        run_branches = active_branches[:10] if test_mode else active_branches
        engine = SFTHiringEngine(
            demand=demand,
            capacity=st.session_state.get("capacity", {}),
            logics=st.session_state["logics"],
            cap_levels=st.session_state["cap_levels"],
            dem_levels=st.session_state["dem_levels"],
            branch_types=st.session_state.get("branch_types", {}),
            branches=run_branches,
            cars=st.session_state.get("cars", {}),
            restricted=st.session_state.get("restricted", set()),
            current_deployment=st.session_state.get("current_deploy", {}),
        )
        progress = st.progress(0, "Starting...")
        def cb(pct, msg):
            progress.progress(min(pct, 100), msg)
        t0 = time.time()
        engine.run(target_drivers=target, progress_callback=cb)
        st.session_state["sft_engine"] = engine
        st.session_state["sft_done"] = True
        elapsed = time.time() - t0
        progress.progress(100, "Done in {:.0f}s".format(elapsed))
        st.rerun()

    # === RESULTS ===
    eng = st.session_state.get("sft_engine")
    if eng:
        res = eng.get_results()
        st.markdown("---")
        st.header("Results")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Allocated", res["total_drivers"])
        c2.metric("Active", res["active_branches"])
        c3.metric("Profit", "{:,.2f}".format(res["total_profit"]))
        c4.metric("Empty", res["total_branches"] - res["active_branches"])
        tabs = st.tabs(["Branch Summary", "Employee Details", "Comparison"])
        with tabs[0]:
            rows_b = []
            for b in sorted(eng.branches):
                nd = eng.allocation.get(b, 0)
                pr = eng.lookup.get(b, {}).get(nd, (0,))[0]
                rows_b.append({"Branch": b, "Type": eng.branch_types.get(b, "5D"), "Drivers": nd, "Profit": round(pr, 2)})
            st.dataframe(pd.DataFrame(rows_b).sort_values("Profit", ascending=False), use_container_width=True, height=400)
        with tabs[1]:
            if eng.attribution:
                st.dataframe(pd.DataFrame(eng.attribution), use_container_width=True, height=400)
        with tabs[2]:
            if eng.current_deployment:
                comp = []
                all_b = sorted(set(list(eng.allocation.keys()) + list(eng.current_deployment.keys())))
                for b in all_b:
                    cur = eng.current_deployment.get(b, 0)
                    mod = eng.allocation.get(b, 0)
                    comp.append({"Branch": b, "Current": cur, "Model": mod, "Delta": mod - cur})
                st.dataframe(pd.DataFrame(comp).sort_values("Delta", ascending=False), use_container_width=True, height=400)
        st.download_button(
            "Download Results (4 sheets)",
            data=eng.export_excel(),
            file_name="SFT_Results_{}.xlsx".format(time.strftime("%Y%m%d_%H%M%S")),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )


def page_eft():
    st.title("EFT Hiring (Expat)")
    if not st.session_state.get("sft_done"):
        st.warning("Complete SFT Hiring first.")
        return
    from config import cfg
    st.markdown("### EFT Logics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("EFT idle penalty", "-15.50 SAR")
    c2.metric("Staff Cost/hr", "{} SAR".format(cfg.cost_staff_per_hour))
    c3.metric("Car penalty", "0 (within headroom)")
    c4.metric("Shift range", "8-12H variable")
    st.markdown("**Cost variables:** 3P Cost/order = {} | V. Cost/order = {}".format(cfg.cost_3p_per_order, cfg.cost_variable_per_order))
    st.info("Coming next -- uses Logics_EFT, depends on SFT remaining orders.")

def page_sched():
    st.title("SFT + EFT Scheduling")
    from config import cfg
    st.markdown("### Scheduling Logics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Car penalty", "0 SAR (by design)")
    c2.metric("Staff Cost/hr", "{} SAR".format(cfg.cost_staff_per_hour))
    c3.metric("3P Cost/order", "{} SAR".format(cfg.cost_3p_per_order))
    c4.metric("V. Cost/order", "{} SAR".format(cfg.cost_variable_per_order))
    st.markdown("**Rules:** Saudi 5D: 8H/5D/2off | Saudi 6D: 8H/6D/1off | Expat: 8-12H/6D/1off")
    st.markdown("**Productivity rule:** When drivers < cars, productivity uses driver=car for calculation")
    st.info("Scheduling -- separate logics from hiring, employee restrictions apply.")

def page_mc():
    st.title("MC Optimizer")
    from config import cfg
    st.markdown("### MC Logics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Primary threshold", "{} ord/hr".format(cfg.mc_threshold_primary))
    c2.metric("Fallback threshold", "{} ord/hr".format(cfg.mc_threshold_fallback))
    c3.metric("Capacity threshold", "{} (eligibility)".format(cfg.mc_capacity_threshold))
    c4.metric("TTB 3P threshold", "{} min".format(cfg.mc_ttb_threshold))
    st.markdown("**Shift:** 8-12H | **Work days:** 6-7 | **Max MCs/branch:** {}".format(cfg.mc_max_default))
    st.markdown("**Dual run:** First at 0.8, retry 0-MC branches at 0.6")
    st.info("MC module -- all params configurable per run by admin.")

def page_cap():
    st.title("Capacity Model")
    st.info("Auto-assembled. Validation only.")

def page_poly():
    st.title("Polygon Optimization")
    st.info("Separate module -- MP routing, driver pool, A.TTCL.")

def page_admin():
    st.title("Admin Settings")
    if not is_admin():
        st.warning("Admin access required. Read-only view.")
        from config import cfg
        st.json(cfg.__dict__)
        return
    st.success("Admin access granted")
    from config import cfg

    st.markdown("### Logics per module")
    tab_sft, tab_eft, tab_sched, tab_mc, tab_poly = st.tabs(["SFT Hiring", "EFT Hiring", "Scheduling", "MC Optimizer", "Polygon"])

    with tab_sft:
        st.markdown("**SFT Hiring** -- Saudi drivers (5D/6D)")
        c1, c2, c3, c4 = st.columns(4)
        cfg.penalty_5d = c1.number_input("5D idle penalty (SAR)", value=cfg.penalty_5d, step=0.01, key="sft_p5")
        cfg.penalty_6d = c2.number_input("6D idle penalty (SAR)", value=cfg.penalty_6d, step=0.01, key="sft_p6")
        cfg.cost_3p_per_order = c3.number_input("3P Cost/order", value=cfg.cost_3p_per_order, step=0.25, key="sft_3p")
        cfg.cost_variable_per_order = c4.number_input("V. Cost/order", value=cfg.cost_variable_per_order, step=0.25, key="sft_vc")
        st.markdown("Car penalty: **Soft** (excess drivers x idle penalty per hour-slot)")

    with tab_eft:
        st.markdown("**EFT Hiring** -- Expat drivers (8-12H variable)")
        c1, c2, c3 = st.columns(3)
        c1.number_input("EFT idle penalty (SAR)", value=15.50, step=0.01, key="eft_pen")
        c2.number_input("3P Cost/order", value=cfg.cost_3p_per_order, step=0.25, key="eft_3p")
        c3.number_input("V. Cost/order", value=cfg.cost_variable_per_order, step=0.25, key="eft_vc")
        st.markdown("Car penalty: **0** (EFT works within SFT car headroom)")

    with tab_sched:
        st.markdown("**Scheduling** -- SFT + EFT combined")
        c1, c2, c3 = st.columns(3)
        c1.number_input("3P Cost/order", value=cfg.cost_3p_per_order, step=0.25, key="sch_3p")
        c2.number_input("Staff Cost/hr", value=cfg.cost_staff_per_hour, step=0.5, key="sch_st")
        c3.number_input("V. Cost/order", value=cfg.cost_variable_per_order, step=0.25, key="sch_vc")
        st.markdown("Car penalty: **0** (by design)")
        st.markdown("Productivity rule: when drivers < cars, use driver=car for calc")

    with tab_mc:
        st.markdown("**MC Optimizer** -- Maestro Captains")
        c1, c2, c3, c4 = st.columns(4)
        cfg.mc_threshold_primary = c1.number_input("Primary threshold", value=cfg.mc_threshold_primary, step=0.1, key="mc_t1")
        cfg.mc_threshold_fallback = c2.number_input("Fallback threshold", value=cfg.mc_threshold_fallback, step=0.1, key="mc_t2")
        cfg.mc_capacity_threshold = c3.number_input("Capacity threshold", value=cfg.mc_capacity_threshold, step=0.25, key="mc_cap")
        cfg.mc_ttb_threshold = c4.number_input("TTB 3P threshold (min)", value=cfg.mc_ttb_threshold, step=1.0, key="mc_ttb")
        st.markdown("Max MCs/branch default: {}".format(cfg.mc_max_default))

    with tab_poly:
        st.markdown("**Polygon** -- MP-to-branch routing")
        c1, c2 = st.columns(2)
        cfg.poly_penalty_per_order = c1.number_input("3P penalty (SAR/order)", value=cfg.poly_penalty_per_order, step=0.25, key="poly_pen")
        cfg.poly_penalty_cap_threshold = c2.number_input("Penalty cap threshold", value=cfg.poly_penalty_cap_threshold, step=0.25, key="poly_cap")

    st.markdown("---")
    st.markdown("### System parameters")
    c1, c2 = st.columns(2)
    cfg.ga_population = c1.number_input("GA population", value=cfg.ga_population, key="ap")
    cfg.ga_generations = c2.number_input("GA generations", value=cfg.ga_generations, key="ag")

    if st.button("Save all parameters", type="primary"):
        cfg.save()
        st.success("All parameters saved!")

    st.markdown("---")
    st.markdown("### Replace data (admin only)")
    f = st.file_uploader("New Simulation Model", type=["xlsx", "xlsm"], key="al")
    if f:
        try:
            from data.logics import load_logics_from_simulation
            lg, cl, dl = load_logics_from_simulation(f)
            st.session_state["logics"] = lg
            st.session_state["cap_levels"] = cl
            st.session_state["dem_levels"] = dl
            st.success("Loaded {} entries".format(len(lg)))
        except Exception as e:
            st.error(str(e))


# === MAIN ===

def main():
    if not check_login():
        return
    if not ensure_data():
        return
    with st.sidebar:
        st.markdown("## Maestro Pizza")
        role_label = "Admin" if is_admin() else "User"
        st.markdown("**{}** ({})".format(st.session_state.get("user", ""), role_label))
        st.markdown("---")
        page = st.radio(
            "Nav",
            ["Dashboard", "SFT Hiring", "EFT Hiring", "Scheduling",
             "MC Optimizer", "Capacity Model", "Polygon", "Admin"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.markdown("### Templates")
        for name in TEMPLATES:
            label = name.replace("_", " ").title()
            st.download_button(
                label,
                data=generate_template(name),
                file_name="{}_SAMPLE.csv".format(name),
                mime="text/csv",
                key="dl_{}".format(name),
            )
        if st.button("Logout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    pages = {
        "Dashboard": page_home,
        "SFT Hiring": page_sft,
        "EFT Hiring": page_eft,
        "Scheduling": page_sched,
        "MC Optimizer": page_mc,
        "Capacity Model": page_cap,
        "Polygon": page_poly,
        "Admin": page_admin,
    }
    pages.get(page, page_home)()

if __name__ == "__main__":
    main()
