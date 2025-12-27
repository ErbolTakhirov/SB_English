# Security Guidelines for SB Finance AI

## 🔐 Critical Security Rules

### 1. API Key Management

**NEVER commit API keys to Git!**

#### ✅ Correct Way:
```bash
# In .env file (ignored by git)
LLM_API_KEY=sk-or-v1-your-actual-key-here
GOOGLE_API_KEY=your-google-key-here
```

#### ❌ Wrong Way:
```python
# NEVER do this in Python files!
LLM_API_KEY = "sk-or-v1-actual-key"  # ❌ WRONG!
```

### 2. Environment File Protection

The `.env` file contains all sensitive information and is protected by `.gitignore`:

```
.env          # ✅ Protected - contains real secrets
env.example   # ✅ Safe - template with no real values
```

### 3. Setup Process

1. **Copy the example file:**
   ```bash
   cp env.example .env
   ```

2. **Edit `.env` with your real keys:**
   ```bash
   # Open .env and replace placeholder values
   LLM_API_KEY=your-real-key-here
   ```

3. **Verify protection:**
   ```bash
   git status
   # .env should NOT appear in the list
   ```

### 4. If You Accidentally Commit a Secret

1. **Immediately rotate the API key** at the provider's website
2. **Remove from Git history:**
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **Force push** (if already pushed to remote)
4. **Add new key** to `.env` file

### 5. GitHub Secret Scanning

GitHub automatically scans for exposed secrets. If detected:
- You'll receive an alert
- The key should be considered compromised
- Rotate immediately

### 6. Code Review Checklist

Before committing, verify:
- [ ] No hardcoded API keys in `.py` files
- [ ] All secrets use `os.getenv()` or `settings.X`
- [ ] `.env` is in `.gitignore`
- [ ] Only `env.example` is committed (with placeholders)

### 7. Supported Patterns in .gitignore

Our `.gitignore` blocks:
- `.env` and all `.env.*` files
- Files with `secret`, `SECRET`, `apikey`, `APIKEY` in name
- Common secret file formats (`.json`, `.yaml`, `.txt`)

## 🛡️ Additional Security Measures

### Data Privacy
- User financial data is never sent to external APIs without anonymization
- PII (Personally Identifiable Information) is masked before AI processing
- Local LLM option available for complete data sovereignty

### Database Security
- Use strong passwords for database credentials
- Store `DATABASE_URL` in `.env`, never in code
- Enable SSL for production database connections

### Production Deployment
- Set `DEBUG=False` in production
- Use strong `SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- Enable HTTPS/SSL certificates
- Implement rate limiting for API endpoints

## 📞 Reporting Security Issues

If you discover a security vulnerability:
1. **DO NOT** create a public GitHub issue
2. Email the maintainers directly
3. Include detailed steps to reproduce
4. Allow time for patching before disclosure
