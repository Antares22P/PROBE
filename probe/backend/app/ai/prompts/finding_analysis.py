"""
Prompts for AI reasoning and finding analysis in PROBE V1.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from app.findings.models import Finding

SYSTEM_PROMPT = """You are PROBE AI, an expert autonomous web application testing and quality reasoning engine.
Your role is to analyze empirical test telemetry and findings detected during automated browser exploration.

CRITICAL GUIDELINES:
1. FACT VS HYPOTHESIS:
   - "observed_facts": State ONLY verifiable, empirical evidence from the telemetry (exact HTTP status, error strings, action targets).
   - "hypotheses": Formulate plausible underlying software/network root causes based on the evidence.
   - "uncertainty": Explicitly state what cannot be confirmed without inspecting backend code, server logs, or additional reproduction runs.
   - Never state speculative hypotheses as confirmed facts.

2. STRUCTURED REASONING:
   - "is_meaningful": Set to false only if the signal is clearly benign noise (e.g. harmless third-party analytics beacon timeout).
   - "category": Choose from functional, network, javascript, crash, performance, ui, ux, security, accessibility, other.
   - "severity_suggestion": low, medium, high, or critical based on user impact.
   - "possible_cause": Likely technical mechanism of failure.
   - "recommendation": Actionable guidance for developers to fix or mitigate the issue.
   - "investigation_suggestion": Concrete next test steps or debugging steps to reproduce or confirm.

3. Keep explanations concise, professional, and directly actionable.
"""


def distill_finding_context(
    finding: Finding,
    evidence_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Distill a Finding and evidence into a concise, relevant payload for the LLM.
    Avoids sending massive raw logs or unnecessary DOM trees.
    """
    context: dict[str, Any] = {
        "finding_id": finding.id,
        "title": finding.title,
        "category": finding.category.value if hasattr(finding.category, "value") else str(finding.category),
        "severity": finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
        "status": finding.status.value if hasattr(finding.status, "value") else str(finding.status),
        "confidence": finding.confidence,
        "description": finding.description,
    }

    # Extract reproduction action sequence
    if finding.reproduction:
        if isinstance(finding.reproduction, dict):
            actions = finding.reproduction.get("action_sequence") or finding.reproduction.get("steps")
            if actions:
                context["reproduction_sequence"] = actions
            if "status" in finding.reproduction:
                context["reproduction_status"] = finding.reproduction["status"]
            if "attempts" in finding.reproduction:
                context["reproduction_attempts"] = finding.reproduction["attempts"]
        else:
            context["reproduction_info"] = str(finding.reproduction)

    # Distill evidence items (max 10 relevant items)
    compact_evidence = []
    for ev in finding.evidence[:10]:
        if isinstance(ev, dict):
            ev_type = ev.get("type", "unknown")
            item: dict[str, Any] = {"type": ev_type}
            if ev.get("url"):
                item["url"] = ev["url"]
            if ev.get("status_code") or ev.get("status"):
                item["status"] = ev.get("status_code") or ev.get("status")
            if ev.get("message") or ev.get("error"):
                item["message"] = str(ev.get("message") or ev.get("error"))[:300]
            if ev.get("method"):
                item["method"] = ev["method"]
            compact_evidence.append(item)
        elif isinstance(ev, str):
            compact_evidence.append({"raw": ev[:300]})

    context["evidence"] = compact_evidence

    # Extra context if provided
    if evidence_context:
        for k, v in evidence_context.items():
            if k not in context and v is not None:
                context[k] = v

    return context


def build_analysis_prompt(distilled_context: dict[str, Any]) -> str:
    """Format the user prompt for finding analysis."""
    return f"""Please analyze the following PROBE test finding and evidence:

```json
{json.dumps(distilled_context, indent=2)}
```

Provide structured analysis separating observed facts from hypotheses and uncertainty."""
