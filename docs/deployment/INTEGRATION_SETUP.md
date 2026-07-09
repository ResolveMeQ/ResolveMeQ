# ResolveMeQ - Full Stack Integration Setup

## 🚀 Quick Start Guide

### Backend (Django API)

1. **Ensure you're in the project root:**
   ```bash
   cd /home/nyuydine/Documents/ResolveMeq/ResolveMeQ
   ```

2. **Activate virtual environment (if not already active):**
   ```bash
   source venv/bin/activate
   ```

3. **Install dependencies (already done):**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations (already done):**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser (for testing):**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start Django development server:**
   ```bash
   python manage.py runserver
   ```
   - API will be available at: `http://localhost:8000`
   - Swagger docs at: `http://localhost:8000/`

### Frontend (React App)

1. **Navigate to the web app directory:**
   ```bash
   cd resolvemeqwebapp
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```
   - App will be available at: `http://localhost:5173`

## ✅ What's Been Configured

### Backend Changes:
- ✅ CORS enabled for React frontend (localhost:5173)
- ✅ JWT authentication configured
- ✅ 23+ API endpoints ready to use
- ✅ PostgreSQL database connected (Render)
- ✅ Settings updated for development

### Frontend Changes:
- ✅ API service layer created (`src/services/api.js`)
- ✅ JWT token management implemented
- ✅ Login/Signup integrated with real API
- ✅ Tickets page connected to backend
- ✅ Environment variables configured
- ✅ Auto token refresh on 401 errors

## 📝 Test the Integration

### 1. First Time Setup - Create a Test User

**Option A: Via Django Admin**
```bash
# From Django project root
python manage.py createsuperuser
# Follow prompts to create admin user
```

**Option B: Via API (Signup)**
- Go to `http://localhost:5173`
- Click "Sign up"
- Fill in the form
- Check console for verification email (development mode)

### 2. Login
- Go to `http://localhost:5173`
- Enter your credentials
- You should be redirected to the dashboard

### 3. Test Tickets
- Click on "Tickets" in the sidebar
- The page should load real tickets from your database
- If no tickets exist, you'll see an empty state or mock data

## 🔧 Troubleshooting

### CORS Errors
If you see CORS errors in browser console:
1. Make sure Django server is running on `http://localhost:8000`
2. Check that `corsheaders` is installed: `pip list | grep django-cors`
3. Verify CORS settings in `resolvemeq/settings.py`

### 401 Unauthorized
- Check that JWT tokens are being set in localStorage
- Open browser DevTools > Application > Local Storage
- Should see `access_token` and `refresh_token`

### Connection Refused
- Ensure both servers are running:
  - Django: `http://localhost:8000`
  - React: `http://localhost:5173`

### API Endpoints Not Found
- Check Django URL patterns: `python manage.py show_urls` (if installed)
- Verify endpoint paths match in `src/services/api.js`

## 🌐 API Endpoints Used

### Authentication
- `POST /api/auth/login/` - User login
- `POST /api/auth/register/` - User registration
- `GET /api/auth/profile/` - Get current user
- `POST /api/auth/api/token/refresh/` - Refresh JWT token

### Tickets
- `GET /api/tickets/list/` - List all tickets
- `GET /api/tickets/{id}/` - Get ticket details
- `POST /api/tickets/` - Create new ticket
- `PATCH /api/tickets/{id}/update/` - Update ticket
- `GET /api/tickets/analytics/` - Ticket analytics

## 📚 Next Steps

1. **Create some test tickets** via Django admin or API
2. **Test AI agent integration** (if external service is running)
3. **Implement additional features:**
   - Real-time updates (WebSockets)
   - File upload functionality
   - Knowledge base integration
   - Slack/Discord integration

## 🎯 Development Workflow

### Making Changes

**Backend (Django):**
1. Make changes to models/views/serializers
2. Create migrations: `python manage.py makemigrations`
3. Run migrations: `python manage.py migrate`
4. Server auto-reloads on file save

**Frontend (React):**
1. Make changes to components/pages
2. Vite auto-reloads on file save
3. Check browser console for errors

### Environment Variables

**Backend (.env):**
- Located at: `/home/nyuydine/Documents/ResolveMeq/ResolveMeQ/.env`
- Contains: DB credentials, Redis, Slack, Email settings

**Frontend (.env):**
- Located at: `/home/nyuydine/Documents/ResolveMeq/ResolveMeQ/resolvemeqwebapp/.env`
- Contains: `VITE_API_URL=http://localhost:8000`

## 🔐 Security Notes

- Never commit `.env` files (both are gitignored)
- Change `SECRET_KEY` before production
- Set `DEBUG=False` in production
- Update `ALLOWED_HOSTS` for production domains
- Use HTTPS in production

## 📞 Support

For issues or questions:
- Check console errors in browser DevTools
- Check Django server logs in terminal
- Review API documentation at `http://localhost:8000/`
