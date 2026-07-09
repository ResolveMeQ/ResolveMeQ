"""Partner API scopes (P4-4)."""

VALID_SCOPES = frozenset([
    "tickets:read",
    "tickets:write",
    "workflows:read",
    "rules:read",
])

DEFAULT_SCOPES = sorted(VALID_SCOPES)

SCOPE_LABELS = {
    "tickets:read": "Read tickets",
    "tickets:write": "Create and update tickets",
    "workflows:read": "Read workflows",
    "rules:read": "Read automation rules",
}


def normalize_scopes(raw) -> list:
    if not raw:
        return list(DEFAULT_SCOPES)
    if not isinstance(raw, list):
        raise ValueError("scopes must be a list")
    scopes = []
    for item in raw:
        s = str(item).strip()
        if s not in VALID_SCOPES:
            raise ValueError(f"Invalid scope: {s}")
        if s not in scopes:
            scopes.append(s)
    return scopes or list(DEFAULT_SCOPES)
