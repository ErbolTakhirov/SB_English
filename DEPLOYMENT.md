# Deployment Guide - SB Finance AI

## 🚀 Free Deployment Options

### Option 1: Render.com (Recommended) ⭐

**Why Render?**
- ✅ Free tier with 750 hours/month
- ✅ Automatic HTTPS
- ✅ PostgreSQL database included
- ✅ Easy GitHub integration
- ✅ Auto-deploy on git push

#### Step-by-Step Guide:

### 1. Prepare Your Code

```bash
# Commit all changes
git add .
git commit -m "Prepare for deployment"
git push origin main
```

### 2. Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Authorize Render to access your repositories

### 3. Create PostgreSQL Database

1. Click "New +" → "PostgreSQL"
2. Name: `sb-finance-db`
3. Database: `sb_finance`
4. User: `sb_finance_user`
5. Region: Choose closest to you
6. Plan: **Free**
7. Click "Create Database"
8. **Copy the "Internal Database URL"** - you'll need this!

### 4. Create Web Service

1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - **Name**: `sb-finance-ai`
   - **Region**: Same as database
   - **Branch**: `main`
   - **Root Directory**: (leave empty)
   - **Runtime**: `Python 3`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn sb_finance.wsgi:application`
   - **Plan**: **Free**

### 5. Add Environment Variables

In the "Environment" section, add these variables:

```
DEBUG=False
DJANGO_SECRET_KEY=<generate-random-key>
DJANGO_ALLOWED_HOSTS=.onrender.com
DATABASE_URL=<paste-internal-database-url>
LLM_API_KEY=<your-openrouter-key>
LLM_MODEL=deepseek-chat-v3.1:free
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 6. Deploy!

1. Click "Create Web Service"
2. Wait 5-10 minutes for build
3. Your app will be live at: `https://sb-finance-ai.onrender.com`

---

## Option 2: Vercel (Easiest for Frontend Devs) 🎨

**Pros:**
- ✅ **Completely FREE** (Hobby plan)
- ✅ Instant deployment from GitHub
- ✅ Automatic HTTPS
- ✅ Global CDN
- ✅ Best for demos and MVPs

**Limitations:**
- ⚠️ Serverless functions (10 second timeout)
- ⚠️ Need external database (use Neon.tech free PostgreSQL)
- ⚠️ Best for read-heavy apps

### Quick Deploy to Vercel:

**1. Install Vercel CLI (optional):**
```bash
npm i -g vercel
```

**2. Deploy via Web:**
1. Go to [vercel.com](https://vercel.com)
2. "Import Project" → Select your GitHub repo
3. Vercel auto-detects Python
4. Add environment variables:
   ```
   DEBUG=False
   DJANGO_SECRET_KEY=<generate-key>
   DJANGO_ALLOWED_HOSTS=.vercel.app
   DATABASE_URL=<neon-postgres-url>
   LLM_API_KEY=<your-key>
   ```
5. Click "Deploy"
6. Live in ~2 minutes! 🚀

**3. Get Free PostgreSQL:**
- Go to [neon.tech](https://neon.tech) (Free tier: 0.5GB)
- Create database
- Copy connection string to `DATABASE_URL`

**OR via CLI:**
```bash
vercel --prod
```

---

## Option 3: Railway.app

**Pros:**
- $5 free credit monthly
- Very fast deployment
- Good for demos

**Steps:**
1. Go to [railway.app](https://railway.app)
2. "New Project" → "Deploy from GitHub"
3. Select your repo
4. Add PostgreSQL from "New" menu
5. Add environment variables (same as Render)
6. Deploy!

---

## Option 4: PythonAnywhere (Limited Free Tier)

**Pros:**
- Simple setup
- Good for small projects

**Cons:**
- Limited to 1 web app on free tier
- No PostgreSQL (MySQL only)

---

## 🔧 Troubleshooting

### Build Fails

**Error: `ModuleNotFoundError`**
```bash
# Make sure all dependencies are in requirements.txt
pip freeze > requirements.txt
```

**Error: `collectstatic failed`**
```bash
# Check STATIC_ROOT in settings.py
# Should be: STATIC_ROOT = BASE_DIR / 'staticfiles'
```

### Database Connection Issues

**Error: `could not connect to server`**
- Verify DATABASE_URL is correct
- Use "Internal Database URL" not "External"
- Check database is in same region as web service

### Static Files Not Loading

```python
# In settings.py, add:
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

---

## 📊 Post-Deployment Checklist

- [ ] Site loads correctly
- [ ] Can register new user
- [ ] Can login
- [ ] Can upload files
- [ ] AI chat works
- [ ] Dashboard displays data
- [ ] Static files (CSS/JS) load

---

## 🔒 Security Checklist for Production

- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` set
- [ ] `ALLOWED_HOSTS` configured
- [ ] HTTPS enabled (automatic on Render)
- [ ] Database backups enabled
- [ ] API keys in environment variables only

---

## 💰 Cost Breakdown

### Render Free Tier:
- Web Service: **Free** (750 hours/month)
- PostgreSQL: **Free** (90 days, then $7/month)
- Bandwidth: 100 GB/month free

### Upgrade When Needed:
- Web Service: $7/month (always on)
- PostgreSQL: $7/month (persistent)
- **Total**: ~$14/month for production

---

## 🎯 Quick Deploy Commands

```bash
# 1. Commit changes
git add .
git commit -m "Deploy to production"
git push

# 2. Render will auto-deploy!
# Check logs at: https://dashboard.render.com
```

---

## 📞 Support

If deployment fails:
1. Check Render logs
2. Verify all environment variables
3. Test locally first: `python manage.py runserver`
4. Check this guide again

**Good luck with your deployment! 🚀**
