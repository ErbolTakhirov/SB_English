from datetime import date
from typing import Optional, Dict

from core.utils.ai_utils import ai_predict_next_month


def forecast_next_month_profit(incomes_qs, expenses_qs, user=None) -> Dict:
    """
    Returns a dict with 'next_month_profit', 'reasoning', and 'method'.
    """
    # Try AI prediction first if user is provided
    if user:
        ai_res = ai_predict_next_month(user, incomes_qs, expenses_qs)
        if ai_res and ai_res.get('next_month_profit_prediction') is not None:
            return {
                'next_month_profit': ai_res['next_month_profit_prediction'],
                'reasoning': ai_res.get('reasoning', ''),
                'method': 'AI (LLM)'
            }

    # Aggregate by month
    by_month = {}
    for o in incomes_qs:
        key = o.date.replace(day=1)
        by_month[key] = by_month.get(key, 0.0) + float(o.amount)
    for o in expenses_qs:
        key = o.date.replace(day=1)
        by_month[key] = by_month.get(key, 0.0) - float(o.amount)

    if not by_month:
        return {'next_month_profit': 0.0, 'method': 'None', 'reasoning': 'Нет данных'}

    months = sorted(by_month.keys())
    profits = [by_month[m] for m in months]
    
    if len(profits) < 2:
        return {'next_month_profit': profits[0] if profits else 0.0, 'method': 'Static', 'reasoning': 'Мало данных для анализа тренда.'}

    # Lazy import to save memory
    from sklearn.linear_model import LinearRegression
    import numpy as np

    X = np.array(range(len(months))).reshape(-1, 1)
    y = np.array(profits)
    model = LinearRegression()
    model.fit(X, y)
    next_idx = np.array([[len(months)]])
    pred = float(model.predict(next_idx)[0])
    
    return {
        'next_month_profit': round(pred, 2),
        'method': 'Linear Regression',
        'reasoning': 'Прогноз на основе линейного тренда прошлых периодов.'
    }
