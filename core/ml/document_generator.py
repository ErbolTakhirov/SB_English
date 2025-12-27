from typing import Dict

# transformers import removed from global scope to save memory
_HF_AVAILABLE = True # Assume available, check later
_MODEL_ID = 'sshleifer/tiny-gpt2'
_tokenizer = None
_model = None


def _lazy_load():
    global _tokenizer, _model, _HF_AVAILABLE
    
    if _tokenizer is not None and _model is not None:
        return True
        
    try:
        # Import ONLY when actually needed
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        
        if _tokenizer is None:
            _tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
        if _model is None:
            _model = AutoModelForCausalLM.from_pretrained(_MODEL_ID)
        return True
    except Exception:
        _HF_AVAILABLE = False
        return False


def _fallback_template(doc_type: str, params: Dict[str, str]) -> str:
    client = params.get('client', 'Клиент')
    total = params.get('total', '0')
    details = params.get('details', '')
    if doc_type == 'invoice':
        return f"Счет на оплату\nПлательщик: {client}\nСумма: {total}\nНазначение: {details}\n"
    if doc_type == 'act':
        return f"Акт выполненных работ\nЗаказчик: {client}\nСумма: {total}\nДетали: {details}\n"
    return f"Договор\nСтороны: {client} и Исполнитель\nСумма: {total}\nПредмет: {details}\n"


def generate_document_text(doc_type: str, params: Dict[str, str]) -> str:
    prompt = (
        f"Сгенерируй {doc_type} на русском языке. Клиент: {params.get('client','')}. "
        f"Сумма: {params.get('total','')}. Детали: {params.get('details','')}\n"
        "Текст: "
    )
    if _lazy_load():
        try:
            input_ids = _tokenizer.encode(prompt, return_tensors='pt')
            out = _model.generate(input_ids, max_new_tokens=80, do_sample=True, top_k=50, top_p=0.95)
            text = _tokenizer.decode(out[0], skip_special_tokens=True)
            return text
        except Exception:
            pass
    return _fallback_template(doc_type, params)

