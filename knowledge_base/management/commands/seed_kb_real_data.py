"""
Seed realistic Community Q&A data for the Knowledge Base.

Usage:
  ./venv/bin/python manage.py seed_kb_real_data
  ./venv/bin/python manage.py seed_kb_real_data --clear-community
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from base.models import User
from knowledge_base.models import (
    KBQuestion,
    KBAnswer,
    KBComment,
    KBQuestionVote,
    KBAnswerVote,
    KBAttachment,
)


QUESTION_FIXTURES = [
    {
        "title": "VPN connects but internal Jira pages still time out",
        "body": (
            "I can connect to VPN successfully and can reach Outlook/Teams, but Jira and Confluence "
            "internal pages time out after 30-40 seconds. Happens on Windows 11 and only from home network."
        ),
        "tags": ["vpn", "jira", "confluence", "networking"],
        "answers": [
            "Check if split tunneling is enabled. Our Jira/Confluence subnets require full tunnel, not split route.",
            "Flush DNS and reset VPN adapter. In elevated cmd run: ipconfig /flushdns then netsh winsock reset.",
        ],
        "accepted_answer_index": 0,
    },
    {
        "title": "Teams call audio drops every 5 minutes on office Wi-Fi",
        "body": (
            "Video stays connected, but audio drops out for around 5-10 seconds repeatedly. "
            "Only in our 5th-floor meeting room."
        ),
        "tags": ["teams", "wifi", "audio", "meeting-room"],
        "answers": [
            "Disable roaming aggressiveness on Intel Wi-Fi adapter. Aggressive roaming is causing AP handoff jitter.",
            "Set Teams media traffic QoS tag and prioritize UDP 3478-3481 on network policy.",
        ],
        "accepted_answer_index": 1,
    },
    {
        "title": "Printer queue shows Offline but ping works",
        "body": (
            "Shared printer says Offline for all users in Finance. Ping to printer IP works and web console opens."
        ),
        "tags": ["printer", "windows", "spooler", "finance"],
        "answers": [
            "Restart Print Spooler service on print server and clear stuck jobs in C:\\Windows\\System32\\spool\\PRINTERS.",
            "Update printer driver from Type 3 to Type 4 package to avoid spool crashes.",
        ],
        "accepted_answer_index": 0,
    },
    {
        "title": "Outlook keeps prompting for password after reset",
        "body": (
            "User changed password today. Web Outlook works, desktop app keeps asking for credentials in a loop."
        ),
        "tags": ["outlook", "password", "auth", "desktop"],
        "answers": [
            "Remove stale credentials in Credential Manager and restart Outlook profile.",
            "Create a new Outlook profile and set as default to clear cached token mismatch.",
        ],
        "accepted_answer_index": 0,
    },
    {
        "title": "Can’t map network drive over VPN (Access denied)",
        "body": (
            "Drive path is correct and VPN is up. User still gets Access denied on \\\\fileserver\\projects."
        ),
        "tags": ["vpn", "network-drive", "permissions", "fileserver"],
        "answers": [
            "Use domain-qualified username when prompted (DOMAIN\\username), not email format.",
            "Purge cached SMB credentials then reconnect. Old cached creds usually cause this exact behavior.",
        ],
        "accepted_answer_index": 1,
    },
    {
        "title": "Laptop battery drains from 100% to 20% in two hours",
        "body": (
            "Dell Latitude 5430, battery health in BIOS says Good, but real runtime has dropped drastically this week."
        ),
        "tags": ["laptop", "battery", "dell", "windows"],
        "answers": [
            "Check if Teams + Chrome hardware acceleration are both enabled; this spikes GPU usage on battery.",
            "Run Dell power manager calibration and switch thermal profile from Ultra Performance to Optimized.",
        ],
        "accepted_answer_index": 1,
    },
    {
        "title": "Blue screen with DRIVER_IRQL_NOT_LESS_OR_EQUAL after update",
        "body": (
            "After Tuesday patching, two laptops blue screen on boot with DRIVER_IRQL_NOT_LESS_OR_EQUAL."
        ),
        "tags": ["windows", "bsod", "drivers", "patching"],
        "answers": [
            "Boot safe mode, roll back latest NIC driver, then reinstall OEM-certified driver package.",
            "Disable memory integrity temporarily to confirm incompatible driver chain.",
        ],
        "accepted_answer_index": 0,
    },
    {
        "title": "Can’t share screen in Teams webinar (button greyed out)",
        "body": (
            "Presenter role was assigned, but Share button stays disabled in Teams webinar."
        ),
        "tags": ["teams", "webinar", "screen-share", "permissions"],
        "answers": [
            "Meeting options had Who can present set to Organizers only; switch to Specific people and rejoin.",
            "Policy blocked desktop sharing for webinar profile. Admin enabled and issue resolved after policy refresh.",
        ],
        "accepted_answer_index": 0,
    },
    {
        "title": "How to handle suspicious MFA fatigue prompts",
        "body": (
            "User receives repeated MFA approve prompts they did not initiate. Need standard response steps."
        ),
        "tags": ["security", "mfa", "incident-response", "identity"],
        "answers": [
            "Immediately deny prompts, reset password, revoke active sessions, and open security incident ticket.",
            "Review sign-in logs for impossible travel and block risky IPs in conditional access.",
        ],
        "accepted_answer_index": 0,
    },
]


class Command(BaseCommand):
    help = "Seed realistic community Q&A data (questions, answers, comments, votes, attachments)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-community",
            action="store_true",
            help="Delete existing KB community data before seeding.",
        )

    def _ensure_seed_users(self):
        users = list(User.objects.filter(is_active=True).order_by("date_joined")[:8])
        if len(users) < 2:
            raise ValueError("Need at least 2 active users to seed realistic community data.")
        # Reuse available users in round-robin.
        return users

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear_community"]:
            KBAttachment.objects.all().delete()
            KBComment.objects.all().delete()
            KBAnswerVote.objects.all().delete()
            KBQuestionVote.objects.all().delete()
            KBAnswer.objects.all().delete()
            KBQuestion.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing community Q&A data."))

        users = self._ensure_seed_users()
        created_questions = 0
        created_answers = 0
        created_comments = 0
        created_attachments = 0

        questions = []
        for i, fixture in enumerate(QUESTION_FIXTURES):
            author = users[i % len(users)]
            question, was_created = KBQuestion.objects.get_or_create(
                title=fixture["title"],
                defaults={
                    "body": fixture["body"],
                    "tags": fixture["tags"],
                    "created_by": author,
                    "is_published": True,
                    "views": 18 + (i * 7),
                },
            )
            if was_created:
                created_questions += 1
            questions.append(question)

            answers = []
            for j, answer_body in enumerate(fixture["answers"]):
                answer_author = users[(i + j + 1) % len(users)]
                answer, answer_created = KBAnswer.objects.get_or_create(
                    question=question,
                    body=answer_body,
                    defaults={
                        "created_by": answer_author,
                        "is_published": True,
                    },
                )
                if answer_created:
                    created_answers += 1
                answers.append(answer)

            accepted_idx = fixture.get("accepted_answer_index")
            if accepted_idx is not None and 0 <= accepted_idx < len(answers):
                for idx, ans in enumerate(answers):
                    should_accept = idx == accepted_idx
                    if ans.is_accepted != should_accept:
                        ans.is_accepted = should_accept
                        ans.save(update_fields=["is_accepted", "updated_at"])

            question.answer_count = question.answers.filter(is_published=True).count()
            question.save(update_fields=["answer_count", "updated_at"])

            # Seed comments on question and accepted answer
            comment_author = users[(i + 2) % len(users)]
            q_comment, q_comment_created = KBComment.objects.get_or_create(
                question=question,
                body="Thanks — confirming this issue is reproducible in our environment too.",
                defaults={"created_by": comment_author},
            )
            if q_comment_created:
                created_comments += 1

            accepted_answer = next((a for a in answers if a.is_accepted), answers[0] if answers else None)
            if accepted_answer:
                a_comment, a_comment_created = KBComment.objects.get_or_create(
                    answer=accepted_answer,
                    body="Applied this fix and it resolved the issue for our team.",
                    defaults={"created_by": users[(i + 3) % len(users)]},
                )
                if a_comment_created:
                    created_comments += 1

            # Seed lightweight attachment metadata on some records
            if i % 3 == 0:
                att, att_created = KBAttachment.objects.get_or_create(
                    question=question,
                    original_name=f"diag-{question.id}.txt",
                    defaults={
                        "uploaded_by": author,
                        "file_path": f"kb_community/seed/diag-{question.id}.txt",
                        "file_url": f"/media/kb_community/seed/diag-{question.id}.txt",
                        "content_type": "text/plain",
                        "file_size": 2048 + i,
                    },
                )
                if att_created:
                    created_attachments += 1

        # Duplicate relationships for realism
        if len(questions) >= 4:
            q = questions[4]
            if q.duplicate_of_id != questions[0].id:
                q.duplicate_of = questions[0]
                q.duplicate_note = "Same symptom pattern observed on VPN + SMB auth."
                q.save(update_fields=["duplicate_of", "duplicate_note", "updated_at"])
            q2 = questions[7]
            if q2.duplicate_of_id != questions[1].id:
                q2.duplicate_of = questions[1]
                q2.duplicate_note = "Webinar permissions overlap with Teams audio meeting policy."
                q2.save(update_fields=["duplicate_of", "duplicate_note", "updated_at"])

        # Votes (question + answer)
        for idx, question in enumerate(questions):
            voters = users[:5]
            for u_idx, voter in enumerate(voters):
                val = 1 if (u_idx + idx) % 4 != 0 else -1
                KBQuestionVote.objects.update_or_create(
                    question=question,
                    user=voter,
                    defaults={"value": val},
                )
            q_score = question.votes.aggregate(total=Sum("value"))["total"] or 0
            if question.score != q_score:
                question.score = q_score
                question.save(update_fields=["score", "updated_at"])

            for a_idx, answer in enumerate(question.answers.all()):
                for u_idx, voter in enumerate(voters):
                    val = 1 if (u_idx + a_idx) % 5 != 0 else -1
                    KBAnswerVote.objects.update_or_create(
                        answer=answer,
                        user=voter,
                        defaults={"value": val},
                    )
                a_score = answer.votes.aggregate(total=Sum("value"))["total"] or 0
                if answer.score != a_score:
                    answer.score = a_score
                    answer.save(update_fields=["score", "updated_at"])

        self.stdout.write(self.style.SUCCESS("Community KB seeding complete."))
        self.stdout.write(self.style.SUCCESS(f"Questions total: {KBQuestion.objects.count()} (created: {created_questions})"))
        self.stdout.write(self.style.SUCCESS(f"Answers total: {KBAnswer.objects.count()} (created: {created_answers})"))
        self.stdout.write(self.style.SUCCESS(f"Comments total: {KBComment.objects.count()} (created: {created_comments})"))
        self.stdout.write(self.style.SUCCESS(f"Attachments total: {KBAttachment.objects.count()} (created: {created_attachments})"))
