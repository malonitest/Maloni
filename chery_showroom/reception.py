"""Reception Q&A reuses the local catalogue dialogue, without locomotion commands."""
import threading
import copy
from .sales import Visit
from .layout import CARS
from .localization import localize


class ReceptionDesk:
    def __init__(self):
        self.lock = threading.Lock()
        self.run_id = None
        self.visit = Visit()

    def respond(self, value, run_id,language='en',context=None):
        text = value.get('text')
        car = value.get('car')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
            raise ValueError('Enter a question between 1 and 1000 characters.')
        if not isinstance(car, str) or car not in CARS:
            raise ValueError('Unknown car.')
        if value.get('run_id') != run_id:
            raise ValueError('The scene was reset; please send your question again.')
        with self.lock:
            if self.run_id != run_id:
                self.visit = Visit(); self.run_id = run_id
            if context is not None:
                # Read the same published visitor context without letting a
                # reception question execute movement from an HTTP thread.
                self.visit.needs=copy.deepcopy(context.get('needs',self.visit.needs))
                self.visit.topics=list(context.get('topics',[]))
            from .robot_dialogue import respond as robot_reply
            identity=robot_reply(text.strip(),(context or {}).get('robot_model'),language)
            if identity:return dict(reply=identity,car=car,run_id=run_id,language=language)
            reply, selected, action = self.visit.respond(text.strip(), car)
            if action:
                self.visit.cancel()
                self.visit.stage = 'consultation'
                reply = ('Conversation paused.' if action == 'stop' else
                         'Use the visit controls in the dashboard for escorting or movement. '
                         'Here at reception I can answer questions about the displayed cars.')
            return dict(reply=localize(reply,language), car=selected, run_id=run_id,language=language)
