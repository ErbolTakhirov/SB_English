# 🚀 SB FINANCE AI - Full AI Accountant Implementation

## 📋 Overview

SB Finance AI has been transformed from a basic income/expense tracker into a **full AI accountant for individuals**, with a focus on **automation** for teenagers and young adults (18-25 years). Users can now send almost any raw financial data, and the system automatically understands, categorizes, and summarizes it.

---

## ✨ New Features Implemented

### 1. 📥 **Automatic Import & Data Parsing**

#### **Flexible Import Options:**
- **Plain Text Import**: Paste transactions in natural language
  - Example: `"01.12 Магнит 450р, 02.12 Яндекс.Такси 320р"`
  - Supports multiple date formats (DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY)
  - Recognizes multiple currencies (RUB, KGS, USD, EUR, KZT)
  - Handles noisy input with automatic cleanup

- **CSV/Excel Import**: Enhanced with AI column mapping
  - Auto-detects column structure
  - Handles missing columns with intelligent defaults
  - Duplicate detection and handling

- **Manual Entry**: Quick single-transaction input

#### **Smart Parsing:**
- Extracts: date, amount, merchant, description, currency
- Handles unclear rows by marking as "needs review"
- No data is dropped - everything is preserved

**API Endpoint:**
```
POST /api/import/text/
{
  "text": "01.12 Магнит 450р\n02.12 Такси 320р",
  "auto_categorize": true
}
```

---

### 2. 🤖 **AI-Powered Categorization**

#### **Intelligent Category Assignment:**
- Uses LLM (via OpenRouter/DeepSeek) for smart categorization
- Falls back to rule-based heuristics when no API key is provided
- **Categories:**
  - **Income**: allowance, salary, freelance, gift, part-time, sales, bonus
  - **Expense**: food, transport, entertainment, shopping, subscriptions, education, health, beauty, games, rent, etc.

#### **Learning System:**
- Remembers user corrections
- Builds merchant-to-category mapping
- Improves accuracy over time

#### **Review UI:**
- Quick scan of newly categorized transactions
- One-click category fixes
- Confidence scores displayed

**API Endpoints:**
```
GET /api/review/queue/          # Get transactions needing review
POST /api/category/update/      # Update category
{
  "transaction_id": 123,
  "transaction_type": "expense",
  "category": "food"
}
```

---

### 3. 📊 **Automatic Summaries & Analytics**

#### **Monthly Summaries:**
- Total income and expenses by month
- Breakdown by category (30/90/365 days)
- Top merchants analysis
- "Money leaks" identification (highest spending categories)

#### **Visual Summaries:**
- Bar charts for category breakdown
- Pie charts for spending distribution
- Trend lines for income/expense over time

#### **Smart Defaults:**
- Dashboard shows last 30 days by default
- Auto-computed totals
- No manual filters required

**API Endpoint:**
```
GET /api/forecast/
Returns:
{
  "historical": {
    "avg_monthly_income": 50000,
    "avg_monthly_expense": 35000,
    "avg_monthly_net": 15000,
    "income_stability": 0.85,
    "expense_stability": 0.72
  },
  "next_month": {
    "predicted_income": 52000,
    "predicted_expense": 36000,
    "predicted_net": 16000,
    "confidence": 0.78
  },
  "money_leaks": [
    {"category": "food", "amount": 12000, "percentage": 34.3}
  ]
}
```

---

### 4. 🎯 **Goals Module**

#### **Full Goal Management:**
- **Fields**: name, target amount, deadline, category, priority, status
- **Auto-computed Progress**:
  - Progress percentage
  - Remaining amount
  - Days left
  - Required monthly saving

#### **Goal-Transaction Integration:**
- Goals automatically linked to categorized transactions
- Real-time progress updates
- Ahead/behind schedule indicators

#### **AI-Powered Recommendations:**
- Personalized advice for each goal
- Probability of achievement
- Suggested weekly/monthly savings

**API Endpoints:**
```
GET /api/goals/<goal_id>/prediction/
Returns:
{
  "probability": 0.85,
  "on_track": true,
  "required_monthly_saving": 5000,
  "current_monthly_saving": 6000,
  "recommendation": "Отлично! Вы на правильном пути..."
}

POST /api/goals/auto-update/    # Auto-update all goals based on transactions
```

---

### 5. 📈 **Forecasting & AI Advisor**

#### **Historical Analysis:**
- Analyzes 3-12 months of transaction history
- Calculates income/expense stability
- Identifies spending patterns

#### **Forecasting Service:**
- **Expected monthly net income**
- **Likely spending per category**
- **Goal achievement probability** (heuristic-based)

#### **AI Advisor:**
- Generates human-readable advice in friendly language
- Focuses on concrete actions:
  - Where to cut spending
  - How to optimize budget
  - How much to set aside for each goal
- Personalized for young adults (18-25)

#### **"Close Month" / "AI Insights" Page:**
- One-click "Analyze my month" button
- Fresh aggregation and AI analysis
- Actionable recommendations

**API Endpoint:**
```
GET /api/advice/monthly/
Returns:
{
  "summary": "💰 Хорошие новости! В среднем вы откладываете 15000 сом в месяц.",
  "advice": "...",
  "action_items": [
    "Сократите траты на food - это 34% ваших расходов",
    "Откладывайте 12000 сом ежемесячно на цели"
  ],
  "highlights": {
    "monthly_net": 15000,
    "top_leak": {"category": "food", "amount": 12000},
    "goals_count": 3
  },
  "confidence": 0.78
}
```

---

## 🏗️ **Architecture**

### **Service Layer** (Clean Business Logic)

All business logic has been extracted into dedicated services:

```
core/services/
├── __init__.py
├── text_parser.py          # Plain text transaction parsing
├── categorization.py       # AI categorization with learning
├── import_service.py       # Unified import handling
├── forecasting.py          # Historical analysis & predictions
└── ai_advisor.py           # Personalized financial advice
```

### **Key Design Principles:**
1. **Separation of Concerns**: Business logic in services, not views
2. **Testability**: Each service is independently testable
3. **Fallback Logic**: Rule-based fallbacks when AI is unavailable
4. **Learning System**: User corrections improve future predictions

---

## 🎨 **UI/UX Flow**

### **Main User Journey:**

```
1. Import Data
   ↓
2. Auto-Parse & Categorize (AI)
   ↓
3. Review & Fix (if needed)
   ↓
4. Dashboard (Auto-computed summaries)
   ↓
5. Goals (Auto-updated progress)
   ↓
6. AI Insights (Monthly advice)
```

### **Pages:**

1. **Dashboard** (`/dashboard/`)
   - Monthly summaries
   - Category breakdowns
   - Visual charts

2. **Import** (`/import/`)
   - Text area for plain text
   - File upload for CSV/Excel
   - Manual entry form

3. **Review** (`/review/`)
   - List of transactions needing review
   - Quick category fixes
   - Confidence scores

4. **Goals** (`/goals/`)
   - Active goals with progress bars
   - Add new goal form
   - Achievement predictions

5. **AI Insights** (`/insights/`)
   - "Analyze My Month" button
   - Monthly advice
   - Action items
   - Spending patterns

6. **Transactions** (`/income/`, `/expense/`)
   - Full transaction lists
   - Edit/delete capabilities
   - Export to CSV

---

## 🔧 **Setup & Configuration**

### **1. Install Dependencies**

```bash
pip install -r requirements.txt
```

### **2. Configure Environment Variables**

Create `.env` file:

```env
# Django Settings
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# AI Settings (OpenRouter recommended)
LLM_API_KEY=sk-or-v1-your-key-here
LLM_API_URL=https://openrouter.ai/api/v1/chat/completions
LLM_MODEL=deepseek-chat-v3.1:free
LLM_MAX_TOKENS=3000

# Optional: HTTP Referer for OpenRouter
LLM_HTTP_REFERER=http://localhost:8000
LLM_APP_TITLE=SB Finance AI
```

### **3. Run Migrations**

```bash
python manage.py migrate
```

### **4. Create Superuser**

```bash
python manage.py createsuperuser
```

### **5. Run Server**

```bash
python manage.py runserver
```

---

## 🧪 **Testing**

### **Manual Testing Flow:**

1. **Test Text Import:**
   ```
   Navigate to /import/
   Paste: "01.12.2024 Магнит 450р
           02.12.2024 Яндекс.Такси 320р
           03.12.2024 Зарплата 50000с"
   Click "Import"
   ```

2. **Test Review Queue:**
   ```
   Navigate to /review/
   Check categorized transactions
   Fix any incorrect categories
   ```

3. **Test Dashboard:**
   ```
   Navigate to /dashboard/
   Verify monthly summaries
   Check category breakdowns
   ```

4. **Test Goals:**
   ```
   Navigate to /goals/
   Create new goal: "iPhone 15" - 100000 KGS - 6 months
   Check auto-computed progress
   ```

5. **Test AI Insights:**
   ```
   Navigate to /insights/
   Click "Analyze My Month"
   Review AI advice and action items
   ```

### **API Testing (Postman/cURL):**

```bash
# Import text
curl -X POST http://localhost:8000/api/import/text/ \
  -H "Content-Type: application/json" \
  -d '{"text": "01.12 Магнит 450р", "auto_categorize": true}'

# Get forecast
curl http://localhost:8000/api/forecast/

# Get monthly advice
curl http://localhost:8000/api/advice/monthly/
```

---

## 📚 **API Documentation**

### **Import & Categorization**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/import/text/` | POST | Import from plain text |
| `/api/upload/` | POST | Import from CSV/Excel |
| `/api/review/queue/` | GET | Get transactions needing review |
| `/api/category/update/` | POST | Update transaction category |

### **Analytics & Forecasting**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/forecast/` | GET | Get financial forecast |
| `/api/spending/analysis/` | GET | Get spending patterns |
| `/api/dashboard/data/` | GET | Get dashboard data |

### **Goals & Advice**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/goals/<id>/prediction/` | GET | Get goal achievement prediction |
| `/api/goals/auto-update/` | POST | Auto-update all goals |
| `/api/advice/monthly/` | GET | Get monthly AI advice |

---

## 🎯 **Target User**

**Teenagers / Young Adults (18-25 years)**

### **User Persona:**
- **Name**: Айдар, 22 года
- **Occupation**: Студент + фриланс
- **Income**: Нерегулярный (карманные деньги + подработка)
- **Pain Points**:
  - Не знает, куда уходят деньги
  - Сложно копить на цели
  - Нет времени вести учет вручную

### **How SB Finance AI Helps:**
1. **Quick Import**: Просто скопировал SMS от банка → вставил → готово
2. **Auto-Categorization**: Система сама поняла, что "Магнит" = еда
3. **Smart Insights**: "Ты тратишь 40% на еду, попробуй готовить дома"
4. **Goal Tracking**: "До iPhone осталось 3 месяца, откладывай 15000/месяц"

---

## 🚀 **Future Enhancements**

1. **Bank Integration**: Direct API connections to banks
2. **Receipt Scanning**: OCR for paper receipts
3. **Telegram Bot**: Import via Telegram messages
4. **Voice Input**: "Потратил 500 на кофе"
5. **Social Features**: Compare spending with friends
6. **Investment Tracking**: Stocks, crypto, savings accounts
7. **Bill Reminders**: Auto-detect recurring payments
8. **Cashback Optimization**: Suggest best cards for categories

---

## 📝 **Code Quality**

### **Best Practices Followed:**
- ✅ Clean service layer separation
- ✅ Comprehensive error handling
- ✅ Logging for debugging
- ✅ Type hints for clarity
- ✅ Docstrings for all functions
- ✅ Fallback logic for robustness
- ✅ No dead code
- ✅ Consistent naming conventions

### **Security:**
- ✅ CSRF protection on all POST endpoints
- ✅ Login required for sensitive operations
- ✅ User data isolation (no cross-user access)
- ✅ Input validation and sanitization

---

## 🎓 **Learning Resources**

For users new to financial management, the app includes:

1. **Learning Modules** (`/learning/`)
   - Financial literacy basics
   - Budgeting 101
   - Saving strategies
   - Investment fundamentals

2. **AI Coach** (`/ai-coach/`)
   - Interactive chat with financial advisor
   - Personalized tips
   - Educational content

3. **Gamification** (`/achievements/`)
   - Achievements for milestones
   - Financial IQ score
   - Streak tracking

---

## 📞 **Support**

For issues or questions:
- **GitHub Issues**: [Report bugs](https://github.com/yourusername/sb-finance-ai/issues)
- **Email**: support@sbfinance.ai
- **Telegram**: @sbfinance_support

---

## 📄 **License**

MIT License - See LICENSE file for details

---

## 🙏 **Acknowledgments**

- **OpenRouter** for AI API access
- **DeepSeek** for free LLM models
- **Django** for the robust framework
- **Hackathon 2024** for the opportunity

---

**Built with ❤️ for the next generation of financially savvy individuals**
