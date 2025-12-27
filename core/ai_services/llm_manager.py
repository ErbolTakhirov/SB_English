"""
Unified LLM Manager for SB Finance AI Teen Platform
Handles multiple LLM providers with consistent interface
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    DEEPSEEK = "deepseek"


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider"""
    content: str
    provider: str
    model: str
    confidence: Optional[float] = None
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    metadata: Optional[Dict] = None


class LLMManager:
    """
    Unified interface for multiple LLM providers
    Handles teen-appropriate responses and educational context
    """
    
    def __init__(self):
        self.providers = {
            LLMProvider.OPENAI: self._openai_chat,
            LLMProvider.ANTHROPIC: self._anthropic_chat,
            LLMProvider.OPENROUTER: self._openrouter_chat,
            LLMProvider.OLLAMA: self._ollama_chat,
            LLMProvider.DEEPSEEK: self._deepseek_chat,
        }
        self.current_provider = self._detect_provider()
        
    def _detect_provider(self) -> LLMProvider:
        """Detect available LLM provider based on settings"""
        api_key = getattr(settings, 'LLM_API_KEY', None)
        provider_name = getattr(settings, 'LLM_PROVIDER', 'openrouter').lower()
        
        if provider_name == 'openai' and api_key:
            return LLMProvider.OPENAI
        elif provider_name == 'anthropic' and api_key:
            return LLMProvider.ANTHROPIC
        elif provider_name == 'openrouter' and api_key:
            return LLMProvider.OPENROUTER
        elif provider_name == 'ollama':
            return LLMProvider.OLLAMA
        elif provider_name == 'deepseek':
            return LLMProvider.DEEPSEEK
        else:
            logger.warning(f"No valid LLM provider found, using OpenRouter")
            return LLMProvider.OPENROUTER
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'SB-Finance-AI-Teen/1.0'
        }
        
        api_key = getattr(settings, 'LLM_API_KEY', None)
        if api_key:
            headers['Authorization'] = f"Bearer {api_key}"
            
        return headers
    
    def _get_base_url(self) -> str:
        """Get base URL for current provider"""
        urls = {
            LLMProvider.OPENAI: 'https://api.openai.com/v1',
            LLMProvider.ANTHROPIC: 'https://api.anthropic.com/v1',
            LLMProvider.OPENROUTER: 'https://openrouter.ai/api/v1',
            LLMProvider.OLLAMA: 'http://localhost:11434/api',
            LLMProvider.DEEPSEEK: 'https://api.deepseek.com/v1',
        }
        return urls[self.current_provider]
    
    def _get_model(self) -> str:
        """Get model name for current provider"""
        models = {
            LLMProvider.OPENAI: getattr(settings, 'LLM_MODEL', 'gpt-4o-mini'),
            LLMProvider.ANTHROPIC: getattr(settings, 'LLM_MODEL', 'claude-3-haiku-20240307'),
            LLMProvider.OPENROUTER: getattr(settings, 'LLM_MODEL', 'openai/gpt-4o-mini'),
            LLMProvider.OLLAMA: getattr(settings, 'LLM_MODEL', 'llama2'),
            LLMProvider.DEEPSEEK: getattr(settings, 'LLM_MODEL', 'deepseek-chat'),
        }
        return models[self.current_provider]
    
    async def chat(self, 
                   messages: List[Dict[str, str]], 
                   temperature: float = 0.7,
                   max_tokens: int = 1000,
                   **kwargs) -> LLMResponse:
        """Async chat with current LLM provider"""
        if self.current_provider in self.providers:
            return await self.providers[self.current_provider](
                messages, temperature, max_tokens, **kwargs
            )
        else:
            raise ValueError(f"Unsupported provider: {self.current_provider}")
    
    def chat_sync(self, 
                  messages: List[Dict[str, str]], 
                  temperature: float = 0.7,
                  max_tokens: int = 1000,
                  **kwargs) -> LLMResponse:
        """Synchronous chat with current LLM provider"""
        provider_method = self.providers.get(self.current_provider)
        if not provider_method:
            return LLMResponse(
                content="Provider not available",
                provider=str(self.current_provider),
                model=self._get_model()
            )
        
        return provider_method(messages, temperature, max_tokens, **kwargs)
    
    def _openai_chat(self, 
                     messages: List[Dict[str, str]], 
                     temperature: float,
                     max_tokens: int,
                     **kwargs) -> LLMResponse:
        """OpenAI API implementation"""
        url = f"{self._get_base_url()}/chat/completions"
        headers = self._get_headers()
        
        payload = {
            "model": self._get_model(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data['choices'][0]['message']['content'],
                provider='openai',
                model=self._get_model(),
                tokens_used=data.get('usage', {}).get('total_tokens'),
                metadata={'finish_reason': data['choices'][0].get('finish_reason')}
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return LLMResponse(
                content="Извините, произошла ошибка. Попробуйте позже.",
                provider='openai',
                model=self._get_model()
            )
    
    def _openrouter_chat(self, 
                         messages: List[Dict[str, str]], 
                         temperature: float,
                         max_tokens: int,
                         **kwargs) -> LLMResponse:
        """OpenRouter API implementation"""
        url = f"{self._get_base_url()}/chat/completions"
        headers = self._get_headers()
        
        # Add OpenRouter specific headers
        headers.update({
            'HTTP-Referer': getattr(settings, 'LLM_HTTP_REFERER', 'http://localhost:8000'),
            'X-Title': 'SB Finance AI - Teen Platform'
        })
        
        payload = {
            "model": self._get_model(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data['choices'][0]['message']['content'],
                provider='openrouter',
                model=self._get_model(),
                tokens_used=data.get('usage', {}).get('total_tokens'),
                metadata={'finish_reason': data['choices'][0].get('finish_reason')}
            )
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            return LLMResponse(
                content="Извините, произошла ошибка. Попробуйте позже.",
                provider='openrouter',
                model=self._get_model()
            )
    
    def _anthropic_chat(self, 
                        messages: List[Dict[str, str]], 
                        temperature: float,
                        max_tokens: int,
                        **kwargs) -> LLMResponse:
        """Anthropic Claude API implementation"""
        url = f"{self._get_base_url()}/messages"
        headers = self._get_headers()
        headers['anthropic-version'] = '2023-06-01'
        
        # Convert messages format for Claude
        system_message = ""
        claude_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                claude_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        payload = {
            "model": self._get_model(),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": claude_messages
        }
        
        if system_message:
            payload["system"] = system_message
            
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data['content'][0]['text'],
                provider='anthropic',
                model=self._get_model(),
                tokens_used=data.get('usage', {}).get('input_tokens') + data.get('usage', {}).get('output_tokens'),
                metadata={'stop_reason': data.get('stop_reason')}
            )
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return LLMResponse(
                content="Извините, произошла ошибка. Попробуйте позже.",
                provider='anthropic',
                model=self._get_model()
            )
    
    def _ollama_chat(self, 
                     messages: List[Dict[str, str]], 
                     temperature: float,
                     max_tokens: int,
                     **kwargs) -> LLMResponse:
        """Ollama local API implementation"""
        url = f"{self._get_base_url()}/chat"
        
        payload = {
            "model": self._get_model(),
            "messages": messages,
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data['message']['content'],
                provider='ollama',
                model=self._get_model(),
                metadata={'model_loaded': True}
            )
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return LLMResponse(
                content="Локальная модель недоступна. Проверьте, что Ollama запущен.",
                provider='ollama',
                model=self._get_model()
            )
    
    def _deepseek_chat(self, 
                       messages: List[Dict[str, str]], 
                       temperature: float,
                       max_tokens: int,
                       **kwargs) -> LLMResponse:
        """DeepSeek API implementation"""
        url = f"{self._get_base_url()}/chat/completions"
        headers = self._get_headers()
        
        payload = {
            "model": self._get_model(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data['choices'][0]['message']['content'],
                provider='deepseek',
                model=self._get_model(),
                tokens_used=data.get('usage', {}).get('total_tokens'),
                metadata={'finish_reason': data['choices'][0].get('finish_reason')}
            )
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            return LLMResponse(
                content="Извините, произошла ошибка. Попробуйте позже.",
                provider='deepseek',
                model=self._get_model()
            )
    
    def create_teen_context_prompt(self, 
                                  user_age: int,
                                  language: str = 'ru',
                                  current_situation: Dict = None) -> str:
        """Create context prompt for teen-appropriate responses"""
        
        base_prompt = {
            'ru': """
Ты - дружелюбный финансовый коуч для подростков 13-18 лет. 
Говори простым языком, понятным школьнику.
Используй примеры из жизни подростков (школа, карманные деньги, покупка телефона, экономия на развлечениях).
Будь позитивным и мотивирующим, но реалистичным.
Всегда объясняй "почему" свои рекомендации простыми словами.

Избегай:
- Сложных финансовых терминов
- Банковских деталей (кредиты, ипотека)
- Взрослых примеров (семья, работа полный день)
- Морализаторства

Помогай:
- Планировать покупки (телефон, курсы, одежда)
- Экономить на развлечениях
- Понимать ценность денег
- Ставить реальные цели
- Объяснять инфляцию простыми словами
""",
            'en': """
You are a friendly financial coach for teenagers aged 13-18.
Speak in simple language that a high school student can understand.
Use examples from teen life (school, allowance, phone purchases, saving on entertainment).
Be positive and motivating, but realistic.
Always explain "why" your recommendations in simple terms.

Avoid:
- Complex financial terminology
- Banking details (loans, mortgages)
- Adult examples (family, full-time job)
- Preaching

Help with:
- Planning purchases (phone, courses, clothes)
- Saving on entertainment
- Understanding the value of money
- Setting realistic goals
- Explaining inflation in simple terms
"""
        }
        
        if current_situation:
            context = f"\nТекущая ситуация пользователя: {json.dumps(current_situation, ensure_ascii=False)}"
            base_prompt['ru'] += context
            base_prompt['en'] += f"\nUser's current situation: {json.dumps(current_situation)}"
        
        return base_prompt.get(language, base_prompt['ru'])
    
    def generate_explanation(self, 
                           original_response: str,
                           user_age: int,
                           language: str = 'ru') -> str:
        """Generate simpler explanation of AI response for younger users"""
        
        explanation_prompt = {
            'ru': f"""
Объясни предыдущий ответ еще проще для {user_age}-летнего подростка.
Используй понятные примеры и избегай сложных слов.
Ответь кратко (1-2 предложения).""",
            'en': f"""
Explain the previous answer in even simpler terms for a {user_age}-year-old teenager.
Use understandable examples and avoid complex words.
Answer briefly (1-2 sentences)."""
        }
        
        messages = [
            {"role": "system", "content": explanation_prompt.get(language, explanation_prompt['ru'])},
            {"role": "user", "content": f"Original response: {original_response}\n\nNow explain it simpler:"}
        ]
        
        try:
            response = self.chat_sync(messages, temperature=0.5, max_tokens=150)
            return response.content
        except:
            return original_response


# Global LLM manager instance
llm_manager = LLMManager()