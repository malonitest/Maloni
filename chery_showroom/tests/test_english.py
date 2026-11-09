"""English dialogue preserves consent boundaries and grounded catalogue answers."""
import json
import unittest
from unittest.mock import MagicMock, patch

from chery_showroom.sales import Visit
from chery_showroom.voice import ShowroomProvider


class EnglishDialogueTests(unittest.TestCase):
    def test_family_advice_and_budget_skip(self):
        visit = Visit()
        self.assertIn('mainly use', visit.respond('Help me choose')[0])
        self.assertIn('How many', visit.respond('Family holidays')[0])
        self.assertIn('matters most', visit.respond('Four')[0])
        self.assertIn('budget', visit.respond('Space and comfort')[0])
        self.assertIn('understood', visit.respond('Skip')[0])
        self.assertIsNone(visit.needs['budget'])
        self.assertIn('not been verified', visit.respond('Yes')[0])
        self.assertIsNone(visit.activity, 'Family travel must not start the family game')
        visit.respond('Volvo XC60')
        self.assertEqual(visit.respond('Yes, please.')[2], 'escort')
        visit.arrived('tiggo7')
        self.assertEqual(visit.respond('Yes')[2], 'present')
        summary = visit.respond('Salesperson summary')[0]
        for expected in ('Family holidays', 'Four', 'Space and comfort', 'no booking'):
            self.assertIn(expected, summary)

    def test_questions_and_negations_never_authorise_motion(self):
        for text in ('Can you take me to BMW?', 'Show me BMW?', 'Do not show me BMW',
                     "Don't take me to Volvo", 'No, take me to BMW', 'Not to the car',
                     'What if I say take me to BMW?', 'Take me to Tiggo 4',
                     'Show me what you can do', 'Take me somewhere', 'Yes'):
            with self.subTest(text=text):
                self.assertIsNone(Visit().respond(text)[2])
        for text, selected in (('Escort me to BMW X1', 'tiggo4'),
                               ('Please take me to Volvo XC60', 'tiggo7'),
                               ('Show me CHERY Tiggo 8 Pro', 'tiggo8')):
            with self.subTest(text=text):
                _, car, action = Visit().respond(text)
                self.assertEqual((car, action), (selected, 'escort'))
        visit = Visit(); visit.select('tiggo8')
        self.assertIsNone(visit.respond('Yes?')[2], 'A question is not consent')

    def test_price_confirmation_is_a_summary_not_escort(self):
        visit = Visit(); visit.select('tiggo8')
        self.assertIn('verified current price', visit.respond('How much does it cost?')[0])
        reply, _, action = visit.respond('Yes')
        self.assertIn('no booking', reply)
        self.assertEqual(visit.stage, 'handoff')
        self.assertIsNone(action)

    def test_english_catalogue_games_and_refusal(self):
        visit = Visit()
        self.assertIn('teal', visit.respond('What colour is the CHERY?')[0])
        visit.respond('Compare the cars')
        comparison = visit.respond('BMW and Volvo')[0]
        self.assertIn('red', comparison); self.assertIn('silver', comparison)
        self.assertIn('without verified', comparison)
        self.assertIn('three questions', visit.respond('Car quiz')[0])
        visit.respond('A'); visit.respond('B')
        self.assertIn('3 out of three', visit.respond('A')[0])
        self.assertIn('Back to cars', visit.respond('Back to cars')[0])
        self.assertIn('adults', visit.respond('Family mini-game')[0])
        self.assertEqual(visit.activity, 'family')
        self.assertIn('human feelings', visit.respond('Do you have feelings?')[0])
        self.assertEqual(visit.respond('Robot greeting')[2], 'greet')
        self.assertEqual(visit.respond('I am just browsing')[2], 'stop')
        self.assertEqual(visit.mode, 'idle')
        self.assertIsNone(visit.activity)
        self.assertEqual(visit.respond('Halt')[2], 'stop')

    def test_english_voice_instructions_without_a_network_call(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'session': {'id': 'test-session'}, 'transport': {'sdp': 'test-answer'}
        }).encode()
        with patch('chery_showroom.voice.urlopen', return_value=response) as request:
            result = ShowroomProvider(key='test-key').create('test-offer', {'language': 'en'})
        body = json.loads(request.call_args.args[0].data)
        instructions = body['session']['instructions']
        self.assertIn('LOCAL_REPLY, in English', instructions)
        self.assertIn('local controller', instructions)
        self.assertEqual(body['transport']['sdp'], 'test-offer')
        self.assertEqual(result['session']['id'], 'test-session')
