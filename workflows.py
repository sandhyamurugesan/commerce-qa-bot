"""Map each Commerce QA workflow to the rules it should run.

Source: the three sheets in `Commerce QA checklist - MS.xlsx`.
"""

from __future__ import annotations


WORKFLOW_CLUB_SALE = "Commerce Club Sale"
WORKFLOW_MIGRATION = "Commerce POS Migration"
WORKFLOW_NEW_ONBOARDING = "Commerce POS New Onboarding"


WORKFLOW_RULES: dict[str, list[str]] = {
    WORKFLOW_CLUB_SALE: [
        "legal_name_match",
        "dba_name_match",
        "tin_last4_match",
        "mcc_code_correct",
        "billing_descriptor_format",
        "processor_correct",
        "transaction_type",
        "card_types_match_repay",
        "omni_token_enabled",
        "bank_account_match",
        "chargeback_email_match",
        "cs_phone_not_owner",
        "owners_25pct",
        "org_code_match",
    ],
    WORKFLOW_MIGRATION: [
        "kyc_stage_complete",
        "legal_name_match",
        "tin_last4_match",
        "mcc_code_correct",
        "billing_descriptor_format",
        "processor_correct",
        "transaction_type",
        "card_types_match_repay",
        "omni_token_enabled",
        "terminals_present",
        "bank_account_match",
        "bank_transfer_method",
        "deposit_schedule_daily",
        "chargeback_email_match",
        "owners_25pct",
        "repay_mid_closed",
        "device_fees_present",
    ],
    WORKFLOW_NEW_ONBOARDING: [
        "legal_name_match",
        "tin_last4_match",
        "mcc_code_correct",
        "billing_descriptor_format",
        "processor_correct",
        "transaction_type",
        "card_types_match_repay",
        "omni_token_enabled",
        "terminals_present",
        "bank_account_match",
        "deposit_schedule_daily",
        "chargeback_email_match",
        "cs_phone_not_owner",
        "owners_25pct",
        "org_code_match",
    ],
}


def rules_for_workflow(workflow: str) -> list[str]:
    return WORKFLOW_RULES.get(workflow, [])


def all_workflows() -> list[str]:
    return list(WORKFLOW_RULES.keys())
