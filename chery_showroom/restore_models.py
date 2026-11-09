"""Fetch only missing pinned GLBs and verify hashes. Never executes downloaded code."""
import argparse,hashlib,json
from urllib.request import urlopen
from .library_models import LIBRARY

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for item in json.loads((LIBRARY/'provenance.json').read_text())['models']:
        path=LIBRARY/item['file']
        if not path.exists():
            if args.check:raise SystemExit('Missing '+str(path))
            with urlopen(item['library_url'],timeout=60) as response:raw=response.read()
            if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise SystemExit('Checksum mismatch: '+path.name)
            path.write_bytes(raw)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('Local model modified: '+path.name)
        print(path.name+' OK')
if __name__=='__main__':main()
