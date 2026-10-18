"""Additive target-value assertion; v1 and its failed controls are preserved."""
from precision_contract import strict_json,delta,bits,validate as compare
TARGET_BITS='3fbf9add3746f65e'
def actual_target(document):
    tables=[t for t in document['model']['tables'] if t['name']=='OperationProfile']
    if len(tables)!=1:raise ValueError('OperationProfile identity')
    table=tables[0];cols=[c['name'] for c in table['columns']]
    if len(set(cols))!=len(cols) or table['columns'][cols.index('DTIM')]['datatype']!='double':raise ValueError('DTIM metadata')
    instances=table['instances']
    if len(instances)!=1 or instances[0]['instance_name']!='' or len(instances[0]['rows'])!=1:raise ValueError('DTIM instance/row identity')
    row=instances[0]['rows'][0]
    if [row[cols.index(k)] for k in ('PRID','SPRID','STIM')]!=['BASIC-SCHEDULE','BASIC-MISSION',8]:raise ValueError('DTIM business key')
    result=bits(row[cols.index('DTIM')])
    if result!=TARGET_BITS:raise ValueError('actual DTIM target binary64 differs: '+result)
    return result
def validate(actual,expected):
    actual_target(expected)
    observed=actual_target(actual)
    result=compare(actual,expected)
    result['target_binary64']=observed
    result['actual_target_independently_verified']=True
    return result
