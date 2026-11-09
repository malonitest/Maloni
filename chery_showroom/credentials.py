"""Reuse the existing Buddha launcher's credential location; never log secrets."""
import os
from pathlib import Path


def api_key():
    if os.environ.get('OPENAI_API_KEY','').strip():return os.environ['OPENAI_API_KEY'].strip()
    config=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))
    path=config/'humanoid-buddha/openai_api_key'
    try:return path.read_text().splitlines()[0].strip()
    except (OSError,IndexError):return ''
