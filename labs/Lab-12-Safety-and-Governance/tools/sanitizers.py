"""Text sanitization and input normalization utilities.

Pure Python standard library only.
"""
from __future__ import annotations

import html
import re
import unicodedata

# Matches HTML script/iframe/object tags and inline event handlers
_DANGEROUS_TAG_PATTERN = re.compile(
    r"<\s*(?:script|iframe|object|embed|applet|form|svg|link|meta)\b[^>]*>.*?</\s*(?:script|iframe|object|embed|applet|form|svg|link|meta)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_SELF_CLOSING_TAG_PATTERN = re.compile(
    r"<\s*(?:script|iframe|object|embed|applet|form|svg|link|meta|img|input)\b[^>]*/>",
    re.IGNORECASE,
)
_ON_EVENT_PATTERN = re.compile(r"\bon\w+\s*=\s*['\"][^'\"]*['\"]", re.IGNORECASE)
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_unicode(text: str) -> str:
    """Normalize text using NFKC normalization to prevent unicode obfuscation.

    Args:
        text: Input string.

    Returns:
        NFKC-normalized string.
    """
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text)


def strip_dangerous_tags(text: str) -> str:
    """Strip dangerous HTML tags and inline javascript event handlers.

    Args:
        text: Input string possibly containing HTML tags.

    Returns:
        Sanitized string.
    """
    if not text:
        return ""
    sanitized = _DANGEROUS_TAG_PATTERN.sub("", text)
    sanitized = _SELF_CLOSING_TAG_PATTERN.sub("", sanitized)
    sanitized = _ON_EVENT_PATTERN.sub("", sanitized)
    return sanitized


def sanitize_input_text(
    text: str,
    max_length: int = 10000,
    strip_tags: bool = True,
    escape_html: bool = False,
) -> str:
    """Comprehensive text sanitizer for user inputs and appraisal submissions.

    1. Enforces unicode normalization (NFKC).
    2. Removes null bytes and dangerous control characters.
    3. Strips executable HTML/script tags.
    4. Enforces upper boundary length.

    Args:
        text: Raw input text.
        max_length: Maximum allowed characters.
        strip_tags: Whether to strip dangerous HTML tags.
        escape_html: Whether to HTML-escape remaining content.

    Returns:
        Sanitized text.
    """
    if not isinstance(text, str):
        text = str(text)

    # 1. Unicode normalization
    text = normalize_unicode(text)

    # 2. Strip control characters (preserve \n, \r, \t)
    text = _CONTROL_CHAR_PATTERN.sub("", text)

    # 3. Strip dangerous HTML/script tags
    if strip_tags:
        text = strip_dangerous_tags(text)

    # 4. Optional HTML escape
    if escape_html:
        text = html.escape(text)

    # 5. Enforce boundary length
    if len(text) > max_length:
        text = text[:max_length]

    return text.strip()
