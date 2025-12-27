# SB Finance AI

**SB Finance AI** is an intelligent financial operating system designed to automate the office of the CFO for small and medium-sized businesses (SMBs). 

Unlike traditional accounting software that merely records data, SB Finance AI leverages **Retrieval-Augmented Generation (RAG)** and advanced statistical modeling to actively analyze, forecast, and advise on business health.

---

## 🚀 Core Technologies

### 🧠 Retrieval-Augmented Generation (RAG)
The system employs a sophisticated RAG architecture to provide context-aware financial consulting:
- **Dynamic Context Injection**: When a user asks a question (e.g., *"Why are our operational costs up?"*), the system retrieves the relevant slice of financial data, historical trends, and vendor specifics.
- **Grounded Accuracy**: By augmenting the LLM with retrieved database records, we eliminate hallucinations. The AI reasons based on *your* actual numbers, not general knowledge.
- **Semantic Search**: (Logical implementation) Understanding the intent behind financial queries to fetch the correct supporting data before generating an answer.

### 📉 Hybrid Intelligence ("Hard Math" + AI)
We separate creative reasoning from calculation:
- **Deterministic Layer**: Critical metrics (cash gaps, burn rate, P&L) are calculated using robust statistical libraries (Pandas/NumPy) to ensure 100% numerical precision.
- **Reasoning Layer**: Large Language Models (LLMs) connect these metrics to provide strategic business advice, ensuring you get the accuracy of a calculator with the insight of a human expert.

### 🛡️ Enterprise-Grade Security
- **PII Masking**: All personally identifiable information (names, card numbers, specific client details) is sanitized before being processed by AI models.
- **Data Sovereignty**: The architecture supports local LLM deployment (via Ollama), allowing sensitive financial data to never leave your on-premise infrastructure.

---

## ⚡ Key Features

### 1. The AI CFO
A conversational interface that replaces the need for a full-time financial director.
- **Strategic Planning**: Ask complex "What-if" scenarios (e.g., *"If we cut marketing by 20%, how does that affect our runway?"*).
- **Deep Dives**: The AI can drill down into specific expense categories to find inefficiencies.

### 2. Automated Financial Operations
- **Smart Import**: Intelligent parsing of bank statements (CSV/Excel) with de-duplication logic.
- **Auto-Categorization**: Machine Learning classifiers automatically tag transactions based on merchant descriptions and past behavior.

### 3. Anomaly Detection
- Real-time monitoring of cash flow.
- Alerts for irregular spending patterns, subscription deviations, or unexpected revenue drops.

### 4. Financial Health Scoring
A proprietary algorithm that aggregates complex financial ratios into a single **Health Score (0-100)**, giving business owners an immediate snapshot of their stability, liquidity, and efficiency.

### 5. Personalized User Profiles
- **Bio/Occupation Field**: During registration, users can provide information about their occupation or business type
- **AI Personalization**: The AI uses this profile information to tailor financial advice and recommendations specifically to the user's industry and situation
- **Context-Aware Insights**: Financial guidance is customized based on whether you're a freelancer, small business owner, student, or other profession

---

## 🏗️ Technical Architecture

This project is built on a scalable, modular architecture:

- **Backend**: Python 3.9+, Django 5.0, Django REST Framework (DRF).
- **Task Queue**: Celery + Redis for asynchronous report generation and ML processing.
- **Database**: PostgreSQL for robust data integrity (configured for high concurrency).
- **AI Orchestration**: Custom `LLMManager` class handling failovers between OpenAI, Anthropic, and Local models.
- **Frontend**: Lightweight, responsive interface utilizing Vanilla JS for maximum performance and compatibility.

---

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.9+
- Redis (for background tasks)
- PostgreSQL (recommended) or SQLite

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd sb-finance-ai
   ```

2. **Set up the environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Create a `.env` file:
   ```env
   DEBUG=True
   SECRET_KEY=your_secret_key
   LLM_PROVIDER=openai  # or 'local', 'anthropic'
   LLM_API_KEY=your_key
   ```

4. **Initialize the Database**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Run the Server**
   ```bash
   python manage.py runserver
   ```

---

## 🔒 Security Best Practices

### API Key Protection
**CRITICAL**: Never commit API keys or secrets to version control!

1. **Environment Variables**: All sensitive data (API keys, database credentials) must be stored in `.env` file
2. **`.gitignore` Protection**: The `.env` file is automatically excluded from git commits
3. **Example Configuration**: Use `env.example` as a template (contains no real secrets)

### Secure Setup Checklist
- ✅ Copy `env.example` to `.env`
- ✅ Add your real API keys to `.env` (never to code files)
- ✅ Verify `.env` is listed in `.gitignore`
- ✅ Never share `.env` file or commit it to GitHub
- ✅ Rotate API keys if accidentally exposed

### Supported API Providers
- **OpenRouter** (Recommended): Get your key at [openrouter.ai/keys](https://openrouter.ai/keys)
- **Google Gemini**: Alternative provider
- **Local LLM**: Use Ollama for complete data privacy

---

## 🤝 Contributing
We welcome contributions to the RAG pipeline and core financial models. Please ensure all PRs include unit tests for any new statistical functions.

---

**License**: MIT
