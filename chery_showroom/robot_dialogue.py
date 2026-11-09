"""Local, factual identity answers for the selected simulated platform."""
import re
import unicodedata

def respond(text,robot_model,language='en'):
    if robot_model!='maloni120':return None
    normalized=''.join(c for c in unicodedata.normalize('NFD',text.lower()) if not unicodedata.combining(c))
    # Movement and emergency intent always remains owned by the main controller.
    if re.search(r'\b(stop|halt|stuj|zastav\w*|jed|jdi|go|move|doprovod\w*|zaved\w*|ukaz\w*|pozdrav\w*|greet\w*)\b',normalized):return None
    if re.search(r'\b(robot|humanoid|maloni|kdo jsi|who are you|pohyb|chodis|walk|kola|wheels)\b',normalized):
        if language=='cs':return ('Jsem virtuální MALONI Humanoid 120. Návrh počítá s výškou 120 cm, dvěma hnacími koly, dvěma osami hlavy a třemi osami na každé paži. '
            'V showroomu používám vlastní simulaci kolového pohonu a mohu vás doprovodit k autům, odpovídat na dotazy a předvést lehká gesta. '
            'Jde o vývojovou simulaci s odhadnutými fyzikálními parametry; schopnosti fyzického prototypu zatím nejsou ověřené.')
        return ('I am the virtual MALONI Humanoid 120. The concept specifies a height of 120 cm, two powered wheels, two head axes and three axes per arm. '
            'In this showroom I use independent wheeled-drive dynamics, guide visitors to cars, answer questions and demonstrate light gestures. '
            'This is a development simulation with estimated physical parameters; hardware capabilities are not yet verified.')
    return None
