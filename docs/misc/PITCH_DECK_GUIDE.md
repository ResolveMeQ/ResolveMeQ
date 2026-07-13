# ResolveMeQ Pitch Deck Guide

**Purpose:** Build investor, sales, and partner decks that match what the product actually does today.  
**Audience:** Founders, sales, solutions engineers, MSP partners.  
**Companion docs:** `MARKETING_PRODUCT_BRIEF.md`, `BUSINESS_ADOPTION_TEST_PLAN.md`, `PLAYBOOK_EMPLOYEE_ONBOARDING.md`

---

## Before you open PowerPoint

### Pick your deck type

| Deck | Audience | Length | Goal |
|------|----------|--------|------|
| **Sales demo** | IT director, VP Ops, MSP owner | 12–15 slides + 10 min live demo | Book pilot or paid trial |
| **Investor** | Angels, seed VCs | 10–12 slides | Raise or strategic intro |
| **Enterprise security** | CISO, procurement, legal | 8 slides + security appendix | Pass review → pilot |
| **MSP partner** | Managed service providers | 10 slides | White-label / multi-client pitch |

This guide centers on the **sales demo deck** — the one you use most. Adapt by dropping slides marked *(investor only)* or *(enterprise only)*.

### North-star message (one sentence)

> **ResolveMeQ is the AI-powered IT helpdesk that deflects repeat tickets with KB-grounded answers, runs real multi-step playbooks (onboarding, provisioning), and connects to the stack you already use — without replacing ServiceNow on day one.**

### Three engines (repeat on slides 2, 6, and close)

| Engine | One-liner | Proof in demo |
|--------|-----------|---------------|
| **AI Engine** | Answers with confidence, citations, and step-by-step fixes | VPN ticket → KB citation → resolved |
| **Operations Engine** | Human-authored playbooks, SLAs, connector checks | Onboarding ticket → workflow → Okta auto-check |
| **Proof Engine** | Deflection %, calibration, audit log | Dashboard metrics + Settings → Security export |

---

## Recommended slide order (sales deck)

```
 1. Title
 2. Problem
 3. Why now
 4. Solution (platform overview)
 5. How it works (ticket → AI → escalate → workflow)
 6. Product pillars (3 engines)
 7. Live differentiators (6 tiles)
 8. Integrations map
 9. Employee onboarding playbook (hero SKU)
10. Security & enterprise
11. Pricing & packaging
12. Traction / proof *(customize)*
13. Competitive positioning
14. Pilot offer & next steps
15. Appendix (architecture, FAQ, security)
```

**Timing:** 20 minutes total = ~8 min slides + 10 min demo + 2 min Q&A buffer.

---

## Slide-by-slide content

### Slide 1 — Title

**Headline:** ResolveMeQ  
**Subhead:** Resolve Me, Quickly — AI-powered IT support automation

**On-slide (minimal):**
- Logo
- Tagline: *Cut tier-1 triage time. Give every ticket a clear next step.*
- Your name, title, date
- `app.resolvemeq.net` | `resolvemeq.net`

**Speaker notes:**  
“ResolveMeQ sits in front of your helpdesk — not instead of it. Employees get faster answers; IT keeps control of playbooks, policies, and escalation.”

**Visual:** Clean dark-on-light or brand primary (`#2563eb`). Avoid stock photos of headset agents.

---

### Slide 2 — Problem

**Headline:** IT teams are drowning in repeat work

**Bullets:**
- **30–50%** of helpdesk volume is repetitive (passwords, VPN, access, “how do I…”)
- Tier-1 engineers re-type the same answers; hard incidents wait in queue
- Employees expect **24/7** first response; static KB portals get ignored
- Generic chatbots **don’t cite your policies** and **can’t run onboarding**

**Speaker notes:**  
Use one real story: “New hire Monday — HR emails IT, IT emails Facilities, ticket sits three days.” Pain is **delay + context loss**, not lack of tools.

**Visual:** Simple funnel: *100 tickets → 40 repeat → 20 stuck in triage → 5 miss SLA*

**Do not claim:** Exact customer ticket volumes unless you have permission.

---

### Slide 3 — Why now

**Headline:** AI finally works for IT — if you ground it and govern it

**Bullets:**
- LLMs are good at **language**; bad at **your environment** without RAG
- Mid-market can’t afford 18-month ServiceNow projects
- Slack/Teams are where employees already ask for help
- **Regulated buyers** need audit trails, not shadow IT chatbots

**Speaker notes:**  
Position as **decision support + automation**, not “fire your helpdesk.” Security and outage tickets always escalate.

*(Investor only)* Add market size slide here if you have sourced TAM/SAM — do not invent numbers.

---

### Slide 4 — Solution

**Headline:** One platform: tickets, AI, playbooks, rules, proof

**Diagram (use on slide):**

```
Employee → Ticket (web / Slack / Teams / API)
              ↓
         AI analysis (KB + confidence)
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
 Deflect            Escalate with full thread
    ↓                   ↓
 Workflow playbook   Human queue + routing hint
    ↓
 Slack/Teams notify · Jira sync · Webhooks
```

**Bullets:**
- **Web app** — dashboard, tickets, workflows, automation, analytics, billing
- **AI agent service** — dedicated FastAPI stack; RAG over your KB
- **Integrations** — Slack, Teams, Okta, Google, M365, Jira, Partner API

**Speaker notes:**  
Three deployable components (React, Django, Agent) = serious product, not a wrapper script.

---

### Slide 5 — How it works

**Headline:** Every ticket gets a clear next step

**Numbered flow:**
1. **Intake** — Employee describes issue in plain language (category, screenshot optional)
2. **Analyze** — AI returns steps, confidence score, KB citations, suggested action
3. **Converse** — Multi-turn chat (“that didn’t work”, “explain step 2”) without resetting
4. **Resolve or escalate** — User confirms fix, or human claims with full context
5. **Automate** — Rules trigger workflows, Slack/Teams, webhooks on events

**Speaker notes:**  
Emphasize **confidence score** — “We show when to trust vs when to get a human.” Critical categories (security, outage, data loss) never auto-resolve.

**Demo hook:** “I’ll show steps 1–4 with a VPN ticket in a minute.”

---

### Slide 6 — Three engines

**Headline:** AI + Operations + Proof

| | AI Engine | Operations Engine | Proof Engine |
|---|-----------|-------------------|--------------|
| **Does** | Analyze, chat, RAG, remediation scripts | Playbooks, SLAs, connector checks, rules | Deflection %, calibration, audit |
| **Wins vs** | Generic ChatGPT / basic Zendesk AI | Spreadsheets + email chains | Vendors who only show ROI in slides |
| **Live today** | ✅ | ✅ | ✅ |

**Speaker notes:**  
“Competitors give you chat OR tickets OR workflows. We connect all three with measurable outcomes.”

---

### Slide 7 — Product pillars (feature tiles)

**Headline:** Built for IT ops, not generic support

Use six tiles (from live marketing — verify before printing):

| Tile | Headline | One line |
|------|----------|----------|
| ⚡ | Instant resolution | KB-grounded AI with citations and confidence |
| 👤 | Real escalation | Full thread + routing hints; no black hole |
| ☑️ | Multi-step workflows | Onboarding playbooks, SLAs, step claims |
| 📈 | Automation rules | Triggers → notify, webhook, start workflow |
| 🔌 | API & integrations | 8+ live connectors + Partner REST API |
| 🛡️ | Enterprise security | Immutable audit log, RBAC, circuit breaker |

**Speaker notes:**  
Expand only the tile your prospect cares about. MSP → workflows + multi-workspace. Regulated → security tile.

---

### Slide 8 — Integrations

**Headline:** Plugs into the stack you already have

**On-slide grid:**

| Channel | Identity | ITSM | Automation |
|---------|----------|------|------------|
| Slack | Okta (read) | Jira Cloud | Outbound webhooks |
| Microsoft Teams | Google Workspace | Partner API | Automation rules |
| Web app | Microsoft 365 | | Signed HMAC deliveries |

**Bullets:**
- **No rip-and-replace** — sit alongside existing ticketing
- **Partner API** — `POST /api/public/v1/tickets/create/` for external intake
- **Webhooks** — `ticket.created`, `ticket.escalated`, `ticket.resolved`, `workflow.step.completed`

**Speaker notes:**  
“We’re not pretending to be ServiceNow year one. We automate the repeat slice and sync escalations to Jira.”

**Demo optional:** Show Settings → Integrations connected state (even one connector counts).

---

### Slide 9 — Hero SKU: Employee onboarding

**Headline:** Sellable playbook — Employee Onboarding Pack

**Bullets:**
- **9-step** global workflow: IT provision → Okta/Google/M365 auto-checks → HR approval → day-one check-in
- **Automation rule:** `ticket.created` + category=onboarding → auto-start
- **KB articles** linked on steps; **child tickets** for IT vs Facilities
- **Remote variant:** `remote_onboarding` skips facilities
- Install: `install_playbook_bundle employee-onboarding`

**10-minute demo script (put in speaker notes):**

| Min | Show |
|-----|------|
| 0–2 | Playbooks → Employee onboarding pack |
| 2–3 | Settings → one IdP connected |
| 3–5 | Create onboarding ticket → workflow auto-starts |
| 5–8 | IT claims step; connector auto-check completes |
| 8–10 | Dashboard metrics + automation execution log |

**Speaker notes:**  
“This is our ‘show me you’re not just a chatbot’ moment — real owners, due dates, Slack pings, connector verification.”

---

### Slide 10 — Security & enterprise *(enterprise only)*

**Headline:** Security-minded by default

**Bullets:**
- **Workspace isolation** — every ticket, rule, KB article scoped to team
- **Delegated admin** — grant playbooks without sharing owner password
- **Immutable audit log** — append-only events; CSV export (Settings → Security)
- **Agent circuit breaker** — 30s max timeout; tickets don’t hang when AI is down
- **Partner API keys** — scoped `rmq_pk_*` with per-key permissions
- **MSP mode** — parent hub, isolated client workspaces

**Speaker notes:**  
For formal questionnaires, use `docs/trust/ENTERPRISE_SECURITY_QUESTIONNAIRE.md`. **Do not claim SOC2 Type II** unless leadership confirms certification status.

**Honest limits (if asked):**
- Formal pen-test report — discuss under NDA
- Data residency — deal-specific
- HIPAA BAA — commercial decision

---

### Slide 11 — Pricing

**Headline:** Start small, grow with volume

**On-slide (from marketing site — confirm with commercial team):**

| Plan | Monthly | Annual | Highlights |
|------|---------|--------|------------|
| **Starter** | $19 | $190/yr | 5 teams, 10 members, basic AI routing |
| **Pro** | $49 | $490/yr | 20 teams, 50 members, advanced AI + analytics |
| **Enterprise** | $99+ | $990/yr | Unlimited, API access, custom terms |

**Bullets:**
- **14-day trial** — upgrade when ready; no surprise charges
- **AI operations quota** — scales with plan (show Billing screen in demo)
- Enterprise = security review, custom integrations, SLA discussion

**Speaker notes:**  
Anchor on **cost of one FTE tier-1** vs subscription. Use prospect’s ticket volume if known.

**Warning:** Marketing hero cites “40% faster resolution” and “500+ companies” — **only use if legal/commercial approves**; otherwise use “teams report” language or pilot-specific metrics.

---

### Slide 12 — Traction / proof

**Headline:** Outcomes you can measure in-product

**Bullets (product-backed — show live dashboard):**
- **Deflection rate** — AI-first resolved without human
- **Confidence calibration** — high-confidence buckets vs actual outcomes
- **Workflow completion** — onboarding started vs completed
- **Automation execution log** — every rule run logged

**Placeholder slots (fill with real data):**
- Pilot customer logo + quote
- “X% deflection in 30-day pilot”
- “Onboarding playbook completed in Y days avg”

**Speaker notes:**  
If no logos yet, demo **your own pilot workspace metrics** — honest beats fabricated logos.

*(Investor only)* Add team slide, roadmap milestone, raise amount here.

---

### Slide 13 — Competitive positioning

**Headline:** Where we win (and where we don’t pretend)

| Competitor | Their strength | ResolveMeQ angle |
|------------|----------------|------------------|
| **ServiceNow** | Full ITSM | Faster to deploy; AI + playbooks without 12-month implementation |
| **Zendesk / Freshservice** | Mature ticketing | IT-native: connector checks, ops roles, deflection calibration |
| **Moveworks / Aisera** | Enterprise AI | Mid-market price; transparent confidence + KB citations |
| **Intercom** | Chat UX | Escalation with IT context; workflows beyond chat |
| **Atomicwork** | Modern IT ops UI | Comparable playbooks + stronger AI/RAG story |

**Positioning line:**  
“We win mid-market IT teams and MSPs who need **AI + playbooks + proof** in weeks, not a platform migration.”

**Do not say:** “We replace ServiceNow” or “Full ITSM platform.”

---

### Slide 14 — Pilot offer & next steps

**Headline:** 30-day pilot — prove deflection on your tickets

**Pilot structure (suggested):**

| Week | Activity |
|------|----------|
| 1 | Workspace setup, KB import, 1 integration (Slack or IdP) |
| 2 | VPN/password pilot categories; measure deflection |
| 3 | Install onboarding playbook; run 2 real new hires |
| 4 | Review analytics + audit export; go/no-go |

**Exit criteria (from adoption test plan):**
- Journeys 1–3 pass (deflection, escalation, onboarding)
- No open P0 issues
- IT lead runs demo without engineering

**CTA:**
- **Start trial:** `https://app.resolvemeq.net/signup`
- **Book demo:** [your calendar link]
- **Docs:** `https://resolvemeq.net/docs`

**Speaker notes:**  
Offer one **champion** (IT lead) and one **executive sponsor** (VP Ops). Scope to 50–200 employees for first pilot.

---

### Slide 15 — Appendix

Keep these backup slides after the main deck:

| Appendix | Contents |
|----------|----------|
| A. Architecture | React + Django + FastAPI agent diagram |
| B. Automation reference | Triggers + actions list |
| C. Audit event types | Full compliance event list |
| D. Partner API | Scopes, sample curl |
| E. FAQ | Top 5 objections (see below) |
| F. Roadmap | Only features with ✅ in engineering tracker |

---

## 10-minute live demo script (pair with deck)

Run this **after slide 5** or **instead of slides 6–9** for technical audiences.

| Step | Screen | Say this |
|------|--------|----------|
| 1 | `/knowledge-base` | “Here’s our internal VPN article — AI will cite this.” |
| 2 | `/tickets` → New | “Employee files VPN issue from home.” |
| 3 | Ticket detail → AI chat | “Steps, confidence, citation — not generic ChatGPT.” |
| 4 | Escalate | “If it fails, one click — full thread to IT.” |
| 5 | `/escalation-queue` | “Owner claims; routing suggestion shown.” |
| 6 | `/workflows/templates` | “Onboarding pack — 9 steps, connector checks.” |
| 7 | New onboarding ticket | “Rule auto-starts workflow.” |
| 8 | `/settings/automation` | “Edit rule: escalated → notify Teams.” |
| 9 | `/` dashboard | “Deflection and workflow metrics — live.” |
| 10 | Settings → Security | “Audit export for your compliance team.” |

**Backup if AI is slow:** Use a pre-processed ticket; say “analysis typically under 30 seconds; circuit breaker prevents hangs.”

---

## Objection handling (FAQ slide content)

| Objection | Response |
|-----------|----------|
| “Is this just ChatGPT?” | No — RAG over **your** KB, confidence scores, citations, escalation paths, audit log. |
| “Will it hallucinate?” | Low confidence → clarify or escalate; security/outage never auto-resolve. |
| “We already have ServiceNow.” | We sit in front — deflect tier-1, sync escalations to Jira, webhook to ITSM. |
| “What if AI goes down?” | Circuit breaker; fallback message within 30s; ticket still creatable. |
| “SOC2?” | Audit log + RBAC shipped; formal SOC2 is a commercial timeline — share security questionnaire. |
| “How long to deploy?” | Pilot in 1 week: KB + Slack + one playbook. |
| “Can MSPs use it?” | Yes — MSP mode, client workspaces, shared playbooks. |

---

## Visual & design guidelines

| Element | Guidance |
|---------|----------|
| **Colors** | Primary blue `#2563eb`, zinc neutrals — match `resolvemeq.net` |
| **Typography** | Clean sans-serif; one display font for headlines |
| **Screenshots** | Use **light mode** app screenshots (product default) |
| **Diagrams** | Simple boxes-and-arrows; avoid busy architecture dumps on main slides |
| **Logos** | Integration logos (Slack, Microsoft, Okta, Google, Jira) on slide 8 |
| **Video** | Hero demo video slot exists but may be empty — record 90s screen capture if needed |
| **Motion** | Subtle on marketing site; keep deck static for PDF export |

**Screenshot checklist (capture from `app.resolvemeq.net`):**
- [ ] Dashboard with deflection metrics
- [ ] Ticket + AI chat with KB citation
- [ ] Workflow checklist on ticket
- [ ] Automation rules list + edit form
- [ ] Settings → Integrations connected
- [ ] Audit log export button

---

## What NOT to put in the deck

| Claim | Why |
|-------|-----|
| “500+ companies” / “40% faster” | On marketing site but **verify** before investor/regulated use |
| “Full ServiceNow replacement” | Not positioned; will fail enterprise eval |
| “SOC2 certified” | Unless formally certified |
| “100% autonomous” | Human-in-loop by design |
| “All automation rules in UI” | `run_agent` and `schedule.cron` are API-only |
| “Analytics fully built” | Some cards still “Coming soon” |
| Stale roadmap items | Rules engine, Teams “hidden” — **shipped**; verify live app |

Always cross-check against `MARKETING_PRODUCT_BRIEF.md` before external send.

---

## Deck variants (quick cuts)

### 5-slide “elevator” version
1. Problem → 2. Solution diagram → 3. Demo screenshot (AI + citation) → 4. Onboarding playbook → 5. CTA + trial link

### MSP partner version
Replace slide 9 with **MSP mode**: hub workspace, client isolation, per-client metrics. Add partner margin / resale slide if applicable.

### Investor version
Add: Team, market size, business model, raise, use of funds, 18-month milestones. Remove deep integration grid.

### Security review version
Expand slide 10; attach `ENTERPRISE_SECURITY_QUESTIONNAIRE.md`; no pricing until procurement asks.

---

## Export checklist (before sending)

- [ ] All URLs use `resolvemeq.net` / `app.resolvemeq.net` / `api.resolvemeq.net` (not `.com` unless ops confirms)
- [ ] Signup link is `/signup` not `/register`
- [ ] Demo environment tested same day (AI agent up, one integration connected)
- [ ] Pricing matches live Billing page
- [ ] No fabricated logos or metrics
- [ ] Appendix security answers match July 2026 questionnaire
- [ ] PDF filename: `ResolveMeQ_[Audience]_[YYYY-MM].pdf`

---

## Related assets

| Asset | Location |
|-------|----------|
| Product brief | `docs/misc/MARKETING_PRODUCT_BRIEF.md` |
| Adoption test plan | `docs/misc/BUSINESS_ADOPTION_TEST_PLAN.md` |
| Onboarding demo script | `docs/playbooks/PLAYBOOK_EMPLOYEE_ONBOARDING.md` |
| Security Q&A | `docs/trust/ENTERPRISE_SECURITY_QUESTIONNAIRE.md` |
| Product manual (customer-facing) | https://resolvemeq.net/docs |
| Partner API docs | https://resolvemeq.net/docs/partner-api |
| Live app | https://app.resolvemeq.net |

---

*Last updated: July 2026. Update this guide when pricing, positioning, or major features change.*
