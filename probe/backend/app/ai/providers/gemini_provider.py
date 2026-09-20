"""
GeminiProvider — concrete AIProvider implementation using Google Gemini API.

Uses the official google-genai SDK with structured Pydantic output.
Dynamically reads model from GEMINI_MODEL (defaults to low-cost/fast model)
and API key from GEMINI_API_KEY / GOOGLE_API_KEY.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Optional

from app.ai.prompts.finding_analysis import (
    SYSTEM_PROMPT,
    build_analysis_prompt,
    distill_finding_context,
)
from app.ai.provider import AIProvider, AIRequest, AIResponse
from app.ai.schemas.finding_analysis import (
    AIError,
    AIErrorType,
    FindingAnalysisResult,
    TestSummaryAnalysis,
)
from app.findings.models import Finding
from app.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"


class GeminiProvider(AIProvider):
    """
    AIProvider implementation backed by Google Gemini API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> None:
        if api_key is not None:
            self._api_key = api_key
        else:
            self._api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        self._model = (
            model_name
            or os.environ.get("GEMINI_MODEL")
            or DEFAULT_GEMINI_MODEL
        )
        self._client: Optional[Any] = None

        if self._api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
                logger.info(
                    "gemini_provider_initialized",
                    component="GeminiProvider",
                    model=self._model,
                )
            except Exception as exc:
                logger.warning(
                    "gemini_client_init_failed",
                    component="GeminiProvider",
                    error=str(exc),
                )

    @property
    def provider_name(self) -> str:
        return f"GeminiProvider({self._model})"

    @property
    def is_available(self) -> bool:
        return bool(self._client and self._api_key)

    @property
    def model_name(self) -> str:
        return self._model

    async def analyze_finding(
        self,
        finding: Finding,
        evidence_context: Optional[dict[str, Any]] = None,
    ) -> FindingAnalysisResult:
        """
        Analyze a finding and evidence using Gemini with structured Pydantic output.
        Distinguishes observed facts from hypotheses and uncertainty.
        Gracefully returns an error object without raising if Gemini is unavailable.
        """
        if not self.is_available:
            return FindingAnalysisResult(
                is_meaningful=True,
                category=finding.category.value if hasattr(finding.category, "value") else str(finding.category),
                severity_suggestion=finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
                confidence=finding.confidence,
                explanation=finding.description,
                observed_facts=[f"Detected {finding.title}"],
                hypotheses=["AI provider not configured — observed telemetry preserved"],
                uncertainty="Analysis generated via fallback rules; AI reasoning unavailable",
                error=AIError(
                    error_type=AIErrorType.UNCONFIGURED if not self._api_key else AIErrorType.UNAVAILABLE,
                    message="Gemini API is unconfigured or unavailable. Set GEMINI_API_KEY to enable AI reasoning.",
                ),
                model_name=self._model,
            )

        distilled = distill_finding_context(finding, evidence_context)
        prompt_text = build_analysis_prompt(distilled)

        try:
            from google.genai import types

            # Run in executor to avoid blocking the asyncio event loop
            loop = asyncio.get_running_loop()

            def _call_gemini():
                config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_json_schema=FindingAnalysisResult.model_json_schema(),
                )
                return self._client.models.generate_content(
                    model=self._model,
                    contents=prompt_text,
                    config=config,
                )

            # 15 second timeout for AI reasoning call
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call_gemini),
                timeout=15.0,
            )

            if not response or not response.text:
                return FindingAnalysisResult(
                    is_meaningful=True,
                    category=finding.category.value if hasattr(finding.category, "value") else str(finding.category),
                    severity_suggestion=finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
                    confidence=finding.confidence,
                    explanation=finding.description,
                    error=AIError(
                        error_type=AIErrorType.INVALID_RESPONSE,
                        message="Gemini returned an empty response",
                    ),
                    model_name=self._model,
                )

            # Parse JSON into structured Pydantic model
            parsed_json = json.loads(response.text)
            result = FindingAnalysisResult.model_validate(parsed_json)
            result.model_name = self._model
            logger.info(
                "gemini_analysis_completed",
                component="GeminiProvider",
                finding_id=finding.id,
                is_meaningful=result.is_meaningful,
                confidence=result.confidence,
            )
            return result

        except asyncio.TimeoutError:
            logger.warning(
                "gemini_analysis_timeout",
                component="GeminiProvider",
                finding_id=finding.id,
            )
            return FindingAnalysisResult(
                is_meaningful=True,
                category=finding.category.value if hasattr(finding.category, "value") else str(finding.category),
                severity_suggestion=finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
                confidence=finding.confidence,
                explanation=finding.description,
                observed_facts=[f"Finding detected: {finding.title}"],
                uncertainty="AI analysis timed out after 15s",
                error=AIError(
                    error_type=AIErrorType.TIMEOUT,
                    message="Gemini API request timed out after 15 seconds",
                ),
                model_name=self._model,
            )

        except Exception as exc:
            err_str = str(exc)
            logger.warning(
                "gemini_analysis_error",
                component="GeminiProvider",
                finding_id=finding.id,
                error=err_str,
            )

            # Classify error type
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                err_type = AIErrorType.QUOTA_EXCEEDED
                msg = f"Gemini rate limit or quota exceeded: {err_str}"
            elif "401" in err_str or "403" in err_str or "api_key" in err_str.lower() or "auth" in err_str.lower():
                err_type = AIErrorType.UNAVAILABLE
                msg = f"Gemini authentication failed: {err_str}"
            elif "json" in err_str.lower() or "validation" in err_str.lower():
                err_type = AIErrorType.INVALID_RESPONSE
                msg = f"Gemini response could not be parsed: {err_str}"
            else:
                err_type = AIErrorType.UNKNOWN
                msg = f"Gemini error: {err_str}"

            return FindingAnalysisResult(
                is_meaningful=True,
                category=finding.category.value if hasattr(finding.category, "value") else str(finding.category),
                severity_suggestion=finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
                confidence=finding.confidence,
                explanation=finding.description,
                observed_facts=[f"Finding detected: {finding.title}"],
                uncertainty="AI reasoning failed to complete",
                error=AIError(
                    error_type=err_type,
                    message=msg,
                    details=err_str,
                ),
                model_name=self._model,
            )

    async def generate_test_summary(
        self,
        findings: list[Finding],
        test_summary: dict[str, Any],
    ) -> TestSummaryAnalysis:
        """
        Produce a high-level test run summary analysis.
        """
        if not self.is_available:
            return TestSummaryAnalysis(
                overall_health="unknown",
                key_takeaways=[f"Test completed with {len(findings)} findings."],
                error=AIError(
                    error_type=AIErrorType.UNCONFIGURED,
                    message="Gemini API key not configured",
                ),
                model_name=self._model,
            )

        compact_findings = [
            {
                "id": f.id,
                "title": f.title,
                "category": f.category.value if hasattr(f.category, "value") else str(f.category),
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "status": f.status.value if hasattr(f.status, "value") else str(f.status),
            }
            for f in findings[:20]
        ]

        payload = {
            "test_summary": test_summary,
            "findings_count": len(findings),
            "findings": compact_findings,
        }

        try:
            from google.genai import types

            loop = asyncio.get_running_loop()

            def _call_gemini():
                config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_json_schema=TestSummaryAnalysis.model_json_schema(),
                )
                return self._client.models.generate_content(
                    model=self._model,
                    contents=f"Summarize the quality and risks of this test session:\n```json\n{json.dumps(payload, indent=2)}\n```",
                    config=config,
                )

            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call_gemini),
                timeout=15.0,
            )

            if response and response.text:
                parsed = json.loads(response.text)
                res = TestSummaryAnalysis.model_validate(parsed)
                res.model_name = self._model
                return res

        except Exception as exc:
            logger.warning("gemini_summary_failed", component="GeminiProvider", error=str(exc))

        has_critical = any(
            (f.severity.value if hasattr(f.severity, "value") else str(f.severity)) == "critical"
            for f in findings
        )
        return TestSummaryAnalysis(
            overall_health="critical_issues_found" if has_critical else "degraded" if findings else "healthy",
            key_takeaways=[f"Found {len(findings)} potential or confirmed issues."],
            error=AIError(
                error_type=AIErrorType.UNKNOWN,
                message="Failed to generate AI summary",
            ),
            model_name="fallback",
        )

    async def generate(self, request: AIRequest) -> AIResponse:
        """Raw text generation."""
        if not self.is_available:
            return AIResponse(
                content="[GeminiProvider unconfigured]",
                model=self._model,
            )
        try:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=request.prompt,
                ),
            )
            return AIResponse(
                content=res.text or "",
                model=self._model,
            )
        except Exception as exc:
            return AIResponse(
                content=f"[Gemini error: {exc}]",
                model=self._model,
            )
