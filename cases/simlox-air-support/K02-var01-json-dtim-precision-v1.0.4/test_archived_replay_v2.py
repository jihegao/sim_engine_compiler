"""Regressions for the two concrete PR556 delivery defects; no native calls."""
import unittest
from pathlib import Path,PureWindowsPath
from replay_archived_native01_v2 import strict_json,validate_log_bytes
ROOT=Path(__file__).resolve().parent

class ArchivedLogBytes(unittest.TestCase):
    def test_actual_logs_and_terminator_rejections(self):
        contract=strict_json((ROOT/'contract.json').read_bytes())
        physical=PureWindowsPath(contract['candidate']['physical_directory'])
        run=ROOT/'runs/k02-json-dtim-v104-ssh-20261018-01'
        for copy in ('original','recovered'):
            for kind,name in (('import','input.json'),('export','roundtrip-raw.json')):
                raw=(run/copy/(kind+'.log')).read_bytes()
                bound=str(physical/name)
                with self.subTest(copy=copy,kind=kind,variant='exact accepted raw'):
                    self.assertTrue(validate_log_bytes(ROOT,raw,kind,bound)['log_bytes_verified'])
                for variant,changed in (
                    ('all LF',raw.replace(b'\r\n',b'\n')),
                    ('mixed endings',raw.replace(b'\r\n',b'\n',1)),
                    ('missing final CRLF',raw[:-2]),
                    ('extra final CRLF',raw+b'\r\n'),
                ):
                    with self.subTest(copy=copy,kind=kind,variant=variant):
                        with self.assertRaises(ValueError):validate_log_bytes(ROOT,changed,kind,bound)
                with self.subTest(copy=copy,kind=kind,variant='body byte mismatch'):
                    with self.assertRaises(ValueError):validate_log_bytes(ROOT,raw.replace(b'completed!',b'completed?',1),kind,bound)
                with self.subTest(copy=copy,kind=kind,variant='wrong physical path'):
                    with self.assertRaises(ValueError):validate_log_bytes(ROOT,raw,kind,bound+'-wrong')

if __name__=='__main__':unittest.main(verbosity=2)
