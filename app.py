"""Commerce POS QA Bot - Streamlit UI.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from extractors import (
    extract_kyc,
    extract_payment_gateway,
    extract_repay,
    extract_transact,
    extract_wp_onboarded,
    load_merchant_from_dir,
)
from facts import MerchantFacts
from report import build_excel_report, _facts_rows
from rules import CheckResult, run_rules
from workflows import (
    WORKFLOW_CLUB_SALE,
    WORKFLOW_MIGRATION,
    WORKFLOW_NEW_ONBOARDING,
    all_workflows,
    rules_for_workflow,
)


APP_DIR = Path(__file__).parent
MOCK_PASS = APP_DIR / "mock_data" / "merchant_pass"
MOCK_FAIL = APP_DIR / "mock_data" / "merchant_fail"


st.set_page_config(
    page_title="Commerce POS QA Bot",
    page_icon=":bar_chart:",
    layout="wide",
)


# -----------------------------------------------------------------------------
# Sidebar - workflow + data source
# -----------------------------------------------------------------------------

with st.sidebar:
    st.title("Commerce POS QA Bot")
    st.caption("ABCIIB-207 - PaymentOps hackathon prototype")

    workflow = st.selectbox(
        "QA Workflow",
        options=all_workflows(),
        index=1,
        help="Choose which checklist sheet to run, matching the Excel from PaymentOps.",
    )

    st.divider()
    st.subheader("Source files")

    st.markdown(
        "Upload one merchant's exports from each system, or load a mock merchant "
        "to see the demo end-to-end."
    )

    col_a, col_b = st.columns(2)
    if col_a.button("Load mock: PASS", use_container_width=True):
        st.session_state["mock_dir"] = str(MOCK_PASS)
        st.session_state.pop("uploaded", None)
    if col_b.button("Load mock: FAIL", use_container_width=True):
        st.session_state["mock_dir"] = str(MOCK_FAIL)
        st.session_state.pop("uploaded", None)

    st.divider()
    st.markdown("**Or upload your own:**")
    kyc_file = st.file_uploader("KYC record (.json)", type=["json"])
    pg_file = st.file_uploader("Payment Gateway export (.csv)", type=["csv"])
    transact_file = st.file_uploader("Commerce Transact export (.csv)", type=["csv"])
    wp_file = st.file_uploader("WP Onboarded Clubs row (.xlsx)", type=["xlsx"])
    repay_file = st.file_uploader("Repay status (.csv)", type=["csv"])

    if any([kyc_file, pg_file, transact_file, wp_file, repay_file]):
        st.session_state["uploaded"] = {
            "kyc": kyc_file,
            "pg": pg_file,
            "transact": transact_file,
            "wp": wp_file,
            "repay": repay_file,
        }
        st.session_state.pop("mock_dir", None)


# -----------------------------------------------------------------------------
# Build MerchantFacts from whichever source is active
# -----------------------------------------------------------------------------

def _facts_from_session() -> MerchantFacts | None:
    if mock_dir := st.session_state.get("mock_dir"):
        return load_merchant_from_dir(mock_dir)
    if uploaded := st.session_state.get("uploaded"):
        m = MerchantFacts()
        try:
            if uploaded.get("kyc"):
                m.kyc = extract_kyc(uploaded["kyc"])
            if uploaded.get("pg"):
                m.pg = extract_payment_gateway(uploaded["pg"])
            if uploaded.get("transact"):
                m.transact = extract_transact(uploaded["transact"])
            if uploaded.get("wp"):
                m.wp = extract_wp_onboarded(uploaded["wp"])
            if uploaded.get("repay"):
                m.repay = extract_repay(uploaded["repay"])
            return m
        except Exception as e:
            st.error(f"Failed to parse uploaded file: {e}")
            return None
    return None


# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------

st.title("Commerce POS QA Bot")
st.markdown(
    "Automates the cross-system QA checks the Payment Operations team performs "
    "today before activating a new Commerce POS merchant. "
    "**Manual today: ~30 min/merchant.**  **Automated: ~5 sec.**"
)

facts = _facts_from_session()

if facts is None:
    st.info(
        "**Get started:** click **Load mock: PASS** or **Load mock: FAIL** in the sidebar "
        "to see the demo, or upload a merchant's source files."
    )
    st.stop()


# -----------------------------------------------------------------------------
# Run rules
# -----------------------------------------------------------------------------

t0 = time.perf_counter()
results: list[CheckResult] = run_rules(facts, rules_for_workflow(workflow))
elapsed_ms = (time.perf_counter() - t0) * 1000

pass_count = sum(1 for r in results if r.status == "PASS")
fail_count = sum(1 for r in results if r.status == "FAIL")
warn_count = sum(1 for r in results if r.status == "WARN")
total = len(results)


# -----------------------------------------------------------------------------
# Summary banner
# -----------------------------------------------------------------------------

st.subheader(f"Merchant: {facts.display_name}")

if fail_count == 0 and warn_count == 0:
    st.success(
        f"**Ready to activate.**  All {total} checks passed for the "
        f"**{workflow}** workflow (in {elapsed_ms:.0f} ms)."
    )
elif fail_count > 0:
    st.error(
        f"**{fail_count} issue(s) found** out of {total} checks for the "
        f"**{workflow}** workflow.  Do not activate until resolved."
    )
else:
    st.warning(
        f"**{warn_count} warning(s)** out of {total} checks for the "
        f"**{workflow}** workflow.  Review before activating."
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total checks", total)
m2.metric("Passed", pass_count)
m3.metric("Failed", fail_count)
m4.metric("Warnings", warn_count)


# -----------------------------------------------------------------------------
# Tabs: Checklist results | Side-by-side facts | Raw data
# -----------------------------------------------------------------------------

tab_checks, tab_facts, tab_raw, tab_download = st.tabs([
    "Checklist results",
    "Side-by-side facts",
    "Raw extracted data",
    "Download QA report",
])


def _status_badge(status: str) -> str:
    icons = {"PASS": ":white_check_mark:", "FAIL": ":x:", "WARN": ":warning:"}
    return f"{icons.get(status, '')}  **{status}**"


with tab_checks:
    st.markdown("Results grouped by section, in the same order as the QA checklist.")

    sections: dict[str, list[CheckResult]] = {}
    for r in results:
        sections.setdefault(r.section, []).append(r)

    for section, items in sections.items():
        sec_pass = sum(1 for r in items if r.status == "PASS")
        sec_fail = sum(1 for r in items if r.status == "FAIL")
        header = f"{section} ({sec_pass}/{len(items)} passed"
        if sec_fail:
            header += f", {sec_fail} failed"
        header += ")"
        with st.expander(header, expanded=any(r.status != "PASS" for r in items)):
            for r in items:
                st.markdown(f"{_status_badge(r.status)}  -  {r.label}")
                if r.status != "PASS":
                    cols = st.columns([1, 1, 1])
                    cols[0].markdown(f"**Expected:** {r.expected or '_(empty)_'}")
                    cols[1].markdown(f"**Actual:** {r.actual or '_(empty)_'}")
                    cols[2].markdown(f"**Sources:** {', '.join(r.sources)}")
                    if r.detail:
                        st.caption(f"Detail: {r.detail}")
                if r.checklist_ref:
                    st.caption(f"Checklist: _{r.checklist_ref}_")
                st.markdown("---")


with tab_facts:
    st.markdown(
        "Same data shown across each source system - mismatches are easy to spot."
    )
    df = pd.DataFrame(_facts_rows(facts))

    def _style_row(row: pd.Series) -> list[str]:
        non_empty = [v for v in [row["KYC"], row["Payment Gateway"], row["Commerce Transact"]] if v]
        clash = len({str(v).strip().lower() for v in non_empty}) > 1
        color = "background-color: #FFC7CE" if clash and len(non_empty) > 1 else ""
        return ["", color, color, color]

    st.dataframe(
        df.style.apply(_style_row, axis=1),
        use_container_width=True,
        hide_index=True,
    )


with tab_raw:
    st.markdown("The normalized data extracted from each source file.")
    sec1, sec2 = st.columns(2)
    with sec1:
        st.markdown("**KYC / Salesforce**")
        st.json(facts.kyc.__dict__, expanded=False)
        st.markdown("**Payment Gateway**")
        st.json(facts.pg.__dict__, expanded=False)
        st.markdown("**WP Onboarded Clubs**")
        st.json(facts.wp.__dict__, expanded=False)
    with sec2:
        st.markdown("**Commerce Transact**")
        st.json(facts.transact.__dict__, expanded=False)
        st.markdown("**Repay**")
        st.json(facts.repay.__dict__, expanded=False)


with tab_download:
    st.markdown(
        "Download the QA report as Excel - the analyst can attach this to the QA "
        "ticket today, no behavior change required."
    )
    xlsx_bytes = build_excel_report(workflow, facts.display_name, results, facts)
    st.download_button(
        "Download QA Report (Excel)",
        data=xlsx_bytes,
        file_name=f"qa_report_{facts.club_number or 'merchant'}_{workflow.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


# -----------------------------------------------------------------------------
# Footer
# -----------------------------------------------------------------------------

st.divider()
st.caption(
    "Rules are sourced directly from `Commerce QA checklist - MS.xlsx`. "
    "No judgement calls - just automating what's already documented. "
    "See README.md for the full demo script and the data ask for Missy / Stephanie."
)
