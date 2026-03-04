"""
Management command to populate sample QuickReply suggestions for the AI chat
"""
from django.core.management.base import BaseCommand
from tickets.chat_models import QuickReply


class Command(BaseCommand):
    help = 'Populate sample QuickReply suggestions for AI chat'

    def handle(self, *args, **options):
        # Clear existing quick replies
        QuickReply.objects.all().delete()
        self.stdout.write(self.style.WARNING('Cleared existing quick replies'))

        quick_replies = [
            # General category
            {
                'category': 'general',
                'label': 'Show similar tickets',
                'message_text': 'Can you show me similar tickets that were resolved?',
                'priority': 100,
                'is_active': True,
            },
            {
                'category': 'general',
                'label': 'Talk to a human',
                'message_text': 'I would like to speak with a human support agent',
                'priority': 90,
                'is_active': True,
            },
            {
                'category': 'general',
                'label': 'I need more help',
                'message_text': 'I still need help with this issue',
                'priority': 80,
                'is_active': True,
            },
            {
                'category': 'general',
                'label': 'Check status',
                'message_text': 'What is the current status of my ticket?',
                'priority': 70,
                'is_active': True,
            },
            {
                'category': 'general',
                'label': 'This is urgent',
                'message_text': 'This is urgent, I need immediate assistance',
                'priority': 60,
                'is_active': True,
            },

            # Printer issues
            {
                'category': 'printer',
                'label': 'Printer is offline',
                'message_text': 'My printer shows as offline and I cannot print',
                'priority': 100,
                'is_active': True,
            },
            {
                'category': 'printer',
                'label': 'Print quality issues',
                'message_text': 'The print quality is poor - blurry or faded',
                'priority': 90,
                'is_active': True,
            },
            {
                'category': 'printer',
                'label': 'Paper jam',
                'message_text': 'There is a paper jam in my printer',
                'priority': 80,
                'is_active': True,
            },
            {
                'category': 'printer',
                'label': 'Connection problems',
                'message_text': 'Cannot connect to the printer from my computer',
                'priority': 70,
                'is_active': True,
            },
            {
                'category': 'printer',
                'label': 'Driver issues',
                'message_text': 'I think there is a problem with the printer drivers',
                'priority': 60,
                'is_active': True,
            },

            # Email issues
            {
                'category': 'email',
                'label': 'Cannot send emails',
                'message_text': 'I cannot send emails from my account',
                'priority': 100,
                'is_active': True,
            },
            {
                'category': 'email',
                'label': 'Not receiving emails',
                'message_text': 'I am not receiving emails that are sent to me',
                'priority': 90,
                'is_active': True,
            },
            {
                'category': 'email',
                'label': 'Sync issues',
                'message_text': 'My email is not syncing properly across devices',
                'priority': 80,
                'is_active': True,
            },
            {
                'category': 'email',
                'label': 'Attachment problems',
                'message_text': 'I cannot open or send email attachments',
                'priority': 70,
                'is_active': True,
            },
            {
                'category': 'email',
                'label': 'Account locked',
                'message_text': 'My email account appears to be locked',
                'priority': 60,
                'is_active': True,
            },

            # Network issues
            {
                'category': 'network',
                'label': 'No internet connection',
                'message_text': 'I have no internet connection on my device',
                'priority': 100,
                'is_active': True,
            },
            {
                'category': 'network',
                'label': 'Slow connection',
                'message_text': 'My internet connection is very slow',
                'priority': 90,
                'is_active': True,
            },
            {
                'category': 'network',
                'label': 'VPN not working',
                'message_text': 'I cannot connect to the company VPN',
                'priority': 80,
                'is_active': True,
            },
            {
                'category': 'network',
                'label': 'WiFi problems',
                'message_text': 'Cannot connect to the office WiFi network',
                'priority': 70,
                'is_active': True,
            },
            {
                'category': 'network',
                'label': 'Intermittent connectivity',
                'message_text': 'My connection keeps dropping intermittently',
                'priority': 60,
                'is_active': True,
            },

            # Access/Password issues
            {
                'category': 'access',
                'label': 'Reset my password',
                'message_text': 'I need to reset my password',
                'priority': 100,
                'is_active': True,
            },
            {
                'category': 'access',
                'label': 'Account locked',
                'message_text': 'My account is locked due to too many failed login attempts',
                'priority': 90,
                'is_active': True,
            },
            {
                'category': 'access',
                'label': 'Cannot log in',
                'message_text': 'I cannot log in to the system',
                'priority': 80,
                'is_active': True,
            },
            {
                'category': 'access',
                'label': 'Need access to system',
                'message_text': 'I need access to a system or application',
                'priority': 70,
                'is_active': True,
            },
            {
                'category': 'access',
                'label': 'MFA not working',
                'message_text': 'My multi-factor authentication is not working',
                'priority': 60,
                'is_active': True,
            },

            # Software issues
            {
                'category': 'software',
                'label': 'Application crashed',
                'message_text': 'The application keeps crashing',
                'priority': 100,
                'is_active': True,
            },
            {
                'category': 'software',
                'label': 'Software not responding',
                'message_text': 'The software is frozen and not responding',
                'priority': 90,
                'is_active': True,
            },
            {
                'category': 'software',
                'label': 'Install new software',
                'message_text': 'I need to install new software',
                'priority': 80,
                'is_active': True,
            },
            {
                'category': 'software',
                'label': 'Update failed',
                'message_text': 'A software update failed to install',
                'priority': 70,
                'is_active': True,
            },
            {
                'category': 'software',
                'label': 'License error',
                'message_text': 'I am getting a software license error',
                'priority': 60,
                'is_active': True,
            },

            # Hardware issues
            {
                'category': 'hardware',
                'label': 'Computer won\'t start',
                'message_text': 'My computer will not start up',
                'priority': 100,
                'is_active': True,
            },
            {
                'category': 'hardware',
                'label': 'Screen issues',
                'message_text': 'There is a problem with my screen/display',
                'priority': 90,
                'is_active': True,
            },
            {
                'category': 'hardware',
                'label': 'Keyboard/Mouse problem',
                'message_text': 'My keyboard or mouse is not working properly',
                'priority': 80,
                'is_active': True,
            },
            {
                'category': 'hardware',
                'label': 'Device overheating',
                'message_text': 'My device is overheating',
                'priority': 70,
                'is_active': True,
            },
            {
                'category': 'hardware',
                'label': 'Battery issue',
                'message_text': 'My laptop battery is not charging or draining quickly',
                'priority': 60,
                'is_active': True,
            },
        ]

        created_count = 0
        for qr_data in quick_replies:
            QuickReply.objects.create(**qr_data)
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} quick reply suggestions across 7 categories'
            )
        )

        # Show summary by category
        self.stdout.write('\nSummary by category:')
        categories = QuickReply.objects.values('category').distinct()
        for cat in categories:
            count = QuickReply.objects.filter(category=cat['category']).count()
            self.stdout.write(f"  {cat['category']}: {count} quick replies")
