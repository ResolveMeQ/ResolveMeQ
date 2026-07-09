# ResolveMeQ Public Partner API (v1)

Documented REST surface for partners building ticket intake, workflow visibility, and automation integrations without a custom fork.

**Public user guide:** [resolvemeq.net/docs/partner-api](https://resolvemeq.net/docs/partner-api) (canonical for partners and search engines).

## Authentication

Create a partner API key in **Settings → Integrations → Partner API** (workspace owner only).

Send the key on every request:

```http
Authorization: Bearer rmq_pk_<secret>
```

or

```http
X-API-Key: rmq_pk_<secret>
```

Keys are team-scoped. All data is isolated to the workspace that issued the key.

## Scopes

| Scope | Access |
|-------|--------|
| `tickets:read` | List and read tickets |
| `tickets:write` | Create tickets, update status, start workflows |
| `workflows:read` | List and read workflows |
| `rules:read` | List automation rules |

## Base URL

```
https://api.resolvemeq.net/api/public/v1/
```

## Endpoints

### API info
`GET /` — capabilities, scopes, outbound webhook event names

### Tickets

| Method | Path | Scope | Description |
|--------|------|-------|-------------|
| GET | `/tickets/` | tickets:read | List tickets (`?status=`, `?limit=`, `?offset=`) |
| POST | `/tickets/create/` | tickets:write | Partner intake (creates reporter if needed) |
| GET | `/tickets/{id}/` | tickets:read | Ticket detail |
| PATCH | `/tickets/{id}/update/` | tickets:write | Update status |

**Create ticket body:**
```json
{
  "reporter_email": "user@customer.com",
  "issue_type": "VPN not connecting",
  "description": "Cannot reach corporate VPN from home",
  "category": "vpn",
  "urgency": "high",
  "tags": ["partner-intake"]
}
```

### Workflows

| Method | Path | Scope | Description |
|--------|------|-------|-------------|
| GET | `/workflows/` | workflows:read | List workflows (`?ticket_id=`) |
| GET | `/workflows/{uuid}/` | workflows:read | Workflow + steps |
| POST | `/workflows/start/` | tickets:write | Start workflow from template |

### Rules

| Method | Path | Scope | Description |
|--------|------|-------|-------------|
| GET | `/rules/` | rules:read | Team + global automation rules |

## Outbound webhooks (partner receives events)

Configure outbound webhooks in the product UI (**Settings → Integrations → Webhooks**). Events are HMAC-signed POSTs — same event catalog returned by `GET /api/public/v1/`.

Typical partner flow:
1. `POST /tickets/create/` — intake from external system
2. Subscribe to `ticket.escalated` / `ticket.resolved` webhooks
3. `GET /workflows/?ticket_id=` — track playbook progress

## Key management (JWT, not partner key)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/public/keys/metadata/` | Available scopes |
| GET | `/api/public/keys/` | List keys (prefix only) |
| POST | `/api/public/keys/` | Create key — **api_key shown once** |
| DELETE | `/api/public/keys/{uuid}/` | Revoke key |

## Rate limits

Partner keys share the same infrastructure as the main API. Use exponential backoff on `429` and `5xx` responses.
