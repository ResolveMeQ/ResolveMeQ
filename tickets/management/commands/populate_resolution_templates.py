"""
Management command to populate sample resolution templates.
Usage: python manage.py populate_resolution_templates
"""
from django.core.management.base import BaseCommand
from tickets.models import ResolutionTemplate


class Command(BaseCommand):
    help = 'Populate the database with sample resolution templates'

    def handle(self, *args, **options):
        templates = [
            {
                'name': 'Email Sync Issues - Outlook',
                'description': 'Standard resolution for Outlook email synchronization problems',
                'category': 'email',
                'issue_types': ['sync', 'connection'],
                'tags': ['outlook', 'email', 'sync', 'exchange'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Verify Internet Connection',
                        'description': 'Check if the user has stable internet connectivity',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Check Outlook Account Settings',
                        'description': 'Go to File > Account Settings > Account Settings and verify the email account is active',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 3,
                        'title': 'Send/Receive All Folders',
                        'description': 'Click Send/Receive > Send/Receive All Folders (F9)',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 4,
                        'title': 'Restart Outlook',
                        'description': 'Close Outlook completely and restart the application',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 5,
                        'title': 'Clear Offline Items',
                        'description': 'If issue persists, clear offline items and re-sync',
                        'estimated_minutes': 5
                    }
                ],
                'estimated_time': 15,
                'is_ai_generated': False
            },
            {
                'name': 'Printer Offline - Network Printer',
                'description': 'Steps to resolve network printer showing as offline',
                'category': 'printer',
                'issue_types': ['offline', 'connection'],
                'tags': ['printer', 'network', 'offline', 'connectivity'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check Physical Connections',
                        'description': 'Verify printer is powered on and connected to network',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Ping Printer IP Address',
                        'description': 'Open CMD and ping the printer IP to verify network connectivity',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 3,
                        'title': 'Restart Print Spooler',
                        'description': 'Open Services, find Print Spooler, and restart the service',
                        'estimated_minutes': 4
                    },
                    {
                        'step_number': 4,
                        'title': 'Remove and Re-add Printer',
                        'description': 'Remove printer from Devices and Printers, then add it back',
                        'estimated_minutes': 6
                    },
                    {
                        'step_number': 5,
                        'title': 'Update Printer Driver',
                        'description': 'Download and install latest driver from manufacturer website',
                        'estimated_minutes': 10
                    }
                ],
                'estimated_time': 25,
                'is_ai_generated': False
            },
            {
                'name': 'VPN Connection Failed',
                'description': 'Troubleshooting VPN connection failures',
                'category': 'network',
                'issue_types': ['vpn', 'connection', 'authentication'],
                'tags': ['vpn', 'remote access', 'authentication', 'network'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Verify Credentials',
                        'description': 'Ensure username and password are correct and account is not locked',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Check Network Connection',
                        'description': 'Verify stable internet connection before attempting VPN',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 3,
                        'title': 'Restart VPN Client',
                        'description': 'Close VPN client completely and restart application',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 4,
                        'title': 'Clear VPN Cache',
                        'description': 'Clear cached credentials and connection history',
                        'estimated_minutes': 4
                    },
                    {
                        'step_number': 5,
                        'title': 'Reinstall VPN Client',
                        'description': 'If issue persists, uninstall and reinstall VPN client software',
                        'estimated_minutes': 10
                    }
                ],
                'estimated_time': 21,
                'is_ai_generated': False
            },
            {
                'name': 'Slow Computer Performance',
                'description': 'General troubleshooting for slow computer performance',
                'category': 'hardware',
                'issue_types': ['performance', 'slow'],
                'tags': ['performance', 'slow', 'cpu', 'memory', 'disk'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check Task Manager',
                        'description': 'Open Task Manager and identify resource-intensive processes',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 2,
                        'title': 'Check Available Disk Space',
                        'description': 'Verify at least 15% free space on system drive',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 3,
                        'title': 'Run Disk Cleanup',
                        'description': 'Use built-in Disk Cleanup tool to remove temporary files',
                        'estimated_minutes': 10
                    },
                    {
                        'step_number': 4,
                        'title': 'Disable Startup Programs',
                        'description': 'Disable unnecessary programs from starting with Windows',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 5,
                        'title': 'Update System and Drivers',
                        'description': 'Install Windows updates and update device drivers',
                        'estimated_minutes': 15
                    },
                    {
                        'step_number': 6,
                        'title': 'Run Antivirus Scan',
                        'description': 'Perform full system scan for malware',
                        'estimated_minutes': 30
                    }
                ],
                'estimated_time': 65,
                'is_ai_generated': False
            },
            {
                'name': 'Password Reset - Active Directory',
                'description': 'Standard procedure for resetting Active Directory passwords',
                'category': 'account',
                'issue_types': ['password', 'locked account'],
                'tags': ['password', 'active directory', 'account', 'reset'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Verify User Identity',
                        'description': 'Confirm user identity through security questions or employee ID',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 2,
                        'title': 'Check Account Status',
                        'description': 'Open Active Directory Users and Computers and check if account is locked',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 3,
                        'title': 'Unlock Account if Needed',
                        'description': 'If locked, unlock the account before resetting password',
                        'estimated_minutes': 1
                    },
                    {
                        'step_number': 4,
                        'title': 'Reset Password',
                        'description': 'Right-click user account and select Reset Password',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 5,
                        'title': 'Set Temporary Password',
                        'description': 'Set temporary password and check "User must change password at next logon"',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 6,
                        'title': 'Communicate New Password',
                        'description': 'Securely communicate temporary password to user',
                        'estimated_minutes': 2
                    }
                ],
                'estimated_time': 12,
                'is_ai_generated': False
            },
            {
                'name': 'Application Crash - General',
                'description': 'General troubleshooting for application crashes',
                'category': 'software',
                'issue_types': ['crash', 'error'],
                'tags': ['application', 'crash', 'error', 'software'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check Error Logs',
                        'description': 'Review Event Viewer for application error details',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 2,
                        'title': 'Restart Application',
                        'description': 'Close application completely and restart',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 3,
                        'title': 'Run as Administrator',
                        'description': 'Try running application with administrator privileges',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 4,
                        'title': 'Check for Updates',
                        'description': 'Verify application is up to date and install any available updates',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 5,
                        'title': 'Repair Installation',
                        'description': 'Use application repair function or reinstall if necessary',
                        'estimated_minutes': 10
                    }
                ],
                'estimated_time': 24,
                'is_ai_generated': False
            },
            {
                'name': 'Shared Drive Access Issues',
                'description': 'Resolving access issues with network shared drives',
                'category': 'storage',
                'issue_types': ['access denied', 'permission'],
                'tags': ['network drive', 'permissions', 'access', 'storage'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Verify Network Connection',
                        'description': 'Ensure user is connected to corporate network',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Check Drive Mapping',
                        'description': 'Verify shared drive is properly mapped in File Explorer',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 3,
                        'title': 'Test Drive Path',
                        'description': 'Try accessing drive using UNC path (\\\\server\\share)',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 4,
                        'title': 'Check Permissions',
                        'description': 'Verify user has appropriate permissions in Active Directory',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 5,
                        'title': 'Remap Network Drive',
                        'description': 'Disconnect and reconnect the network drive',
                        'estimated_minutes': 4
                    }
                ],
                'estimated_time': 16,
                'is_ai_generated': False
            },
            {
                'name': 'WiFi Connection Drops',
                'description': 'Troubleshooting intermittent WiFi disconnections',
                'category': 'network',
                'issue_types': ['wifi', 'disconnection'],
                'tags': ['wifi', 'wireless', 'connection', 'network'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check WiFi Signal Strength',
                        'description': 'Verify signal strength is adequate (3+ bars)',
                        'estimated_minutes': 1
                    },
                    {
                        'step_number': 2,
                        'title': 'Forget and Reconnect',
                        'description': 'Forget the WiFi network and reconnect with credentials',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 3,
                        'title': 'Update WiFi Drivers',
                        'description': 'Update wireless network adapter drivers',
                        'estimated_minutes': 8
                    },
                    {
                        'step_number': 4,
                        'title': 'Disable Power Saving',
                        'description': 'Disable power saving mode for wireless adapter',
                        'estimated_minutes': 4
                    },
                    {
                        'step_number': 5,
                        'title': 'Reset Network Settings',
                        'description': 'Reset TCP/IP stack and Winsock catalog',
                        'estimated_minutes': 6
                    }
                ],
                'estimated_time': 22,
                'is_ai_generated': False
            },
            {
                'name': 'Microsoft Teams Audio Issues',
                'description': 'Resolving audio problems in Microsoft Teams',
                'category': 'software',
                'issue_types': ['audio', 'microphone', 'speakers'],
                'tags': ['teams', 'audio', 'microphone', 'communication'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check Device Settings',
                        'description': 'Verify correct audio devices selected in Teams settings',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Test Call',
                        'description': 'Make a test call in Teams to diagnose issue',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 3,
                        'title': 'Check System Audio',
                        'description': 'Verify audio devices working in Windows Sound settings',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 4,
                        'title': 'Update Audio Drivers',
                        'description': 'Update audio device drivers from manufacturer',
                        'estimated_minutes': 7
                    },
                    {
                        'step_number': 5,
                        'title': 'Clear Teams Cache',
                        'description': 'Clear Teams cache and restart application',
                        'estimated_minutes': 5
                    }
                ],
                'estimated_time': 20,
                'is_ai_generated': False
            },
            {
                'name': 'Blue Screen of Death (BSOD)',
                'description': 'Initial troubleshooting for Windows BSOD errors',
                'category': 'hardware',
                'issue_types': ['crash', 'bsod', 'system failure'],
                'tags': ['bsod', 'crash', 'system', 'hardware'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Document Error Code',
                        'description': 'Record the STOP code and error message from BSOD',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Check Recent Changes',
                        'description': 'Identify any recent hardware or software changes',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 3,
                        'title': 'Boot into Safe Mode',
                        'description': 'Restart computer in Safe Mode to diagnose startup issues',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 4,
                        'title': 'Run Memory Diagnostic',
                        'description': 'Use Windows Memory Diagnostic tool to check RAM',
                        'estimated_minutes': 15
                    },
                    {
                        'step_number': 5,
                        'title': 'Update Drivers',
                        'description': 'Update all device drivers, especially graphics and chipset',
                        'estimated_minutes': 15
                    },
                    {
                        'step_number': 6,
                        'title': 'Escalate if Persistent',
                        'description': 'If BSOD continues, escalate to hardware team',
                        'estimated_minutes': 2
                    }
                ],
                'estimated_time': 44,
                'is_ai_generated': False
            },
            {
                'name': 'Software Installation Failure',
                'description': 'Troubleshooting failed software installations',
                'category': 'software',
                'issue_types': ['installation', 'error'],
                'tags': ['installation', 'software', 'error', 'deployment'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check System Requirements',
                        'description': 'Verify system meets minimum requirements for software',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 2,
                        'title': 'Run as Administrator',
                        'description': 'Run installer with administrator privileges',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 3,
                        'title': 'Disable Antivirus Temporarily',
                        'description': 'Temporarily disable antivirus during installation',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 4,
                        'title': 'Check Installation Logs',
                        'description': 'Review installation logs for specific error messages',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 5,
                        'title': 'Clean Previous Installation',
                        'description': 'Remove any partial installation files and registry entries',
                        'estimated_minutes': 8
                    },
                    {
                        'step_number': 6,
                        'title': 'Retry Installation',
                        'description': 'Attempt installation again with fresh installer',
                        'estimated_minutes': 10
                    }
                ],
                'estimated_time': 31,
                'is_ai_generated': False
            },
            {
                'name': 'External Monitor Not Detected',
                'description': 'Resolving external monitor detection issues',
                'category': 'hardware',
                'issue_types': ['display', 'monitor'],
                'tags': ['monitor', 'display', 'hardware', 'external'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check Physical Connections',
                        'description': 'Verify cable is securely connected to both monitor and computer',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Try Different Cable/Port',
                        'description': 'Test with different cable or video port if available',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 3,
                        'title': 'Force Detection',
                        'description': 'Use Windows+P and select "Detect" or "Extend"',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 4,
                        'title': 'Update Graphics Drivers',
                        'description': 'Install latest graphics drivers from manufacturer',
                        'estimated_minutes': 10
                    },
                    {
                        'step_number': 5,
                        'title': 'Restart Computer',
                        'description': 'Restart with monitor connected',
                        'estimated_minutes': 3
                    }
                ],
                'estimated_time': 20,
                'is_ai_generated': False
            },
            {
                'name': 'Browser Extremely Slow',
                'description': 'Optimizing slow web browser performance',
                'category': 'software',
                'issue_types': ['performance', 'browser'],
                'tags': ['browser', 'performance', 'chrome', 'edge', 'firefox'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Clear Browser Cache',
                        'description': 'Clear browsing data, cache, and cookies',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 2,
                        'title': 'Disable Extensions',
                        'description': 'Disable browser extensions and test performance',
                        'estimated_minutes': 4
                    },
                    {
                        'step_number': 3,
                        'title': 'Update Browser',
                        'description': 'Ensure browser is updated to latest version',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 4,
                        'title': 'Check for Malware',
                        'description': 'Run malware scan to check for browser hijackers',
                        'estimated_minutes': 15
                    },
                    {
                        'step_number': 5,
                        'title': 'Reset Browser Settings',
                        'description': 'Reset browser to default settings if issue persists',
                        'estimated_minutes': 5
                    }
                ],
                'estimated_time': 32,
                'is_ai_generated': False
            },
            {
                'name': 'File Accidentally Deleted',
                'description': 'Steps to recover accidentally deleted files',
                'category': 'storage',
                'issue_types': ['data recovery', 'deletion'],
                'tags': ['recovery', 'deleted files', 'backup', 'storage'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check Recycle Bin',
                        'description': 'Check if file is in Recycle Bin and restore',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Check Shadow Copies',
                        'description': 'Right-click folder and check Previous Versions',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 3,
                        'title': 'Check Network Backup',
                        'description': 'Verify if file exists in network backup location',
                        'estimated_minutes': 5
                    },
                    {
                        'step_number': 4,
                        'title': 'Check Cloud Sync',
                        'description': 'If using OneDrive/SharePoint, check online recycle bin',
                        'estimated_minutes': 4
                    },
                    {
                        'step_number': 5,
                        'title': 'Submit Backup Restore Request',
                        'description': 'If not found, submit formal backup restore request',
                        'estimated_minutes': 5
                    }
                ],
                'estimated_time': 19,
                'is_ai_generated': False
            },
            {
                'name': 'Mobile Device Not Syncing Email',
                'description': 'Troubleshooting mobile device email synchronization',
                'category': 'email',
                'issue_types': ['sync', 'mobile'],
                'tags': ['mobile', 'email', 'sync', 'exchange', 'ios', 'android'],
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Check Network Connection',
                        'description': 'Verify device has active cellular or WiFi connection',
                        'estimated_minutes': 2
                    },
                    {
                        'step_number': 2,
                        'title': 'Force Email Refresh',
                        'description': 'Pull down to refresh inbox manually',
                        'estimated_minutes': 1
                    },
                    {
                        'step_number': 3,
                        'title': 'Check Sync Settings',
                        'description': 'Verify sync is enabled and sync period is appropriate',
                        'estimated_minutes': 3
                    },
                    {
                        'step_number': 4,
                        'title': 'Remove and Re-add Account',
                        'description': 'Remove email account from device and add it back',
                        'estimated_minutes': 6
                    },
                    {
                        'step_number': 5,
                        'title': 'Update Mail App',
                        'description': 'Check for and install any available app updates',
                        'estimated_minutes': 4
                    }
                ],
                'estimated_time': 16,
                'is_ai_generated': False
            }
        ]

        created_count = 0
        updated_count = 0

        for template_data in templates:
            # Check if template already exists
            existing = ResolutionTemplate.objects.filter(name=template_data['name']).first()
            
            if existing:
                # Update existing template
                for key, value in template_data.items():
                    setattr(existing, key, value)
                existing.save()
                updated_count += 1
                self.stdout.write(f"  Updated: {template_data['name']}")
            else:
                # Create new template
                ResolutionTemplate.objects.create(**template_data)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {template_data['name']}"))

        self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully populated {created_count} new templates"))
        if updated_count > 0:
            self.stdout.write(self.style.WARNING(f"✓ Updated {updated_count} existing templates"))
        
        total = ResolutionTemplate.objects.count()
        self.stdout.write(self.style.SUCCESS(f"✓ Total templates in database: {total}"))
