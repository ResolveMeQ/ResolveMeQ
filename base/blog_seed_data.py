"""
Legacy marketing blog posts from resolvemeqWeb/src/data/blogPosts.js.

Keep in sync when editing the static JS source until the marketing site
relies entirely on the API.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Tuple

STATIC_BLOG_AUTHOR = "Nyuydine Bill"

STATIC_BLOG_POSTS: List[Dict[str, Any]] = [
    {
        "slug": "how-ai-transforms-it-support",
        "title": "How AI Is Transforming IT Support in 2025",
        "iso_date": "2025-02-01",
        "excerpt": (
            "A practical look at where AI helps IT desks today—triage, knowledge, and escalation—"
            "without pretending the humans go away."
        ),
        "read_time_minutes": 12,
        "category": "AI & Automation",
        "body": """For most organizations, the question is no longer whether AI belongs in the service desk—it’s where it earns its keep without creating new failure modes. The teams we talk to aren’t trying to replace tier-1 overnight; they’re trying to stop the same questions from bouncing between three queues before anyone solves the root cause.

This article is about that middle path: automation that respects your policies, your tooling, and the fact that some tickets will always need a person who can read context.

## From “chatbot in the corner” to workflow-aware assistance

Early IT chat experiments often failed because they were disconnected from ticketing, identity, and knowledge. A user would get a plausible paragraph that didn’t match your VPN runbook, or an answer that conflicted with what security expects. Modern setups treat the conversation as the front end of a structured flow: capture intent, attach evidence (device, location, error text), then either resolve from approved content or open a ticket with a useful starting point.

That shift matters because it changes what you measure. Instead of “did the bot reply,” you track first-contact resolution for well-defined intents, time-to-first-action for escalations, and repeat rates for the same issue class.

## What to automate first (and what to leave alone)

Good first candidates share a few traits: high volume, clear success criteria, and documentation your team already trusts. Password resets, MFA lockouts, standard software installs, and “how do I connect to the VPN” are classic examples—if your articles are accurate and your identity stack supports safe automation.

Poor first candidates are the ones where the cost of a wrong answer is high or the inputs are messy: vague “internet is slow” reports without diagnostics, access requests that need manager approval, or anything that routinely turns into a multi-team investigation. Those are better handled with structured intake and smart routing than with a fully automated resolution path on day one.

## Knowledge quality is the ceiling

AI suggestions are only as good as the corpus you point them at. If your knowledge base is a graveyard of PDFs from 2019, automation will amplify confusion, not remove it. Teams that see durable gains usually pair AI rollout with a lightweight editorial rhythm: owners per category, stale-article review, and explicit “retired” states so old guidance stops surfacing.

You don’t need perfection on day one—you need a honest baseline and a process to improve it weekly.

## Escalation that doesn’t reset the conversation

The best handoffs read like a briefing, not a transcript dump. When automation stops, the human should see what was tried, what failed, and what the system would try next if it had permissions. That single change often shaves more time off resolution than another five percentage points of deflection.

## Getting started without a twelve-month program

Pick one channel (portal chat, Teams, or email-to-ticket), one category of tickets, and one success metric. Run a pilot for four to six weeks with a weekly review of failures. Expand only when the failure modes are understood—not when the slide deck says you’re “AI-enabled.”

If you keep humans in the loop, measure honestly, and treat knowledge as a product, AI stops being a slogan and becomes part of how your desk keeps pace with the business.""",
    },
    {
        "slug": "best-practices-ticket-routing",
        "title": "Best Practices for Smart Ticket Routing",
        "iso_date": "2025-01-08",
        "excerpt": (
            "Design routing rules that reflect how work really flows: skills, load, time zones, "
            "and the difference between urgency and impact."
        ),
        "read_time_minutes": 11,
        "category": "Best Practices",
        "body": """Ticket routing is one of those invisible systems that everyone feels when it breaks. Users notice when everything goes to a single “IT” bucket. Agents notice when security tickets land on the hardware team. Leadership notices when SLAs look fine on paper while real priorities stall.

Smart routing isn’t about fancier labels—it’s about matching work to the people who can finish it with the least round-trip.

## Start with categories people actually use

If your request types are so granular that users guess wrong half the time, your data—and your automation—will be noisy. If they’re so broad that every ticket says “General IT,” you can’t route or report meaningfully. The workable middle is usually ten to twenty top-level intents at the portal, with sub-types used internally after triage.

Run a quarterly review of miscategorized tickets. If two categories constantly bleed into each other, merge them or split on a dimension users understand (“Laptop” vs “Phone” beats “Endpoint A” vs “Endpoint B”).

## Separate priority from impact

“Urgent” is emotional; impact is operational. A single user blocked from payroll is urgent to them; a degraded VPN for two hundred remote workers is urgent to the business. Routing rules should encode impact and dependency, not just the red exclamation mark in the subject line.

Many teams use a simple matrix: user count affected, revenue or compliance sensitivity, and whether there’s a known workaround. That feeds both queue assignment and executive communication when things go sideways.

## Load and skills: the forgotten variables

Even perfect category logic fails if one queue is underwater. Rotation policies help, but they’re a bandage if underlying volume is uneven. Look at arrivals by hour and time zone, not just daily totals. If APAC opens tickets into a queue that nobody owns until US morning, you’ll always look slow—even if your SLA math says you’re “green.”

Skill-based routing is powerful when skills are maintained. If your CMDB says everyone on the network team can handle firewalls but only two people actually do, your rules will keep disappointing you. Keep skill tags small, audited, and tied to real escalation patterns.

## When to bring AI into routing

AI is most useful when language is messy but patterns are stable: vague descriptions that still map to known problem classes, or subject lines that don’t match your portal vocabulary. The goal is suggestion, not silent reassignment—show agents why a ticket was scored a certain way, and let them correct it so the model learns your org’s language.

## Metrics that tell the truth

Time-to-first-touch by queue, reopen rate after first response, and percentage of tickets reassigned within an hour are blunt but honest signals. Pair them with qualitative review: sample twenty tickets a week and ask, “Did this land in the right place on the first try?”

Routing is never “done.” It’s a living system that should change when hiring changes, when tools change, and when the business opens a new site. Treat it that way and the helpdesk stops feeling like a black hole.""",
    },
    {
        "slug": "reducing-support-costs-with-automation",
        "title": "Reducing Support Costs Without Sacrificing Quality",
        "iso_date": "2025-01-20",
        "excerpt": (
            "Cost cutting that sticks usually comes from fewer round trips and less rework—not from "
            "shaving minutes off handle time in a spreadsheet."
        ),
        "read_time_minutes": 10,
        "category": "Strategy",
        "body": """When finance asks IT to “do more with less,” the worst response is a blunt hiring freeze with no change to how work flows. The best response is to remove repetitive work, shorten escalation chains, and make it obvious where quality is slipping before users churn internally.

Automation is one lever—but it’s not the only one, and it’s never free.

## Where the money actually goes

Labor dominates service desk budgets, but the hidden costs are often rework: tickets bounced between teams, duplicate incidents for the same root cause, and “swivel chair” diagnostics where three people collect the same screenshots. If you only automate the easy 10% of tickets but cut rework by a third, the savings can dwarf a flashy chatbot pilot.

Start by tagging a month of tickets with “reopened,” “reassigned,” and “duplicate follow-up.” That histogram tells you where to invest first.

## Automation that protects quality

Cheap automation pushes users into self-service that doesn’t work, which drives more phone calls and more shadow IT. Good automation finishes the job for simple cases and makes complex cases faster by structuring data up front. Measure CSAT and time-to-resolution together; if one improves and the other tanks, you’re trading quality for throughput in a way that won’t hold.

Keep humans in the loop for access changes, anything touching regulated data, and any workflow where a wrong click breaks production.

## Self-service people will actually use

Portals fail when search is bad, articles are stale, and the path to a human is hidden. If your KB opens with a wall of PDFs, fix that before you buy another tool. Short articles, consistent titles, and “last verified” dates signal that someone owns the content.

Pair self-service with gentle deflection: suggest two articles before offering a form, but never trap users in a loop when they’re clearly stuck.

## Governance without bureaucracy

You need owners: who approves new automated actions, who reviews failures weekly, and who can roll back a change in minutes when something misfires in prod. That’s not paperwork for its own sake—it’s how you keep automation from becoming tomorrow’s incident root cause.

## The honest ROI conversation

Frame savings as capacity reclaimed, not heads removed. “We freed six FTE equivalents of triage time” is a story hiring managers and project teams can use. “We cut two agents” might be true eventually, but it’s the wrong opening line if you want partnership from the people doing the work.

Automation and good routing compound. Fix rework first, then automate the clean, high-volume paths, and costs usually follow without a race to the bottom on service quality.""",
    },
    {
        "slug": "building-internal-knowledge-base",
        "title": "Building an Internal Knowledge Base That Actually Gets Used",
        "iso_date": "2024-12-05",
        "excerpt": (
            "Structure, ownership, and habits that keep articles findable for humans and trustworthy "
            "for automation—not another graveyard of PDFs."
        ),
        "read_time_minutes": 13,
        "category": "Knowledge Base",
        "body": """Most internal knowledge bases don’t die from lack of tools—they die from lack of habit. Someone launches Confluence or SharePoint with good intentions, three teams publish in different formats, and six months later everyone asks questions in Slack because search returns seventeen versions of “VPN setup.”

A usable KB is a behavior change project disguised as a documentation project.

## Design for the person who’s stressed

Your reader is often annoyed, in a hurry, and on a small screen. Lead with the outcome (“Connect to VPN on Windows 11”) not the history of your network architecture. Put prerequisites up front: required software, permissions, and links to related tickets or forms.

One topic per article. If you’re covering install, troubleshooting, and uninstall in the same page, split them. Long scrolling walls signal “nobody owns this.”

## Templates beat blank pages

Give authors a skeleton: purpose, audience, steps, verification, escalation path, owner, last reviewed date. Consistent headings make search and AI retrieval both work better because the model can rely on structure, not just keywords.

## Ownership beats volunteerism

“Everyone contributes” usually means no one contributes. Assign categories to named owners—network, identity, collaboration, HRIS integrations—and give them a quarterly quota that’s small but non-zero: review five articles, retire two, add one net-new for recurring incidents you saw last quarter.

Celebrate fixes. When someone updates an article that prevented ten tickets, say so in your IT newsletter or standup. Knowledge work is invisible unless you make it visible.

## Integrate where questions already happen

Articles should surface inside the ticketing tool, chat, and email templates agents use—not only on a wiki nobody bookmarks. If agents paste the same workaround into tickets weekly, that workaround should become an article with their name on the byline.

## Feeding automation without feeding garbage

If you plan to use AI to suggest articles, you need explicit “approved for self-service” flags and a way to exclude drafts. Nothing erodes trust faster than an automated suggestion that points to an internal-only doc or an outdated screenshot.

## Measure adoption, not page views alone

Track deflection after suggested articles, agent insertions of KB links, and time spent on page for top tasks. High views with high bounce can mean SEO-ish titles that don’t match content—fix the mismatch instead of celebrating traffic.

A knowledge base that gets used feels boring in the best way: fewer surprises, faster onboarding for new agents, and a calmer queue. That’s worth the maintenance discipline.""",
    },
    {
        "slug": "measuring-it-support-metrics",
        "title": "The IT Support Metrics That Matter Most",
        "iso_date": "2024-12-18",
        "excerpt": (
            "A focused set of KPIs that tie the help desk to business outcomes—without drowning "
            "leaders in dashboards nobody opens."
        ),
        "read_time_minutes": 11,
        "category": "Analytics",
        "body": """Dashboards multiply faster than insights. If your service desk reviews twenty charts in a weekly meeting but can’t answer “are we getting faster for the work that matters?” your metrics program is decoration.

The goal is a small set of numbers everyone agrees on, tied to actions when they move the wrong direction.

## Start with the user’s timeline

Mean time to resolve (MTTR) is common, but it hides ugly variance. Pair it with time-to-first meaningful response—not auto-replies—and the percentage of tickets resolved without reassignment. Those two expose process friction early.

For internal customers, add a lightweight periodic survey (two questions: “Did we solve it?” “How easy was it?”) sampled across channels so you’re not only hearing from the angriest 1%.

## Volume and mix tell you where to invest

Ticket counts by category trend over quarters, not days. Spikes in access requests might follow a hiring wave; jumps in “Wi-Fi” after an office move point to infrastructure debt. If you only watch SLA compliance, you’ll miss the story the mix is telling.

Normalize by headcount when comparing sites or business units—raw counts punish larger teams unfairly.

## Agent health metrics (the ones people avoid)

Throughput per agent is tempting for micromanagers and toxic for quality. Better signals: overtime hours, after-hours volume, reopen rates by individual (with context), and training hours completed. Burnout shows up in rework and attrition before it shows up in a single chart.

Use team-level aggregates for coaching conversations, not leaderboard rankings on a wall.

## Business-aligned measures

Pick one or two metrics tied to what the company cares about this year: onboarding time-to-productivity, downtime minutes for revenue systems, or audit findings related to access. IT support won’t own all of those end-to-end, but you can show contribution—faster laptop provisioning, fewer P1 incidents, cleaner access reviews.

When executives see IT metrics adjacent to business metrics, budgets get easier.

## Review rhythm beats real-time everything

Daily ops can watch queues in real time; leadership should review trends monthly with pre-reads, not live dashboard theater. Publish a one-page narrative: what changed, what we think caused it, what we’re doing next. That document ages into a useful historical record—unlike a forgotten BI bookmark.

## Goodhart’s law still applies

When a metric becomes a target, it ceases to be a good measure. If you bonus on closed ticket counts, you’ll get premature closes and ticket splitting. If you hammer first response time, you’ll get empty acknowledgments. Pair every target metric with a guardrail metric and occasional manual audits.

Fewer charts, clearer ownership, and honest narratives will beat another ten widgets on a wall. Your future self—and your users—will notice.""",
    },
]


def parse_read_time_minutes(value: Any, *, body: str = "") -> int:
    """Parse ``12 min read`` or an integer; estimate from body when missing."""
    if isinstance(value, int):
        return max(1, min(25, value))
    text = str(value or "").strip()
    match = re.search(r"(\d+)", text)
    if match:
        return max(1, min(25, int(match.group(1))))
    words = len(re.findall(r"\w+", body or ""))
    return max(5, min(25, round(words / 200) or 5))


def _row_to_fields(row: Dict[str, Any], *, author_name: str) -> Dict[str, Any]:
    body = str(row.get("body") or "").strip()
    read_minutes = parse_read_time_minutes(row.get("read_time_minutes"), body=body)
    iso = str(row.get("iso_date") or row.get("isoDate") or "").strip()
    published_at = date.fromisoformat(iso) if iso else date.today()
    image_url = row.get("image_url") or row.get("imageUrl") or row.get("ogImage")
    if image_url is not None:
        image_url = str(image_url).strip() or None
    return {
        "title": str(row["title"]).strip()[:300],
        "excerpt": str(row["excerpt"]).strip()[:2000],
        "body": body,
        "category": str(row["category"]).strip()[:100],
        "read_time_minutes": read_minutes,
        "image_url": image_url,
        "author_name": str(row.get("author_name") or author_name).strip()[:120],
        "published_at": published_at,
        "is_published": True,
        "is_ai_generated": False,
    }


def import_static_blog_posts(
    *,
    force: bool = False,
    dry_run: bool = False,
    author_name: str = STATIC_BLOG_AUTHOR,
) -> Tuple[int, int, int]:
    """
    Import STATIC_BLOG_POSTS into BlogPost.

    Returns (created, updated, skipped).
    """
    from base.models import BlogPost

    created = updated = skipped = 0
    for row in STATIC_BLOG_POSTS:
        slug = str(row["slug"]).strip()
        fields = _row_to_fields(row, author_name=author_name)
        existing = BlogPost.objects.filter(slug=slug).first()

        if existing and not force:
            skipped += 1
            continue

        if dry_run:
            if existing and force:
                updated += 1
            elif not existing:
                created += 1
            continue

        if existing and force:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            updated += 1
        else:
            BlogPost.objects.create(slug=slug, **fields)
            created += 1

    return created, updated, skipped
