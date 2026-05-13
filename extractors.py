"""Parse each uploaded source file into a typed slice of MerchantFacts.

Each extractor is intentionally tolerant: missing columns become empty strings
rather than crashes, so the QA report can still flag them.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any, IO, Union

import pandas as pd

from facts import (
    KycFacts,
    MerchantFacts,
    PaymentGatewayFacts,
    RepayFacts,
    TransactFacts,
    WpOnboardedFacts,
)


FileLike = Union[str, IO[bytes], bytes]


def _to_buffer(src: FileLike) -> Any:
    """Accept a path, a Streamlit UploadedFile, or raw bytes."""
    if isinstance(src, (str, bytes)):
        return src if isinstance(src, str) else BytesIO(src)
    return src


def _str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    s = _str(value).lower()
    return s in {"true", "yes", "y", "1", "on", "enabled", "checked"}


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_str(v) for v in value if _str(v)]
    s = _str(value)
    if not s:
        return []
    return [part.strip() for part in s.split(";") if part.strip()]


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# -----------------------------------------------------------------------------
# KYC (json)
# -----------------------------------------------------------------------------

def extract_kyc(src: FileLike) -> KycFacts:
    raw = src if isinstance(src, dict) else None
    if raw is None:
        buf = _to_buffer(src)
        if isinstance(buf, str):
            with open(buf, "r") as fh:
                raw = json.load(fh)
        else:
            buf.seek(0)
            raw = json.load(buf)

    bank = raw.get("bank", {}) or {}
    rates = raw.get("rates", {}) or {}
    fees = raw.get("fees", {}) or {}

    return KycFacts(
        club_number=_str(raw.get("club_number")),
        legal_name=_str(raw.get("legal_name")),
        dba_name=_str(raw.get("dba_name")),
        tin_last4=_str(raw.get("tin_last4")),
        mcc_code=_str(raw.get("mcc_code")),
        customer_service_phone=_str(raw.get("customer_service_phone")),
        chargeback_email=_str(raw.get("chargeback_email")),
        bank_account_last4=_str(bank.get("account_last4")),
        transfer_method=_str(bank.get("transfer_method")),
        deposit_schedule=_str(bank.get("deposit_schedule")),
        owners=raw.get("owners", []) or [],
        card_types=_list(raw.get("card_types")),
        rate_transaction=_float(rates.get("transaction")),
        rate_authorization=_float(rates.get("authorization")),
        rate_misc=_float(rates.get("misc")),
        monthly_fees=_list(fees.get("monthly")),
        device_fees=_list(fees.get("device")),
        has_device_fees=_bool(fees.get("has_device_fees")),
        country=_str(raw.get("country")),
        client_type=_str(raw.get("client_type")),
    )


# -----------------------------------------------------------------------------
# Payment Gateway (csv: 1 row, key/value style)
# -----------------------------------------------------------------------------

def _kv_csv(src: FileLike) -> dict[str, str]:
    """Parse a 1-row CSV into a key->value dict (header row = keys)."""
    buf = _to_buffer(src)
    df = pd.read_csv(buf)
    if df.empty:
        return {}
    row = df.iloc[0]
    return {str(k): _str(v) for k, v in row.items()}


def extract_payment_gateway(src: FileLike) -> PaymentGatewayFacts:
    row = _kv_csv(src)

    terminals: list[dict] = []
    for i in (1, 2):
        label = row.get(f"terminal_{i}_label", "")
        if label:
            terminals.append({
                "label": label,
                "type": row.get(f"terminal_{i}_type", ""),
            })

    owners_raw = row.get("owners", "")
    owners: list[dict] = []
    if owners_raw:
        for entry in owners_raw.split(";"):
            parts = [p.strip() for p in entry.split("|")]
            if parts and parts[0]:
                owners.append({
                    "name": parts[0],
                    "ownership_pct": float(parts[1]) if len(parts) > 1 and parts[1] else 0.0,
                })

    return PaymentGatewayFacts(
        club_number=row.get("club_number", ""),
        legal_name=row.get("legal_name", ""),
        dba_name=row.get("dba_name", ""),
        tin_last4=row.get("tin_last4", ""),
        mcc_code=row.get("mcc_code", ""),
        billing_descriptor=row.get("billing_descriptor", ""),
        processor=row.get("processor", ""),
        transaction_type=row.get("transaction_type", ""),
        card_types=_list(row.get("card_types", "")),
        omni_token_enabled=_bool(row.get("omni_token_enabled", "")),
        onboarding_status=row.get("onboarding_status", ""),
        org_code=row.get("org_code", ""),
        owners=owners,
        terminals=terminals,
    )


# -----------------------------------------------------------------------------
# Commerce Transact (csv: 1 row)
# -----------------------------------------------------------------------------

def extract_transact(src: FileLike) -> TransactFacts:
    row = _kv_csv(src)
    return TransactFacts(
        club_number=row.get("club_number", ""),
        chargeback_email=row.get("chargeback_email", ""),
        customer_service_phone=row.get("customer_service_phone", ""),
        bank_account_last4=row.get("bank_account_last4", ""),
        transfer_method=row.get("transfer_method", ""),
        deposit_schedule=row.get("deposit_schedule", ""),
        rate_transaction=_float(row.get("rate_transaction")),
        rate_authorization=_float(row.get("rate_authorization")),
        rate_misc=_float(row.get("rate_misc")),
        monthly_fees=_list(row.get("monthly_fees", "")),
        device_fees=_list(row.get("device_fees", "")),
        cost_plus_enabled=_bool(row.get("cost_plus_enabled", "")),
    )


# -----------------------------------------------------------------------------
# WP Onboarded Clubs (xlsx: 1 row)
# -----------------------------------------------------------------------------

def extract_wp_onboarded(src: FileLike) -> WpOnboardedFacts:
    buf = _to_buffer(src)
    df = pd.read_excel(buf)
    if df.empty:
        return WpOnboardedFacts()
    row = df.iloc[0]
    g = lambda key: _str(row.get(key)) if key in row.index else ""
    return WpOnboardedFacts(
        club_number=g("club_number"),
        kyc_stage=g("kyc_stage"),
        country=g("country"),
        org_code=g("org_code"),
        repay_account_closed=g("repay_account_closed"),
        device_fee_added=g("device_fee_added"),
    )


# -----------------------------------------------------------------------------
# Repay (csv: 1 row)
# -----------------------------------------------------------------------------

def extract_repay(src: FileLike) -> RepayFacts:
    row = _kv_csv(src)
    return RepayFacts(
        club_number=row.get("club_number", ""),
        mid_status=row.get("mid_status", ""),
        card_types=_list(row.get("card_types", "")),
    )


# -----------------------------------------------------------------------------
# Top-level: load all 5 from a directory
# -----------------------------------------------------------------------------

def load_merchant_from_dir(dir_path: str) -> MerchantFacts:
    """Load a complete MerchantFacts from a directory of mock files."""
    import os
    return MerchantFacts(
        kyc=extract_kyc(os.path.join(dir_path, "kyc_record.json")),
        pg=extract_payment_gateway(os.path.join(dir_path, "payment_gateway_export.csv")),
        transact=extract_transact(os.path.join(dir_path, "commerce_transact_export.csv")),
        wp=extract_wp_onboarded(os.path.join(dir_path, "wp_onboarded_clubs_row.xlsx")),
        repay=extract_repay(os.path.join(dir_path, "repay_status.csv")),
    )
