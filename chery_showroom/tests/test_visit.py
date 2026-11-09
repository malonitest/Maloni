"""Behavior acceptance scenarios: dialogue must never fabricate motion or car facts."""
import time
import unittest
from unittest.mock import patch
import numpy as np
from chery_showroom.sales import Visit, CATALOG
from chery_showroom.runtime import Showroom


class VisitTests(unittest.TestCase):
    def setUp(self):
        self.v=Visit()

    def test_family_visit_and_handoff(self):
        v=self.v
        v.start('advice')
        self.assertIn('How many',v.respond('Pro rodinu a na dovolenou')[0])
        self.assertIn('matters most',v.respond('Čtyři')[0])
        self.assertIn('budget',v.respond('Prostor a pohodlí')[0])
        self.assertIn('understood',v.respond('Přeskočit')[0])
        self.assertIn('not been verified',v.respond('Ano')[0])
        self.assertEqual(v.selected,'tiggo4')
        self.assertIn('Volvo',v.respond('Volvo XC60')[0])
        self.assertEqual(v.respond('Ano')[2],'escort')
        self.assertNotIn('We have reached',v.message)
        v.arrived('tiggo7')
        self.assertEqual(v.respond('Ano')[2],'present')
        v.present(20)
        self.assertIn('Volvo',v.message)
        v.respond('Porovnej vozy')
        v.respond('Zkušební jízda')
        summary=v.summary()
        for value in ('rodinu','Čtyři','pohodlí','not provided by the customer','comparison','test drive','booking'):
            self.assertIn(value,summary)

    def test_budget_and_priority_changes_do_not_rank_unverified_cars(self):
        v=self.v
        v.selected='tiggo7'
        v.respond('Mám rozpočet 800000')
        self.assertIn('800000',v.needs['budget'])
        v.respond('Raději je priorita pohodlí')
        self.assertIn('pohodlí',v.needs['priority'])
        self.assertEqual(v.selected,'tiggo7')
        self.assertIn('not been verified',v.message)
        for text in ('kolik stojí','jaká je výbava','jaký má výkon'):
            self.assertIn('verif',v.respond(text)[0])

    def test_decline_and_stop(self):
        self.v.activity_start('quiz',0)
        result=self.v.respond('Jen se rozhlížím')
        self.assertEqual(result[2],'stop')
        self.assertEqual(self.v.mode,'idle')
        self.assertIsNone(self.v.activity)
        self.assertIsNone(self.v.advance(1000))
        for text in ('Stop','Stůj','Prosím zastav'):
            self.v.activity_start('quiz',0)
            self.assertEqual(self.v.respond(text)[2],'stop')
            self.assertIsNone(self.v.activity)

    def test_no_motion_from_negated_speculative_or_unknown_commands(self):
        for text in ('Neukazuj mi auto','Nechci doprovod','Můžete mě doprovodit?',
                     'Ukaž mi co umíš','Zaveď mě k Tiggo 4','Doprovod mě někam',
                     'Co když řeknu doprovod mě k BMW?'):
            self.assertIsNone(Visit().respond(text)[2],text)
        for text in ('Doprovod mě k BMW X1','Zaveď mě k Volvo XC60','Ukaž mi CHERY Tiggo 8 Pro'):
            self.assertEqual(Visit().respond(text)[2],'escort',text)

    def test_quiz_answers_recovery_and_return(self):
        v=self.v
        v.select('tiggo8')
        v.activity_start('quiz',1)
        self.assertIn('rephrase',v.respond('nevím')[0])
        self.assertIn('panel',v.respond('netuším')[0])
        self.assertIn('speedometer',v.respond('B')[0])
        v.respond('B')
        self.assertIn('2 out of three',v.respond('A')[0])
        v.respond('Zpět k autům')
        self.assertEqual(v.selected,'tiggo8')
        self.assertEqual(v.mode,'tour')
        self.assertIsNone(v.activity)

    def test_family_riddle_robot_and_greeting(self):
        v=self.v
        self.assertIn('adults',v.activity_start('family',0)[0])
        v.respond('A');v.respond('B')
        self.assertIn('3 out of three',v.respond('A')[0])
        v.activity_start('riddle',0)
        self.assertIn('silver Volvo',v.respond('BMW')[0])
        self.assertIn('locomotion policy',v.respond('Jak chodí robot?')[0])
        self.assertIn('I do not have human feelings',v.respond('Máte pocity?')[0])
        self.assertEqual(v.respond('Robotický pozdrav')[2],'greet')
        self.assertIsNone(v.activity)

    def test_activity_and_quick_time_limits(self):
        v=self.v
        v.activity_start('quiz',0)
        self.assertIsNone(v.advance(119))
        self.assertIn('two-minute activity',v.advance(120)[0])
        self.assertIsNone(v.activity)
        v.start('quick',200)
        v.respond('Ano',now=201)
        self.assertEqual(v.advance(320)[2],'stop')
        self.assertIsNone(v.quick_started)

    def test_presentation_schedule_and_interruption(self):
        v=self.v
        v.present(10)
        self.assertIsNone(v.advance(29))
        self.assertIn('reference',v.advance(30)[0])
        self.assertIn('Would you like',v.advance(55)[0])
        self.assertIsNone(v.presentation)
        v.present(100)
        v.respond('Jaká je cena?')
        self.assertIsNone(v.presentation)
        self.assertIsNone(v.advance(200))

    def test_unknowns_and_reset_privacy(self):
        v=self.v
        self.assertIn('rephrase',v.respond('xyz')[0])
        self.assertIn('panel',v.respond('xyz')[0])
        v.needs['budget']='123456'
        snapshot=v.snapshot();snapshot['needs']['budget']='changed'
        self.assertEqual(v.needs['budget'],'123456')
        v.__init__()
        self.assertNotIn('123456',str(v.snapshot()))

    def test_price_consent_never_becomes_escort(self):
        v=self.v
        v.select('tiggo7')
        v.respond('Kolik stojí?')
        response=v.respond('Ano')
        self.assertIsNone(response[2])
        self.assertEqual(v.stage,'handoff')
        self.assertIn('booking',response[0])

    def test_compare_two_cars_and_resume_questionnaire(self):
        v=self.v
        v.respond('Porovnej vozy')
        result=v.respond('BMW a Volvo')[0]
        self.assertIn('red',result)
        self.assertIn('silver',result)
        self.assertNotIn('better value',result)
        v.start('advice');v.respond('Pro rodinu')
        v.start('entertainment');v.activity_start('quiz',0)
        self.assertIn('How many',v.respond('Zpět k autům')[0])
        self.assertEqual(v.stage,'passengers')
        v.respond('Čtyři')
        self.assertEqual(v.needs['passengers'],'Čtyři')

    def test_catalog_sources_belong_to_actual_models(self):
        for car,marker in zip(CATALOG['cars'],('bmw','volvo','chery')):
            self.assertIn(marker,car['source'].lower())
            self.assertEqual(car['verified_facts'],[])
            self.assertNotIn('cherymotor.cz',car['source'])
            self.assertIsNone(car['price'])


class ControllerVisitTests(unittest.TestCase):
    def setUp(self):
        self.app=Showroom()
        self.step(60)

    def tearDown(self):
        self.app.close()

    def step(self,n=1):
        for _ in range(n):
            self.app.last_client=time.monotonic();self.app.tick()
            self.assertFalse(self.app.sim.snapshot()['fallen'])

    def action(self,action,**kwargs):
        self.app.command(dict(action=action,**kwargs));self.step()

    def test_local_actions_quiz_stop_and_reset(self):
        a=self.app
        self.action('advice');self.action('chat',text='Pro rodinu')
        self.assertIn('rodinu',a.state['conversation']['needs']['use'])
        self.action('entertainment');self.action('chat',text='Kvíz')
        self.assertEqual(a.state['conversation']['activity'],'quiz')
        self.assertFalse(a.path)
        self.action('stop')
        self.assertIsNone(a.state['conversation']['activity'])
        old=a.run_id
        self.action('reset')
        self.assertNotEqual(a.run_id,old)
        self.assertTrue(all(x is None for x in a.state['conversation']['needs'].values()))
        self.assertNotIn('rodinu',a.message)

    def test_decline_route_failure_and_stale_activity(self):
        a=self.app
        self.action('chat',text='Jen se rozhlížím')
        self.assertEqual(a.state['conversation']['mode'],'idle')
        self.assertIn('Of course',a.message)
        with patch.object(a.navigator,'route',side_effect=ValueError('blocked')):
            self.action('escort',car='tiggo7')
        self.assertEqual(a.failure_code,'blocked')
        self.assertIn('Continue',a.message)
        self.assertNotIn('We have reached',a.message)
        self.assertFalse(a.path)
        self.action('reset');self.action('chat',text='Kvíz')
        a.last_client=time.monotonic()-3;a.tick()
        self.assertIsNone(a.visit.activity)
        self.assertIn('connection',a.message)

    def test_actual_walk_present_interrupt_and_reset(self):
        a=self.app
        self.action('select',car='tiggo7')
        self.action('present')
        self.assertFalse(a.gesture_until)
        self.assertIsNone(a.visit.presentation)
        self.action('chat',text='Ano')
        self.assertTrue(a.path)
        self.assertNotIn('We have reached',a.message)
        self.action('present')
        self.assertFalse(a.gesture_until)
        for _ in range(6000):
            self.step()
            if not a.path:break
        self.assertEqual(a.phase,'arrived',a.error)
        self.assertIn('Volvo',a.message)
        self.step(40)
        self.action('chat',text='Ano')
        self.assertIsNotNone(a.visit.presentation)
        self.assertTrue(a.gesture_until)
        self.action('chat',text='Jaká je cena?')
        self.assertFalse(a.gesture_until)
        self.assertIsNone(a.visit.presentation)
        self.assertIn('do not have a verified',a.message)
        self.action('present');self.action('reset')
        self.assertIsNone(a.visit.presentation)
        self.assertFalse(a.gesture_until)

    def test_game_and_handoff_interrupt_ongoing_walk(self):
        a=self.app
        self.action('escort',car='tiggo7')
        self.assertTrue(a.path)
        self.action('chat',text='Kvíz')
        self.assertFalse(a.path)
        self.assertEqual(a.visit.activity,'quiz')
        self.action('chat',text='Zpět k autům')
        self.action('escort',car='tiggo7')
        self.action('chat',text='Shrnutí pro prodejce')
        self.assertFalse(a.path)
        self.assertEqual(a.visit.stage,'handoff')

    def test_greeting_requires_standstill_and_stop_cancels(self):
        a=self.app
        self.action('greet')
        self.assertTrue(a.gesture_until)
        self.action('stop');self.assertFalse(a.gesture_until)
        self.action('escort')
        self.action('greet');self.assertFalse(a.gesture_until)
        self.assertIn('safe stop',a.message)
