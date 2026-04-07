from django.test import TestCase
from base.models import User
from .models import Ticket
from .services import compose_issue_type
from .views import _magic_bytes_valid

class TicketModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )

    def test_create_ticket(self):
        ticket = Ticket.objects.create(
            user=self.user,
            issue_type="wifi (high)",
            status="new",
            description="Cannot connect to Wi-Fi",
            category="wifi"
        )
        self.assertEqual(ticket.user, self.user)
        self.assertEqual(ticket.issue_type, "wifi (high)")
        self.assertEqual(ticket.status, "new")
        self.assertEqual(ticket.category, "wifi")


class ComposeIssueTypeTest(TestCase):
    def test_with_valid_urgency(self):
        self.assertEqual(
            compose_issue_type("Printer offline", "high"),
            "Printer offline (high)",
        )

    def test_without_urgency(self):
        self.assertEqual(compose_issue_type("VPN issue", None), "VPN issue")
        self.assertEqual(compose_issue_type("VPN issue", ""), "VPN issue")

    def test_invalid_urgency_ignored(self):
        self.assertEqual(compose_issue_type("Email", "ASAP"), "Email")

    def test_truncates_to_model_max_length(self):
        max_len = Ticket._meta.get_field("issue_type").max_length
        long_subject = "a" * (max_len + 50)
        out = compose_issue_type(long_subject, "medium")
        self.assertEqual(len(out), max_len)


class MagicBytesTest(TestCase):
    def test_jpeg_png_gif_webp(self):
        self.assertTrue(_magic_bytes_valid(b"\xff\xd8\xff" + b"\x00" * 20))
        self.assertTrue(_magic_bytes_valid(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10))
        self.assertTrue(_magic_bytes_valid(b"GIF89a" + b"\x00" * 20))
        self.assertTrue(_magic_bytes_valid(b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 10))

    def test_rejects_non_image(self):
        self.assertFalse(_magic_bytes_valid(b"<!DOCTYPE html>"))
        self.assertFalse(_magic_bytes_valid(b""))
