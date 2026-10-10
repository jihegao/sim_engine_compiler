import json,sys,argparse
from pathlib import Path
from author_reader_method_v1 import controls,validate
from check_model import parse
O=Path(__file__).resolve().parent
if __name__=='__main__':
 try:
  if sys.argv[1:]==['--self-check']:
   d=controls();checks={x['name']:x['rejected'] for x in d['full_comparator_negatives']+d['direct_start_ledger_negatives']};r={'decision':'GO_AUTHOR_METHOD_CONTROLS_ONLY','checks':checks,'checks_total':len(checks),'native_calls':0,'details':d}
  else:
   ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['child'],required=True);ap.add_argument('--model-log',required=True);ap.add_argument('--report',required=True);a=ap.parse_args();log=Path(a.model_log);r={'decision':'GO_AUTHOR_RAW_REPLAY','full_typed_report_and_log_passed':True,'arm':'child','details':validate(log.read_bytes(),parse(a.report),parse(log.parent/'roundtrip-raw.json'))}
 except Exception as e:print(json.dumps({'decision':'NO_GO_AUTHOR','error':type(e).__name__+': '+str(e)}));sys.exit(1)
 print(json.dumps(r))
