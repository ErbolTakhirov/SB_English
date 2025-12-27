# ⚠️ Render Free Tier Limitations & ML

## The Reality of 512MB RAM

You are running a Django application with machine learning components on a server with only 512MB or RAM.

**Consuming Memory:**
1. **Django + Gunicorn**: ~100-150 MB (baseline)
2. **PyTorch (just importing)**: ~150-200 MB
3. **Transformers (just importing)**: ~50 MB
4. **Model Weights**: depends on model

**Remaining Memory for Inference:** ~50-100 MB. This is extremely tight.

## What I have done to make it work:

1. **Lazy Loading**: I rewrote `predictor.py`, `forecast.py`, and `document_generator.py`. Now, heavy libraries (`sklearn`, `pandas`, `transformers`, `torch`) are NOT loaded when the app starts. They are loaded **only when a user triggers relevant functionality**.
   - *Benefit*: The app will start fast and stay alive.
   - *Risk*: The first time a user tries to generate a document or predict a category, the app *might* crash (OOM) if it hits the limit.

2. **Gunicorn Tuning**:
   - `workers 1`: Only one process handles requests. Multiprocessing would kill the server immediately.
   - `threads 1`: No threading overhead.
   - `timeout 120`: Gives time for the "Lazy Load" to happen without timing out (loading PyTorch takes time).

## Recommendations

1. **If it crashes on Document Generation:**
   - Admit defeat on running Transformers locally.
   - Switch `document_generator.py` to use an external API (like OpenAI/Deepseek) instead of local `tiny-gpt2`.
   
2. **If it crashes on Categorization:**
   - The current `joblib` model is small, it *should* work. If not, switch to rule-based categorization defined in the fallback logic.

## Command for Render
The `Procfile` has been updated to the most stable configuration:
```bash
web: gunicorn sb_finance.wsgi:application --workers 1 --threads 1 --timeout 120 --keep-alive 5 --log-level info
```
