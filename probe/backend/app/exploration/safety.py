"""
Safety Policy abstraction and default rule implementation for PROBE V1.

Ensures autonomous exploration never executes dangerous, financial, destructive,
or out-of-bounds actions.
"""
from __future__ import annotations

import re
import urllib.parse
from abc import ABC, abstractmethod
from typing import Optional

from app.core.models import Action, ActionType, Element
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Destructive & financial keywords (matched as words / substrings)
DANGEROUS_KEYWORDS = {
    # Financial / Transactions
    "buy",
    "purchase",
    "pay",
    "payment",
    "checkout",
    "order now",
    "place order",
    "subscribe",
    "credit card",
    "billing",
    "wire transfer",
    # Destructive / Account termination
    "delete",
    "delete account",
    "remove account",
    "close account",
    "deactivate",
    "wipe",
    "destroy",
    "terminate",
    "drop table",
    "drop database",
    "truncate",
    "unsubscribe",
    # Communications / External publishing
    "send email",
    "send message",
    "post tweet",
    "publish post",
}

BLOCKED_SCHEMES = {"mailto:", "tel:", "javascript:", "whatsapp:", "sms:"}


class SafetyPolicy(ABC):
    """Abstract interface for checking action safety."""

    @abstractmethod
    def is_safe_action(
        self,
        action: Action,
        element: Optional[Element],
        current_url: str,
        initial_url: str,
        allowed_domains: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        """
        Evaluate if an action is safe to execute.

        Returns:
            (is_safe: bool, reason: str)
        """
        ...


class DefaultSafetyPolicy(SafetyPolicy):
    """
    Default deterministic safety policy for PROBE V1.
    """

    def __init__(self, blocked_keywords: Optional[set[str]] = None) -> None:
        self._blocked_keywords = set(blocked_keywords) if blocked_keywords else DANGEROUS_KEYWORDS

    def is_safe_action(
        self,
        action: Action,
        element: Optional[Element],
        current_url: str,
        initial_url: str,
        allowed_domains: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        # 1. Check prohibited schemes
        if action.type == ActionType.NAVIGATE and action.value:
            for scheme in BLOCKED_SCHEMES:
                if action.value.strip().lower().startswith(scheme):
                    return False, f"Blocked unsafe protocol scheme: {scheme}"

        # 2. Check link targets (if element has href or action has value)
        href = ""
        if element and element.attributes.get("href"):
            href = element.attributes["href"].strip()
        elif action.type == ActionType.NAVIGATE and action.value:
            href = action.value.strip()

        if href:
            for scheme in BLOCKED_SCHEMES:
                if href.lower().startswith(scheme):
                    return False, f"Blocked unsafe link protocol: {scheme}"

            # Check domain boundary
            if not self._is_within_domain_scope(href, current_url, initial_url, allowed_domains):
                return False, f"Blocked out-of-scope external navigation: {href}"

        # 3. Check element types (e.g. file upload)
        if element:
            el_type = (element.type or "").lower()
            tag = (element.tag or "").lower()
            if el_type == "input:file" or (tag == "input" and element.attributes.get("type") == "file"):
                return False, "Blocked file upload input"

            # 4. Check dangerous keywords in text, label, id, name, and attributes
            combined_text = " ".join([
                element.text,
                element.label,
                element.id,
                element.attributes.get("name", ""),
                element.attributes.get("value", ""),
                element.attributes.get("aria-label", ""),
                element.attributes.get("title", ""),
            ]).lower()

            for kw in self._blocked_keywords:
                # Word boundary or substring check
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, combined_text):
                    return False, f"Blocked dangerous keyword '{kw}' in element: '{element.text or element.label}'"

        # 5. Check action values if typing
        if action.type == ActionType.TYPE and action.value:
            val_lower = action.value.lower()
            for kw in self._blocked_keywords:
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, val_lower):
                    return False, f"Blocked dangerous keyword '{kw}' in typed value"

        return True, "Safe"

    def _is_within_domain_scope(
        self,
        target_href: str,
        current_url: str,
        initial_url: str,
        allowed_domains: Optional[list[str]] = None,
    ) -> bool:
        """Verify the link stays within the target domain or allowed domains."""
        target_href = target_href.strip()

        # Relative paths and anchors and data URLs are within same scope
        if (
            target_href.startswith("/")
            or target_href.startswith("#")
            or target_href.startswith("?")
            or target_href.startswith("data:")
            or target_href.startswith("about:")
        ):
            return True

        # If it's a full URL, parse hostname
        try:
            target_parsed = urllib.parse.urlparse(target_href)
            if not target_parsed.netloc:
                return True

            target_host = target_parsed.netloc.lower().split(":")[0]

            # Compare against initial_url host
            init_parsed = urllib.parse.urlparse(initial_url)
            init_host = init_parsed.netloc.lower().split(":")[0]

            if not init_host:
                return True

            # Same host or subdomain
            if target_host == init_host or target_host.endswith(f".{init_host}"):
                return True

            # Compare with allowed domains
            if allowed_domains:
                for domain in allowed_domains:
                    d = domain.lower().strip()
                    if target_host == d or target_host.endswith(f".{d}"):
                        return True

            return False
        except Exception:
            return True


# Singleton default policy instance
default_safety_policy = DefaultSafetyPolicy()
