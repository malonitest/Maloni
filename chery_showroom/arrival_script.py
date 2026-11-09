"""Existing arrival script and coordinates; no simulator dependency."""
import json
from pathlib import Path
import numpy as np
SCRIPT=json.loads(Path(__file__).with_name('arrival_script.json').read_text())
DURATION=float(SCRIPT['duration'])
HOST_START=np.array([5.0,-.6])
CUSTOMER_START=np.array([0.,-4.85])
CUSTOMER_WELCOME=np.array([3.3,-1.7])
