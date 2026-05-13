"""QA rules - one function per checklist item.

Each rule reads from MerchantFacts and returns a CheckResult. The rule's
docstring is the one-line label shown in the UI; `checklist_ref` cites the
exact wording from the source `Commerce QA checklist - MS.xlsx`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from facts import (
    MerchantFacts,
    SOURCE_KYC,
    SOURCE_PG,
    SOURCE_REPAY,
    SOURCE_TRANSACT,
    SOURCE_WP,
)


PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


@dataclass
class CheckResult:
    rule_id: str
    label: str
    status: str
    expected: str = ""
    actual: str = ""
    sources: list[str] = field(default_factory=list)
    detail: str = ""
    checklist_ref: str = ""
    section: str = "General"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _eq(a: Any, b: Any) -> bool:
    return _norm(a) == _norm(b)


# -----------------------------------------------------------------------------
# Rules
# -----------------------------------------------------------------------------

def rule_legal_name_match(m: MerchantFacts) -> CheckResult:
    """Legal Name matches between KYC and Payment Gateway."""
    expected = m.kyc.legal_name
    actual = m.pg.legal_name
    status = PASS if expected and _eq(expected, actual) else FAIL
    return CheckResult(
        rule_id="legal_name_match",
        label="Legal Name matches between KYC and Payment Gateway",
        status=status,
        expected=expected,
        actual=actual,
        sources=[SOURCE_KYC, SOURCE_PG],
        checklist_ref="Legal Name is correct",
        section="Merchant Identity",
    )


def rule_dba_name_match(m: MerchantFacts) -> CheckResult:
    """DBA Name matches between KYC and Payment Gateway."""
    expected = m.kyc.dba_name
    actual = m.pg.dba_name
    status = PASS if expected and _eq(expected, actual) else FAIL
    return CheckResult(
        rule_id="dba_name_match",
        label="DBA Name matches between KYC and Payment Gateway",
        status=status,
        expected=expected,
        actual=actual,
        sources=[SOURCE_KYC, SOURCE_PG],
        checklist_ref="Confirm banking matches DBA name or legal entity",
        section="Merchant Identity",
    )


def rule_tin_last4_match(m: MerchantFacts) -> CheckResult:
    """Last 4 of Tax ID matches KYC."""
    expected = m.kyc.tin_last4
    actual = m.pg.tin_last4
    status = PASS if expected and _eq(expected, actual) else FAIL
    return CheckResult(
        rule_id="tin_last4_match",
        label="Last 4 of Tax ID matches KYC",
        status=status,
        expected=expected,
        actual=actual,
        sources=[SOURCE_KYC, SOURCE_PG],
        checklist_ref="Last 4 of the Tax ID are correct",
        section="Merchant Identity",
    )


def rule_mcc_code_correct(m: MerchantFacts) -> CheckResult:
    """MCC Code matches KYC (typically 7997 for clubs)."""
    expected = m.kyc.mcc_code
    actual = m.pg.mcc_code
    status = PASS if expected and _eq(expected, actual) else FAIL
    detail = ""
    if status == PASS and expected != "7997":
        detail = "MCC is not 7997 (typical for clubs) - confirm with UW"
    return CheckResult(
        rule_id="mcc_code_correct",
        label="MCC Code matches KYC",
        status=status,
        expected=expected,
        actual=actual,
        sources=[SOURCE_KYC, SOURCE_PG],
        detail=detail,
        checklist_ref="Correct MCC Code (usually 7997) / MCC Code is correct",
        section="Merchant Identity",
    )


def rule_billing_descriptor_format(m: MerchantFacts) -> CheckResult:
    """Billing Descriptor starts with 'ABC*P' + club number, max 25 chars."""
    desc = m.pg.billing_descriptor
    club = m.club_number
    issues = []
    if not desc.upper().startswith("ABC*P"):
        issues.append("must start with 'ABC*P'")
    if club and club not in desc:
        issues.append(f"must include club number '{club}'")
    if len(desc) > 25:
        issues.append(f"length is {len(desc)}, max is 25")
    status = PASS if not issues else FAIL
    return CheckResult(
        rule_id="billing_descriptor_format",
        label="Billing Descriptor format (ABC*P + club number, max 25 chars)",
        status=status,
        expected=f"ABC*P {club} (<= 25 chars)",
        actual=f"{desc} ({len(desc)} chars)",
        sources=[SOURCE_PG],
        detail="; ".join(issues),
        checklist_ref="Billing Descriptor - Includes ABC*P and club number. Max character limit is 25.",
        section="Payment Gateway Onboarding",
    )


def rule_processor_correct(m: MerchantFacts) -> CheckResult:
    """Processor matches the country (US/PR = ON1061, CAD = 0TP831)."""
    country = (m.kyc.country or m.wp.country or "US").upper()
    actual = m.pg.processor
    if country in {"CA", "CAD", "CANADA"}:
        expected = "Worldpay Core POS MA 0TP831"
        ok = "0TP831" in actual
    else:
        expected = "Worldpay Core POS ON1061"
        ok = "ON1061" in actual and "0N1064" not in actual
    status = PASS if ok else FAIL
    return CheckResult(
        rule_id="processor_correct",
        label="Processor matches country (ON1061 US/PR, 0TP831 CAD)",
        status=status,
        expected=expected,
        actual=actual,
        sources=[SOURCE_PG],
        checklist_ref="Processor shows Worldpay Core POS ON1061 (CAD: 0TP831; PR: ON1061 NOT 0N1064)",
        section="Payment Gateway Onboarding",
    )


def rule_transaction_type(m: MerchantFacts) -> CheckResult:
    """Transaction Type is set to Online Store."""
    actual = m.pg.transaction_type
    status = PASS if _eq(actual, "Online Store") else FAIL
    return CheckResult(
        rule_id="transaction_type",
        label="Transaction Type is 'Online Store'",
        status=status,
        expected="Online Store",
        actual=actual,
        sources=[SOURCE_PG],
        checklist_ref="Transaction Type is set for Online Store",
        section="Payment Gateway Onboarding",
    )


def rule_card_types_match_repay(m: MerchantFacts) -> CheckResult:
    """All card types in Payment Gateway match Repay setup."""
    pg_set = {c.lower() for c in m.pg.card_types}
    repay_set = {c.lower() for c in m.repay.card_types}
    if not pg_set or not repay_set:
        return CheckResult(
            rule_id="card_types_match_repay",
            label="Card types match between Payment Gateway and Repay",
            status=WARN,
            expected=", ".join(sorted(repay_set)) or "(missing)",
            actual=", ".join(sorted(pg_set)) or "(missing)",
            sources=[SOURCE_PG, SOURCE_REPAY],
            detail="One side is missing card type data",
            checklist_ref="All card types are set up to match Repay",
            section="Payment Gateway Onboarding",
        )
    diff = pg_set.symmetric_difference(repay_set)
    status = PASS if not diff else FAIL
    return CheckResult(
        rule_id="card_types_match_repay",
        label="Card types match between Payment Gateway and Repay",
        status=status,
        expected=", ".join(sorted(repay_set)),
        actual=", ".join(sorted(pg_set)),
        sources=[SOURCE_PG, SOURCE_REPAY],
        detail=("Differences: " + ", ".join(sorted(diff))) if diff else "",
        checklist_ref="All card types are set up to match Repay",
        section="Payment Gateway Onboarding",
    )


def rule_omni_token_enabled(m: MerchantFacts) -> CheckResult:
    """OmniToken is enabled in Payment Gateway."""
    status = PASS if m.pg.omni_token_enabled else FAIL
    return CheckResult(
        rule_id="omni_token_enabled",
        label="OmniToken is enabled",
        status=status,
        expected="Enabled (blue box checked)",
        actual="Enabled" if m.pg.omni_token_enabled else "Not enabled",
        sources=[SOURCE_PG],
        checklist_ref="OmniToken is enabled (blue box checked)",
        section="Payment Gateway Onboarding",
    )


def rule_terminals_present(m: MerchantFacts) -> CheckResult:
    """Two terminals (POS + MICO) are present, label length 25-27 chars."""
    terms = m.pg.terminals
    if len(terms) != 2:
        return CheckResult(
            rule_id="terminals_present",
            label="Two terminals (POS + MICO) present with correct label length",
            status=FAIL,
            expected="2 terminals (POS + MICO)",
            actual=f"{len(terms)} terminal(s)",
            sources=[SOURCE_PG],
            checklist_ref="Under Terminals Tab make sure 2 terminals are present, POS and Online (1 and MICO), 25-27 chars",
            section="Terminals",
        )
    types_present = {_norm(t.get("type")) for t in terms}
    issues = []
    if "pos" not in types_present:
        issues.append("missing POS terminal")
    if "mico" not in types_present:
        issues.append("missing MICO terminal")
    for t in terms:
        label_len = len(t.get("label", ""))
        if not 25 <= label_len <= 27:
            issues.append(f"'{t.get('label')}' length {label_len} (need 25-27)")
    status = PASS if not issues else FAIL
    return CheckResult(
        rule_id="terminals_present",
        label="Two terminals (POS + MICO) present with correct label length",
        status=status,
        expected="2 terminals (POS + MICO), labels 25-27 chars",
        actual="; ".join(f"{t.get('type')}: '{t.get('label')}' ({len(t.get('label', ''))} chars)" for t in terms),
        sources=[SOURCE_PG],
        detail="; ".join(issues),
        checklist_ref="Under Terminals Tab make sure 2 terminals are present, POS and Online (1 and MICO), 25-27 chars",
        section="Terminals",
    )


def rule_bank_account_match(m: MerchantFacts) -> CheckResult:
    """Bank account last 4 matches between KYC and Commerce Transact."""
    expected = m.kyc.bank_account_last4
    actual = m.transact.bank_account_last4
    status = PASS if expected and _eq(expected, actual) else FAIL
    return CheckResult(
        rule_id="bank_account_match",
        label="Bank account last 4 matches KYC",
        status=status,
        expected=expected,
        actual=actual,
        sources=[SOURCE_KYC, SOURCE_TRANSACT],
        checklist_ref="Check last 4 of Checking Account",
        section="Banking",
    )


def rule_bank_transfer_method(m: MerchantFacts) -> CheckResult:
    """Bank account transfer method must be ACH (not Wire) for POS."""
    actual = m.transact.transfer_method
    status = PASS if _eq(actual, "ACH") else FAIL
    return CheckResult(
        rule_id="bank_transfer_method",
        label="Bank transfer method is ACH (not Wire)",
        status=status,
        expected="ACH",
        actual=actual,
        sources=[SOURCE_TRANSACT],
        checklist_ref="Bank account for POS should be set for ACH not Wire",
        section="Banking",
    )


def rule_deposit_schedule_daily(m: MerchantFacts) -> CheckResult:
    """Deposit Schedule is set to Daily."""
    actual = m.transact.deposit_schedule
    status = PASS if _eq(actual, "Daily") else FAIL
    return CheckResult(
        rule_id="deposit_schedule_daily",
        label="Deposit Schedule is set to Daily",
        status=status,
        expected="Daily",
        actual=actual,
        sources=[SOURCE_TRANSACT],
        checklist_ref="Verify Deposit Schedule is set to Daily",
        section="Banking",
    )


def rule_chargeback_email_match(m: MerchantFacts) -> CheckResult:
    """Chargeback email in Commerce Transact matches KYC."""
    expected = m.kyc.chargeback_email
    actual = m.transact.chargeback_email
    status = PASS if expected and _eq(expected, actual) else FAIL
    return CheckResult(
        rule_id="chargeback_email_match",
        label="Chargeback email matches KYC",
        status=status,
        expected=expected,
        actual=actual,
        sources=[SOURCE_KYC, SOURCE_TRANSACT],
        checklist_ref="Confirm Chargeback email is correct on Profile tab",
        section="Commerce Transact",
    )


def rule_cs_phone_not_owner(m: MerchantFacts) -> CheckResult:
    """Customer service phone is not the same as any owner's phone."""
    cs = m.transact.customer_service_phone or m.kyc.customer_service_phone
    if not cs:
        return CheckResult(
            rule_id="cs_phone_not_owner",
            label="Customer service phone is not an owner's phone",
            status=WARN,
            expected="Non-owner phone",
            actual="(missing)",
            sources=[SOURCE_KYC, SOURCE_TRANSACT],
            checklist_ref="DBA and Corp Phone number do not match the Signer's Phone number",
            section="Commerce Transact",
        )
    owner_phones = {_norm(o.get("phone", "")) for o in m.kyc.owners}
    overlap = _norm(cs) in owner_phones and _norm(cs) != ""
    status = FAIL if overlap else PASS
    return CheckResult(
        rule_id="cs_phone_not_owner",
        label="Customer service phone is not an owner's phone",
        status=status,
        expected="Non-owner phone",
        actual=cs,
        sources=[SOURCE_KYC, SOURCE_TRANSACT],
        detail="Customer service phone matches an owner phone" if overlap else "",
        checklist_ref="DBA and Corp Phone number do not match the Signer's Phone number",
        section="Commerce Transact",
    )


def rule_owners_25pct(m: MerchantFacts) -> CheckResult:
    """All owners with >=25% are listed in Payment Gateway."""
    kyc_owners = [o for o in m.kyc.owners if float(o.get("ownership_pct", 0) or 0) >= 25]
    pg_owners = m.pg.owners
    expected_names = {_norm(o.get("name")) for o in kyc_owners}
    actual_names = {_norm(o.get("name")) for o in pg_owners}
    missing = expected_names - actual_names
    status = PASS if not missing else FAIL
    return CheckResult(
        rule_id="owners_25pct",
        label="All owners with >=25% ownership are listed",
        status=status,
        expected=", ".join(sorted(expected_names)),
        actual=", ".join(sorted(actual_names)),
        sources=[SOURCE_KYC, SOURCE_PG],
        detail=("Missing in PG: " + ", ".join(sorted(missing))) if missing else "",
        checklist_ref="All owners with 25% or more ownership are listed",
        section="Merchant Identity",
    )


CLIENT_TYPE_TO_ORG = {
    "abc psp": "99000",
    "planet fitness": "161600",
    "cad": "21600",
}


def rule_org_code_match(m: MerchantFacts) -> CheckResult:
    """Org code matches client type (ABC PSP 99000, PF 161600, CAD 21600)."""
    ct = _norm(m.kyc.client_type)
    expected = CLIENT_TYPE_TO_ORG.get(ct, "")
    actual = m.pg.org_code or m.wp.org_code
    if not expected:
        return CheckResult(
            rule_id="org_code_match",
            label="Billing MID is on the correct Org",
            status=WARN,
            expected="Known client type",
            actual=f"Client type '{m.kyc.client_type}' not recognized",
            sources=[SOURCE_KYC, SOURCE_PG],
            checklist_ref="Billing MID is on the correct Org - ABC PSP 99000, Planet Fitness 161600, CAD 21600",
            section="Merchant Identity",
        )
    status = PASS if _eq(expected, actual) else FAIL
    return CheckResult(
        rule_id="org_code_match",
        label="Billing MID is on the correct Org",
        status=status,
        expected=expected,
        actual=actual,
        sources=[SOURCE_KYC, SOURCE_PG],
        checklist_ref="Billing MID is on the correct Org - ABC PSP 99000, Planet Fitness 161600, CAD 21600",
        section="Merchant Identity",
    )


def rule_repay_mid_closed(m: MerchantFacts) -> CheckResult:
    """Repay MID is closed (migration only)."""
    status = PASS if _eq(m.repay.mid_status, "Closed") else FAIL
    return CheckResult(
        rule_id="repay_mid_closed",
        label="Repay MID is closed",
        status=status,
        expected="Closed",
        actual=m.repay.mid_status,
        sources=[SOURCE_REPAY],
        checklist_ref="Check that Repay MID has been closed",
        section="Migration Completion",
    )


def rule_kyc_stage_complete(m: MerchantFacts) -> CheckResult:
    """KYC stage is at least 'MS Stage 1 - Completed' (not still in progress)."""
    stage = m.wp.kyc_stage
    is_in_progress = "in progress" in stage.lower()
    status = FAIL if is_in_progress or not stage else PASS
    return CheckResult(
        rule_id="kyc_stage_complete",
        label="KYC stage is past 'MS Stage 1 - In Progress'",
        status=status,
        expected="MS Stage 1 - Completed (or beyond)",
        actual=stage,
        sources=[SOURCE_WP],
        checklist_ref="Stage is not on 'MS Stage 1 - In Progress', anything beyond is okay",
        section="Migration Readiness",
    )


def rule_device_fees_present(m: MerchantFacts) -> CheckResult:
    """If the club has device fees, both POS06 and POS07 must be added."""
    if not m.kyc.has_device_fees:
        return CheckResult(
            rule_id="device_fees_present",
            label="Device fees POS06 + POS07 added when applicable",
            status=PASS,
            expected="N/A (no device fees)",
            actual="N/A",
            sources=[SOURCE_TRANSACT, SOURCE_KYC],
            checklist_ref="If the club has device fees, both POS06 and POS07 have been added",
            section="Migration Completion",
        )
    fees = {_norm(f) for f in m.transact.device_fees}
    missing = [code for code in ("POS06", "POS07") if code.lower() not in fees]
    status = PASS if not missing else FAIL
    return CheckResult(
        rule_id="device_fees_present",
        label="Device fees POS06 + POS07 added when applicable",
        status=status,
        expected="POS06, POS07",
        actual=", ".join(sorted(fees)) or "(none)",
        sources=[SOURCE_TRANSACT],
        detail=("Missing: " + ", ".join(missing)) if missing else "",
        checklist_ref="If the club has device fees, both POS06 and POS07 have been added",
        section="Migration Completion",
    )


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------

ALL_RULES: dict[str, Callable[[MerchantFacts], CheckResult]] = {
    "legal_name_match": rule_legal_name_match,
    "dba_name_match": rule_dba_name_match,
    "tin_last4_match": rule_tin_last4_match,
    "mcc_code_correct": rule_mcc_code_correct,
    "billing_descriptor_format": rule_billing_descriptor_format,
    "processor_correct": rule_processor_correct,
    "transaction_type": rule_transaction_type,
    "card_types_match_repay": rule_card_types_match_repay,
    "omni_token_enabled": rule_omni_token_enabled,
    "terminals_present": rule_terminals_present,
    "bank_account_match": rule_bank_account_match,
    "bank_transfer_method": rule_bank_transfer_method,
    "deposit_schedule_daily": rule_deposit_schedule_daily,
    "chargeback_email_match": rule_chargeback_email_match,
    "cs_phone_not_owner": rule_cs_phone_not_owner,
    "owners_25pct": rule_owners_25pct,
    "org_code_match": rule_org_code_match,
    "repay_mid_closed": rule_repay_mid_closed,
    "kyc_stage_complete": rule_kyc_stage_complete,
    "device_fees_present": rule_device_fees_present,
}


def run_rules(m: MerchantFacts, rule_ids: list[str]) -> list[CheckResult]:
    """Run a chosen set of rules and return results in the requested order."""
    results: list[CheckResult] = []
    for rid in rule_ids:
        fn = ALL_RULES.get(rid)
        if fn is None:
            continue
        try:
            results.append(fn(m))
        except Exception as e:  # rule-level safety: never crash the dashboard
            results.append(CheckResult(
                rule_id=rid,
                label=fn.__doc__ or rid,
                status=WARN,
                actual=f"(error running rule: {e})",
                section="Errors",
            ))
    return results
