"""
AI Categorization Service for SB Finance AI
Automatically categorizes transactions using LLM with rule-based fallback
"""

import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from django.conf import settings
from core.ai_services.llm_manager import llm_manager
from core.models import Income, Expense

logger = logging.getLogger(__name__)


class TransactionCategorizationService:
    """
    AI-powered transaction categorization with learning capabilities
    """
    
    # Rule-based patterns for fallback (when no API key)
    INCOME_PATTERNS = {
        'allowance': ['карманные', 'allowance', 'родители', 'parents', 'мама', 'папа'],
        'salary': ['зарплата', 'salary', 'wage', 'payment', 'оплата труда'],
        'freelance': ['фриланс', 'freelance', 'upwork', 'fiverr', 'заказ'],
        'gift': ['подарок', 'gift', 'birthday', 'день рождения'],
        'part_time': ['подработка', 'part-time', 'part time', 'временная'],
        'sales': ['продажа', 'sale', 'sold', 'продал'],
        'bonus': ['бонус', 'bonus', 'премия', 'reward'],
    }
    
    EXPENSE_PATTERNS = {
        'food': ['магнит', 'пятерочка', 'макдоналдс', 'кфс', 'kfc', 'mcdonalds', 'cafe', 'кафе', 
                'ресторан', 'restaurant', 'еда', 'food', 'обед', 'lunch', 'завтрак'],
        'transport': ['такси', 'taxi', 'uber', 'яндекс', 'yandex', 'метро', 'metro', 'bus', 
                     'автобус', 'транспорт', 'transport'],
        'entertainment': ['кино', 'cinema', 'movie', 'игра', 'game', 'концерт', 'concert', 
                         'развлечения', 'entertainment'],
        'shopping': ['ozon', 'wildberries', 'wb', 'amazon', 'aliexpress', 'одежда', 'clothes', 
                    'обувь', 'shoes', 'магазин', 'shop'],
        'subscriptions': ['подписка', 'subscription', 'netflix', 'spotify', 'youtube', 'premium'],
        'education': ['курс', 'course', 'книга', 'book', 'учеба', 'education', 'школа', 'school'],
        'health': ['аптека', 'pharmacy', 'врач', 'doctor', 'лекарство', 'medicine'],
        'beauty': ['салон', 'salon', 'парикмахер', 'barber', 'косметика', 'cosmetics'],
        'games': ['steam', 'playstation', 'xbox', 'nintendo', 'игра', 'game'],
    }
    
    def __init__(self):
        self.has_api_key = bool(getattr(settings, 'LLM_API_KEY', None))
        self.user_corrections = {}  # Store user corrections for learning
    
    def categorize_batch(self, transactions: List[Dict], transaction_type: str = 'expense') -> List[str]:
        """
        Categorize a batch of transactions
        Args:
            transactions: List of dicts with 'description', 'merchant', 'amount'
            transaction_type: 'income' or 'expense'
        Returns:
            List of category strings
        """
        if not transactions:
            return []
        
        # Use AI if available, otherwise fallback to rules
        if self.has_api_key:
            return self._categorize_with_ai(transactions, transaction_type)
        else:
            return self._categorize_with_rules(transactions, transaction_type)
    
    def categorize_single(self, description: str, merchant: str = '', 
                         amount: float = 0, transaction_type: str = 'expense') -> Tuple[str, float]:
        """
        Categorize a single transaction
        Returns: (category, confidence_score)
        """
        transaction = {
            'description': description,
            'merchant': merchant,
            'amount': amount
        }
        
        categories = self.categorize_batch([transaction], transaction_type)
        category = categories[0] if categories else 'other'
        
        # Calculate confidence based on method used
        confidence = 0.9 if self.has_api_key else 0.6
        
        # Check if merchant was learned from corrections
        merchant_key = merchant.lower().strip()
        if merchant_key in self.user_corrections:
            category = self.user_corrections[merchant_key]
            confidence = 0.95  # High confidence for learned patterns
        
        return category, confidence
    
    def learn_from_correction(self, merchant: str, correct_category: str):
        """
        Learn from user corrections
        """
        merchant_key = merchant.lower().strip()
        self.user_corrections[merchant_key] = correct_category
        logger.info(f"Learned: {merchant} -> {correct_category}")
    
    def _categorize_with_ai(self, transactions: List[Dict], transaction_type: str) -> List[str]:
        """Use LLM to categorize transactions"""
        # Get available categories
        if transaction_type == 'income':
            categories = [choice[0] for choice in Income._meta.get_field('income_type').choices]
        else:
            categories = [choice[0] for choice in Expense._meta.get_field('expense_type').choices]
        
        # Build prompt
        transactions_text = "\n".join([
            f"{i+1}. {t.get('merchant', '')} - {t.get('description', '')} - {t.get('amount', 0)}"
            for i, t in enumerate(transactions)
        ])
        
        prompt = f"""Categorize these {transaction_type} transactions into one of these categories:
{', '.join(categories)}

Transactions:
{transactions_text}

Return ONLY a JSON array of categories in the same order, like: ["category1", "category2", ...]
If unsure, use "other".
"""
        
        try:
            messages = [
                {"role": "system", "content": "You are a financial transaction categorization assistant. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ]
            
            response = llm_manager.chat_sync(messages, temperature=0.3, max_tokens=500)
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                
                # Validate categories
                validated = []
                for cat in result:
                    if cat in categories:
                        validated.append(cat)
                    else:
                        validated.append('other')
                
                return validated
            
        except Exception as e:
            logger.error(f"AI categorization error: {e}")
        
        # Fallback to rules if AI fails
        return self._categorize_with_rules(transactions, transaction_type)
    
    def _categorize_with_rules(self, transactions: List[Dict], transaction_type: str) -> List[str]:
        """Rule-based categorization fallback"""
        patterns = self.INCOME_PATTERNS if transaction_type == 'income' else self.EXPENSE_PATTERNS
        results = []
        
        for transaction in transactions:
            text = f"{transaction.get('merchant', '')} {transaction.get('description', '')}".lower()
            
            # Check learned corrections first
            merchant_key = transaction.get('merchant', '').lower().strip()
            if merchant_key in self.user_corrections:
                results.append(self.user_corrections[merchant_key])
                continue
            
            # Check patterns
            category = 'other'
            for cat, keywords in patterns.items():
                if any(keyword in text for keyword in keywords):
                    category = cat
                    break
            
            results.append(category)
        
        return results
    
    def get_category_suggestions(self, description: str, merchant: str = '', 
                                transaction_type: str = 'expense') -> List[Tuple[str, float]]:
        """
        Get top 3 category suggestions with confidence scores
        Returns: [(category, confidence), ...]
        """
        # For now, return the top category with alternatives
        category, confidence = self.categorize_single(description, merchant, 0, transaction_type)
        
        # Get all available categories
        if transaction_type == 'income':
            all_categories = [choice[0] for choice in Income._meta.get_field('income_type').choices]
        else:
            all_categories = [choice[0] for choice in Expense._meta.get_field('expense_type').choices]
        
        # Return top category and two random alternatives
        suggestions = [(category, confidence)]
        
        for cat in all_categories:
            if cat != category and len(suggestions) < 3:
                suggestions.append((cat, 0.3))
        
        return suggestions[:3]


# Singleton instance
categorization_service = TransactionCategorizationService()
