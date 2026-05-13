"""AI-assisted review layer for the Commerce POS QA Bot.

The deterministic rules are the source of truth for pass/fail decisions. This
module turns the normalized source data and rule outcomes into an AI comparison
brief. If an OpenAI API key is present, it can call a real LLM; otherwise it
returns a local brief that keeps the hackathon demo fully self-contained.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field

from facts import MerchantFacts
from rules import CheckResult


@dataclass
class AiReview:
    """Structured AI review the UI can render with rich components."""
    recommendation: str
    headline: str
    summary: str
    counts: dict[str, int] = field(default_factory=dict)
    highest_risk: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    follow_up: list[str] = field(default_factory=list)


def _summary_counts(results: list[CheckResult]) -> dict[str, int]:
    return {
        "pass": sum(1 for r in results if r.status == "PASS"),
        "fail": sum(1 for r in results if r.status == "FAIL"),
        "warn": sum(1 for r in results if r.status == "WARN"),
        "total": len(results),
    }


def build_ai_prompt(
    workflow: str,
    facts: MerchantFacts,
    results: list[CheckResult],
) -> str:
    """Build the prompt a real AI reviewer would receive."""
    failed_or_warn = [r for r in results if r.status != "PASS"]
    comparison_packet = {
        "workflow": workflow,
        "merchant": facts.display_name,
        "source_documents": {
            "setup_document_or_kyc_record": asdict(facts.kyc),
            "repay_configuration": asdict(facts.repay),
            "commerce_pos_records": {
                "payment_gateway": asdict(facts.pg),
                "commerce_transact": asdict(facts.transact),
                "wp_onboarded_clubs": asdict(facts.wp),
            },
        },
        "rule_results": [asdict(r) for r in results],
        "exceptions_to_review": [asdict(r) for r in failed_or_warn],
    }

    return (
        "You are assisting Payment Operations with Commerce POS merchant setup QA.\n"
        "Compare the setup document/KYC source of truth, Repay configuration, "
        "and Commerce POS records before the merchant is flipped live.\n\n"
        "Focus on fees, merchant details, banking, merchant IDs/configuration, "
        "terminal setup, processor, card types, and activation readiness.\n\n"
        "Return:\n"
        "1. Activation recommendation: READY / NOT READY / REVIEW NEEDED.\n"
        "2. The highest-risk mismatches in plain English.\n"
        "3. Which source system appears wrong.\n"
        "4. The exact follow-up PaymentOps should take.\n\n"
        "Comparison packet:\n"
        f"{json.dumps(comparison_packet, indent=2)}"
    )


def _build_local_review(
    workflow: str,
    facts: MerchantFacts,
    results: list[CheckResult],
) -> AiReview:
    """Build a structured AI review for the demo (no LLM required)."""
    counts = _summary_counts(results)
    failed = [r for r in results if r.status == "FAIL"]
    warned = [r for r in results if r.status == "WARN"]

    if failed:
        recommendation = "NOT READY"
        headline = (
            f"Do NOT activate {facts.display_name} yet - "
            f"{counts['fail']} blocking issue(s) found."
        )
        reason = "one or more setup fields do not match the source of truth"
    elif warned:
        recommendation = "REVIEW NEEDED"
        headline = (
            f"Review {facts.display_name} before activation - "
            f"{counts['warn']} warning(s) need a human eye."
        )
        reason = "some source data is missing or ambiguous"
    else:
        recommendation = "READY"
        headline = (
            f"{facts.display_name} is ready to activate - "
            f"all {counts['total']} checks passed."
        )
        reason = "all configured QA checks passed"

    summary = (
        f"For **{facts.display_name}**, the **{workflow}** review compared the "
        f"setup/KYC document, Repay configuration, and Commerce POS records. "
        f"Of **{counts['total']} checks**, **{counts['pass']} passed**, "
        f"**{counts['fail']} failed**, and **{counts['warn']} produced warnings**. "
        f"The merchant is **{recommendation.lower()}** because {reason}."
    )

    highest_risk = [
        {
            "label": r.label,
            "expected": r.expected or "(empty)",
            "actual": r.actual or "(empty)",
            "sources": r.sources,
            "detail": r.detail,
            "checklist_ref": r.checklist_ref,
        }
        for r in failed[:8]
    ]

    warnings = [
        {
            "label": r.label,
            "detail": r.detail or "missing or ambiguous source data",
            "sources": r.sources,
        }
        for r in warned[:5]
    ]

    if failed or warned:
        follow_up = [
            "Correct the source system listed in each failed check before flipping live.",
            "Re-run the bot after updates and attach the downloaded QA report to the ticket.",
        ]
    else:
        follow_up = [
            "Attach the QA report to the ticket as evidence.",
            "Merchant can proceed to activation if no external approvals are pending.",
        ]

    return AiReview(
        recommendation=recommendation,
        headline=headline,
        summary=summary,
        counts=counts,
        highest_risk=highest_risk,
        warnings=warnings,
        follow_up=follow_up,
    )


def review_to_markdown(review: AiReview) -> str:
    """Flatten a structured review into markdown for the Excel report."""
    lines = [
        f"Activation recommendation: {review.recommendation}",
        "",
        review.headline,
        "",
        review.summary,
    ]
    if review.highest_risk:
        lines.extend(["", "Highest-risk mismatches:"])
        for item in review.highest_risk:
            lines.append(
                f"- {item['label']}: expected {item['expected']}, "
                f"actual {item['actual']}. Source(s): {', '.join(item['sources'])}."
            )
    if review.warnings:
        lines.extend(["", "Warnings to review:"])
        for item in review.warnings:
            lines.append(f"- {item['label']}: {item['detail']}.")
    if review.follow_up:
        lines.extend(["", "PaymentOps follow-up:"])
        lines.extend(f"- {step}" for step in review.follow_up)
    return "\n".join(lines)


def generate_local_ai_brief(
    workflow: str,
    facts: MerchantFacts,
    results: list[CheckResult],
) -> str:
    """Backwards-compatible string brief used by the Excel report."""
    return review_to_markdown(_build_local_review(workflow, facts, results))


def generate_llm_brief(prompt: str) -> str | None:
    """Call OpenAI Responses API when OPENAI_API_KEY is configured.

    The app does not require this for the hackathon demo. Returning None lets
    the UI fall back to the local brief.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "input": prompt,
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip() or None


def generate_ai_review(
    workflow: str,
    facts: MerchantFacts,
    results: list[CheckResult],
) -> tuple[str, str]:
    """Return (brief, prompt) - markdown string for the Excel report."""
    prompt = build_ai_prompt(workflow, facts, results)
    brief = generate_llm_brief(prompt) or generate_local_ai_brief(workflow, facts, results)
    return brief, prompt


def generate_ai_review_structured(
    workflow: str,
    facts: MerchantFacts,
    results: list[CheckResult],
) -> tuple[AiReview, str | None, str]:
    """Return (structured_review, llm_text, prompt) for rich UI rendering.

    `llm_text` is populated only when a real LLM call succeeds. When None, the
    UI renders the structured local review with rich Streamlit components.
    """
    prompt = build_ai_prompt(workflow, facts, results)
    review = _build_local_review(workflow, facts, results)
    llm_text = generate_llm_brief(prompt)
    return review, llm_text, prompt
