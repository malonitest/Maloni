"""Reuse the existing Live provider's transport and hangup, with showroom context."""
import json
import os
from urllib.parse import quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

class ShowroomProvider:
    def __init__(self,key=None):self.key=key if key is not None else os.environ.get('OPENAI_API_KEY','')
    @property
    def configured(self):return bool(self.key)
    def hangup(self,session_id):
        if not session_id or not self.key:return
        request=Request('https://api.openai.com/v1/live/sessions/'+quote(session_id,safe='')+'/hangup',
            data=b'{}',headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=8) as response:response.read()
        except (OSError,HTTPError,URLError):return

    def create(self,sdp,context):
        if not self.configured:raise ValueError('Set OPENAI_API_KEY and restart the showroom to enable cloud conversation.')
        instructions=('You are the friendly, professional English-speaking host of MALONI Robotics. Use short, polite sentences. '
          'Visitors include adults and families; activities are optional and refusals must be respected without pressure. '
          'The local controller manages conversation, needs, games, summaries and movement. You are its voice interface. '
          'The controller processes the user transcript; do not answer independently or start your own quiz. '
          'Speak only the latest message marked LOCAL_REPLY, in the language selected in the controller context; do not add questions or claims. '
          'Do not finish an older reply after interruption. Stop interrupts movement, gestures and activities. '
          'Never guess car specifications, recommend based on legacy IDs tiggo4/7/8, or confirm bookings. '
          'Only the actual controller state confirms arrival and gestures. You have no direct video input, '
          'do not recognise people and have no human feelings. You do not represent car manufacturers. '
          'Connection context: '+json.dumps(context,ensure_ascii=False))
        data=dict(session=dict(model='gpt-live-1',instructions=instructions,store=False,audio={'output':{'voice':'marin'}}),transport=dict(type='webrtc',sdp=sdp))
        req=Request('https://api.openai.com/v1/live/sessions',data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=25) as response:result=json.load(response)
        except HTTPError as exc:raise RuntimeError(f'The voice service rejected the connection (HTTP {exc.code}).') from None
        except (URLError,OSError,TimeoutError):raise RuntimeError('The voice service is unavailable. Text mode still works.') from None
        if not isinstance(result.get('session',{}).get('id'),str) or not isinstance(result.get('transport',{}).get('sdp'),str):raise RuntimeError('Invalid response from the voice service.')
        return result
