"""Complete physical log contract, with only path and elapsed-time variability."""
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def lines(raw):
    # Sealed native logs are ASCII. No replacement decoding, whitespace stripping,
    # blank-line removal, or substring error scanning substitutes for full identity.
    if isinstance(raw, bytes): raw=raw.decode('ascii',errors='strict')
    if not isinstance(raw,str): raise TypeError('log must be bytes or text')
    if '\x00' in raw: raise ValueError('NUL in log')
    return raw.splitlines()
def validate_log(raw,kind,expected_path):
    if kind not in ('import','export'): raise ValueError('unsupported log kind')
    if not isinstance(expected_path,str) or not expected_path or '\n' in expected_path or '\r' in expected_path:
        raise ValueError('invalid bound path')
    actual=lines(raw)
    template=lines((ROOT/'source-snapshots'/('parent-'+kind+'.log')).read_bytes())
    prefix='Importing data from Json file: ' if kind=='import' else 'Exporting data to Json file: '
    completion='Import' if kind=='import' else 'Export'
    if len(actual)!=len(template) or actual[:-1]!=[prefix+expected_path,*template[1:-1]]:
        raise ValueError('complete log body/path/line-count differs')
    if re.fullmatch(completion+r' completed! Time: (?:0|[1-9][0-9]*)\.[0-9]{2} secs',actual[-1]) is None:
        raise ValueError('invalid explicit completion/elapsed-time grammar')
    return dict(kind=kind,physical_lines=len(actual),full_body_verified=True,elapsed_only_variable=True)
