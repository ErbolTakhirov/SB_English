# 🎨 КАК ИНТЕГРИРОВАТЬ WOW-ФИЧИ В workspace.html

## ✅ ЧТО УЖЕ ГОТОВО (Backend):

Основной AI chat endpoint (`/ai/chat/`) теперь возвращает:

```json
{
  "ok": true,
  "reply": "...",
  "session_id": "...",
  // 🚀 NEW WOW-features:
  "query_type": "advice",  // trends, anomalies, advice, comparison, forecast
  "confidence": {
    "confidence": 85,
    "level": "high",  // high, medium, low
    "icon": "🟢",    // 🟢🟡🔴
    "message": "Высокая уверенность в анализе"
  },
  "health_score": {  // Только для некоторых типов запросов
    "score": 78,
    "grade": "B",
    "emoji": "👍",
    "message": "Хорошее финансовоесостояние",
    "components": {
      "savings_rate": { "score": 25, "max": 35 },
      "income_stability": { "score": 20, "max": 25 },
      "diversification": { "score": 15, "max": 20 },
      "expense_control": { "score": 18, "max": 20 }
    }
  }
}
```

---

## 🎨 ЧТО НУЖНО ДОБАВИТЬ В FRONTEND (workspace.html):

### 1. **Индикатор Confidence Score**

После каждого ответа AI показывать confidence:

```html
<!-- Добавить после сообщения AI -->
<div class="confidence-indicator" style="
    margin-top: 10px;
    padding: 10px 15px;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    border-radius: 10px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
">
    <span class="confidence-icon" style="font-size: 20px;">🟢</span>
    <div>
        <div style="font-weight: 600; color: #2d3748;">
            Уверенность: <span style="color: #48bb78;">85%</span>
        </div>
        <div style="font-size: 12px; color: #718096;">
            Высокая уверенность в анализе
        </div>
    </div>
</div>
```

### 2. **Health Score Badge** (показывать в шапке чата)

```html
<!-- Добавить в верхнюю часть чата -->
<div class="health-score-badge" style="
    position: fixed;
    top: 80px;
    right: 30px;
    background: white;
    padding: 15px 20px;
    border-radius: 15px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    text-align: center;
    cursor: pointer;
    transition: transform 0.3s;
">
    <div style="font-size: 32px; margin-bottom: 5px;">👍</div>
    <div style="font-size: 24px; font-weight: 700; color: #667eea;">78</div>
    <div style="font-size: 12px; color: #718096; margin-top: 3px;">Grade: B</div>
    <div style="font-size: 11px; color: #4a5568; margin-top: 5px;">
        Health Score
    </div>
</div>

<!-- При клике показывать детали -->
<div class="health-score-details" style="display: none; ...">
  <h4>Финансовое здоровье: 78/100</h4>
  <div class="component">
    <span>Savings Rate</span>
    <div class="progress-bar">
      <div class="fill" style="width: 71%">25/35</div>
    </div>
  </div>
  <!-- Остальные компоненты ... -->
</div>
```

### 3. **Query Type Badge** (показывать тип запроса)

```html
<!-- Маленький badge рядом с сообщением пользователя -->
<span class="query-type-badge" style="
    display: inline-block;
    padding: 4px 10px;
    background: #e6fffa;
    color: #047857;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 10px;
">
    📈 TRENDS
</span>
```

---

## 💻 JAVASCRIPT КОД ДЛЯ ИНТЕГРАЦИИ:

```javascript
// В функции отправки сообщения (примерно строка ~500 в workspace.html)
fetch('/ai/chat/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
    },
    body: JSON.stringify({
        message: userMessage,
        session_id: currentSessionId
    })
})
.then(r => r.json())
.then(data => {
    if (data.ok) {
        // Основной ответ
        displayAIMessage(data.reply);
        
        // 🚀 NEW: Показываем confidence
        if (data.confidence) {
            displayConfidence(data.confidence);
        }
        
        // 🚀 NEW: Обновляем health score
        if (data.health_score) {
            updateHealthScoreBadge(data.health_score);
        }
        
        // 🚀 NEW: Показываем тип запроса
        if (data.query_type) {
            addQueryTypeBadge(data.query_type);
        }
    }
});

// Функция отображения confidence
function displayConfidence(confidence) {
    const confidenceHtml = `
        <div class="confidence-indicator animate-fade-in">
            <span class="confidence-icon">${confidence.icon}</span>
            <div>
                <div class="confidence-value">
                    Уверенность: <span style="color: ${getConfidenceColor(confidence.level)}">
                        ${confidence.confidence}%
                    </span>
                </div>
                <div class="confidence-message">${confidence.message}</div>
            </div>
        </div>
    `;
    
    // Добавить после последнего сообщения AI
    document.querySelector('.message.ai:last-child').insertAdjacentHTML('beforeend', confidenceHtml);
}

// Функция обновления health score badge
function updateHealthScoreBadge(healthScore) {
    const badgeElement = document.querySelector('.health-score-badge');
    if (!badgeElement) return;
    
    badgeElement.innerHTML = `
        <div style="font-size: 32px; margin-bottom: 5px;">${healthScore.emoji}</div>
        <div style="font-size: 24px; font-weight: 700; color: #667eea;">${healthScore.score}</div>
        <div style="font-size: 12px; color: #718096; margin-top: 3px;">Grade: ${healthScore.grade}</div>
        <div style="font-size: 11px; color: #4a5568; margin-top: 5px;">Health Score</div>
    `;
    
    // Добавить bounce анимацию
    badgeElement.classList.add('bounce-animation');
    setTimeout(() => badgeElement.classList.remove('bounce-animation'), 600);
}

// Функция добавления query type badge
function addQueryTypeBadge(queryType) {
    const icons = {
        'trends': '📈',
        'anomalies': '🔍',
        'advice': '💡',
        'comparison': '⚖️',
        'forecast': '🔮',
        'specific': '🎯'
    };
    
    const colors = {
        'trends': '#e6fffa',
        'anomalies': '#fff5f5',
        'advice': '#fef5e7', 
        'comparison': '#f3e5f5',
        'forecast': '#e3f2fd',
        'specific': '#f1f8e9'
    };
    
    const badge = `
        <span class="query-type-badge" style="
            background: ${colors[queryType] || '#f7fafc'};
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 10px;
        ">
            ${icons[queryType] || '💬'} ${queryType.toUpperCase()}
        </span>
    `;
    
    // Добавить к последнему сообщению пользователя
    document.querySelector('.message.user:last-child').insertAdjacentHTML('beforeend', badge);
}

// Вспомогательная функция для цвета
function getConfidenceColor(level) {
    return level === 'high' ? '#48bb78' : 
           level === 'medium' ? '#ed8936' : '#f56565';
}
```

---

## 🎨 CSS СТИЛИ:

```css
/* Добавить в <style> секцию workspace.html */

.confidence-indicator {
    margin-top: 10px;
    padding: 12px 16px;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    border-radius: 12px;
    display: inline-flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.confidence-icon {
    font-size: 24px;
    animation: pulse 2s ease-in-out infinite;
}

.confidence-value {
    font-weight: 600;
    color: #2d3748;
    margin-bottom: 2px;
}

.confidence-message {
    font-size: 12px;
    color: #718096;
}

.health-score-badge {
    position: fixed;
    top: 80px;
    right: 30px;
    background: white;
    padding: 15px 20px;
    border-radius: 15px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    text-align: center;
    cursor: pointer;
    transition: transform 0.3s, box-shadow 0.3s;
    z-index: 100;
}

.health-score-badge:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 25px rgba(0,0,0,0.15);
}

.bounce-animation {
    animation: bounce 0.6s ease-in-out;
}

@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.animate-fade-in {
    animation: fadeIn 0.4s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.query-type-badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 10px;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}
```

---

## 🎯 ПРИОРИТЕТ ИНТЕГРАЦИИ (для хакатона):

### Must-Have (сделай обязательно):
1. ✅ **Confidence Score** после каждого AI ответа
2. ✅ **Health Score Badge** в шапке чата

### Nice-to-Have (если есть время):
3. ⭐ Query Type badge
4. ⭐ Health Score детали при клике
5. ⭐ Анимации

---

## 🚀 БЫСТРЫЙ СТАРТ:

1. Скопируй CSS стили в `<style>` секцию workspace.html
2. Добавь JavaScript функции в основной script
3. Обнови fetch callback чтобы вызывать новые функции
4. Добавь HTML для health score badge

**Результат:** Твой чат станет в 10 раз круче с минимальными изменениями!

---

**Файл для справки:** Смотри `/demo/` как пример работы всех фич!
