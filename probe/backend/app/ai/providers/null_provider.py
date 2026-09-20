"""
NullProvider — no-op AIProvider implementation.

Returns baseline rule-based reasoning without calling external LLM APIs.
Used when GEMINI_API_KEY is not configured or when offline.
"""
from __future__ import annotations

from typing import Any, Optional

from app.ai.provider import AIProvider, AIRequest, AIResponse
from app.ai.schemas.finding_analysis import (
    AIError,
    AIErrorType,
    FindingAnalysisResult,
    TestSummaryAnalysis,
)
from app.findings.models import Finding


class NullProvider(AIProvider):
    """
    No-op AI provider.
    """

    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            content="[AI analysis not configured]",
            model="null",
            tokens_used=0,
        )

    async def analyze_finding(
        self,
        finding: Finding,
        evidence_context: Optional[dict[str, Any]] = None,
    ) -> FindingAnalysisResult:
        # Generate safe fallback analysis based directly on finding telemetry
        category_str = finding.category.value if hasattr(finding.category, "value") else str(finding.category)
        severity_str = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)

        facts = [f"Signal: {finding.title}"]
        if finding.description:
            facts.append(finding.description)

        for ev in finding.evidence[:3]:
            if isinstance(ev, dict) and ev.get("url"):
                facts.append(f"Affected URL: {ev['url']}")

        return FindingAnalysisResult(
            is_meaningful=True,
            category=category_str,
            severity_suggestion=severity_str,
            confidence=finding.confidence,
            observed_facts=facts,
            hypotheses=["Deterministic rule detected this finding without external AI reasoning"],
            uncertainty="AI provider not configured (NullProvider active)",
            explanation=finding.description or f"{category_str.capitalize()} issue identified: {finding.title}",
            possible_cause=f"Direct observation of {finding.title}",
            recommendation="Review the affected page and action sequence to resolve the issue",
            investigation_suggestion="Replay reproduction sequence in the test dashboard",
            error=AIError(
                error_type=AIErrorType.UNCONFIGURED,
                message="AI provider is unconfigured. Set GEMINI_API_KEY to enable Gemini reasoning.",
            ),
            model_name="null",
        )

    async def generate_test_summary(
        self,
        findings: list[Finding],
        test_summary: dict[str, Any],
    ) -> TestSummaryAnalysis:
        has_critical = any(
            (f.severity.value if hasattr(f.severity, "value") else str(f.severity)) == "critical"
            for f in findings
        )
        return TestSummaryAnalysis(
            overall_health="critical_issues_found" if has_critical else "degraded" if findings else "healthy",
            key_takeaways=[f"Exploration concluded with {len(findings)} findings."],
            top_risks=[f.title for f in findings[:3]],
            recommended_actions=["Review and reproduce high-severity findings."],
            error=AIError(
                error_type=AIErrorType.UNCONFIGURED,
                message="AI provider is unconfigured.",
            ),
            model_name="null",
        )

    @property
    def provider_name(self) -> str:
        return "NullProvider"

    @property
    def is_available(self) -> bool:
        return False
