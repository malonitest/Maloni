"""Compare real captures from ambience.cjs; catches cumulative reflection dimming."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def compare(directory):
    def read(name):
        with Image.open(directory / name) as image:
            return np.asarray(image.convert('RGB'), dtype=np.float32)

    reference = read('day-original.png')
    results = {}
    for name in ['day-return-1.png', 'day-return-2.png', 'evening-1.png']:
        actual = read(name)
        if actual.shape != reference.shape:
            raise AssertionError('Comparison requires the same camera and canvas size')
        results[name] = {
            'meanAbsoluteRGB': float(np.abs(actual - reference).mean()),
            'relativeMeanRGB': float(actual.mean() / reference.mean()),
        }
    (directory / 'roundtrip-comparison.json').write_text(json.dumps(results, indent=2))
    # Permit small driver/PMREM rounding differences, but no accumulating loss of light.
    for name in ['day-return-1.png', 'day-return-2.png']:
        assert results[name]['meanAbsoluteRGB'] < 1, results
    assert results['evening-1.png']['meanAbsoluteRGB'] > 5, results
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / 'assets/review/gallery/atmospheres'
    compare(directory)
