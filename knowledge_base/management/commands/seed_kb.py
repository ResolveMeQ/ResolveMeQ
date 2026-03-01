"""
Seed comprehensive Knowledge Base articles.
Usage: python manage.py seed_kb [--clear]
"""

from django.core.management.base import BaseCommand
from knowledge_base.models import KnowledgeBaseArticle

KB_ARTICLES = [
    {
        "title": "How to Unlock a Locked User Account",
        "content": """## Overview

User accounts may lock after multiple failed login attempts due to security policies. This typically happens after 5-10 incorrect password entries.

## Immediate Steps

1. **Wait 15-30 minutes** - Many systems auto-unlock after a cooling-off period
2. **Verify Caps Lock is OFF** - Capitals matter in passwords
3. **Use Self-Service Password Reset** - Go to portal.company.com/reset
4. **Clear browser cache** - Old cached credentials can cause issues

## If Still Locked

- Contact IT Help Desk at ext. 4567 or helpdesk@company.com
- Provide your employee ID and department for verification
- IT will verify identity and unlock within 30 minutes during business hours

## Prevention

- Use a password manager to avoid incorrect entries
- Enable MFA to reduce lockout risk
- Do not share credentials""",
        "tags": ["account", "lockout", "login", "security", "user_access"],
    },
    {
        "title": "Multi-Factor Authentication (MFA) Setup Guide",
        "content": """## Overview

MFA adds a second verification step to protect your account. You'll need your phone and the Microsoft Authenticator app.

## Prerequisites

- Smartphone (iOS or Android)
- Access to security portal
- 5 minutes for setup

## Step-by-Step Setup

1. **Download Microsoft Authenticator** from App Store or Google Play
2. **Log into** portal.office.com
3. **Navigate** to Security Info (click your profile > Security Info)
4. **Click** "Add method" > Select "Authenticator app"
5. **Scan the QR code** with your phone's Authenticator app
6. **Enter the 6-digit code** shown on your phone to verify
7. **Save** - MFA is now active

## Backup Methods

Add a phone number for SMS backup and generate backup codes (Settings > Backup codes). Store backup codes in a secure location.

## Troubleshooting

- **Codes not working**: Ensure phone time is set to automatic
- **Lost phone**: Use backup codes or contact IT to reset MFA
- **App not syncing**: Reinstall Authenticator and re-register""",
        "tags": ["mfa", "security", "authentication", "account", "user_access"],
    },
    {
        "title": "VPN Connection Troubleshooting - Complete Guide",
        "content": """## Overview

VPN (Virtual Private Network) allows secure remote access to company resources. Connection issues are common and usually fixable.

## Quick Fixes (Try First)

1. **Check internet connection** - Ensure you have stable connectivity
2. **Restart VPN client** - Fully close and reopen
3. **Verify credentials** - Username format: firstname.lastname, ensure domain is correct
4. **Update VPN client** - Check for updates in the app store or company portal

## Cannot Connect at All

1. Ensure firewall allows VPN traffic (ports 443, 500, 4500)
2. Disable other VPN software that may conflict
3. Try different network (e.g., mobile hotspot) to isolate issue
4. Clear VPN client cache/settings and reconfigure

## VPN Keeps Disconnecting

1. **Disable IPv6** - Can cause tunnel instability
2. **Change protocol** - Try IKEv2 instead of SSTP or vice versa
3. **Adjust MTU** - Reduce to 1400 if experiencing drops
4. **Check power settings** - Disable "Allow computer to turn off this device" for network adapters

## Slow VPN Performance

- Connect to geographically closer VPN server
- Use wired connection instead of WiFi when possible
- Close bandwidth-heavy applications
- Verify no other users on home network streaming 4K

## Escalation

Contact IT if: Multiple connection attempts fail, error codes appear, or issue persists after 24 hours.""",
        "tags": ["vpn", "networking", "connectivity", "remote", "troubleshooting"],
    },
    {
        "title": "Wi-Fi Connection Issues on Windows Laptop",
        "content": """## Overview

Wi-Fi connectivity problems can stem from drivers, settings, or hardware. Follow these steps in order.

## Basic Troubleshooting

1. **Toggle Wi-Fi** - Turn off and on in network settings
2. **Restart router** - Unplug 30 seconds, plug back in
3. **Forget and reconnect** - Settings > Network > Wi-Fi > Manage known networks > Forget > Reconnect
4. **Run Network Troubleshooter** - Settings > Network & Internet > Status > Network troubleshooter

## Driver Issues

1. Open Device Manager
2. Expand "Network adapters"
3. Right-click Wi-Fi adapter > Update driver > Search automatically
4. If no update found, download latest from manufacturer (Dell, HP, Lenovo) support site

## Advanced Steps

- **Reset TCP/IP**: Open Command Prompt as Admin, run `netsh int ip reset`
- **Flush DNS**: Run `ipconfig /flushdns`
- **Check for conflicting software**: Antivirus or VPN may block connections

## When Other Devices Work

If only your laptop fails:
- Update Windows to latest version
- Check if adapter is disabled in Device Manager
- Run `netsh wlan show drivers` to verify adapter status

## Escalation

- No networks visible at all
- Adapter shows error in Device Manager
- Issue persists across different locations""",
        "tags": ["wifi", "network", "connectivity", "laptop", "windows"],
    },
    {
        "title": "Mapping Network Drives on Windows",
        "content": """## Overview

Network drives provide access to shared company folders. You need VPN connection when working remotely.

## Windows 10/11 Steps

1. **Open File Explorer** (Win + E)
2. **Click** "This PC" in left pane
3. **Click** "Map network drive" on the Computer tab
4. **Select drive letter** (e.g., Z:)
5. **Enter folder path**: \\\\servername\\sharename (e.g., \\\\fileserver\\projects)
6. **Check** "Reconnect at sign-in"
7. **Check** "Connect using different credentials" if required
8. **Click** Finish
9. **Enter** domain\\username and password when prompted

## Common Paths

- Documents: \\\\fileserver\\shared\\documents
- Projects: \\\\fileserver\\projects
- Department share: \\\\fileserver\\dept\\[department]

## Troubleshooting

**"Network path not found"**
- Verify VPN is connected
- Check path spelling (use backslashes \\\\)
- Confirm you have permissions

**"Access denied"**
- Request access from folder owner or IT
- Ensure you're using domain credentials

**Drive disconnects after reboot**
- Ensure "Reconnect at sign-in" was checked
- Verify VPN connects before accessing drive""",
        "tags": ["network_drive", "shared_folder", "windows", "mapping", "access"],
    },
    {
        "title": "Password Reset - Self-Service Procedure",
        "content": """## Overview

Reset your password without IT assistance using the self-service portal. Available 24/7.

## Requirements

- Access to registered backup email or phone
- Knowledge of current password (if changing) or access to reset link

## Steps

1. Go to **portal.company.com/reset**
2. Enter your **company email address**
3. Complete **CAPTCHA** verification
4. Choose verification method (email or SMS)
5. Enter the **code** received
6. Create **new password** meeting requirements:
   - Minimum 12 characters
   - Uppercase, lowercase, number, special character
   - Cannot reuse last 5 passwords
7. **Confirm** new password and submit

## Password Best Practices

- Use a passphrase: "Correct-Horse-Battery-Staple-42!"
- Enable password manager for work passwords
- Never share or write down passwords
- Change immediately if compromise suspected

## When Self-Service Fails

- **"Account not found"**: Ensure using company email
- **No verification code**: Check spam folder, wait 5 min, request new code
- **Locked out**: Wait 30 min or contact IT""",
        "tags": ["password", "reset", "security", "account", "self_service"],
    },
    {
        "title": "Software Installation Request Process",
        "content": """## Overview

All software installations require approval to ensure licensing compliance and security. Unauthorized software may be blocked by policy.

## How to Request

1. **Log into IT Portal** (portal.company.com)
2. **Create new ticket** - Category: Software Request
3. **Provide**:
   - Software name and version needed
   - Business justification (project, role requirement)
   - Manager email for approval
4. **Submit** - Ticket routes to manager for approval
5. **After approval** - IT installs within 2-3 business days

## Pre-Approved Software

These are available via Company Portal without ticket:
- Microsoft 365 apps
- Adobe Acrobat Reader
- Standard browsers (Chrome, Edge)
- VPN client
- Microsoft Teams

## Timeline

- Manager approval: 1-2 business days
- IT installation: 1-2 business days after approval
- Urgent requests: Mark as "High" priority with justification

## Denied Requests

If denied: Review feedback, provide additional justification, or explore alternative approved tools.""",
        "tags": ["software", "installation", "approval", "request", "policy"],
    },
    {
        "title": "Laptop Battery Not Charging - Troubleshooting",
        "content": """## Overview

"Plugged in, not charging" or rapid battery drain indicates a power delivery issue. Most cases are software-related.

## Quick Checks

1. **Try different outlet** - Rule out power source
2. **Inspect cable** - Look for fraying, bent connectors
3. **Reseat connection** - Unplug and replug firmly
4. **Restart laptop** - Clears power management glitches

## Calibrate Battery (Windows)

1. Charge to 100%
2. Unplug and use until it shuts down (~5%)
3. Let sit off for 2-3 hours
4. Charge to 100% without interruption

## Power Settings

1. Control Panel > Power Options
2. Change plan settings > Change advanced settings
3. Expand "Battery" - ensure no aggressive power-saving
4. Disable "Allow computer to turn off this device" for USB root hubs (Device Manager)

## Hardware Check

- **Battery health**: Run manufacturer diagnostic (Dell SupportAssist, HP PC Hardware Diagnostics)
- **Below 60% health**: Consider replacement - contact IT for warranty/battery order

## Escalation

- Battery swells or gets hot
- No charging with multiple adapters
- Battery health below 50%""",
        "tags": ["battery", "laptop", "charging", "hardware", "power"],
    },
    {
        "title": "Blue Screen of Death (BSOD) - Windows Troubleshooting",
        "content": """## Overview

A Blue Screen error (stop code) indicates a critical system failure. Note the error code displayed - it's essential for troubleshooting.

## Immediate Steps

1. **Restart** the computer
2. **Document the stop code** (e.g., MEMORY_MANAGEMENT, DRIVER_IRQL_NOT_LESS_OR_EQUAL)
3. **Note what you were doing** when it occurred

## Common Causes & Fixes

**MEMORY_MANAGEMENT / PAGE_FAULT**
- Run Windows Memory Diagnostic: mdsched.exe
- Reseat RAM if comfortable; otherwise escalate

**DRIVER_IRQL / DPC_WATCHDOG_VIOLATION**
- Update all drivers, especially graphics and network
- Use Device Manager > Update driver
- Uninstall recently added software

**SYSTEM_SERVICE_EXCEPTION**
- Run `sfc /scannow` in elevated Command Prompt
- Install Windows updates

## General Fixes

1. **Update Windows** - Settings > Update & Security
2. **Update drivers** - Manufacturer support site (Dell, HP, Lenovo)
3. **Check disk** - Run chkdsk /f (requires restart)
4. **Remove recent software** - Uninstall apps added before issue started

## Escalation

- BSOD occurs repeatedly (3+ times)
- Stop code: CRITICAL_PROCESS_DIED, KERNEL_DATA_INPAGE_ERROR
- Hardware failure suspected""",
        "tags": ["bsod", "blue_screen", "windows", "error", "troubleshooting"],
    },
    {
        "title": "Cannot Access Shared Folder - Permissions Guide",
        "content": """## Overview

Access denied to shared folders usually means permissions haven't been granted or VPN is required.

## Verification Steps

1. **VPN connected?** - Required when remote. Check system tray.
2. **Correct path?** - Use \\\\servername\\share (double backslashes)
3. **Reachability** - Can you ping the server? Open CMD: `ping fileserver`

## Requesting Access

1. **Identify folder owner** - Usually your manager or project lead
2. **Email request** - Include: folder path, reason, your username
3. **Owner grants access** - They add you via folder properties > Sharing
4. **Wait 15-30 minutes** - Permissions can take time to propagate

## Clearing Cached Credentials

If you had access and lost it:

1. Control Panel > Credential Manager
2. Windows Credentials
3. Remove entries for the file server
4. Reconnect to drive/folder - re-enter credentials

## UNC Path Format

Correct: \\\\fileserver\\department\\team
Incorrect: //fileserver/department/team (wrong slashes)
Incorrect: \\fileserver\department\team (single slash)""",
        "tags": ["shared_folder", "permissions", "access", "network", "denied"],
    },
    {
        "title": "Outlook Email Signature Configuration",
        "content": """## Overview

Professional email signatures include name, title, and contact info. Configure once and use for all emails.

## Outlook Desktop - Setup

1. **File** > Options > Mail
2. **Click** "Signatures..."
3. **New** - Name it (e.g., "Standard")
4. **Edit signature** - Add:
   - Your name
   - Title
   - Department
   - Phone (optional)
   - Company disclaimer if required
5. **Set default** - Choose for "New messages" and "Replies/forwards"
6. **OK** to save

## Formatting Tips

- Use company logo if approved (Insert > Picture)
- Keep under 4-5 lines for readability
- Use web-safe fonts (Arial, Calibri)
- Test send to yourself on mobile

## Outlook Web

1. Settings (gear) > View all Outlook settings
2. Mail > Compose and reply
3. Create signature under "Email signature"
4. Toggle "Automatically include my signature" ON""",
        "tags": ["email", "signature", "outlook", "configuration"],
    },
    {
        "title": "Low Disk Space - Free Up Storage on Windows",
        "content": """## Overview

Disk space below 10% free can cause slowdowns, failed updates, and application crashes. Act before it becomes critical.

## Quick Wins

1. **Empty Recycle Bin** - Right-click > Empty
2. **Disk Cleanup** - Search "Disk Cleanup" > Select C: > Clean up system files
3. **Temp files** - Delete contents of %temp% and C:\\Windows\\Temp

## Large File Cleanup

1. **Settings** > System > Storage
2. **Click C: drive** - See what's using space
3. **Temporary files** - Select all, Remove
4. **Downloads** - Move or delete old files
5. **Large files** - Use "Show more categories" to find big folders

## Move Data

- **Personal files** to OneDrive/SharePoint
- **Project files** to network drive
- **Old archives** to external storage

## Uninstall Unused Programs

1. Settings > Apps > Apps & features
2. Sort by size
3. Uninstall applications you don't use

## Escalation

- Need more than 50GB freed
- System drive under 5GB free
- Cannot identify what's using space""",
        "tags": ["disk_space", "storage", "performance", "cleanup", "windows"],
    },
    {
        "title": "Keyboard or Mouse Not Working - Troubleshooting",
        "content": """## Overview

Peripheral failures can be cable, port, driver, or hardware related. Systematic checks resolve most issues.

## Wired Devices

1. **Check cable** - Fully seated on both ends
2. **Try different USB port** - Prefer rear ports (direct to motherboard)
3. **Restart computer** - Clears USB controller issues
4. **Test on another PC** - Confirms if device or computer problem

## Wireless Devices

1. **Replace batteries** - Even "new" batteries can be depleted
2. **Re-pair receiver** - Unplug USB receiver, wait 10 sec, replug
3. **Check pairing button** - Some mice need re-sync
4. **USB 3.0 ports** - Can interfere with 2.4GHz; try USB 2.0 port

## Driver Update

1. Device Manager
2. Expand "Mice and other pointing devices" or "Keyboards"
3. Right-click device > Update driver
4. Search automatically

## When Device Not Detected

- Try different USB cable (for wired)
- Check if device appears in Device Manager with yellow warning
- BIOS: Ensure USB ports enabled
- Test in Safe Mode - if works, software conflict""",
        "tags": ["keyboard", "mouse", "peripheral", "hardware", "usb"],
    },
    {
        "title": "Joining Microsoft Teams Meetings - User Guide",
        "content": """## Overview

Teams meetings can be joined via link, calendar, or Teams app. Ensure audio/video work before joining important calls.

## Joining Options

**From email invite**: Click "Join Microsoft Teams Meeting" link

**From Teams calendar**: Open Teams > Calendar > Click meeting > Join

**From Outlook**: Open meeting > Click "Join Teams Meeting"

## Before You Join

1. **Test equipment** - Teams > Settings > Devices > Make test call
2. **Choose audio** - Select correct microphone/speakers
3. **Camera** - Preview your video
4. **Background** - Blur or custom if needed

## In-Meeting Controls

- **Mute**: Ctrl+Shift+M (or mic icon)
- **Video**: Ctrl+Shift+O (or camera icon)
- **Share screen**: Click share, select window or screen
- **Chat**: Right panel for questions
- **Leave**: Red phone icon

## Troubleshooting

**No audio**
- Check correct device selected (click ^ next to mute)
- Restart Teams
- Verify system sounds work elsewhere

**Others can't hear you**
- Unmute (red slash = muted)
- Check microphone not blocked
- Try headphones with built-in mic

**Can't share screen**
- Ensure presenter permissions
- Close sensitive applications first
- Try sharing specific window instead of entire screen""",
        "tags": ["teams", "meeting", "video_call", "collaboration", "microsoft"],
    },
    {
        "title": "Phishing Email - How to Recognize and Report",
        "content": """## Overview

Phishing emails attempt to steal credentials or install malware. Report suspicious emails immediately - do not click links or attachments.

## Red Flags

- **Urgent language** - "Act now or account suspended"
- **Unknown sender** - Especially if claiming to be from IT/bank
- **Suspicious links** - Hover to see real URL (different from display text)
- **Attachment request** - Unexpected invoice, document
- **Personal info request** - Passwords, SSN via email

## What to Do

1. **Do NOT click** any links or open attachments
2. **Do NOT reply** - Confirms your email is active
3. **Report** - Use "Report Phishing" button (Outlook) or forward to security@company.com
4. **Delete** the email after reporting

## Report Phishing (Outlook)

1. Select the suspicious email
2. Home tab > "Report message" > "Phishing"
3. Or: Report to security team per company procedure

## If You Clicked a Link

1. **Do not enter credentials** if redirected to login page
2. **Change password** immediately (from known-good device)
3. **Enable MFA** if not already
4. **Report** to IT Security - include full email headers

## Legitimate vs Phishing

- Real IT never asks for password via email
- Hover over links before clicking
- Check sender address carefully (support@company.com vs support@company-security.com)""",
        "tags": ["phishing", "security", "email", "cybersecurity", "report"],
    },
    {
        "title": "Monitor Shows No Signal - Display Troubleshooting",
        "content": """## Overview

"No signal" or blank screen usually means connection or input source issue, not necessarily monitor failure.

## Check Connections

1. **Power** - Monitor power light on? (not in sleep)
2. **Video cable** - HDMI/DisplayPort fully seated on both ends
3. **Correct port** - Ensure plugged into GPU, not motherboard (if using dedicated graphics)

## Input Source

1. Use monitor's **physical buttons** to open menu
2. Select **correct input** (HDMI 1, HDMI 2, DisplayPort, etc.)
3. Some monitors auto-detect - try cycling inputs

## Computer Side

1. **Restart** computer - Clears display driver issues
2. **Reseat cable** at computer end
3. **Try different cable** - Cable faults are common
4. **Try different port** on graphics card

## Laptop Docking/External

- Undock and use laptop screen - if that works, dock/cable issue
- Press Win+P to cycle display mode (PC screen only, Extend, etc.)

## Escalation

- No signal with known-good cable and different computer
- Monitor shows artifacts/colored lines
- Power light flashes (error code - check manual)""",
        "tags": ["monitor", "display", "no_signal", "hardware", "hdmi"],
    },
    {
        "title": "Windows Update - Installation and Troubleshooting",
        "content": """## Overview

Keeping Windows updated is critical for security. Updates are typically automatic; manual check may be needed for urgent patches.

## Manual Update Check

1. **Settings** (Win + I) > Update & Security > Windows Update
2. **Check for updates**
3. **Download and install** if available
4. **Restart** when prompted (save work first)

## Best Practices

- **Plug in power** during updates - prevents interruption
- **Don't force shutdown** during "Installing updates"
- **Schedule** outside work hours if possible (Settings > Schedule the restart)

## Update Stuck/Failed

1. **Restart** and check again
2. **Run troubleshooter**: Settings > Update & Security > Troubleshoot > Windows Update
3. **Clear update cache**: Services > Stop Windows Update > Delete C:\\Windows\\SoftwareDistribution\\Download contents > Start Windows Update
4. **Manual install**: Download from Microsoft Update Catalog for specific KB number

## Defer Updates (if allowed)

Some orgs allow deferral: Settings > Update & Security > Advanced options. Don't defer security updates long-term.

## Escalation

- Updates repeatedly fail with error code
- Update causes boot loop
- Need specific update blocked (business critical app)""",
        "tags": ["windows", "update", "patch", "maintenance", "security"],
    },
    {
        "title": "Printer Offline - How to Get Back Online",
        "content": """## Overview

Printers often show "offline" due to connection or spooler issues. Rarely a hardware failure.

## Quick Fixes

1. **Power cycle** - Turn off printer, wait 30 seconds, turn on
2. **Check connections** - USB cable or network cable secure
3. **Ping printer** - From CMD: `ping printerip` (for network printers)
4. **Set as default** - Settings > Devices > Printers > Right-click > Set as default

## Restart Print Spooler

1. Services (Win + R, type services.msc)
2. Find "Print Spooler"
3. Right-click > Restart

## Clear Print Queue

1. Settings > Devices > Printers & scanners
2. Click printer > Open queue
3. Printer > Cancel all documents
4. Restart Print Spooler (above)

## Network Printer Specific

- Verify on same network/VLAN
- Re-add printer: Remove device, then Add printer > The printer I want isn't listed > Add by TCP/IP

## Driver Reinstall

1. Remove printer from Devices
2. Download latest driver from manufacturer
3. Install driver, then add printer

## Escalation

- Printer not found on network
- Hardware error lights on printer
- Multiple users affected (server/queue issue)""",
        "tags": ["printer", "offline", "printing", "troubleshooting", "hardware"],
    },
    {
        "title": "Outlook Not Syncing - Email Sync Issues",
        "content": """## Overview

Emails not appearing can be sync, cache, or account configuration issues. Affects Outlook desktop and mobile.

## Outlook Desktop

1. **Check status** - Bottom right: "All folders are up to date" or sync error?
2. **Send/Receive** - Send/Receive tab > Send/Receive All
3. **Restart Outlook** - Fully quit and reopen
4. **Repair account** - File > Account Settings > Select account > Repair

## Cache Issues

1. File > Options > Advanced
2. Under "Send and receive" > Uncheck "Download shared folders"
3. Or: Clear cache - Close Outlook, delete .ost file in %localappdata%\\Microsoft\\Outlook (will re-download)

## Outlook Mobile

1. **Check sync settings** - Account settings > Mail sync
2. **Manual sync** - Pull down to refresh
3. **Re-add account** - Remove and add back
4. **App update** - Ensure Outlook app is current

## Common Causes

- **Large mailbox** - Archive old emails
- **Offline mode** - File > Work Offline (uncheck)
- **Server issues** - Check status.office.com

## Escalation

- Sync fails consistently
- Error messages (e.g., 0x8004010F)
- Only some folders not syncing""",
        "tags": ["outlook", "email", "sync", "microsoft", "troubleshooting"],
    },
    {
        "title": "Requesting New Software Licenses",
        "content": """## Overview

Additional licenses for existing software (Adobe, specialized tools) require manager approval and IT provisioning.

## Process

1. **Verify need** - Confirm software is approved for your role
2. **Check availability** - Some licenses are pooled; IT can assign
3. **Submit ticket** - IT Portal > Software Request
   - Specify: Software name, version, business justification
   - Attach manager approval email
4. **Timeline** - 3-5 business days for license assignment

## License Types

- **Pooled** - Shared, assigned on demand (faster)
- **Named** - Dedicated to you (for specialized tools)
- **Concurrent** - Limited seats, first-come when launching

## If Denied

- License budget exhausted - Wait for next cycle
- Software not approved - Request exception with VP approval
- Alternative exists - IT may suggest approved alternative""",
        "tags": ["license", "software", "request", "approval"],
    },
    {
        "title": "Laptop Running Slow - Performance Optimization",
        "content": """## Overview

Slow performance is usually high CPU/memory usage, disk full, or too many startup programs.

## Quick Checks

1. **Task Manager** (Ctrl+Shift+Esc) - What's using CPU/RAM?
2. **Restart** - Clears memory leaks
3. **Close unused apps** - Especially browser tabs

## Startup Programs

1. Task Manager > Startup tab
2. Disable unnecessary programs (high "Startup impact")
3. Restart to apply

## Disk & Memory

- **Free disk space** - Need 15%+ free on C: drive
- **RAM** - 8GB minimum for Windows 10/11; 16GB recommended for multitasking

## Browser

- Clear cache and cookies
- Disable unused extensions
- Consider fewer tabs (each uses memory)

## Malware Scan

- Run Windows Defender full scan
- Ensure no unauthorized software

## Escalation

- Consistently slow after optimization
- Specific application slow (may need upgrade)
- Hardware upgrade needed (RAM, SSD)""",
        "tags": ["performance", "slow", "laptop", "optimization", "windows"],
    },
    {
        "title": "Accessing Company Resources from Home",
        "content": """## Overview

Working remotely requires VPN and sometimes additional setup for full access to systems and files.

## Requirements

1. **VPN client** - Install from Company Portal or IT
2. **MFA** - Must be enrolled for secure access
3. **Stable internet** - 10+ Mbps recommended

## Connection Order

1. Connect to home Wi-Fi
2. Launch VPN client and connect
3. Open applications (Outlook, Teams, file shares)
4. Access internal sites (intranet, apps)

## Common Resources

- **Email**: Outlook - works without VPN for basic sync
- **Teams**: Works without VPN
- **File shares**: VPN required
- **Internal apps**: VPN required
- **Remote Desktop**: VPN + RDP client

## Troubleshooting

- **Can't reach internal sites**: Verify VPN connected (check system tray icon)
- **Slow file access**: Normal over VPN; use sync/offline if available
- **VPN won't connect**: See VPN troubleshooting guide""",
        "tags": ["remote", "vpn", "work_from_home", "access", "connectivity"],
    },
    {
        "title": "Forgotten Password - Account Recovery",
        "content": """## Overview

If you've forgotten your password, use self-service reset. Account recovery is available 24/7.

## Self-Service Reset

1. Go to **passwordreset.company.com** (or portal login > "Forgot password")
2. Enter **work email**
3. Complete **identity verification** (phone/email code, security questions)
4. Create **new password** (meet complexity requirements)
5. **Sign in** with new password

## Verification Methods

Ensure you've registered:
- **Mobile number** - SMS codes
- **Alternate email** - Backup codes
- **Authenticator app** - If MFA is required for reset

## If Verification Fails

- **Wrong phone/email**: Contact IT with employee ID - they'll verify identity and reset
- **MFA locked**: IT can reset MFA after verification
- **Account compromised**: Report to IT Security immediately

## After Reset

- Update password in password manager
- Re-authenticate on mobile devices (Outlook, Teams)
- Consider enabling MFA if not already""",
        "tags": ["password", "forgot", "recovery", "account", "reset"],
    },
    {
        "title": "New Employee - IT Onboarding Checklist",
        "content": """## Overview

New hires receive equipment and accounts. This checklist ensures nothing is missed.

## Before Day 1

- [ ] Equipment ordered (laptop, monitor, accessories)
- [ ] Accounts created (email, AD, applications)
- [ ] VPN access provisioned
- [ ] MFA enrollment invite sent

## Day 1 - Equipment Setup

- [ ] Laptop unboxed and charged
- [ ] First login (temporary password - change required)
- [ ] Connect to Wi-Fi
- [ ] Install VPN, connect
- [ ] Enroll in MFA
- [ ] Join Teams, verify calendar

## Accounts & Access

- [ ] Email accessible
- [ ] Network drives mapped
- [ ] Required software installed
- [ ] Shared mailboxes/distribution lists added

## Training

- [ ] Password policy and MFA
- [ ] Phishing awareness
- [ ] How to submit IT tickets
- [ ] Escalation contacts

## New Hire Tickets

Submit ticket for: Software not in standard image, special permissions, hardware requests.""",
        "tags": ["onboarding", "new_employee", "checklist", "setup"],
    },
    {
        "title": "Employee Offboarding - IT Checklist",
        "content": """## Overview

When employees leave, IT must secure accounts and equipment promptly.

## Before Last Day

- [ ] Disable account (or set date in HR system)
- [ ] Forward email to manager (30 days)
- [ ] Identify knowledge transfer needs

## Last Day

- [ ] Collect laptop, phone, accessories
- [ ] Collect badges, keys
- [ ] Disable all accounts (email, VPN, apps)
- [ ] Remove from distribution lists
- [ ] Revoke MFA
- [ ] Disable VPN access

## Access Revocation

- Email (convert to shared if needed)
- Network drives
- Cloud apps (Teams, SharePoint, etc.)
- VPN
- Building access

## Equipment

- Wipe device (if company-owned) before disposal/reissue
- Document serial numbers returned

## Manager Responsibility

- Ensure work files transferred
- Delegate ongoing responsibilities
- Update org chart/contact lists""",
        "tags": ["offboarding", "termination", "checklist", "accounts"],
    },
    {
        "title": "Reporting a Lost or Stolen Laptop",
        "content": """## Overview

Lost or stolen company devices must be reported immediately. Quick action protects company data.

## Immediate Steps (Within 1 Hour)

1. **Report to IT** - helpdesk@company.com or ext. 4567, mark URGENT
2. **Report to manager** - Notify your supervisor
3. **If stolen** - File police report, get report number
4. **Change passwords** - From a different device, change work password and any personal passwords used on the device

## What IT Will Do

- **Remote wipe** - Erase device data (if enabled)
- **Disable account** - Prevent access
- **Revoke VPN** - Block remote access
- **Monitor** - Watch for suspicious login attempts

## What You Should Do

- Don't attempt to recover device yourself
- Provide: Device serial number, last known location, police report if applicable
- Check with lost & found (building, transport) if misplaced

## Prevention

- Never leave laptop unattended in public
- Use cable lock in office
- Enable Find My Device / BitLocker (if company policy)

## Replacement

IT will issue replacement per company policy. May require manager approval and police report for theft.""",
        "tags": ["lost", "stolen", "laptop", "security", "report"],
    },
    {
        "title": "Webcam or Microphone Not Working in Teams",
        "content": """## Overview

Teams needs permission to access camera and microphone. Blocked access or wrong device selection causes issues.

## Permissions Check

1. **Windows Settings** > Privacy > Camera - Ensure "Allow apps to access your camera" ON
2. **Windows Settings** > Privacy > Microphone - Same for microphone
3. **Teams** - Settings > Devices - Verify correct camera and microphone selected

## Device Selection in Teams

1. Join meeting (or before)
2. Click ^ next to mute/camera buttons
3. Select **camera** - Preview available
4. Select **microphone** - Test with meter
5. Select **speaker** - Play test tone

## Hardware Checks

- **Camera**: Is there a physical shutter? Ensure it's open
- **Laptop**: Built-in cam disabled in BIOS? Check Fn key for camera toggle
- **External**: Try different USB port; ensure driver installed

## One Device Works, Other Doesn't

- Update driver for non-working device
- Check if another app is exclusive (close Zoom, Skype)
- Restart Teams
- Restart computer

## Escalation

- No devices appear in Teams
- Device works in other apps but not Teams
- Driver install fails""",
        "tags": ["webcam", "microphone", "teams", "video_call", "audio"],
    },
    {
        "title": "Duplicate or Missing Calendar Events in Outlook",
        "content": """## Overview

Calendar sync issues cause duplicates, missing events, or wrong times. Usually fixable with cache/sync repair.

## Duplicate Events

1. **Delete duplicates** manually (if few)
2. **Check shared calendars** - Ensure not subscribed multiple times
3. **Cache rebuild** - Close Outlook, rename Calendar folder in %localappdata%\\Microsoft\\Outlook, reopen (re-syncs)

## Missing Events

1. **View settings** - Ensure calendar view isn't filtered (View > View Settings > Filter)
2. **Date range** - Scroll to correct month
3. **Send/Receive** - Force sync
4. **Recreate** - If one-time event, re-add; check with organizer

## Wrong Time Zone

1. Outlook > File > Options > Calendar
2. Time zone settings - Verify correct zone
3. "Show a second time zone" if coordinating across zones

## Shared Calendar Issues

- Re-share if you lost access
- Remove and re-add shared calendar
- Check organizer hasn't removed your access""",
        "tags": ["calendar", "outlook", "duplicate", "sync", "events"],
    },
    {
        "title": "Cannot Send Email - Outlook Sending Blocked",
        "content": """## Overview

Emails stuck in Outbox or "message could not be sent" usually indicate connection, size, or policy issues.

## Connection

1. **Check internet** - Can you browse?
2. **Work Offline** - File > Work Offline (should be unchecked)
3. **Send/Receive** - Manual send/receive

## Large Attachments

- **Limit** - Typically 25-35MB total
- **Solution** - Use OneDrive/SharePoint link instead of attaching
- **Compress** - Zip files to reduce size

## Recipient Issues

- **Invalid address** - Check spelling, ensure no spaces
- **Full mailbox** - Recipient's mailbox may be full
- **Blocked** - Company policy may block external to that domain

## Authentication

- Re-enter password if prompted
- Repair account: File > Account Settings > Repair

## Safety Tips

- Verify recipient - especially for sensitive data
- Check "To" field before send
- Use Recall (limited) if sent to wrong person - act quickly""",
        "tags": ["email", "outlook", "send", "blocked", "troubleshooting"],
    },
]


class Command(BaseCommand):
    help = "Seed comprehensive Knowledge Base articles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing KB articles before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count = KnowledgeBaseArticle.objects.count()
            KnowledgeBaseArticle.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {count} existing KB articles"))

        created = 0
        for article_data in KB_ARTICLES:
            _, was_created = KnowledgeBaseArticle.objects.get_or_create(
                title=article_data["title"],
                defaults={
                    "content": article_data["content"],
                    "tags": article_data["tags"],
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {article_data['title']}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Done. Created {created} new articles."))
        self.stdout.write(self.style.SUCCESS(f"Total KB articles: {KnowledgeBaseArticle.objects.count()}"))
