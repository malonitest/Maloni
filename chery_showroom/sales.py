"""Local English visit dialogue, retaining Czech input aliases and validated actions."""
import copy
import json
import re
import unicodedata
from pathlib import Path
from .catalog_data import reference_reply

CATALOG = json.loads(Path(__file__).with_name('catalog.json').read_text())
WELCOME = ('Hello, welcome to MALONI Robotics. I am your robotic guide. '
           'Would you like to explore the cars, get help choosing, or learn about robots?')
QUIZ = (
    ('What does ABS mean? A: anti-lock braking system. B: automatic parking.', 'a',
     'ABS helps prevent the wheels from locking during braking.'),
    ('What does a speedometer measure? A: fuel level. B: vehicle speed.', 'b',
     'A speedometer shows vehicle speed.'),
    ('What helps a robot balance? A: sensor feedback. B: random movements.', 'a',
     'The controller adjusts movement using sensor feedback.'),
)
FAMILY = (
    ('Where do we sit with a seat belt in a car? A: on a seat. B: on the roof.', 'a', 'The correct place is on a seat.'),
    ('What does a car use to travel on the road? A: skis. B: wheels.', 'b', 'A car travels on wheels.'),
    ('What colour is the BMW on display? A: red. B: green.', 'a', 'The BMW model on display is red.'),
)
ENTERTAINMENT = ('Would you like a car quiz, a riddle about a displayed car, a family mini-game, '
                 'a robotic greeting, or to ask about how a robot works?')


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def car_entry(selected):
    return next(c for c in CATALOG['cars'] if c['id'] == selected)


def mentioned_car(text):
    for c in CATALOG['cars']:
        if any(re.search(r'\b' + re.escape(normalized(a)) + r'\b', text) for a in c['aliases']):
            return c['id']
    return None


def is_stop(text):
    return bool(re.search(r'\b(stop|halt|stuj|zastav(?:te)?)\b', normalized(text)))


def is_yes(text):
    return normalized(text).strip().rstrip('.!') in ('ano', 'jo', 'prosim', 'chci', 'muzeme', 'spravne', 'presne',
        'yes', 'yes please', 'yes, please', 'yes thank you', 'yes, thank you',
        'please', 'sure', 'okay', 'ok', 'correct', 'that is correct')


def is_no(text):
    return normalized(text).strip().rstrip('.!') in ('ne', 'no', 'no thanks', 'no, thanks', 'no thank you', 'no, thank you')


def visual_description(selected):
    c = car_entry(selected)
    return f"{c['display_model']}. {c['appearance']['description']}"


def product_reply(selected):
    c = car_entry(selected)
    # Only individually sourced, market-tagged and dated facts may enter product speech.
    facts = [f['text'] for f in c.get('verified_facts', [])
             if f.get('source') and f.get('verified') and f.get('market') == CATALOG['market']][:3]
    return (visual_description(selected) + ' ' + (' '.join(facts) if facts else
            'I do not have verified technical details for this specification; a salesperson can provide them.'))


class Visit:
    """Session-local conversation, deliberately independent of locomotion phase."""
    def __init__(self):
        self.mode = 'welcome'
        self.stage = 'welcome'
        self.needs = {'use': None, 'passengers': None, 'priority': None, 'budget': None}
        self.topics = []
        self.activity = None
        self.activity_started = None
        self.activity_index = 0
        self.score = 0
        self.resume = None
        self.return_stage = None
        self.comparison_first = None
        self.misses = 0
        self.presentation = None
        self.presentation_started = None
        self.presentation_index = 0
        self.quick_started = None
        self.selected = 'tiggo4'
        self.message = WELCOME
        self.serial = 0

    def say(self, text, action=None):
        self.message = text
        self.serial += 1
        self.misses = 0
        return text, self.selected, action

    def snapshot(self):
        return dict(mode=self.mode, stage=self.stage, needs=copy.deepcopy(self.needs),
                    topics=list(self.topics), activity=self.activity,
                    activity_index=self.activity_index, score=self.score,
                    presentation_active=self.presentation is not None,
                    message_id=self.serial, handoff=self.summary())

    def summary(self):
        labels = {'use': 'Intended use', 'passengers': 'Number of passengers',
                  'priority': 'Priority', 'budget': 'Budget'}
        lines = [f'{label}: {self.needs[key] or "not provided by the customer"}.' for key, label in labels.items()]
        lines.append('Selected display model: ' + car_entry(self.selected)['display_model'] + '.')
        if self.topics:
            lines.append('Interests: ' + ', '.join(self.topics) + '.')
        lines.append('The summary is ready to share; no booking has been made and no salesperson has been contacted.')
        return '\n'.join(lines)

    def cancel(self):
        self.activity = None
        self.activity_started = None
        self.presentation = None
        self.presentation_started = None
        self.quick_started = None

    def interrupted(self, message):
        self.cancel()
        self.stage = 'paused'
        return self.say(message)

    def select(self, selected):
        self.selected = selected
        self.cancel()
        self.mode, self.stage = 'tour', 'offer_escort'
        return self.say(visual_description(selected) + ' Would you like to take a closer look?')

    def start(self, mode, now=0):
        if mode == 'entertainment' and self.mode != 'entertainment':
            self.resume = (self.mode, self.stage)
        self.cancel()
        self.mode = mode
        if mode == 'advice':
            self.stage = 'use'
            return self.say('What will you mainly use the car for?')
        if mode == 'quick':
            self.stage = 'offer_escort'
            self.quick_started = now
            return self.say('I can offer a two-minute tour of the selected car. ' +
                            visual_description(self.selected) + ' Would you like to take a closer look at it?')
        self.stage = 'choose_activity'
        return self.say(ENTERTAINMENT)

    def recommendation(self):
        self.mode, self.stage = 'advice', 'offer_escort'
        return self.say('I can show you the displayed models and their appearance. The information needed for '
                        'a reliable recommendation has not been verified. A salesperson can provide it. '
                        'Would you like to choose the BMW X1, Volvo XC60 or CHERY Tiggo 8 Pro?')

    def needs_summary(self):
        n = self.needs
        return ('Let me check: intended use ' + (n['use'] or 'not provided') + ', number of passengers ' +
                (n['passengers'] or 'not provided') + ', priorities ' + (n['priority'] or 'not provided') +
                ', budget ' + (n['budget'] or 'not provided') + '. Have I understood correctly?')

    def topic(self, name):
        if name not in self.topics:
            self.topics.append(name)

    def activity_start(self, kind, now):
        if self.mode != 'entertainment':
            self.resume = (self.mode, self.stage)
        self.presentation = None
        self.mode, self.stage = 'entertainment', 'playing'
        self.activity, self.activity_started = kind, now
        self.activity_index = self.score = 0
        if kind in ('quiz', 'family'):
            question = (QUIZ if kind == 'quiz' else FAMILY)[0][0]
            return self.say(('There are three questions. Just answer A or B. ' if kind == 'quiz' else
                             'This short game is for families with children accompanied by adults. ') + question)
        if kind == 'riddle':
            return self.say('Riddle: the displayed car is silver and its brand starts with V. Which car is it?')
        return self.say('I can explain walking, balance or sensors. What would you like to know?')

    def return_to_cars(self):
        self.cancel()
        self.mode, self.stage = self.resume or ('tour', 'offer_escort')
        self.resume = None
        prompts={'use':'What will you mainly use the car for?',
                 'passengers':'How many people usually travel with you?',
                 'priority':'Which matters most: space, running costs or comfort?',
                 'budget':'Would you like to give an approximate budget? You can skip this question.',
                 'confirm':self.needs_summary()}
        question=prompts.get(self.stage,'Would you like to take a closer look at the selected car?')
        if self.stage not in prompts:self.stage='offer_escort'
        return self.say('Back to cars. The selected model is ' + car_entry(self.selected)['display_model'] +
                        '. '+question)

    def arrived(self, selected=None):
        if selected:
            self.selected = selected
            self.stage = 'at_vehicle'
            return self.say('We have reached the presentation area for the ' +
                            car_entry(selected)['display_model'] + '. Would you like a short introduction?')
        return self.say('Destination reached. We can continue our conversation here.')

    def present(self, now):
        self.stage = 'presenting'
        self.presentation_started, self.presentation_index = now, 0
        self.presentation = [
            'In front of us is the ' + product_reply(self.selected),
            'This car is a reference 3D model in an independent MALONI Robotics demonstration. '
            'A salesperson can confirm the current price, availability and specifications.',
            'Would you like to focus on appearance, compare the displayed cars, or prepare questions for a salesperson?',
        ]
        return self.say(self.presentation[0])

    def advance(self, now):
        if self.activity and now - self.activity_started >= 120:
            result = self.return_to_cars()
            return self.say('The two-minute activity is now over. ' + result[0])
        if self.quick_started is not None and now - self.quick_started >= 120:
            self.cancel()
            self.stage = 'consultation'
            return self.say('The two-minute tour has ended. Would you like a summary for a salesperson?', 'stop')
        if self.presentation:
            elapsed = now - self.presentation_started
            index = 2 if elapsed >= 45 else (1 if elapsed >= 20 else 0)
            if index > self.presentation_index:
                self.presentation_index = index
                text = self.presentation[index]
                if index == 2:
                    self.presentation = None
                    self.stage = 'consultation'
                return self.say(text)
        return None

    def respond(self, text, selected=None, now=0):
        if selected:
            self.selected = selected
        t = normalized(text).strip()
        if is_stop(t):
            self.cancel()
            self.stage = 'paused'
            return self.say('Stopping movement, gestures and the current activity.', 'stop')
        if re.search(r"\b(jen se rozhlizim|nechte me|nemam zajem|nechci nic|just looking|just browsing|not interested|leave me alone)\b", t):
            self.cancel()
            self.mode, self.stage = 'idle', 'idle'
            return self.say('Of course. I will be at reception if you need anything.', 'stop')
        # Every new utterance interrupts the timed presentation immediately.
        if self.presentation is not None:
            self.presentation = None
            self.stage = 'consultation'
        if self.stage == 'choose_activity' and self.resume and is_yes(t):
            return self.return_to_cars()
        if any(s in t for s in ('zpet k aut', 'zpet k voz', 'konec hry', 'ukonci hru', 'back to cars', 'back to the cars', 'end the game', 'quit the game')):
            return self.return_to_cars()
        if any(s in t for s in ('shrnuti', 'prodejc', 'zkusebni jizd', 'konzultaci', 'summary', 'salesperson', 'dealer', 'test drive')):
            if 'jizd' in t or 'test drive' in t:
                self.topic('test drive information')
            self.cancel()
            self.stage = 'handoff'
            return self.say(self.summary())
        if self.stage == 'offer_handoff' and is_yes(t):
            self.topic('questions for a salesperson');self.cancel();self.stage='handoff'
            return self.say(self.summary())
        if self.stage == 'offer_handoff' and is_no(t):
            self.stage=self.return_stage or 'welcome'
            return self.say('Understood. Would you like to talk about cars or robots?')
        if re.search(r'\b(cena|cenu|ceny|stoji|skladem|sleva|slevu|dostupnost|price|cost|discount|availability|available|in stock)\b', t) or 'kolik stoji' in t or 'how much' in t:
            self.topic('current price and availability')
            self.return_stage=self.stage;self.stage='offer_handoff'
            return self.say('I do not have a verified current price, discount or stock availability for this version. '
                            'Would you like me to prepare a question for a salesperson?')
        if 'umite ridit' in t or 'can you drive' in t:
            return self.say('Today I can guide you around the showroom. I will leave the driving seat to you.')
        if 'pozdrav' in t or 'zamavej' in t or 'greeting' in t or re.fullmatch(r'(?:please )?wave[.!]?', t):
            self.cancel()
            return self.say('Hello from MALONI Robotics! I would be happy to guide you through cars and robotics.', 'greet')
        if 'kviz' in t or 'quiz' in t:
            return self.activity_start('quiz', now)
        if 'hadank' in t or 'poznej auto' in t or 'riddle' in t or 'guess the car' in t:
            return self.activity_start('riddle', now)
        if any(s in t for s in ('rodinna hra', 'minih', 'hra pro deti', 'family game', 'family mini-game', 'mini-game', 'game for children')):
            return self.activity_start('family', now)
        if 'zabav' in t or 'activities' in t or 'entertainment' in t:
            if self.mode != 'entertainment':
                self.resume = (self.mode, self.stage)
            return self.start('entertainment', now)
        if self.activity in ('quiz', 'family'):
            choice = re.fullmatch(r'(?:moznost |odpoved |option |answer )?([ab])[.!?]?', t)
            if choice:
                questions = QUIZ if self.activity == 'quiz' else FAMILY
                _, correct, explanation = questions[self.activity_index]
                right = choice[1] == correct
                self.score += int(right)
                self.activity_index += 1
                prefix = ('Exactly. ' if right else 'Thank you for your answer. ') + explanation
                if self.activity_index == len(questions):
                    score = self.score
                    self.activity = None
                    self.stage = 'choose_activity'
                    return self.say(prefix + f' Finished: {score} out of three correct. Would you like to return to the cars?')
                return self.say(prefix + ' ' + questions[self.activity_index][0])
        if self.activity == 'riddle' and mentioned_car(t):
            right = mentioned_car(t) == 'tiggo7'
            self.activity = None
            self.stage = 'choose_activity'
            return self.say(('Exactly! ' if right else 'Thank you for your guess. ') +
                            'It is the silver Volvo XC60 on display. Would you like to return to the cars?')
        if any(s in t for s in ('robot', 'rovnovah', 'senzor', 'jak chod', 'pocity', 'balance', 'sensor', 'feelings')):
            if self.mode != 'entertainment':
                self.resume = (self.mode, self.stage)
            self.activity_start('robot', now) if self.activity != 'robot' else None
            if 'pocit' in t or 'feelings' in t:
                return self.say('I do not have human feelings. I am a robotic assistant controlled by software. What would you like to know about how I work?')
            return self.say('In this simulation I am controlled by a locomotion policy. It receives joint positions, '
                            'body movement and orientation, and continuously adjusts the controls. The panel camera is for you; '
                            'I do not recognise customers through it in this version. What else would you like to know?')
        if 'porad' in t or 'vyberem' in t or 'help me choose' in t or (any(s in t for s in ('hledam auto', 'looking for a car', 'looking for a family car')) and self.stage not in ('use','passengers','priority','budget')):
            return self.start('advice', now)
        if any(s in t for s in ('rychla prohlidka', 'rychlou prohlidku', 'dvouminut', 'quick tour', 'two-minute tour')):
            return self.start('quick', now)
        if any(s in t for s in ('dobry den', 'ahoj', 'zacit rozhovor', 'hello', 'good morning', 'good afternoon', 'start a conversation')) or t in ('hi', 'hi!'):
            self.stage = 'welcome'
            return self.say(WELCOME)
        if 'porovn' in t or 'srovn' in t or 'rozdil' in t or 'compare' in t or 'difference' in t:
            self.topic('car comparison')
            self.stage='compare';self.comparison_first=None
            names = ', '.join(c['display_model'] for c in CATALOG['cars'])
            return self.say('Displayed models: ' + names + '. I can compare their appearance; '
                            'I cannot assess technical differences, prices or value without verified information. '
                            'Which two cars would you like to compare?')
        explicit = mentioned_car(t)
        matches=[c['id'] for c in CATALOG['cars'] if any(
            re.search(r'\b'+re.escape(normalized(alias))+r'\b',t) for alias in c['aliases'])]
        if self.stage=='compare' and matches:
            pair=list(dict.fromkeys(([self.comparison_first] if self.comparison_first else [])+matches))[:2]
            if len(pair)==1:
                self.comparison_first=pair[0]
                return self.say('The first car is '+car_entry(pair[0])['display_model']+'. Which second car would you like to compare?')
            self.topic('comparison: '+' and '.join(car_entry(k)['display_model'] for k in pair))
            self.stage='welcome'
            return self.say(' '.join(visual_description(k) for k in pair)+
                            ' I cannot compare specifications or value without verified information. Would you like a summary for a salesperson?')
        # Never reinterpret a question, negation or speculative sentence as motion consent.
        negative = bool(re.search(r"\b(ne|nechci|neukazuj|nechod|nedoprovazej|no|not|don't|dont|do not)\b", t))
        if explicit and not negative:
            self.selected = explicit
            self.mode, self.stage = 'tour', 'offer_escort'
        motion = re.fullmatch(r'(?:prosim )?(?:doprovod(?:te)?(?: me)?|zaved(?:te)?(?: me)?|ukaz(?:te)?(?: mi)?|pojdme)(.*)', t)
        if motion is None:
            motion = re.fullmatch(r"(?:please )?(?:escort me|take me|lead me|show me|let's go)(.*)", t)
        if not negative and motion:
            destination = motion[1].strip(' .!')
            generic = destination in ('', 'k autu', 'k vozu', 'auto', 'vuz', 'vybrane auto', 'k vybranemu vozu', 'to the car', 'the car', 'to the selected car', 'the selected car')
            target = re.sub(r'^(?:k |ke |to )?(?:the )?(?:vozu |autu |car |vehicle )?', '', destination)
            exact = any(normalized(alias) == target for c in CATALOG['cars'] for alias in c['aliases'])
            if generic or exact:
                self.activity=None;self.presentation=None
                self.stage = 'escort_requested'
                return self.say('I will request an escort to the ' + car_entry(self.selected)['display_model'] + '.', 'escort')
            return self.say('Please specify the car: BMW X1, Volvo XC60 or CHERY Tiggo 8 Pro.')
        if self.stage == 'offer_escort' and is_yes(t):
            self.stage = 'escort_requested'
            return self.say('I will request an escort to the selected car.', 'escort')
        reference=reference_reply(car_entry(explicit or self.selected),t)
        if reference:
            if explicit:self.selected=explicit
            self.topic('question: '+text.strip())
            return self.say(reference)
        if any(s in t for s in ('technick', 'vybav', 'dojezd', 'vykon', 'spotreb', 'mist ma', 'specification', 'equipment', 'range', 'power', 'engine', 'fuel consumption', 'seats', 'dimension', 'length', 'width', 'height', 'rozmer', 'dlouh', 'delka', 'sedadel')):
            if explicit:self.selected=explicit
            self.topic('question: '+text.strip())
            self.return_stage=self.stage;self.stage='offer_handoff'
            return self.say('I do not have verified technical details for this specification. May I add your question to the salesperson summary?')
        if explicit and not negative:
            quick=self.quick_started
            result=self.select(explicit)
            self.quick_started=quick
            return result
        if (self.stage == 'at_vehicle' and is_yes(t)) or re.fullmatch(r'(?:prosim )?(predstav(?:te)?(?: mi)?(?: vuz| auto)?|prezentace)', t) or t in ('presentation', 'present the car', 'introduce the car'):
            return self.say('I will check our position and make sure we have stopped before the presentation.', 'present')
        if negative and self.stage != 'budget' and self.stage != 'confirm':
            return self.say('Understood. Would you like to ask more questions or end the conversation?')
        # Explicit changes may be made even after the questionnaire or a game.
        change = re.search(r'(?:zmen(?:a|it|te)?|radeji|nove|change|prefer|instead)\b', t)
        budget = re.search(r'\b(?:rozpocet|rozpoc|maximalne|limit|budget|maximum)\w*\s*(?:je|mam|do|na|is|of|up to)?\s*(\d[\d\s.,]*(?:tisic|tis|milionu|milion|mil|thousand|million)?(?:\s*(?:kc|czk|eur|usd))?)', t)
        if budget:
            self.needs['budget'] = budget[1].strip()
            if self.stage != 'budget':
                return self.recommendation()
        if change and ('priorit' in t or any(s in t for s in ('prostor', 'pohodl', 'naklad', 'space', 'comfort', 'running costs'))):
            self.needs['priority'] = text.strip()
            return self.recommendation()
        if change and any(s in t for s in ('rodin', 'mest', 'family', 'city')):
            self.needs['use'] = text.strip()
            return self.recommendation()
        if self.stage in ('use', 'passengers', 'priority', 'budget'):
            key = self.stage
            if not (key == 'budget' and any(s in t for s in ('neuved', 'preskoc', 'nevim', 'nechci', 'skip', 'not sure', 'prefer not', 'rather not'))):
                self.needs[key] = text.strip()
            next_stage = {'use': 'passengers', 'passengers': 'priority', 'priority': 'budget', 'budget': 'confirm'}[key]
            self.stage = next_stage
            prompts = {'passengers': 'How many people usually travel with you?',
                       'priority': 'Which matters most: space, running costs or comfort?',
                       'budget': 'Would you like to give an approximate budget? You can skip this question.',
                       'confirm': self.needs_summary()}
            return self.say(prompts[next_stage])
        if self.stage == 'confirm' and is_yes(t):
            return self.recommendation()
        if self.stage == 'confirm' and is_no(t):
            self.stage = 'use'
            return self.say('Let us clarify. What will you mainly use the car for?')
        if self.mode == 'idle':
            return self.say('I am here if you would like advice or a quiz.')
        if any(s in t for s in ('vzhled', 'co je vystav', 'jaky model', 'jake auto', 'appearance', 'colour', 'color', 'on display', 'which model', 'what car')):
            return self.say(visual_description(self.selected) + ' Would you like to compare its appearance with another displayed car?')
        self.misses += 1
        if self.misses == 1:
            self.message = 'I did not quite understand. Could you rephrase that?'
        else:
            self.message = 'Please choose an option in the panel: Help me choose, Quick tour, Activities or Salesperson summary.'
        self.serial += 1
        return self.message, self.selected, None


def answer(text, selected):
    """Compatibility for callers without a visit. Runtime always retains Visit."""
    return Visit().respond(text, selected)
