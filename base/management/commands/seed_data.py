# base/management/commands/seed_data.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from base.models import User, Profile, Team, UserPreferences
from tickets.models import Ticket, TicketInteraction
from solutions.models import Solution, KnowledgeBaseEntry
from knowledge_base.models import KnowledgeBaseArticle, LLMResponse


class Command(BaseCommand):
    help = 'Seeds realistic data for a specific user across all models'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default='billleynyuy@gmail.com', help='User email to seed data for')

    def handle(self, *args, **options):
        email = options['email']
        
        self.stdout.write(self.style.WARNING(f'Starting data seeding for {email}...'))
        
        # Create or get user
        user = self.create_user(email)
        
        # Create profile and preferences
        self.create_profile(user)
        self.create_preferences(user)
        
        # Create teams
        teams = self.create_teams(user)
        
        # Create knowledge base articles
        kb_articles = self.create_kb_articles()
        
        # Create tickets with interactions and solutions
        tickets = self.create_tickets(user, teams)
        self.create_ticket_interactions(tickets, user)
        self.create_solutions(tickets, user, kb_articles)
        
        # Create LLM responses
        self.create_llm_responses(tickets, kb_articles)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Successfully seeded data for {email}'))
        self.stdout.write(self.style.SUCCESS(f'   - User: {user.email}'))
        self.stdout.write(self.style.SUCCESS(f'   - Teams: {len(teams)}'))
        self.stdout.write(self.style.SUCCESS(f'   - Tickets: {len(tickets)}'))
        self.stdout.write(self.style.SUCCESS(f'   - KB Articles: {len(kb_articles)}'))

    def create_user(self, email):
        """Create or get user"""
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': 'Billley',
                'last_name': 'Nyuy',
                'is_active': True,
                'is_staff': True,
                'is_superuser': True,
                'role': 'admin',
                'department': 'Engineering',
                'phone_number': '+237670123456',
            }
        )
        if created:
            user.set_password('admin123')  # Set a password
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created user: {email}'))
        else:
            self.stdout.write(self.style.WARNING(f'User already exists: {email}'))
        return user

    def create_profile(self, user):
        """Create user profile"""
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                'bio': 'Senior IT Support Engineer with expertise in network infrastructure, cloud services, and automation.',
                'location': 'Douala, Cameroon',
                'phone': '+237670123456',
                'title': 'Senior IT Support Engineer',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created user profile'))
        return profile

    def create_preferences(self, user):
        """Create user preferences"""
        prefs, created = UserPreferences.objects.get_or_create(
            user=user,
            defaults={
                'email_notifications': True,
                'push_notifications': True,
                'ticket_updates': True,
                'system_alerts': True,
                'daily_digest': True,
                'timezone': 'Africa/Douala',
                'language': 'en',
                'theme': 'light',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created user preferences'))
        return prefs

    def create_teams(self, user):
        """Create teams"""
        teams_data = [
            {
                'name': 'Infrastructure Team',
                'description': 'Manages servers, networks, and cloud infrastructure',
                'department': 'IT',
                'location': 'Douala Office'
            },
            {
                'name': 'Security Team',
                'description': 'Handles security incidents, audits, and compliance',
                'department': 'IT Security',
                'location': 'Douala Office'
            },
            {
                'name': 'Application Support',
                'description': 'Supports business applications and integrations',
                'department': 'IT',
                'location': 'Remote'
            },
            {
                'name': 'Help Desk',
                'description': 'First-line support for end users',
                'department': 'IT Support',
                'location': 'Douala Office'
            }
        ]
        
        teams = []
        for team_data in teams_data:
            team, created = Team.objects.get_or_create(
                name=team_data['name'],
                defaults={
                    'description': team_data['description'],
                    'department': team_data['department'],
                    'location': team_data['location'],
                    'lead': user,
                    'is_active': True
                }
            )
            if created:
                team.members.add(user)
                self.stdout.write(self.style.SUCCESS(f'Created team: {team.name}'))
            teams.append(team)
        
        return teams

    def create_kb_articles(self):
        """Create knowledge base articles"""
        articles_data = [
            {
                'title': 'VPN Connection Troubleshooting Guide',
                'content': '''# VPN Connection Issues

## Common Problems and Solutions

### Cannot Connect to VPN
1. Check your internet connection
2. Verify VPN credentials are correct
3. Ensure VPN client is up to date
4. Check if VPN service is running
5. Try connecting to a different VPN server

### Slow VPN Connection
- Switch to a closer VPN server
- Use wired connection instead of WiFi
- Check for bandwidth-heavy applications
- Update VPN client software

### VPN Keeps Disconnecting
1. Disable IPv6
2. Change VPN protocol (try OpenVPN or IKEv2)
3. Adjust MTU settings
4. Check firewall settings

For persistent issues, contact IT Support.''',
                'tags': ['vpn', 'networking', 'connectivity', 'troubleshooting']
            },
            {
                'title': 'Password Reset Procedure',
                'content': '''# Password Reset Guide

## Self-Service Password Reset

### Online Portal
1. Go to portal.company.com/reset
2. Enter your email address
3. Click "Send Reset Link"
4. Check your email for reset instructions
5. Click the link and create new password

### Password Requirements
- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character
- Cannot reuse last 5 passwords

### Unable to Reset Online?
Contact Help Desk at ext. 4567 or helpdesk@company.com''',
                'tags': ['password', 'security', 'authentication', 'account']
            },
            {
                'title': 'Email Configuration for Mobile Devices',
                'content': '''# Mobile Email Setup

## iOS Setup
1. Open Settings > Mail > Accounts
2. Tap "Add Account"
3. Select "Microsoft Exchange"
4. Enter your email and password
5. Server: mail.company.com
6. Domain: COMPANY
7. Save and sync

## Android Setup
1. Open Settings > Accounts
2. Add Account > Exchange
3. Email: yourname@company.com
4. Server: mail.company.com
5. Domain\\Username: COMPANY\\yourname
6. Enable SSL
7. Complete setup''',
                'tags': ['email', 'mobile', 'configuration', 'exchange']
            },
            {
                'title': 'Azure MFA Setup Guide',
                'content': '''# Multi-Factor Authentication Setup

## Download Microsoft Authenticator
- iOS: App Store
- Android: Google Play Store

## Enable MFA
1. Login to portal.office.com
2. Go to Security Info
3. Click "Add method"
4. Select "Authenticator app"
5. Scan QR code with your phone
6. Enter verification code
7. Save settings

## Backup Methods
- Add phone number for SMS
- Setup security questions
- Generate backup codes

Always keep backup methods updated!''',
                'tags': ['mfa', 'security', 'authentication', 'azure']
            },
            {
                'title': 'Printer Installation and Troubleshooting',
                'content': '''# Printer Setup Guide

## Installing Network Printer
1. Open Control Panel > Devices and Printers
2. Click "Add a printer"
3. Select network printer
4. Find printer by name or IP
5. Install drivers if prompted
6. Set as default if needed

## Common Issues

### Printer Offline
- Check network cable/WiFi connection
- Restart printer
- Remove and re-add printer
- Update printer drivers

### Print Job Stuck
1. Open print queue
2. Cancel all documents
3. Restart print spooler service
4. Try printing again

Need help? Call ext. 4567''',
                'tags': ['printer', 'hardware', 'troubleshooting', 'printing']
            },
            {
                'title': 'Microsoft Teams Best Practices',
                'content': '''# Microsoft Teams Usage Guide

## Starting a Meeting
1. Click Calendar tab
2. Select "New meeting"
3. Add participants
4. Set date and time
5. Send invitation

## Screen Sharing
- Click share screen button
- Select window or full screen
- Choose audio sharing if needed
- Click "Stop sharing" when done

## Tips for Effective Meetings
- Mute when not speaking
- Use video for important meetings
- Share agenda beforehand
- Record meetings for reference
- Use chat for questions

## Keyboard Shortcuts
- Ctrl+Shift+M: Toggle mute
- Ctrl+Shift+O: Toggle video
- Ctrl+Shift+E: Start screen share''',
                'tags': ['teams', 'collaboration', 'meetings', 'communication']
            }
        ]
        
        articles = []
        for article_data in articles_data:
            article, created = KnowledgeBaseArticle.objects.get_or_create(
                title=article_data['title'],
                defaults={
                    'content': article_data['content'],
                    'tags': article_data['tags'],
                    'views': random.randint(50, 500),
                    'helpful_votes': random.randint(20, 100),
                    'total_votes': random.randint(25, 110)
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created KB article: {article.title}'))
            articles.append(article)
        
        return articles

    def create_tickets(self, user, teams):
        """Create realistic tickets"""
        now = timezone.now()
        
        tickets_data = [
            {
                'issue_type': 'VPN connection keeps dropping',
                'description': 'My VPN connection drops every 10-15 minutes. I have tried reconnecting multiple times but the issue persists. This is affecting my ability to access company resources.',
                'category': 'vpn',
                'priority': 'high',
                'status': 'open',
                'tags': ['vpn', 'connectivity', 'network'],
                'created_days_ago': 2
            },
            {
                'issue_type': 'Cannot access shared drive',
                'description': 'I am getting "Access Denied" when trying to open files on the shared drive \\\\server\\projects. I need access to complete my work.',
                'category': 'access',
                'priority': 'high',
                'status': 'in_progress',
                'tags': ['permissions', 'shared-drive', 'access'],
                'created_days_ago': 1
            },
            {
                'issue_type': 'Laptop running very slow',
                'description': 'My laptop has become extremely slow over the past week. Applications take a long time to open and the system freezes frequently.',
                'category': 'laptop',
                'priority': 'medium',
                'status': 'open',
                'tags': ['performance', 'laptop', 'slow'],
                'created_days_ago': 3
            },
            {
                'issue_type': 'Email not syncing on mobile',
                'description': 'My work email stopped syncing on my iPhone. I can send but not receive new emails on my phone.',
                'category': 'email',
                'priority': 'medium',
                'status': 'pending',
                'tags': ['email', 'mobile', 'sync'],
                'created_days_ago': 1
            },
            {
                'issue_type': 'Password reset needed',
                'description': 'I forgot my password and the self-service reset is not working. I need help resetting my account password.',
                'category': 'account',
                'priority': 'high',
                'status': 'resolved',
                'tags': ['password', 'security', 'authentication'],
                'created_days_ago': 5
            },
            {
                'issue_type': 'Printer not responding',
                'description': 'The 3rd floor printer is not responding. Print jobs are stuck in the queue and nothing is printing.',
                'category': 'printer',
                'priority': 'medium',
                'status': 'resolved',
                'tags': ['printer', 'hardware', 'printing'],
                'created_days_ago': 7
            },
            {
                'issue_type': 'Software installation request - Adobe Creative Cloud',
                'description': 'I need Adobe Creative Cloud installed on my workstation for a new project. Please install Photoshop, Illustrator, and InDesign.',
                'category': 'software',
                'priority': 'low',
                'status': 'open',
                'tags': ['software', 'installation', 'adobe'],
                'created_days_ago': 1
            },
            {
                'issue_type': 'Teams meeting audio issues',
                'description': 'During Teams meetings, other participants cannot hear me even though my microphone is working. I can hear them fine.',
                'category': 'software',
                'priority': 'high',
                'status': 'in_progress',
                'tags': ['teams', 'audio', 'meetings'],
                'created_days_ago': 0
            },
            {
                'issue_type': 'Access to Azure DevOps needed',
                'description': 'I have joined the development team and need access to Azure DevOps for our project repositories.',
                'category': 'access',
                'priority': 'medium',
                'status': 'pending',
                'tags': ['azure', 'devops', 'access'],
                'created_days_ago': 2
            },
            {
                'issue_type': 'Laptop battery not charging',
                'description': 'My laptop battery shows "plugged in, not charging". The battery percentage stays at 60% and does not increase.',
                'category': 'hardware',
                'priority': 'medium',
                'status': 'open',
                'tags': ['laptop', 'battery', 'hardware'],
                'created_days_ago': 1
            }
        ]
        
        tickets = []
        for i, ticket_data in enumerate(tickets_data):
            created_at = now - timedelta(days=ticket_data['created_days_ago'])
            
            ticket, created = Ticket.objects.get_or_create(
                issue_type=ticket_data['issue_type'],
                user=user,
                defaults={
                    'description': ticket_data['description'],
                    'category': ticket_data['category'],
                    'status': ticket_data['status'],
                    'tags': ticket_data['tags'],
                    'created_at': created_at,
                    'updated_at': created_at + timedelta(hours=random.randint(1, 48)),
                    'assigned_to': user if ticket_data['status'] in ['in_progress', 'pending'] else None,
                    'agent_processed': ticket_data['status'] in ['resolved', 'in_progress'],
                    'agent_response': {
                        'confidence': random.uniform(0.7, 0.95),
                        'priority': ticket_data['priority'],
                        'category': ticket_data['category'],
                        'recommended_action': 'auto_resolve' if ticket_data['status'] == 'resolved' else 'assign_to_team'
                    } if ticket_data['status'] in ['resolved', 'in_progress'] else None
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created ticket: {ticket.issue_type}'))
            
            tickets.append(ticket)
        
        return tickets

    def create_ticket_interactions(self, tickets, user):
        """Create ticket interactions"""
        interaction_types = ['user_message', 'agent_response', 'status_change', 'assignment']
        
        for ticket in tickets:
            # Create 2-5 interactions per ticket
            num_interactions = random.randint(2, 5)
            
            for i in range(num_interactions):
                interaction_time = ticket.created_at + timedelta(hours=i * 2)
                
                interaction_type = random.choice(interaction_types)
                
                content_map = {
                    'user_message': f'Additional information: {random.choice(["I tried restarting but it did not help", "This issue is blocking my work", "Any update on this?", "Thank you for looking into this"])}',
                    'agent_response': f'Agent note: {random.choice(["Investigating the issue", "Applied fix, please test", "Escalated to level 2 support", "Issue resolved"])}',
                    'status_change': f'Status changed to {ticket.status}',
                    'assignment': f'Assigned to {user.first_name}'
                }
                
                TicketInteraction.objects.get_or_create(
                    ticket=ticket,
                    user=user,
                    interaction_type=interaction_type,
                    created_at=interaction_time,
                    defaults={
                        'content': content_map.get(interaction_type, 'Interaction logged')
                    }
                )

    def create_solutions(self, tickets, user, kb_articles):
        """Create solutions for resolved tickets"""
        resolved_tickets = [t for t in tickets if t.status == 'resolved']
        
        solutions_data = [
            {
                'steps': '''1. Reset the VPN client settings
2. Update VPN client to latest version
3. Configure split tunneling
4. Connect to alternate VPN server
5. Issue resolved - connection stable''',
                'worked': True,
                'confidence_score': 0.92,
                'kb_solution': 'Check VPN settings and update client software. Ensure proper network configuration.'
            },
            {
                'steps': '''1. Reset password using self-service portal
2. Verified password meets complexity requirements
3. Tested login on multiple devices
4. Password reset successful''',
                'worked': True,
                'confidence_score': 0.88,
                'kb_solution': 'Use self-service portal to reset password. Verify password meets all security requirements.'
            },
            {
                'steps': '''1. Restart print spooler service
2. Clear print queue
3. Update printer drivers
4. Test print - successful
5. Printer back online''',
                'worked': True,
                'confidence_score': 0.85,
                'kb_solution': 'Restart print spooler, clear queue, and update drivers. Test after each step.'
            }
        ]
        
        for i, ticket in enumerate(resolved_tickets[:len(solutions_data)]):
            solution_data = solutions_data[i]
            
            solution, created = Solution.objects.get_or_create(
                ticket=ticket,
                defaults={
                    'steps': solution_data['steps'],
                    'worked': solution_data['worked'],
                    'created_by': user,
                    'confidence_score': solution_data['confidence_score']
                }
            )
            
            if created:
                # Create KB Entry for this solution
                KnowledgeBaseEntry.objects.get_or_create(
                    ticket=ticket,
                    defaults={
                        'issue_type': ticket.issue_type,
                        'description': ticket.description[:200],
                        'solution': solution_data['kb_solution'],
                        'category': ticket.category,
                        'tags': ticket.tags,
                        'confidence_score': solution_data['confidence_score'],
                        'verified': True,
                        'verified_by': user,
                        'verification_date': timezone.now(),
                        'usage_count': random.randint(1, 10)
                    }
                )

    def create_llm_responses(self, tickets, kb_articles):
        """Create LLM responses for tickets"""
        for ticket in tickets[:5]:  # Create for first 5 tickets
            if kb_articles:
                related_articles = random.sample(kb_articles, min(2, len(kb_articles)))
            else:
                related_articles = []
            
            response, created = LLMResponse.objects.get_or_create(
                ticket=ticket,
                defaults={
                    'query': ticket.description[:100],
                    'response': f'Based on the issue description, I recommend checking the {ticket.category} settings and following the troubleshooting steps in the knowledge base.',
                    'response_type': 'TICKET',
                    'helpful_votes': random.randint(0, 10),
                    'total_votes': random.randint(5, 15)
                }
            )
            
            if created and related_articles:
                response.related_kb_articles.set(related_articles)
