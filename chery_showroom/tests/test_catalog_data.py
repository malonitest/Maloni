import copy
import unittest
from chery_showroom.catalog_data import reference_facts
from chery_showroom.sales import Visit, car_entry


class CatalogDataTests(unittest.TestCase):
    def test_scoped_dimensions_and_seats(self):
        for text,number,market in [('What is the length of Volvo XC60?', '4708', 'NZ'),
                                   ('How many seats does CHERY Tiggo 8 Pro have?', 'seven', 'MY')]:
            reply,_,action=Visit().respond(text)
            self.assertIn(number,reply);self.assertIn(market,reply)
            self.assertIn('Source: https://',reply);self.assertIn('Czech',reply)
            self.assertIsNone(action)

    def test_facts_do_not_leak_to_other_models_or_commercial_answers(self):
        self.assertNotIn('4708',Visit().respond('What is the length of BMW X1?')[0])
        for text in ['How much does CHERY cost?', 'Is Volvo available?', 'What engine does the BMW have?']:
            reply,_,action=Visit().respond(text)
            self.assertIn('verif',reply);self.assertIsNone(action)

    def test_reject_mismatched_missing_and_future_evidence(self):
        original=car_entry('tiggo7')
        self.assertEqual(len(reference_facts(original)),1)
        for key,value in [('model_year',2024),('model','BMW X1 2013'),('verified','2999-01-01'),
                          ('verified',True),('source',''),('scope',''),('market','CZ;MY')]:
            car=copy.deepcopy(original);car['reference_facts'][0][key]=value
            self.assertEqual(reference_facts(car),[],key)


if __name__=='__main__':unittest.main()
