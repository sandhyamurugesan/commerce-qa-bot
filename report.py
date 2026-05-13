"""Build a downloadable Excel QA report from a list of CheckResults.

Two sheets:
- 'QA Results' - one row per rule (color-coded PASS/FAIL/WARN).
- 'Facts' - the normalized cross-system view, for audit.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from facts import MerchantFacts
from rules import CheckResult


_FILL = {
    "PASS": PatternFill("solid", fgColor="C6EFCE"),
    "FAIL": PatternFill("solid", fgColor="FFC7CE"),
    "WARN": PatternFill("solid", fgColor="FFEB9C"),
}
_FONT = {
    "PASS": Font(color="006100", bold=True),
    "FAIL": Font(color="9C0006", bold=True),
    "WARN": Font(color="9C5700", bold=True),
}


def _facts_rows(m: MerchantFacts) -> list[dict]:
    """Side-by-side facts: one row per field, columns per source."""
    rows = [
        {
            "Field": "Legal Name",
            "KYC": m.kyc.legal_name,
            "Payment Gateway": m.pg.legal_name,
            "Commerce Transact": "",
        },
        {
            "Field": "DBA Name",
            "KYC": m.kyc.dba_name,
            "Payment Gateway": m.pg.dba_name,
            "Commerce Transact": "",
        },
        {
            "Field": "TIN last 4",
            "KYC": m.kyc.tin_last4,
            "Payment Gateway": m.pg.tin_last4,
            "Commerce Transact": "",
        },
        {
            "Field": "MCC Code",
            "KYC": m.kyc.mcc_code,
            "Payment Gateway": m.pg.mcc_code,
            "Commerce Transact": "",
        },
        {
            "Field": "Billing Descriptor",
            "KYC": "",
            "Payment Gateway": m.pg.billing_descriptor,
            "Commerce Transact": "",
        },
        {
            "Field": "Processor",
            "KYC": "",
            "Payment Gateway": m.pg.processor,
            "Commerce Transact": "",
        },
        {
            "Field": "Transaction Type",
            "KYC": "",
            "Payment Gateway": m.pg.transaction_type,
            "Commerce Transact": "",
        },
        {
            "Field": "Card Types",
            "KYC": ", ".join(m.kyc.card_types),
            "Payment Gateway": ", ".join(m.pg.card_types),
            "Commerce Transact": "",
        },
        {
            "Field": "OmniToken Enabled",
            "KYC": "",
            "Payment Gateway": "Yes" if m.pg.omni_token_enabled else "No",
            "Commerce Transact": "",
        },
        {
            "Field": "Org Code",
            "KYC": "",
            "Payment Gateway": m.pg.org_code,
            "Commerce Transact": "",
        },
        {
            "Field": "Bank Account last 4",
            "KYC": m.kyc.bank_account_last4,
            "Payment Gateway": "",
            "Commerce Transact": m.transact.bank_account_last4,
        },
        {
            "Field": "Bank Transfer Method",
            "KYC": m.kyc.transfer_method,
            "Payment Gateway": "",
            "Commerce Transact": m.transact.transfer_method,
        },
        {
            "Field": "Deposit Schedule",
            "KYC": m.kyc.deposit_schedule,
            "Payment Gateway": "",
            "Commerce Transact": m.transact.deposit_schedule,
        },
        {
            "Field": "Chargeback Email",
            "KYC": m.kyc.chargeback_email,
            "Payment Gateway": "",
            "Commerce Transact": m.transact.chargeback_email,
        },
        {
            "Field": "Customer Service Phone",
            "KYC": m.kyc.customer_service_phone,
            "Payment Gateway": "",
            "Commerce Transact": m.transact.customer_service_phone,
        },
        {
            "Field": "Repay MID Status",
            "KYC": "",
            "Payment Gateway": "",
            "Commerce Transact": m.repay.mid_status,
        },
        {
            "Field": "KYC Stage (WP Onboarded Clubs)",
            "KYC": "",
            "Payment Gateway": "",
            "Commerce Transact": m.wp.kyc_stage,
        },
    ]
    return rows


def build_excel_report(
    workflow: str,
    merchant_name: str,
    results: list[CheckResult],
    facts: MerchantFacts,
    ai_brief: str = "",
) -> bytes:
    """Return an .xlsx file as bytes for Streamlit to serve."""
    buf = BytesIO()

    pass_count = sum(1 for r in results if r.status == "PASS")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    warn_count = sum(1 for r in results if r.status == "WARN")

    results_df = pd.DataFrame([
        {
            "Status": r.status,
            "Section": r.section,
            "Check": r.label,
            "Expected": r.expected,
            "Actual": r.actual,
            "Detail": r.detail,
            "Sources": ", ".join(r.sources),
            "Checklist Reference": r.checklist_ref,
        }
        for r in results
    ])
    facts_df = pd.DataFrame(_facts_rows(facts))

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="QA Results", index=False, startrow=4)
        facts_df.to_excel(writer, sheet_name="Facts", index=False)
        if ai_brief:
            pd.DataFrame({"AI Validation Brief": ai_brief.splitlines()}).to_excel(
                writer,
                sheet_name="AI Review",
                index=False,
            )

        wb = writer.book
        ws = writer.sheets["QA Results"]

        ws["A1"] = "Commerce POS QA Report"
        ws["A1"].font = Font(size=16, bold=True)
        ws["A2"] = f"Workflow: {workflow}    Merchant: {merchant_name}"
        ws["A3"] = (
            f"Generated: {datetime.now():%Y-%m-%d %H:%M}    "
            f"Result: {pass_count} PASS / {fail_count} FAIL / {warn_count} WARN "
            f"(out of {len(results)} checks)"
        )
        ws["A2"].font = Font(bold=True)
        ws["A3"].font = Font(italic=True)

        for col_idx, _ in enumerate(results_df.columns, start=1):
            ws.cell(row=5, column=col_idx).font = Font(bold=True)

        for row_offset, r in enumerate(results, start=6):
            cell = ws.cell(row=row_offset, column=1)
            cell.fill = _FILL.get(r.status, PatternFill())
            cell.font = _FONT.get(r.status, Font())
            cell.alignment = Alignment(horizontal="center")

        widths = {"A": 10, "B": 22, "C": 50, "D": 30, "E": 50, "F": 40, "G": 25, "H": 60}
        for col, width in widths.items():
            ws.column_dimensions[col].width = width

        ws_facts = writer.sheets["Facts"]
        for col_idx, _ in enumerate(facts_df.columns, start=1):
            ws_facts.cell(row=1, column=col_idx).font = Font(bold=True)
        for col, width in {"A": 32, "B": 35, "C": 35, "D": 35}.items():
            ws_facts.column_dimensions[col].width = width

        if ai_brief:
            ws_ai = writer.sheets["AI Review"]
            ws_ai["A1"].font = Font(bold=True)
            ws_ai.column_dimensions["A"].width = 120
            for row in ws_ai.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")

    return buf.getvalue()
