"""Tokenized KB search helpers for agent RAG."""

from __future__ import annotations

import re

from django.db.models import Q

# Common IT filler words — skip for multi-word agent queries.
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "at", "is", "it",
    "my", "me", "i", "we", "our", "can", "not", "no", "with", "from", "this", "that",
    "have", "has", "had", "be", "been", "are", "was", "were", "do", "does", "did",
    "get", "got", "please", "help", "issue", "problem", "error", "when", "how", "what",
    "user", "users", "ticket", "support", "need", "cant", "cannot", "won't", "don't",
})


def kb_search_terms(query: str, *, max_terms: int = 8) -> list[str]:
    """Extract meaningful search tokens from a free-text query."""
    if not query:
        return []
    raw = re.findall(r"[a-z0-9]{2,}", str(query).lower())
    seen: set[str] = set()
    terms: list[str] = []
    for token in raw:
        if token in _STOPWORDS or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) >= max_terms:
            break
    return terms


def build_kb_content_filter(query: str, *, content_field: str = "content") -> Q:
    """
    OR-match articles where any token appears in title or body.
    Falls back to whole-string match when tokenization yields nothing.
    """
    terms = kb_search_terms(query)
    if not terms:
        q = (query or "").strip()
        if not q:
            return Q(pk__in=[])
        return Q(title__icontains=q) | Q(**{f"{content_field}__icontains": q})

    combined = Q()
    for term in terms:
        combined |= Q(title__icontains=term) | Q(**{f"{content_field}__icontains": term})
    return combined
