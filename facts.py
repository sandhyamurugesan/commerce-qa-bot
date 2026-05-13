"""Normalized cross-system view of a single merchant.

Each source system contributes its own slice. The QA rules read from this
single object so they don't have to know how each file was parsed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


SOURCE_KYC = "KYC / Salesforce"
SOURCE_PG = "Payment Gateway"
SOURCE_TRANSACT = "Commerce Transact"
SOURCE_WP = "WP Onboarded Clubs"
SOURCE_REPAY = "Repay"


@dataclass
class KycFacts:
    """Source of truth - what underwriting approved."""
    club_number: str = ""
    legal_name: str = ""
    dba_name: str = ""
    tin_last4: str = ""
    mcc_code: str = ""
    customer_service_phone: str = ""
    chargeback_email: str = ""
    bank_account_last4: str = ""
    transfer_method: str = ""
    deposit_schedule: str = ""
    owners: list[dict] = field(default_factory=list)
    card_types: list[str] = field(default_factory=list)
    rate_transaction: Optional[float] = None
    rate_authorization: Optional[float] = None
    rate_misc: Optional[float] = None
    monthly_fees: list[str] = field(default_factory=list)
    device_fees: list[str] = field(default_factory=list)
    has_device_fees: bool = False
    country: str = ""
    client_type: str = ""


@dataclass
class PaymentGatewayFacts:
    """Merchant Management / Onboarding / Terminals."""
    club_number: str = ""
    legal_name: str = ""
    dba_name: str = ""
    tin_last4: str = ""
    mcc_code: str = ""
    billing_descriptor: str = ""
    processor: str = ""
    transaction_type: str = ""
    card_types: list[str] = field(default_factory=list)
    omni_token_enabled: bool = False
    onboarding_status: str = ""
    org_code: str = ""
    owners: list[dict] = field(default_factory=list)
    terminals: list[dict] = field(default_factory=list)


@dataclass
class TransactFacts:
    """Commerce Transact - profile, deposits, rates, fees."""
    club_number: str = ""
    chargeback_email: str = ""
    customer_service_phone: str = ""
    bank_account_last4: str = ""
    transfer_method: str = ""
    deposit_schedule: str = ""
    rate_transaction: Optional[float] = None
    rate_authorization: Optional[float] = None
    rate_misc: Optional[float] = None
    monthly_fees: list[str] = field(default_factory=list)
    device_fees: list[str] = field(default_factory=list)
    cost_plus_enabled: bool = False


@dataclass
class WpOnboardedFacts:
    """The migration spreadsheet row."""
    club_number: str = ""
    kyc_stage: str = ""
    country: str = ""
    org_code: str = ""
    repay_account_closed: str = ""
    device_fee_added: str = ""


@dataclass
class RepayFacts:
    """Repay status."""
    club_number: str = ""
    mid_status: str = ""
    card_types: list[str] = field(default_factory=list)


@dataclass
class MerchantFacts:
    """Everything we know about one merchant, across all systems."""
    kyc: KycFacts = field(default_factory=KycFacts)
    pg: PaymentGatewayFacts = field(default_factory=PaymentGatewayFacts)
    transact: TransactFacts = field(default_factory=TransactFacts)
    wp: WpOnboardedFacts = field(default_factory=WpOnboardedFacts)
    repay: RepayFacts = field(default_factory=RepayFacts)

    @property
    def club_number(self) -> str:
        return (
            self.kyc.club_number
            or self.pg.club_number
            or self.transact.club_number
            or self.wp.club_number
            or self.repay.club_number
        )

    @property
    def display_name(self) -> str:
        name = self.kyc.dba_name or self.kyc.legal_name or self.pg.dba_name
        if self.club_number:
            return f"{name} (#{self.club_number})" if name else f"Club #{self.club_number}"
        return name or "Unknown merchant"
