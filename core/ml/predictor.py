import os
from pathlib import Path
from typing import Optional

MODEL_PATH = Path(getattr(settings, 'MEDIA_ROOT', Path.cwd()) / 'ml' / 'expense_classifier.joblib')


class ExpenseAutoCategorizer:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ExpenseAutoCategorizer, cls).__new__(cls)
        return cls._instance

    def _get_model(self):
        if self._model is None:
            try:
                import joblib
                if MODEL_PATH.exists():
                    self._model = joblib.load(MODEL_PATH)
            except Exception:
                self._model = None
        return self._model

    def predict_category(self, text: str) -> Optional[str]:
        text = (text or '').strip()
        if not text:
            return None
            
        # Lazy load model only when needed
        model = self._get_model()
        
        # ML path
        if model is not None:
            try:
                pred = model.predict([text])[0]
                return str(pred)
            except Exception:
                pass
                
        # Fallback simple rules
        low = text.lower()
        if any(w in low for w in ['аренда', 'офис', 'помещ']):
            return 'rent'
        if any(w in low for w in ['налог', 'ндс', 'фнс']):
            return 'tax'
        if any(w in low for w in ['зарплат', 'оклад']):
            return 'salary'
        if any(w in low for w in ['реклам', 'маркет']):
            return 'marketing'
        if any(w in low for w in ['закуп', 'покуп']):
            return 'purchase'
        return 'other'

