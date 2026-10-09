import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .models import RepairRequest


class AIAnalysisError(Exception):
    pass


def analyze_repair_request(repair):
    prompt = (
        'You help dorm maintenance staff triage repair requests. '
        'Return only a JSON object with string fields summary_th, summary_en, category, urgency, reason_th, reason_en. '
        'summary_th must briefly restate the issue in natural Thai; summary_en must briefly restate it in natural English. '
        'category must be exactly one of electricity, plumbing, furniture, internet, other. '
        'urgency must be exactly one of urgent, normal, low. '
        'Use urgent for possible immediate safety hazards such as electric shock, fire, gas, '
        'major flooding, or structural danger. Do not give repair instructions. '
        'Otherwise choose normal or low based only on the stated impact. '
        'reason_th must briefly explain the suggestions in natural Thai; reason_en must explain them in natural English. '
        'These are suggestions for a human to verify, not decisions.\n\n'
        f'Title: {repair.title[:160]}\n'
        f'Current category: {repair.category}\n'
        f'Description: {repair.description[:8000]}'
    )
    payload = json.dumps({
        'model': settings.OLLAMA_MODEL,
        'prompt': prompt,
        'stream': False,
        'format': 'json',
        'options': {'temperature': 0},
    }).encode('utf-8')
    request = Request(
        f'{settings.OLLAMA_BASE_URL.rstrip("/")}/api/generate',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urlopen(request, timeout=120) as response:
            ollama_response = json.loads(response.read().decode('utf-8'))
        result = json.loads(ollama_response['response'])
    except HTTPError as error:
        raise AIAnalysisError(
            'Ollama could not analyze this request. Check that the selected model is installed.'
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise AIAnalysisError(
            'Could not connect to Ollama. Start Ollama and try again.'
        ) from error
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise AIAnalysisError(
            'Ollama returned an invalid analysis. Please try again.'
        ) from error

    if not isinstance(result, dict):
        raise AIAnalysisError('Ollama returned an invalid analysis. Please try again.')

    summary_th = result.get('summary_th')
    summary_en = result.get('summary_en')
    category = result.get('category')
    urgency = result.get('urgency')
    reason_th = result.get('reason_th')
    reason_en = result.get('reason_en')
    valid_categories = {value for value, _ in RepairRequest.Category.choices}
    valid_urgencies = {value for value, _ in RepairRequest.AIUrgency.choices}
    if (
        not isinstance(summary_th, str) or not summary_th.strip()
        or not isinstance(summary_en, str) or not summary_en.strip()
        or not isinstance(category, str) or category not in valid_categories
        or not isinstance(urgency, str) or urgency not in valid_urgencies
        or not isinstance(reason_th, str) or not reason_th.strip()
        or not isinstance(reason_en, str) or not reason_en.strip()
    ):
        raise AIAnalysisError('Ollama returned incomplete suggestions. Please try again.')

    return {
        'summary_th': summary_th.strip()[:2000],
        'summary_en': summary_en.strip()[:2000],
        'category': category,
        'urgency': urgency,
        'reason_th': reason_th.strip()[:2000],
        'reason_en': reason_en.strip()[:2000],
    }
