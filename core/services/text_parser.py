"""
Text Parser Service for SB Finance AI
Parses plain text financial data into structured transactions
"""

import re
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from decimal import Decimal


class TextTransactionParser:
    """
    Parses plain text financial data in various formats:
    - "01.12 Магнит 450р"
    - "02.12.2024 Яндекс.Такси 320 сом"
    - "15 Dec Coffee Shop $5.50"
    - "2024-01-01 Salary 50000"
    """
    
    # Common date patterns
    DATE_PATTERNS = [
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # DD.MM.YYYY
        r'(\d{1,2})\.(\d{1,2})',            # DD.MM (current year)
        r'(\d{4})-(\d{1,2})-(\d{1,2})',    # YYYY-MM-DD
        r'(\d{1,2})/(\d{1,2})/(\d{4})',    # MM/DD/YYYY
        r'(\d{1,2})\s+([A-Za-zа-яА-Я]{3,})',  # 15 Dec or 15 декабря
    ]
    
    # Currency symbols and keywords
    CURRENCIES = {
        'р': 'RUB', 'руб': 'RUB', 'rub': 'RUB', '₽': 'RUB',
        'сом': 'KGS', 'kgs': 'KGS', 'с': 'KGS',
        '$': 'USD', 'usd': 'USD', 'dollar': 'USD',
        '€': 'EUR', 'eur': 'EUR', 'euro': 'EUR',
        '₸': 'KZT', 'тг': 'KZT', 'kzt': 'KZT',
    }
    
    # Month names
    MONTHS = {
        'jan': 1, 'january': 1, 'янв': 1, 'января': 1,
        'feb': 2, 'february': 2, 'фев': 2, 'февраля': 2,
        'mar': 3, 'march': 3, 'мар': 3, 'марта': 3,
        'apr': 4, 'april': 4, 'апр': 4, 'апреля': 4,
        'may': 5, 'май': 5, 'мая': 5,
        'jun': 6, 'june': 6, 'июн': 6, 'июня': 6,
        'jul': 7, 'july': 7, 'июл': 7, 'июля': 7,
        'aug': 8, 'august': 8, 'авг': 8, 'августа': 8,
        'sep': 9, 'september': 9, 'сен': 9, 'сентября': 9,
        'oct': 10, 'october': 10, 'окт': 10, 'октября': 10,
        'nov': 11, 'november': 11, 'ноя': 11, 'ноября': 11,
        'dec': 12, 'december': 12, 'дек': 12, 'декабря': 12,
    }
    
    def __init__(self, default_currency: str = 'KGS'):
        self.default_currency = default_currency
        self.current_year = datetime.now().year
    
    def parse_text(self, text: str) -> List[Dict]:
        """
        Parse plain text into list of transaction dictionaries.
        Returns: [{'date': date, 'amount': Decimal, 'merchant': str, 
                   'description': str, 'currency': str, 'needs_review': bool}]
        """
        if not text or not text.strip():
            return []
        
        transactions = []
        lines = text.strip().split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or len(line) < 5:  # Skip empty or too short lines
                continue
            
            try:
                transaction = self._parse_line(line)
                if transaction:
                    transaction['line_number'] = line_num
                    transactions.append(transaction)
            except Exception as e:
                # Mark as needs review if parsing fails
                transactions.append({
                    'date': None,
                    'amount': None,
                    'merchant': None,
                    'description': line,
                    'currency': self.default_currency,
                    'needs_review': True,
                    'parse_error': str(e),
                    'line_number': line_num
                })
        
        return transactions
    
    def _parse_line(self, line: str) -> Optional[Dict]:
        """Parse a single line into a transaction"""
        # Extract date
        parsed_date = self._extract_date(line)
        
        # Extract amount and currency
        amount, currency = self._extract_amount_and_currency(line)
        
        # Extract merchant/description (everything else)
        merchant, description = self._extract_merchant_description(line, parsed_date, amount, currency)
        
        # Determine if needs review
        needs_review = (parsed_date is None or amount is None or 
                       not merchant or len(merchant.strip()) < 2)
        
        return {
            'date': parsed_date,
            'amount': amount,
            'merchant': merchant,
            'description': description or line,
            'currency': currency or self.default_currency,
            'needs_review': needs_review
        }
    
    def _extract_date(self, text: str) -> Optional[date]:
        """Extract date from text"""
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Handle different date formats
                if len(groups) == 3:
                    if '-' in match.group(0):  # YYYY-MM-DD
                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    elif '/' in match.group(0):  # MM/DD/YYYY
                        month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                    else:  # DD.MM.YYYY
                        day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                    
                    try:
                        return date(year, month, day)
                    except ValueError:
                        continue
                
                elif len(groups) == 2:
                    # Check if second group is month name
                    if groups[1].lower() in self.MONTHS:
                        day = int(groups[0])
                        month = self.MONTHS[groups[1].lower()]
                        year = self.current_year
                    else:
                        # DD.MM format
                        day, month = int(groups[0]), int(groups[1])
                        year = self.current_year
                    
                    try:
                        return date(year, month, day)
                    except ValueError:
                        continue
        
        return None
    
    def _extract_amount_and_currency(self, text: str) -> Tuple[Optional[Decimal], Optional[str]]:
        """Extract amount and currency from text"""
        # First, remove the date part to avoid confusion
        text_without_date = text
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text_without_date, re.IGNORECASE)
            if match:
                # Remove the matched date
                text_without_date = text_without_date[:match.start()] + ' ' + text_without_date[match.end():]
                break
        
        # Pattern for amounts with currency symbols
        amount_patterns = [
            # Currency symbol before number: $100, €50
            r'([₽$€₸])\s*(\d+(?:[,\s]\d{3})*(?:[.,]\d{1,2})?)',
            # Number with currency after: 100р, 50с, 200руб, 300сом, 200$
            r'(\d+(?:[,\s]\d{3})*(?:[.,]\d{1,2})?)\s*([₽рсомтгруб\$€₸usdeurkgs]+)',
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text_without_date, re.IGNORECASE)
            for match in matches:
                try:
                    # Determine which group is amount and which is currency
                    if match[0] and match[0][0].isdigit():
                        # Pattern: amount currency
                        amount_str = match[0]
                        currency_str = match[1] if len(match) > 1 else ''
                    else:
                        # Pattern: currency amount
                        currency_str = match[0]
                        amount_str = match[1] if len(match) > 1 else ''
                    
                    # Clean amount string: remove spaces and commas
                    amount_str = amount_str.replace(' ', '').replace(',', '')
                    
                    # Skip if amount looks like a date (has dot with 2 digits on each side)
                    if '.' in amount_str:
                        parts = amount_str.split('.')
                        if len(parts) == 2 and len(parts[0]) <= 2 and len(parts[1]) <= 2:
                            # This looks like a date (01.12), skip it
                            continue
                    
                    amount = Decimal(amount_str)
                    
                    # Skip very small amounts that are likely dates or years
                    if amount < Decimal('10'):
                        continue
                    
                    # Detect currency - prioritize exact symbol matches
                    currency = None
                    
                    # Check for exact symbol matches first (highest priority)
                    if '$' in currency_str:
                        currency = 'USD'
                    elif '₽' in currency_str or 'р' in currency_str.lower():
                        currency = 'RUB'
                    elif '€' in currency_str:
                        currency = 'EUR'
                    elif '₸' in currency_str:
                        currency = 'KZT'
                    elif 'сом' in currency_str.lower() or 'с' == currency_str.lower():
                        currency = 'KGS'
                    else:
                        # Fallback to text matching
                        currency_str_lower = currency_str.lower()
                        for key, val in self.CURRENCIES.items():
                            if key.lower() in currency_str_lower:
                                currency = val
                                break
                    
                    return amount, currency
                except (ValueError, IndexError, Exception):
                    continue
        
        return None, None
    
    def _extract_merchant_description(self, text: str, parsed_date: Optional[date], 
                                     amount: Optional[Decimal], currency: Optional[str]) -> Tuple[str, str]:
        """Extract merchant and description by removing date, amount, currency"""
        cleaned = text
        
        # Remove date - only remove the first match
        if parsed_date:
            for pattern in self.DATE_PATTERNS:
                match = re.search(pattern, cleaned, re.IGNORECASE)
                if match:
                    cleaned = cleaned[:match.start()] + cleaned[match.end():]
                    break
        
        # Remove amount - find the specific amount value with currency
        if amount and currency:
            # Build pattern to match amount with currency
            amount_int = int(amount) if amount == int(amount) else None
            if amount_int:
                # Match number followed by currency symbols
                amount_pattern = rf'\b{amount_int}\s*[₽рсомтгруб\$€₸usdeurkgs]+'
                cleaned = re.sub(amount_pattern, '', cleaned, count=1, flags=re.IGNORECASE)
            else:
                # For decimal amounts
                amount_str = str(amount).replace('.', r'\.')
                amount_pattern = rf'\b{amount_str}\s*[₽рсомтгруб\$€₸usdeurkgs]+'
                cleaned = re.sub(amount_pattern, '', cleaned, count=1, flags=re.IGNORECASE)
        
        # Clean up whitespace
        cleaned = ' '.join(cleaned.split()).strip()
        
        # Merchant is the cleaned text, description is original
        merchant = cleaned if cleaned else 'Unknown'
        
        return merchant, text


# Singleton instance
text_parser = TextTransactionParser()
