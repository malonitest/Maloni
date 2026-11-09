"""Shared Czech/English messages; internal dialogue decisions remain language-neutral."""
import hashlib
import json
import re
from pathlib import Path

CATALOG=json.loads(Path(__file__).with_name('messages.json').read_text())
LANGUAGES=('cs','en')
TEMPLATES=[]
for key,variants in CATALOG['messages'].items():
    pattern=re.escape(variants['en'])
    for name in re.findall(r'\{(\w+)\}',variants['en']):
        pattern=pattern.replace(re.escape('{'+name+'}'),'(?P<'+name+'>.+?)')
    TEMPLATES.append((key,re.compile(pattern),variants['cs']))
FRAGMENTS=CATALOG['fragments']
FRAGMENT_PATTERN=re.compile(r'https?://\S+|'+'|'.join(re.escape(k) for k in sorted(FRAGMENTS,key=len,reverse=True)))


def message(key,language='en',**values):
    if language not in LANGUAGES:raise ValueError('Unsupported language')
    return CATALOG['messages'][key][language].format(**values)


def localize(value,language='en'):
    if language=='en' or not isinstance(value,str):return value
    if language not in LANGUAGES:raise ValueError('Unsupported language')
    for _,pattern,translated in TEMPLATES:
        match=pattern.fullmatch(value)
        if match:return translated.format(**match.groupdict())
    # Compile templates once, but never cache customer text or preferences.
    return FRAGMENT_PATTERN.sub(lambda m:FRAGMENTS.get(m[0],m[0]),value)


def message_key(value):
    for key,pattern,_ in TEMPLATES:
        if pattern.fullmatch(value):return key
    return 'dialogue.'+hashlib.sha256(value.encode()).hexdigest()[:12]
