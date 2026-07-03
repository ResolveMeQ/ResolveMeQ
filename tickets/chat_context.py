"""
Structured chat context for agent requests — keeps retrieval and response focus separate.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tickets.chat_intent import user_message_indicates_resolution_success


_SOCIAL_PREFIXES = (
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank you",
    "bye",
    "good morning",
    "good afternoon",
    "good evening",
)


def _looks_social_or_closure(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return True
    if user_message_indicates_resolution_success(message):
        return True
    if len(text) <= 48:
        for p in _SOCIAL_PREFIXES:
            if text == p or text.startswith(p + " ") or text.startswith(p + ","):
                return True
    return False


def derive_rag_search_query(*, ticket, conversation, latest_message: str) -> str:
    """
    KB retrieval should track the underlying IT issue, not short social/closure phrases.
    """
    parts: List[str] = []
    issue = (getattr(ticket, "issue_type", None) or "").strip()
    desc = (getattr(ticket, "description", None) or "").strip()
    summary = (getattr(conversation, "summary", None) or "").strip()
    category = (getattr(ticket, "category", None) or "").strip()

    if issue:
        parts.append(issue)
    if category and category.lower() not in issue.lower():
        parts.append(category)
    if desc:
        parts.append(desc[:500])
    if summary:
        parts.append(summary[:350])

    latest = (latest_message or "").strip()
    if latest and len(latest) > 40 and not _looks_social_or_closure(latest):
        parts.append(latest[:250])

    query = " ".join(p for p in parts if p).strip()
    return (query[:700] if query else "technical support")


def build_conversation_history(
    conversation,
    *,
    latest_message: str,
    max_messages: int = 12,
) -> List[Dict[str, str]]:
    """Chronological transcript with optional rolling summary prefix."""
    recent = list(conversation.messages.order_by("-created_at")[:max_messages])
    recent.reverse()
    history: List[Dict[str, str]] = []
    summary = (conversation.summary or "").strip()
    if summary:
        history.append(
            {
                "role": "assistant",
                "text": f"Conversation summary so far: {summary}",
            }
        )
    for msg in recent:
        if msg.sender_type == "user":
            role = "user"
        elif msg.sender_type in ("ai", "system", "agent"):
            role = "assistant"
        else:
            continue
        text = (msg.text or "").strip()
        if text:
            history.append({"role": role, "text": text})
    return history


def build_conversation_focus(
    *,
    ticket,
    conversation,
    latest_message: str,
    conversation_history: List[Dict[str, str]],
) -> str:
    """Explicit briefing so the model answers the latest turn, not the original ticket alone."""
    turn = sum(1 for m in conversation_history if m.get("role") == "user")
    last_assistant = ""
    for m in reversed(conversation_history):
        if m.get("role") == "assistant" and not str(m.get("text", "")).startswith(
            "Conversation summary"
        ):
            last_assistant = (m.get("text") or "").strip()
            break

    lines = [
        "CONVERSATION FOCUS (read before replying):",
        f"- Ticket #{ticket.ticket_id}: {ticket.issue_type or 'support'} — {(ticket.description or '')[:200]}",
        f"- Turn {max(turn, 1)}: respond ONLY to the user's latest message below.",
        f'- Latest user message: "{(latest_message or "").strip()[:500]}"',
    ]
    if last_assistant:
        preview = " ".join(last_assistant.split())
        if len(preview) > 320:
            preview = preview[:317] + "..."
        lines.append(f'- Your previous reply (context for short follow-ups): "{preview}"')
    lines.append(
        "- Do not re-run the initial ticket analysis unless the user asks for it or reports a new problem."
    )
    return "\n".join(lines)


def enrich_agent_chat_payload(
    payload: Dict[str, Any],
    *,
    ticket,
    conversation,
    latest_message: str,
) -> Dict[str, Any]:
    """Add fields the agent uses for context-aware multi-turn chat."""
    history = build_conversation_history(conversation, latest_message=latest_message)
    is_follow_up = any(m.get("role") == "assistant" for m in history) or conversation.messages.filter(
        sender_type="ai"
    ).exists()

    out = dict(payload)
    out["conversation_history"] = history
    out["latest_user_message"] = (latest_message or "").strip()
    out["rag_search_query"] = derive_rag_search_query(
        ticket=ticket, conversation=conversation, latest_message=latest_message
    )
    out["is_chat_follow_up"] = bool(is_follow_up)
    out["conversation_turn"] = sum(1 for m in history if m.get("role") == "user")
    focus = build_conversation_focus(
        ticket=ticket,
        conversation=conversation,
        latest_message=latest_message,
        conversation_history=history,
    )
    existing = (out.get("conversation_guidance") or "").strip()
    out["conversation_guidance"] = f"{focus}\n\n{existing}".strip() if existing else focus
    return out
