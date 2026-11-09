"""Individually sourced reference facts; never infer a Czech sales specification."""
from datetime import date
import re
from urllib.parse import urlsplit

TOPICS = {
    'dimensions': r'\b(dimensions?|length|width|height|rozmery|delka|delku|sirka|sirku|vyska|vysku)\b|jak.{0,8}dlouh',
    'seats': r'\b(seats?|passengers|mist|mistne|sedadel|sedadla)\b',
}


def reference_facts(car):
    accepted=[]
    for fact in car.get('reference_facts', []):
        try:
            verified=date.fromisoformat(fact['verified'])
            model_year=fact['model_year']
            valid=(verified<=date.today() and model_year==car.get('model_year') and
                   fact['model']==car['display_model'] and fact['topic'] in TOPICS and
                   re.fullmatch('[A-Z]{2}',fact['market']) and
                   urlsplit(fact['source']).scheme=='https' and urlsplit(fact['source']).netloc and
                   isinstance(fact['text'],str) and bool(fact['text'].strip()) and
                   isinstance(fact['scope'],str) and bool(fact['scope'].strip()))
            if valid:accepted.append(fact)
        except (KeyError,TypeError,ValueError):
            continue
    return accepted


def reference_reply(car, normalized_question):
    topics=[key for key, pattern in TOPICS.items() if re.search(pattern, normalized_question)]
    facts=[fact for fact in reference_facts(car) if fact['topic'] in topics]
    if not facts:return None
    return ' '.join(f"{car['display_model']}: {f['text']} Reference: {f['scope']} "
                    f"({f['market']}, model year {f['model_year']}; checked {f['verified']}). "
                    f"Source: {f['source']}" for f in facts[:2]) + (
        ' These reference figures do not verify the trim of the displayed 3D asset or a Czech sales offer.')
