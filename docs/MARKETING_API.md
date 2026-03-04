# Marketing Site API Documentation

This document describes the public API endpoints for the ResolveMeQ marketing site. These endpoints are used to collect newsletter subscriptions and demo/contact requests.

## Table of Contents

- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
- [CORS Configuration](#cors-configuration)
- [Endpoints](#endpoints)
  - [1. Newsletter Subscribe](#1-newsletter-subscribe)
  - [2. Contact/Demo Request](#2-contactdemo-request)
- [Error Handling](#error-handling)
- [Admin Panel](#admin-panel)

---

## Overview

The marketing API provides two public endpoints:

1. **Newsletter Subscribe** - Collects email addresses for newsletter subscriptions
2. **Contact Request** - Collects demo requests with email and company size

Both endpoints:
- Are **publicly accessible** (no authentication required)
- Accept **POST** requests with **JSON** payloads
- Return **JSON** responses
- Capture client IP addresses for analytics
- Are protected against CORS issues

---

## Base URL

### Production
```
https://api.resolvemeq.net
```

### Development
```
http://localhost:8000
```

---

## Authentication

**None required** - These endpoints are public and designed for anonymous visitors to the marketing site.

---

## CORS Configuration

The backend is configured to allow requests from your marketing site origin. CORS headers include:

- **Allowed Origins**: Your marketing site domain (e.g., `https://resolvemeq.net`)
- **Allowed Methods**: `POST`, `OPTIONS`
- **Allowed Headers**: `Content-Type`, `Accept`
- **Credentials**: Supported

---

## Endpoints

### 1. Newsletter Subscribe

Collects email addresses for newsletter subscriptions from the marketing site footer.

#### Request

**Endpoint**
```
POST /api/subscribe
```

**Headers**
```
Content-Type: application/json
```

**Body**
```json
{
  "email": "user@example.com"
}
```

| Field | Type   | Required | Description                    |
|-------|--------|----------|--------------------------------|
| email | string | Yes      | Valid email address (max 254 chars) |

#### Response

**Success (201 Created)**
```json
{
  "ok": true,
  "message": "Subscribed successfully"
}
```

**Error (400 Bad Request)**

Already subscribed:
```json
{
  "ok": false,
  "error": "Already subscribed"
}
```

Invalid email:
```json
{
  "ok": false,
  "error": "Enter a valid email address."
}
```

Missing email:
```json
{
  "ok": false,
  "error": "This field is required."
}
```

#### Behavior

- Email addresses are normalized to lowercase and trimmed of whitespace
- Duplicate subscriptions return a 400 error with "Already subscribed" message
- If a user previously unsubscribed, resubscribing will reactivate their subscription
- Client IP address is captured for analytics (not exposed in response)

#### Example Request

```bash
curl -X POST https://api.resolvemeq.net/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

#### Frontend Integration

```javascript
async function subscribeNewsletter(email) {
  try {
    const response = await fetch('https://api.resolvemeq.net/api/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email }),
    });

    const data = await response.json();

    if (response.ok) {
      // Show success message
      console.log(data.message); // "Subscribed successfully"
      return { success: true, message: data.message };
    } else {
      // Show error message
      console.error(data.error);
      return { success: false, error: data.error };
    }
  } catch (error) {
    // Network error
    console.error('Network error:', error);
    return { success: false, error: 'Network error. Please try again.' };
  }
}
```

---

### 2. Contact/Demo Request

Collects demo requests with email and company size from the marketing site CTA section.

#### Request

**Endpoint**
```
POST /api/contact
```

**Headers**
```
Content-Type: application/json
```

**Body**
```json
{
  "email": "user@company.com",
  "company_size": "51-200"
}
```

| Field         | Type   | Required | Description                                      |
|---------------|--------|----------|--------------------------------------------------|
| email         | string | Yes      | Valid email address (max 254 chars)              |
| company_size  | string | Yes      | One of: `"1-50"`, `"51-200"`, `"201-500"`, `"501+"` |

#### Response

**Success (201 Created)**
```json
{
  "ok": true,
  "message": "Request received"
}
```

**Error (400 Bad Request)**

Invalid email:
```json
{
  "ok": false,
  "error": "Enter a valid email address."
}
```

Invalid company size:
```json
{
  "ok": false,
  "error": "Invalid company size. Must be one of: 1-50, 51-200, 201-500, 501+"
}
```

Missing required field:
```json
{
  "ok": false,
  "error": "This field is required."
}
```

#### Behavior

- Email addresses are normalized to lowercase and trimmed of whitespace
- Company size must exactly match one of the allowed values (case-sensitive)
- Client IP address is captured for analytics (not exposed in response)
- Multiple requests from the same email are allowed (each creates a new record)
- Requests are marked as "not contacted" by default for follow-up tracking

#### Valid Company Size Values

| Value     | Description        |
|-----------|--------------------|
| `"1-50"`  | 1-50 employees     |
| `"51-200"` | 51-200 employees  |
| `"201-500"` | 201-500 employees |
| `"501+"`  | 501+ employees     |

#### Example Request

```bash
curl -X POST https://api.resolvemeq.net/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@company.com",
    "company_size": "51-200"
  }'
```

#### Frontend Integration

```javascript
async function submitContactRequest(email, companySize) {
  try {
    const response = await fetch('https://api.resolvemeq.net/api/contact', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email,
        company_size: companySize,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      // Show success message and optionally redirect
      console.log(data.message); // "Request received"
      return { success: true, message: data.message };
    } else {
      // Show error message
      console.error(data.error);
      return { success: false, error: data.error };
    }
  } catch (error) {
    // Network error
    console.error('Network error:', error);
    return { success: false, error: 'Network error. Please try again.' };
  }
}
```

---

## Error Handling

All endpoints follow a consistent error response format:

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 OK      | Success (some endpoints) |
| 201 Created | Resource created successfully |
| 400 Bad Request | Invalid input data |
| 500 Internal Server Error | Server error |

### Error Response Format

```json
{
  "ok": false,
  "error": "Error message here"
}
```

### Frontend Error Handling Strategy

1. **2xx responses** → Show success message
2. **4xx responses** → Show specific error from `error` field
3. **5xx responses** → Show generic "Server error" message
4. **Network errors** → Show "Please check your connection" message

---

## Admin Panel

Both newsletter subscriptions and contact requests can be managed through the Django admin panel.

### Admin URL

```
https://api.resolvemeq.net/admin/
```

### Newsletter Subscriptions

**Admin Path:** `/admin/base/newslettersubscription/`

**Available Fields:**
- Email address
- Active status (can be toggled to unsubscribe)
- Subscription date
- IP address (read-only)

**Features:**
- Search by email
- Filter by active status and subscription date
- Bulk actions support

### Contact Requests

**Admin Path:** `/admin/base/contactrequest/`

**Available Fields:**
- Email address
- Company size
- Contacted status (checkbox for follow-up tracking)
- Request date
- IP address (read-only)
- Notes (for internal use)

**Features:**
- Search by email and notes
- Filter by company size, contacted status, and request date
- Add internal notes for follow-up
- Mark as contacted after reaching out

---

## Testing

### Test Newsletter Subscribe

```bash
# Success case
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Already subscribed (run twice)
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Invalid email
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "invalid-email"}'

# Missing email
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Test Contact Request

```bash
# Success case
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@company.com",
    "company_size": "51-200"
  }'

# Invalid company size
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@company.com",
    "company_size": "invalid"
  }'

# Missing fields
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@company.com"}'
```

---

## Database Models

### NewsletterSubscription

| Field          | Type      | Description |
|----------------|-----------|-------------|
| id             | UUID      | Primary key |
| email          | Email     | Email address (unique) |
| subscribed_at  | DateTime  | Subscription timestamp |
| is_active      | Boolean   | Active status |
| ip_address     | IP        | Client IP address |

### ContactRequest

| Field          | Type      | Description |
|----------------|-----------|-------------|
| id             | UUID      | Primary key |
| email          | Email     | Email address |
| company_size   | String    | Company size category |
| requested_at   | DateTime  | Request timestamp |
| is_contacted   | Boolean   | Follow-up status |
| ip_address     | IP        | Client IP address |
| notes          | Text      | Internal notes |

---

## Rate Limiting

**Note:** No rate limiting is currently implemented on these endpoints. Consider implementing rate limiting in production to prevent abuse:

- Per IP address: 10 requests per minute
- Per email: 1 request per hour

---

## Additional Features

### Future Enhancements

1. **Email Verification**
   - Send confirmation email for newsletter subscriptions
   - Implement double opt-in for GDPR compliance

2. **Automated Follow-up**
   - Trigger email notifications when contact requests are received
   - Auto-assign to sales team members

3. **Analytics**
   - Track conversion rates
   - Geographic distribution of requests
   - Integration with analytics platforms

4. **Export Functionality**
   - Export subscriber lists to CSV
   - Integration with email marketing platforms (Mailchimp, SendGrid, etc.)

---

## Support

For technical support or questions about the API, contact:
- **Email:** support@resolvemeq.net
- **Documentation:** https://docs.resolvemeq.net

---

## Changelog

### Version 1.0.0 (2026-03-04)

- Initial release
- Newsletter subscription endpoint
- Contact/demo request endpoint
- Admin panel integration
- CORS configuration
