"""Private, in-memory negatives for the independent E02.var02 v104 reader.

No native, SSH, Git, author implementation, or accepted checker invocation.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
READER = HERE / 'e02-var02-v104-independent-reader-final.py'
if HERE.name == 'review':
    READER = HERE / 'independent_reader.py'
spec = importlib.util.spec_from_file_location('e02_independent_reader', READER)
assert spec is not None and spec.loader is not None
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def reject(name, action):
    try:
        action()
    except (AssertionError, ValueError, UnicodeError, json.JSONDecodeError):
        return name
    raise AssertionError('accepted malformed clone: ' + name)


def model_check(expected, actual, shape):
    r.keys(expected, {'model'}); r.keys(actual, {'model'})
    r.keys(expected['model'], {'database_version','tables'})
    r.keys(actual['model'], {'database_version','tables'})
    assert r.typed(expected['model']['database_version'],actual['model']['database_version'])
    assert r.compare_tables(expected['model']['tables'],actual['model']['tables']) == shape


def cloned(doc, edit):
    out = copy.deepcopy(doc)
    edit(out)
    assert json.dumps(out,sort_keys=True,allow_nan=False) != json.dumps(doc,sort_keys=True,allow_nan=False)
    return out


def main():
    r.source_oracles()
    parent = r.strict_json(r.exact(r.PARENT/'native-input.json',{'bytes':43699,'sha256':r.PARENT_INPUT_SHA}))
    child = r.one_dirpt(parent)
    model_check(child,child,(31,24,274))
    old_export = r.strict_json(r.exact(r.PARENT_RUN/'roundtrip-raw.json',{'bytes':57995,'sha256':r.PARENT_EXPORT_SHA}))
    export = r.one_dirpt(old_export)
    model_check(export,export,(31,35,369))

    def source_row(doc):
        return next(t for t in doc['model']['tables'] if t['name']=='ItemRepair')['instances'][0]['rows'][0]
    negatives=[]
    x=cloned(child,lambda d: source_row(d).__setitem__(2,1.0))
    negatives.append(reject('source-dirpt-reverted',lambda: model_check(child,x,(31,24,274))))
    x=cloned(child,lambda d: source_row(d).__setitem__(2,True))
    negatives.append(reject('source-dirpt-bool',lambda: model_check(child,x,(31,24,274))))
    x=cloned(child,lambda d: next(t for t in d['model']['tables'] if t['name']=='ItemRepair')['instances'][0]['rows'].__setitem__(0,{'DIRPT':10.75}))
    negatives.append(reject('source-row-dict',lambda: model_check(child,x,(31,24,274))))
    x=cloned(child,lambda d: next(t for t in d['model']['tables'] if t['name']=='ItemRepair')['instances'][0].__setitem__('rows',{'one':source_row(d)}))
    negatives.append(reject('source-rows-dict',lambda: model_check(child,x,(31,24,274))))
    x=cloned(child,lambda d: d['model'].__setitem__('unexpected',0))
    negatives.append(reject('source-extra-model-key',lambda: model_check(child,x,(31,24,274))))
    x=cloned(export,lambda d: source_row(d).__setitem__(2,1.0))
    negatives.append(reject('export-dirpt-reverted',lambda: model_check(export,x,(31,35,369))))
    x=cloned(export,lambda d: d['model'].__setitem__('database_version',True))
    negatives.append(reject('export-version-bool',lambda: model_check(export,x,(31,35,369))))

    template=r.exact(r.CASE/'preserved-oracle/expected-log-template.bin',
                     {'bytes':9178,'sha256':r.TEMPLATE_SHA},readonly=True)
    assert template.count(b'{{FINITE_GT34}}')==1
    goodlog=template.replace(b'{{FINITE_GT34}}',b'35.5')
    assert r.physical_log(goodlog)=={'physical_lines':123,'timed_lines':99}
    def logline(data,index,text):
        lines=data.split(b'\r\n')
        assert len(lines)==124 and lines[-1]==b''
        lines[index]=text
        return b'\r\n'.join(lines)
    line103=goodlog.split(b'\r\n')[103]
    prefix=b'Time: 32 <TEACH-AIR-01,0> Next random failure will occur '
    assert line103==prefix+b'35.5'
    for label,bad in [
        ('rng-boundary-34',logline(goodlog,103,prefix+b'34')),
        ('rng-nonfinite',logline(goodlog,103,prefix+b'NaN')),
        ('rng-malformed',logline(goodlog,103,prefix+b'35.5extra')),
        ('rng-wrong-id',logline(goodlog,103,prefix.replace(b'TEACH-AIR-01',b'OTHER-AIR-01')+b'35.5')),
        ('log-bom',b'\xef\xbb\xbf'+goodlog),
        ('log-lf-only',goodlog.replace(b'\r\n',b'\n')),
        ('log-terminal-missing',goodlog[:-2]),
        ('log-extra-line',goodlog+b'UNPLANNED\r\n'),
        ('log-early-line-change',logline(goodlog,0,b'Time: 0')),
    ]:
        negatives.append(reject(label,lambda data=bad:r.physical_log(data)))

    parts=goodlog.split(b'\r\n')
    assert len(parts)==124 and parts[-1]==b''
    assert parts[67:73]==[b' Systems ready: ',b' Systems in prep: ',
                          b' Systems in reconfig: ',b' Systems preassigned: ',
                          b' Systems in assign buffer: ',b'']
    missing=parts.copy(); missing.pop(68)
    negatives.append(reject('cancel-continuation-missing',
                            lambda:r.physical_log(b'\r\n'.join(missing))))
    swapped=parts.copy(); swapped[68],swapped[69]=swapped[69],swapped[68]
    negatives.append(reject('cancel-continuation-reordered',
                            lambda:r.physical_log(b'\r\n'.join(swapped))))
    duplicate=parts.copy(); duplicate.insert(70,parts[70])
    negatives.append(reject('cancel-continuation-duplicated',
                            lambda:r.physical_log(b'\r\n'.join(duplicate))))

    expected=r.strict_json(r.exact(r.CASE/'preserved-oracle/expected-report.json',
                                   {'bytes':100409,'sha256':r.REPORT_SHA},readonly=True))
    assert r.report_cells(expected)==4044
    def tables(doc): return doc['report']['tables']
    x=cloned(expected,lambda d: tables(d)[0]['instances'][0]['rows'][0].__setitem__(0,'changed'))
    negatives.append(reject('report-description',lambda:r.report_cells(x)))
    x=cloned(expected,lambda d: tables(d)[1]['instances'][0]['rows'][0].__setitem__(0,True))
    negatives.append(reject('report-integer-bool',lambda:r.report_cells(x)))
    x=cloned(expected,lambda d: tables(d)[1]['instances'][0]['rows'][0].__setitem__(3,0.5))
    negatives.append(reject('report-summary-fraction',lambda:r.report_cells(x)))
    x=cloned(expected,lambda d: tables(d)[2]['instances'][0]['rows'][0].__setitem__(0,'WRONG'))
    negatives.append(reject('report-system-id',lambda:r.report_cells(x)))
    x=cloned(expected,lambda d: tables(d)[2]['columns'][0].__setitem__('key',1))
    negatives.append(reject('report-key-bool',lambda:r.report_cells(x)))
    x=cloned(expected,lambda d: tables(d)[2]['instances'][0].__setitem__('rows',{'one':tables(d)[2]['instances'][0]['rows'][0]}))
    negatives.append(reject('report-rows-dict',lambda:r.report_cells(x)))
    x=cloned(expected,lambda d: tables(d)[0]['instances'][0]['rows'].__setitem__(0,{'PDESC':'changed'}))
    negatives.append(reject('report-row-dict',lambda:r.report_cells(x)))
    x=cloned(expected,lambda d: d['report'].__setitem__('extra',0))
    negatives.append(reject('report-extra-root',lambda:r.report_cells(x)))

    assert tables(expected)[2]['columns'][23]['name']=='NREPT'
    assert tables(expected)[2]['instances'][0]['rows'][41][23]==0
    assert tables(expected)[2]['instances'][0]['rows'][42][23]==1
    x=cloned(expected,lambda d: tables(d)[2]['instances'][0]['rows'][41].__setitem__(23,1.0))
    negatives.append(reject('report-NREPT-prior-bin',lambda:r.report_cells(x)))
    x=cloned(expected,lambda d: tables(d)[2]['instances'][0]['rows'][42].__setitem__(23,0.0))
    negatives.append(reject('report-NREPT-interior-bin',lambda:r.report_cells(x)))

    converter=r.converter_fixture()
    assert r.converter_bytes(converter)==15
    for label,bad in [
        ('converter-bom',b'\xef\xbb\xbf'+converter),
        ('converter-lf-only',converter.replace(b'\r\n',b'\n')),
        ('converter-no-terminal',converter[:-2]),
        ('converter-extra-warning',converter.replace(b'Form: Control',b'Form: System\r\nForm: Control')),
        ('converter-summary-two-warnings',converter.replace(b'Warnings: 1',b'Warnings: 2')),
        ('converter-file-alias',converter.replace(str(r.RUN/'model.sxi').replace('\\','/').encode(),str(r.RUN/'model.sxi').encode())),
        ('converter-nonfinite-time',converter.replace(b'Input data conversion time: 0.01',b'Input data conversion time: NaN')),
    ]:
        assert bad!=converter,label
        negatives.append(reject(label,lambda data=bad:r.converter_bytes(data)))
    negatives.append(reject('json-duplicate-key',lambda:r.strict_json(b'{"x":1,"x":2}')))
    negatives.append(reject('json-nonfinite',lambda:r.strict_json(b'{"x":NaN}')))
    assert len(negatives)==38 and len(set(negatives))==len(negatives)
    return {'decision':'PASS_PRIVATE_NEGATIVES','negative_count':len(negatives),
            'physical_lines':123,'report_cells':4044,'native_calls':0}


if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True))
