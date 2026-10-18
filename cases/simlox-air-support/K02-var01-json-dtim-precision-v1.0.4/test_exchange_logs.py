import unittest
from pathlib import Path
from exchange_logs import validate_log,lines
ROOT=Path(__file__).parent
class LogControls(unittest.TestCase):
    def fixture(self,kind):
        data=lines((ROOT/'source-snapshots'/('parent-'+kind+'.log')).read_bytes())
        data[0]=('Importing data from Json file: ' if kind=='import' else 'Exporting data to Json file: ')+r'C:\frozen\input.json'
        return data
    def check(self,data,kind='import',path=r'C:\frozen\input.json'):
        return validate_log(('\r\n'.join(data)+'\r\n').encode('ascii'),kind,path)
    def reject(self,data,kind='import'):
        with self.assertRaises(ValueError):self.check(data,kind)
    def test_complete_import_positive(self):self.assertEqual(self.check(self.fixture('import'))['physical_lines'],53)
    def test_complete_export_positive(self):self.assertEqual(self.check(self.fixture('export'),'export')['physical_lines'],2)
    def test_elapsed_variable_positive(self):
        d=self.fixture('import');d[-1]='Import completed! Time: 123.45 secs';self.check(d)
    def test_wrong_source_path(self):
        with self.assertRaises(ValueError):self.check(self.fixture('import'),path=r'C:\old\parent.json')
    def test_missing_diagnostic(self):d=self.fixture('import');d.pop(1);self.reject(d)
    def test_extra_warning(self):d=self.fixture('import');d.insert(-1,'Warning 254');self.reject(d)
    def test_form_count(self):d=self.fixture('import');d[-2]='Number of forms inserted: 31';self.reject(d)
    def test_insertion_order(self):d=self.fixture('import');d[20],d[21]=d[21],d[20];self.reject(d)
    def test_trailing_blank_line(self):d=self.fixture('import');d.append('');self.reject(d)
    def test_missing_completion(self):d=self.fixture('import');d.pop();self.reject(d)
    def test_negative_elapsed(self):d=self.fixture('import');d[-1]='Import completed! Time: -0.01 secs';self.reject(d)
    def test_nonfinite_elapsed(self):d=self.fixture('export');d[-1]='Export completed! Time: NaN secs';self.reject(d,'export')
    def test_wrong_completion_kind(self):d=self.fixture('export');d[-1]='Import completed! Time: 0.00 secs';self.reject(d,'export')
    def test_whitespace_corruption(self):d=self.fixture('import');d[19]=d[19].strip();self.reject(d)
    def test_nonascii_rejected(self):
        with self.assertRaises(UnicodeDecodeError):validate_log(b'\xff','import',r'C:\frozen\input.json')
if __name__=='__main__':unittest.main()
