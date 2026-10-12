"""Hand-authored round-2 benchmark. Never expose this module to modeling agents.

Behavior arithmetic is written in literals and explanations before execution.
No runtime imports, trace extraction, or expected-output regeneration occur here.
Run this file to rebuild public requests and private contracts deterministically.
"""
from pathlib import Path
import copy
import json
import random

ROOT = Path(__file__).resolve().parents[1]
COMMON = ('只建立文中指定的飞机、任务和共享资源，内部标识保留这些英文业务名称。'
          '飞机均从健康、空闲、无任务的状态开始；未提到的故障、定期维护、库存、运输都不存在；'
          '未提到的返航周转耗时为零。准备工作按列出的顺序进行，每架飞机独立准备；'
          '资源数量表示同时可占用的容量，步骤结束释放。数字优先级越小越优先，未指定则均为1。'
          '只要求这些业务机制，不额外引入现实世界规则。')
DEV=[]; HOLD=[]
def air(name,typ='Utility',**kw):
    d=dict(id=name,type=typ,turnround_hours=0,repair_mode='none',repair_hours=0,
           remove_hours=0,fit_hours=0,item_repair_hours=0,stock_node=None,
           repair_node=None,installed_item=None,pm=None);d.update(kw);return d

def mission(name,start,notice,duration,delay=0,quantity=1,process='Prepare',typ='Utility',priority=1,depends=None):
    return dict(id=name,start_hours=start,notice_hours=notice,duration_hours=duration,
                delay_hours=delay,priority=priority,requirements={typ:quantity},process=process,depends_on=depends or [])
def step(duration,demands=None,name='Step'):
    return dict(id=name,duration_hours=duration,demands=demands or {})
def process(duration,steps=None,name='Prepare'):
    return dict(id=name,scalar_hours=duration,steps=steps or [])
def fault(name,when,aircraft,operation='fault'):
    return dict(id=name,time_hours=when,operation=operation,aircraft=aircraft,node=None,item=None,value_hours=0)
def model(aircraft,processes,missions,resources=None,horizon=2,report=.1,events=None):
    return dict(horizon_hours=horizon,report_interval_hours=report,
                rng_profile='external-events/v1' if events else 'none',aircraft=aircraft,
                resources=resources or [],processes=processes,missions=missions,nodes=[],routes=[],external_events=events or [])
def pm(clock,interval,duration,name='Maintenance'):
    return dict(id=name,clock=clock,interval_hours=interval,duration_hours=duration)
def resource(name,capacity):return dict(id=name,capacity=capacity)
def event(suffix,kind,rows,project=('hour',),where=None,unordered=False):
    return dict(id=suffix,kind=kind,where=where or {},project=list(project),expected=rows,unordered=unordered)
def ev(suffix,kind,times,where=None):return event(suffix,kind,[[t] for t in times],where=where)
def change(select,value):return dict(select=select,value=value)
def intervention(name,changes,behavior,explanation):
    return dict(id=name,changes=changes,behavior=behavior,manual_derivation=explanation)
def mutation(name,select,value,failed):
    return dict(id=name,changes=[change(select,value)],expected_failed_ids=failed)
def constraints(m):
    """Business-relevant projections, deliberately not full-model equality."""
    c=[]
    def eq(s,v):c.append(dict(id='R-structure-'+s,op='eq',select=s,expected=v))
    for f in ('horizon_hours','report_interval_hours','rng_profile'):eq(f,m[f])
    for table in ('aircraft','resources','missions','nodes','routes','external_events'):
        c.append(dict(id='R-identities-'+table,op='ids_eq',select=table,expected=[r['id'] for r in m[table]]))
    for a in m['aircraft']:
        for field in ('type','turnround_hours','repair_mode','repair_hours'):
            eq(f'aircraft[id={a["id"]}]/{field}',a[field])
        # PM identity is not a business requirement; clock, threshold and work are.
        if a['pm'] is None:eq(f'aircraft[id={a["id"]}]/pm',None)
        else:
            for field in ('clock','interval_hours','duration_hours'):
                eq(f'aircraft[id={a["id"]}]/pm/{field}',a['pm'][field])
    for r in m['resources']:eq(f'resources[id={r["id"]}]/capacity',r['capacity'])
    for task in m['missions']:
        for field in ('start_hours','notice_hours','duration_hours','delay_hours','priority','requirements','depends_on'):
            eq(f'missions[id={task["id"]}]/{field}',task[field])
        p=next(p for p in m['processes'] if p['id']==task['process'])
        work=[dict(duration_hours=s['duration_hours'],demands=s['demands']) for s in p['steps']]
        if not work:work=[dict(duration_hours=p['scalar_hours'],demands={})]
        c.append(dict(id='R-work-'+task['id'],op='process_work',mission=task['id'],expected=work))
    for driver in m['external_events']:
        for field in ('time_hours','operation','aircraft','node','item','value_hours'):
            eq(f'external_events[id={driver["id"]}]/{field}',driver[field])
    return c

def make(label,category,paragraphs,m,behavior,reason,interventions=None,mutations=None):
    reqs=[dict(id=f'{label}-R{i+1:02}',text=p) for i,p in enumerate(paragraphs)]
    return dict(task_id=label,category=category,request=COMMON+'\n\n'+'\n'.join(paragraphs),
                requirements=reqs,reference_model=m,constraints=constraints(m) if m else [],
                behavior=behavior,manual_derivation=reason,interventions=interventions or [],
                mutations=mutations or [],terminal=dict(all_aircraft_ready=True,active_jobs=0,backorders=0))

def clarify(label,paragraphs,m,behavior,reason,concept,groups,aliases,answer,mutations=None):
    c=make(label,'clarify',paragraphs,m,behavior,reason,mutations=mutations)
    answered=copy.deepcopy(c);answered['category']='modeling'
    c['clarification']=dict(questions=[dict(concept=concept,keyword_groups=groups,field_aliases=aliases)],
                           simulated_answer=answer,answered_case=answered)
    return c

def unsupported(label,paragraphs,groups,gap):
    c=make(label,'unsupported',paragraphs,None,[],gap)
    c['unsupported']=dict(keyword_groups=groups,capability_gap=gap)
    return c

# Development tasks: never tune from held-out task outcomes.
m=model([air('Dove')],[process(.05)],[mission('Morning',.1,.05,.35),mission('Afternoon',.7,.6,.25)],horizon=1.2)
DEV.append(make('D01','modeling',[
 '对Dove这架Utility型飞机安排两次独立巡航Morning和Afternoon。观察到1.2小时结束，每0.1小时报告。每次出动前准备0.05小时，不占任何资源。',
 'Morning在0.05小时通知、0.1小时计划起飞、飞行0.35小时；Afternoon在0.6小时通知、0.7小时计划起飞、飞行0.25小时。每次仅需Dove，不允许延误。'],m,
 [event('R-start','mission_started',[[.1,'Morning'],[.7,'Afternoon']],('hour','mission')),event('R-return','mission_returned',[[.45,'Morning'],[.95,'Afternoon']],('hour','mission'))],
 '两次准备分别0.05→0.10、0.60→0.65，后者等待计划起飞0.70；返航为0.45和0.95。',
 mutations=[mutation('drop-second-flight','missions[id=Afternoon]/duration_hours',.1,['R-return'])]))

m=model([air('Teal',repair_mode='direct',repair_hours=.16)],[process(.04)],[mission('Survey',.15,.1,1),mission('Resurvey',.8,.73,.25)],horizon=1.3,events=[fault('DamageNotice',.52,'Teal','damaged_arrival')])
DEV.append(make('D02','composition',[
 'Teal是唯一Utility型飞机，观察1.3小时、每0.1小时报告。每次准备0.04小时且无需资源。Survey于0.1通知、0.15计划起飞、原计划飞行1小时；Resurvey于0.73通知、0.8起飞、飞行0.25小时，两次都不允许延误。',
 '外部已确定Teal在0.52小时以受损状态返场，记录名DamageNotice；Survey当时立即结束并记为中止，而不是继续飞到原计划返航时刻。落地后直接维修0.16小时才恢复健康。'],m,
 [ev('R-damage','external_damaged_arrival',[.52]),event('R-return','mission_returned',[[.52,'Survey','aborted'],[1.05,'Resurvey','successful']],('hour','mission','outcome')),ev('R-repair','repair_finished',[.68]),event('R-start','mission_started',[[.15,'Survey'],[.8,'Resurvey']],('hour','mission'))],
 '受损返场结束实际飞行0.52-0.15=0.37小时；维修0.52+0.16=0.68；第二次准备0.73→0.77，于0.8起飞。',
 mutations=[mutation('fault-is-not-early-return','external_events[id=DamageNotice]/operation','fault',['R-return','R-repair'])]))

m=model([air('QueryDove')],[process(.07)],[mission('Check',.3,.2,.45,.1)],horizon=1)
DEV.append(clarify('D03',[
 'QueryDove是唯一Utility型飞机，计划执行Check巡飞。观察1小时、每0.1小时报告。0.2小时通知，准备0.07小时且无需资源，计划0.3起飞，最多延误0.1小时。请据此建立可以计算返航的模型。'],m,
 [ev('R-start','mission_started',[.3]),ev('R-return','mission_returned',[.75])],
 '必要缺口是巡飞持续时长。固定答复为0.45小时，故0.30+0.45=0.75返航。','flight duration',
 [['Check','飞行','flight','巡飞'],['多久','时长','持续','duration','long']],['missions/Check/duration_hours'],
 'Check每次飞行0.45小时，其他要求保持不变。',mutations=[mutation('wrong-flight-duration','missions[id=Check]/duration_hours',.3,['R-return'])]))

DEV.append(unsupported('D04',[
 '希望用当前飞机有界事件后端建立FuelBird单机模型。飞机初始燃油100升，飞行期间高度连续变化，燃油消耗率为每小时10+0.002乘高度的升数；高度随燃油变化由二阶微分方程决定。',
 '观察2小时，每0.1小时报告；请在事件之间联立积分高度和燃油，精确检测油量到零的时刻，并在那一刻强制返航。不能把油耗或返航时刻预先给定。'],
 [['连续','微分','continuous','differential','积分'],['不支持','无法','缺少','未实现','unsupported','cannot']],
 '当前bounded profile没有连续状态变量、微分方程积分器或连续零交叉事件；外生事件不能代替内生求解。'))


def finalize():
    def relabel(case,label):
        old=case['task_id'];case=copy.deepcopy(case);case['task_id']=label
        for r in case['requirements']:r['id']=r['id'].replace(old+'-',label+'-',1)
        if 'clarification' in case:case['clarification']['answered_case']=relabel(case['clarification']['answered_case'],label)
        return case
    shuffled=copy.deepcopy(HOLD);random.Random(20261012).shuffle(shuffled)
    hold=[relabel(c,f'Q{i:02}') for i,c in enumerate(shuffled,1)]
    for name,cases in [('development',DEV),('holdout',hold)]:
        (ROOT/'public'/f'{name}.json').write_text(json.dumps([{k:c[k] for k in ('task_id','request')} for c in cases],ensure_ascii=False,indent=2)+'\n')
    private=dict(schema_version='codex-modeling-round2-cases/v1',method='Hand-authored business requests and arithmetic before execution; no runtime-generated expectations. Reference models are internal positive controls only.',development=DEV,holdout=hold)
    (ROOT/'private/cases.json').write_text(json.dumps(private,ensure_ascii=False,indent=2)+'\n')
    print('Wrote',len(DEV),'development and',len(hold),'held-out tasks.')



# Eight complete-information modeling requests.
m=model([air('Raven'),air('Kite'),air('Swift')],[process(.14,[step(.14,{'Crew':1})])],[mission('Patrol',.9,.7,.55,.3,3)],resources=[resource('Crew',2)],horizon=2.4)
HOLD.append(make('B1','modeling',[
 'Raven、Kite、Swift三架Utility型飞机共同执行Patrol，三架都准备完成才能成队起飞。观察2.4小时、每0.1小时报告。',
 'Crew共有2名；每架起飞前连续检查0.14小时，检查时独占1名Crew。0.7小时统一通知准备，0.9小时计划起飞，最多延误0.3小时；任务飞行0.55小时。'],m,
 [ev('R-prepared','preparation_finished',[.84,.84,.98]),ev('R-launch','mission_started',[.98]),ev('R-return','mission_returned',[1.53])],
 '2人先在0.7→0.84准备两架，余下一架0.84→0.98；全队0.98起飞，1.53返航。',
 [intervention('extra-person',[change('resources[id=Crew]/capacity',3)],[ev('I-launch','mission_started',[.9]),ev('I-return','mission_returned',[1.45])],'3人并发0.84准备完，等至0.9起飞。')],
 [mutation('lose-resource-limit','resources[id=Crew]/capacity',3,['R-launch'])]))

m=model([air('MinuteBird',turnround_hours=.15)],[process(.25)],[mission('MinuteRoute',.9,.65,.55)],horizon=2)
HOLD.append(make('B2','modeling',[
 '本题文字时间全部使用分钟。MinuteBird是唯一Utility型飞机，执行MinuteRoute。观察120分钟，每6分钟报告。',
 '第39分钟通知准备，准备15分钟且不占共享资源；第54分钟必须起飞，不允许延误；飞行33分钟，返航后周转9分钟恢复可用。请保留亚小时精度。'],m,
 [ev('R-launch','mission_started',[.9]),ev('R-return','mission_returned',[1.45]),ev('R-turn','turnround_finished',[1.6])],
 '39/60+15/60=0.9；0.9+33/60=1.45；1.45+9/60=1.6。',
 [intervention('longer-turn',[change('aircraft[id=MinuteBird]/turnround_hours',.3)],[ev('I-turn','turnround_finished',[1.75])],'只延长周转，1.45+0.30=1.75。')],
 [mutation('minutes-as-hours','mission_process[id=MinuteRoute]/scalar_hours',15,['R-launch'])]))

m=model([air('SerialBird')],[process(.36,[step(.08,{'Crew':1},'Safety'),step(.17,name='Warmup'),step(.11,{'Crew':1},'Release')])],[mission('SerialRoute',1.4,1.2,.4,.3)],resources=[resource('Crew',1)],horizon=2.4)
HOLD.append(make('B3','modeling',[
 'SerialBird是唯一Utility型飞机，执行SerialRoute；观察2.4小时、每0.1小时报告。1.2小时通知、1.4小时计划起飞，最多延误0.3小时，飞行0.4小时。',
 '准备必须依次完成：安全检查0.08小时占1名Crew；暖机0.17小时无需人员；放行检查0.11小时再占1名Crew。Crew总容量为1。安全检查结束必须释放人员，不能把三步并行，也不能在暖机时继续占人。'],m,
 [ev('R-prepared','preparation_finished',[1.56]),ev('R-launch','mission_started',[1.56]),ev('R-return','mission_returned',[1.96]),ev('R-release','resource_released',[1.28,1.56])],
 '1.20+0.08=1.28释放Crew；暖机到1.45；再次检查到1.56；返航1.96。',
 [intervention('tight-cutoff',[change('missions[id=SerialRoute]/delay_hours',.1)],[ev('I-cancel','mission_cancelled',[1.5]),ev('I-launch','mission_started',[])],'新截止1.5早于1.56，取消当前放行检查且释放资源。')],
 [mutation('omit-final-work','mission_process[id=SerialRoute]/steps/2/duration_hours',0,['R-prepared'])]))

m=model([air('CalendarBird',pm=pm('calendar',.8,.2))],[process(.03)],[mission('CalendarRoute',1.1,1.05,.4,.2)],horizon=2.4)
HOLD.append(make('B4','modeling',[
 'CalendarBird是唯一Utility型飞机。观察2.4小时、每0.1小时报告。它从时刻0开始按日历每0.8小时到期维护，维护耗时0.2小时；每次维护完成后重新计0.8小时。空闲地面时执行维护，不在飞行中中断任务。',
 'CalendarRoute在1.05小时通知、1.1计划起飞，最多延误0.2小时；准备0.03小时无需资源，飞行0.4小时。'],m,
 [ev('R-pm-start','pm_started',[.8,1.8]),ev('R-pm-finish','pm_finished',[1,2]),ev('R-launch','mission_started',[1.1]),ev('R-return','mission_returned',[1.5])],
 '首次维护0.8→1.0，下一次到期1.0+0.8=1.8并至2.0结束；航次1.1→1.5位于两次维护间。',
 [intervention('different-calendar',[change('aircraft[id=CalendarBird]/pm/interval_hours',1)],[ev('I-pm-start','pm_started',[1,2.2]),ev('I-pm-end','pm_finished',[1.2,2.4]),ev('I-launch','mission_started',[1.23]),ev('I-return','mission_returned',[1.63])],'首次维护1→1.2，随后准备0.03所以1.23起飞；下一次维护2.2→2.4。')],
 [mutation('wrong-pm-clock','aircraft[id=CalendarBird]/pm/clock','flight',['R-pm-start'])]))

m=model([air('Scout','Recon'),air('Carrier','Cargo')],[process(.1)],[mission('ReconRun',.45,.25,.75,typ='Recon'),mission('CargoRun',.8,.7,.4,.6,typ='Cargo',priority=2,depends=['ReconRun'])],horizon=2)
HOLD.append(make('B5','modeling',[
 'Scout是Recon型、Carrier是Cargo型，各一架。观察2小时、每0.1小时报告。两个任务都只需相应类型1架，各准备0.1小时，无共享资源。',
 'ReconRun在0.25通知、0.45计划起飞、飞行0.75小时，不允许延误，优先级1。CargoRun在0.7通知、0.8计划起飞、飞行0.4小时，最多延误0.6小时，优先级2。',
 'CargoRun可以提前准备，但只有ReconRun成功结束并返航才准许起飞。'],m,
 [event('R-launch','mission_started',[[.45,'ReconRun'],[1.2,'CargoRun']],('hour','mission')),event('R-return','mission_returned',[[1.2,'ReconRun'],[1.6,'CargoRun']],('hour','mission'))],
 'ReconRun返航0.45+0.75=1.2，CargoRun虽0.8已准备完也须等到1.2起飞。',
 [intervention('longer-recon',[change('missions[id=ReconRun]/duration_hours',.95)],[event('I-launch','mission_started',[[.45,'ReconRun'],[1.4,'CargoRun']],('hour','mission')),ev('I-cancel','mission_cancelled',[])],'前序返航1.4恰为后序截止0.8+0.6，返航完成先于截止，仍可发射。')],
 [mutation('drop-predecessor','missions[id=CargoRun]/depends_on',[],['R-launch'])]))

m=model([air('OnlyBird')],[process(.12)],[mission('Alpha',1,.8,.3,.1,priority=2),mission('Beta',1,.8,.3,.1,priority=1)],horizon=1.6)
HOLD.append(make('B6','modeling',[
 'OnlyBird是唯一Utility型飞机；Alpha和Beta都要求这1架飞机。观察1.6小时、每0.1小时报告。两任务都在0.8通知、1小时计划起飞、飞行0.3小时，最多延误0.1小时；起飞前准备0.12小时，不占资源。',
 'Beta优先级1、Alpha优先级2，因此竞争飞机时先满足Beta。未获完整编队的任务在“计划起飞+允许延误−准备时长”的最迟可准备时刻取消，不能等已开始飞行的飞机返回再补做。'],m,
 [event('R-launch','mission_started',[[1,'Beta']],('hour','mission')),event('R-cancel','mission_cancelled',[[.98,'Alpha']],('hour','mission'))],
 'Beta先分到飞机0.8→0.92准备；Alpha最迟准备1+0.1−0.12=0.98无机取消；Beta1起飞1.3返回。',
 [intervention('priority-reversal',[change('missions[id=Alpha]/priority',1),change('missions[id=Beta]/priority',2)],[event('I-launch','mission_started',[[1,'Alpha']],('hour','mission')),event('I-cancel','mission_cancelled',[[.98,'Beta']],('hour','mission'))],'优先级交换后飞机分配交换，时间不变。')],
 [mutation('wrong-priority','missions[id=Alpha]/priority',0,['R-launch'])]))

m=model([air('HeavyOne'),air('HeavyTwo')],[process(.25,[step(.25,{'Crew':2})])],[mission('HeavyLift',1.3,1,.4,.3,2)],resources=[resource('Crew',1)],horizon=2.2)
HOLD.append(make('B7','modeling',[
 'HeavyOne和HeavyTwo是两架Utility型飞机，HeavyLift要求两架同时出动。观察2.2小时、每0.1小时报告。1小时通知、1.3计划起飞，最多延误0.3小时，飞行0.4小时。',
 '每架准备0.25小时，必须同时占用2名Crew才可开始；基地实际上只有1名Crew。不得把双人检查分成两次单人检查。若资源总容量永久不足，在最迟准备时刻“起飞时间+允许延误−0.25小时”取消任务。'],m,
 [ev('R-no-acquisition','resource_acquired',[]),ev('R-cancel','mission_cancelled',[1.35]),ev('R-no-launch','mission_started',[])],
 '单次需求2大于总容量1，无法取得任何完整租约；1.3+0.3−0.25=1.35取消。',
 [intervention('crew-fixed',[change('resources[id=Crew]/capacity',2)],[ev('I-launch','mission_started',[1.5]),ev('I-return','mission_returned',[1.9])],'2名Crew每次仍只能服务1架：1→1.25、1.25→1.5，全队1.5起飞。')],
 [mutation('illegal-demand-reduction','mission_process[id=HeavyLift]/steps/0/demands/Crew',1,['R-no-acquisition'])]))

m=model([air('RepairBird',repair_mode='direct',repair_hours=.28)],[process(0)],[mission('RepairRoute',.2,.2,.9)],horizon=1.8,events=[fault('KnownFault',.65,'RepairBird')])
HOLD.append(make('B8','modeling',[
 'RepairBird是唯一Utility型飞机。观察1.8小时、每0.1小时报告。RepairRoute在0.2小时通知并计划起飞，无需准备、不能延误，飞行0.9小时。',
 '外部已确定名为KnownFault的故障在0.65小时发生于RepairBird：任务记中止，但飞机仍按原计划返航。返航后直接维修0.28小时恢复健康；没有人员限制或备件更换，也没有随机生成故障。'],m,
 [ev('R-fault','external_fault',[.65]),event('R-return','mission_returned',[[1.1,'aborted',.9]],('hour','outcome','flight_hours')),ev('R-repair-start','repair_started',[1.1]),ev('R-repair-end','repair_finished',[1.38])],
 '已定故障不改变飞行结束0.2+0.9=1.1，维修1.1+0.28=1.38。',
 [intervention('longer-repair',[change('aircraft[id=RepairBird]/repair_hours',.42)],[ev('I-repair','repair_finished',[1.52])],'故障与返航不变，直接维修1.1+0.42=1.52。')],
 [mutation('wrong-return-mode','external_events[id=KnownFault]/operation','damaged_arrival',['R-return'])]))

# Eight multi-mechanism combinations.
m=model([air('PairOne',turnround_hours=.2),air('PairTwo',turnround_hours=.2)],[process(.1,[step(.1,{'Crew':1})])],[mission('FirstPair',.4,.2,.5,quantity=2),mission('SecondPair',1.1,.95,.3,.3,2,priority=2)],resources=[resource('Crew',2)],horizon=2)
HOLD.append(make('C1','composition',[
 'PairOne和PairTwo是两架Utility型飞机，每次任务都要求二者全部准备好才起飞。观察2小时、每0.1小时报告。Crew容量2，每架每次准备0.1小时并占用1名Crew。',
 'FirstPair在0.2通知、0.4起飞、飞行0.5小时、不能延误、优先级1；SecondPair在0.95通知、1.1计划起飞、飞行0.3小时、最多延误0.3小时、优先级2。每次成功返航周转0.2小时。',
 '正在周转的飞机可以被第二任务预先分配，但必须完成周转后才可开始第二次准备；第二任务没有额外的前序成功依赖。'],m,
 [event('R-launch','mission_started',[[.4,'FirstPair'],[1.2,'SecondPair']],('hour','mission')),ev('R-turn','turnround_finished',[1.1,1.1,1.7,1.7]),event('R-return','mission_returned',[[.9,'FirstPair'],[1.5,'SecondPair']],('hour','mission'))],
 '第一队0.4→0.9，周转至1.1；第二队虽0.95预分配，但1.1→1.2才能准备，1.2→1.5飞行，再周转至1.7。',
 [intervention('single-crew',[change('resources[id=Crew]/capacity',1)],[event('I-launch','mission_started',[[.4,'FirstPair'],[1.3,'SecondPair']],('hour','mission')),ev('I-turn','turnround_finished',[1.1,1.1,1.8,1.8])],'第一轮串行0.2→0.3→0.4；第二轮1.1→1.2→1.3。')],
 [mutation('skip-turnround','aircraft[id=PairOne]/turnround_hours',0,['R-turn','R-launch'])]))

m=model([air('ThresholdBird',repair_mode='direct',repair_hours=.25,pm=pm('flight',1,.35))],[process(0)],[mission('Exposure',.35,.35,1.15),mission('DeadlineRun',1.75,1.75,.25,.34,priority=2)],horizon=2.5,events=[fault('ThresholdFault',.95,'ThresholdBird')])
HOLD.append(make('C2','composition',[
 'ThresholdBird为唯一Utility型飞机；观察2.5小时、每0.1小时报告。所有出动无需准备。Exposure在0.35通知并起飞，飞行1.15小时，不延误；DeadlineRun在1.75通知并计划起飞，飞行0.25小时，最多延误0.34小时，优先级2。',
 '外生ThresholdFault于0.95发生，Exposure中止但按原计划返航，随后直接维修0.25小时。每累计飞行1小时需维护0.35小时：飞行中不打断，返航检查，失败航次的实际飞行时间也计入；维修优先，之后立即履行已到期维护。',
 'DeadlineRun如果到允许延误截止仍不可起飞就取消，维护结束不恢复已取消任务。'],m,
 [event('R-return','mission_returned',[[1.5,'Exposure','aborted']],('hour','mission','outcome')),ev('R-repair','repair_finished',[1.75]),ev('R-pm-start','pm_started',[1.75]),ev('R-pm-end','pm_finished',[2.1]),event('R-cancel','mission_cancelled',[[2.09,'DeadlineRun']],('hour','mission')),event('R-launch','mission_started',[[.35,'Exposure']],('hour','mission'))],
 '0.35+1.15=1.5返航，维修至1.75；累计1.15≥1所以维护至2.10；后续截止1.75+0.34=2.09，提前0.01取消。',
 [intervention('deadline-equality',[change('missions[id=DeadlineRun]/delay_hours',.35)],[event('I-launch','mission_started',[[.35,'Exposure'],[2.1,'DeadlineRun']],('hour','mission')),ev('I-cancel','mission_cancelled',[])],'截止改为2.1，维护结束在同刻截止前可派遣，2.1起飞2.35返航。')],
 [mutation('forget-failed-flight-pm','aircraft[id=ThresholdBird]/pm',None,['R-pm-start','R-cancel'])]))

m=model([air('CancelOne'),air('CancelTwo')],[process(.38,[step(.22,{'Crew':1},'Inspect'),step(.16,{'Crew':1,'Cart':1},'Equip')],name='LongPrep'),process(.09,[step(.09,{'Crew':1})],name='ShortPrep')],[mission('TightPair',1,.5,.4,.19,2,process='LongPrep'),mission('Recovery',1.2,1.19,.25,.2,process='ShortPrep',priority=2)],resources=[resource('Crew',1),resource('Cart',1)],horizon=2)
HOLD.append(make('C3','composition',[
 'CancelOne和CancelTwo是两架Utility型飞机；观察2小时、每0.1小时报告。Crew容量1、Cart容量1。',
 'TightPair需要两架，在0.5通知、1小时计划起飞，最多延误0.19小时，飞行0.4小时。每架按序准备：检查0.22小时占Crew 1，随后装载0.16小时同时占Crew 1和Cart 1。准备按飞机名单CancelOne、CancelTwo及先来先服务执行。',
 'Recovery只需1架，在1.19通知、1.2计划起飞，最多延误0.2小时，飞行0.25小时，优先级2；它的准备只有0.09小时并占Crew 1。',
 'TightPair到截止仍未凑齐已准备编队就取消，释放人员、设备和飞机；旧准备完成计时器不得再影响Recovery。'],m,
 [event('R-cancel','mission_cancelled',[[1.19,'TightPair']],('hour','mission')),event('R-launch','mission_started',[[1.28,'Recovery']],('hour','mission')),event('R-return','mission_returned',[[1.53,'Recovery']],('hour','mission')),ev('R-long-complete','preparation_finished',[.88],where={'mission':'TightPair'}),ev('R-recovery-complete','preparation_finished',[1.28],where={'mission':'Recovery'})],
 '第一架0.50→0.72→0.88；第二架0.88→1.10→1.26。截止1.19取消正在装载的第二架，Recovery1.19→1.28准备并出发，1.53返回；1.26旧事件无效。',
 [intervention('allow-final-step',[change('missions[id=TightPair]/delay_hours',.26)],[event('I-launch','mission_started',[[1.26,'TightPair']],('hour','mission')),event('I-cancel','mission_cancelled',[[1.31,'Recovery']],('hour','mission'))],'TightPair1.26完成恰能起飞；Recovery最迟准备1.2+0.2−0.09=1.31无空闲飞机而取消。')],
 [mutation('wrong-cutoff','missions[id=TightPair]/delay_hours',.26,['R-cancel','R-launch'])]))

m=model([air('HeavyBird','Heavy'),air('LightBird','Light')],[process(.18,[step(.18,{'Crew':1,'Cart':1})],name='HeavyPrep'),process(.12,[step(.12,{'Crew':1})],name='LightPrep')],[mission('HeavyRun',.9,.6,.4,.2,typ='Heavy',process='HeavyPrep'),mission('LightRun',.8,.65,.3,typ='Light',process='LightPrep',priority=2)],resources=[resource('Crew',1),resource('Cart',0)],horizon=1.5)
HOLD.append(make('C4','composition',[
 'HeavyBird为Heavy型、LightBird为Light型，各一架；观察1.5小时、每0.1小时报告。Crew容量1，Cart容量0。',
 'HeavyRun在0.6通知、0.9计划起飞、飞行0.4小时，最多延误0.2小时；准备0.18小时，必须同时取得Crew 1和Cart 1，不能先占Crew再等待Cart。永久无法满足资源时在最迟准备时刻取消。',
 'LightRun在0.65通知、0.8起飞、飞行0.3小时，不允许延误，优先级2；准备0.12小时仅需要Crew 1。每任务只需对应类型1架。'],m,
 [event('R-launch','mission_started',[[.8,'LightRun']],('hour','mission')),event('R-cancel','mission_cancelled',[[.92,'HeavyRun']],('hour','mission')),event('R-acquire','resource_acquired',[[.65,'Crew']],('hour','resource'))],
 'HeavyRun因Cart总容量0不应拿走Crew，LightRun0.65→0.77准备后0.8起飞。HeavyRun最迟准备0.9+0.2−0.18=0.92取消。',
 [intervention('add-cart',[change('resources[id=Cart]/capacity',1)],[event('I-launch','mission_started',[[.9,'HeavyRun']],('hour','mission')),event('I-cancel','mission_cancelled',[[.8,'LightRun']],('hour','mission'))],'Cart修好后HeavyRun占Crew0.6→0.78，LightRun0.78才开始0.12小时准备，在0.8截止取消。')],
 [mutation('drop-cart-requirement','mission_process[id=HeavyRun]/steps/0/demands',{'Crew':1},['R-launch','R-acquire'])]))

m=model([air('PMScout','Recon',pm=pm('flight',.5,.4)),air('PMCarrier','Cargo')],[process(.1)],[mission('ReconBeforeCargo',.3,.15,.7,typ='Recon'),mission('CargoAfterRecon',.8,.75,.35,.5,typ='Cargo',priority=2,depends=['ReconBeforeCargo'])],horizon=1.6)
HOLD.append(make('C5','composition',[
 'PMScout为Recon型、PMCarrier为Cargo型，各一架；观察1.6小时、每0.1小时报告。两者每次准备0.1小时，无共享资源。PMScout累计飞行达到0.5小时后在返航时维护0.4小时；PMCarrier不维护。',
 'ReconBeforeCargo在0.15通知、0.3起飞，飞行0.7小时，不允许延误。CargoAfterRecon在0.75通知、0.8计划起飞，飞行0.35小时，最多延误0.5小时、优先级2。每任务只需对应类型1架。',
 'CargoAfterRecon可提前准备，但须等ReconBeforeCargo成功返航。依赖的是前序任务成功结束，不要求PMScout随后完成维护。'],m,
 [event('R-launch','mission_started',[[.3,'ReconBeforeCargo'],[1,'CargoAfterRecon']],('hour','mission')),ev('R-pm-start','pm_started',[1]),ev('R-pm-end','pm_finished',[1.4]),event('R-return','mission_returned',[[1,'ReconBeforeCargo'],[1.35,'CargoAfterRecon']],('hour','mission'))],
 '前序0.3+0.7=1成功返航，同时触发维护至1.4；不同飞机的后序任务只依赖返航，故1即可起飞，1.35返回。',
 [intervention('longer-predecessor',[change('missions[id=ReconBeforeCargo]/duration_hours',.9)],[event('I-launch','mission_started',[[.3,'ReconBeforeCargo'],[1.2,'CargoAfterRecon']],('hour','mission')),ev('I-pm-end','pm_finished',[1.6])],'前序改为1.2返航，后序1.2起飞1.55返回，PMScout1.6维护完成。')],
 [mutation('remove-predecessor-gate','missions[id=CargoAfterRecon]/depends_on',[],['R-launch'])]))

m=model([air('CalendarFaultBird',repair_mode='direct',repair_hours=.2,pm=pm('calendar',.7,.25))],[process(0)],[mission('LongFlight',.2,.2,.9),mission('AfterService',1.3,1.3,.2,.3,priority=2)],horizon=2,events=[fault('CalendarFault',.8,'CalendarFaultBird')])
HOLD.append(make('C6','composition',[
 'CalendarFaultBird为唯一Utility型飞机；观察2小时、每0.1小时报告，起飞无准备耗时。LongFlight在0.2通知并起飞、飞行0.9小时、不能延误；AfterService在1.3通知并计划起飞、飞行0.2小时、最多延误0.3小时、优先级2。',
 '日历维护从0开始每0.7小时到期，维护0.25小时，完成后重新计周期；飞行期间到期只记为待维护。外生CalendarFault在0.8发生，LongFlight中止但仍按原计划返航，返航后直接维修0.2小时。',
 '维修完成后必须先履行已经到期的日历维护，维护完成才可用于AfterService。'],m,
 [ev('R-repair','repair_finished',[1.3]),ev('R-pm-start','pm_started',[1.3]),ev('R-pm-end','pm_finished',[1.55]),event('R-launch','mission_started',[[.2,'LongFlight'],[1.55,'AfterService']],('hour','mission')),event('R-return','mission_returned',[[1.1,'LongFlight','aborted'],[1.75,'AfterService','successful']],('hour','mission','outcome'))],
 '0.7维护到期时在飞行，0.8故障；1.1落地维修至1.3，再维护至1.55；后序截止1.6之前得以1.55起飞。',
 [intervention('repair-overrun',[change('aircraft[id=CalendarFaultBird]/repair_hours',.35)],[ev('I-pm-start','pm_started',[1.45]),ev('I-pm-end','pm_finished',[1.7]),event('I-cancel','mission_cancelled',[[1.6,'AfterService']],('hour','mission'))],'维修至1.45，再维护至1.7，超过后序1.6截止。')],
 [mutation('forget-calendar-obligation','aircraft[id=CalendarFaultBird]/pm',None,['R-pm-start','R-launch'])]))

m=model([air('RigBird','RigType'),air('CrewBird','CrewType')],[process(.27,[step(.27,{'Crew':2,'Rig':1})],name='RigPrep'),process(.18,[step(.18,{'Crew':1})],name='CrewPrep')],[mission('RigRun',.75,.5,.35,.3,typ='RigType',process='RigPrep'),mission('CrewRun',.75,.5,.2,.3,typ='CrewType',process='CrewPrep',priority=2)],resources=[resource('Crew',2),resource('Rig',1)],horizon=1.5)
HOLD.append(make('C7','composition',[
 'RigBird为RigType型、CrewBird为CrewType型；观察1.5小时、每0.1小时报告。Crew容量2、Rig容量1。两个任务同时0.5小时通知，计划0.75起飞，最多延误0.3小时。',
 'RigRun优先级1，仅需RigBird；准备0.27小时，必须一次同时取得Crew 2和Rig 1，连续占用至完成；飞行0.35小时。CrewRun优先级2，仅需CrewBird；准备0.18小时只占Crew 1，飞行0.2小时。',
 '资源不能超额占用；空闲Rig不代表Crew空闲，完成释放必须唤醒等待准备的另一架飞机。'],m,
 [event('R-launch','mission_started',[[.77,'RigRun'],[.95,'CrewRun']],('hour','mission')),event('R-return','mission_returned',[[1.12,'RigRun'],[1.15,'CrewRun']],('hour','mission')),ev('R-Crew-acquire','resource_acquired',[.5,.77],where={'resource':'Crew'})],
 'RigRun0.5→0.77独占2人和Rig，之后CrewRun0.77→0.95准备；两个任务分别0.77和0.95起飞。',
 [intervention('extra-crew',[change('resources[id=Crew]/capacity',3)],[event('I-launch','mission_started',[[.75,'CrewRun'],[.77,'RigRun']],('hour','mission'))],'3人允许同时准备；CrewRun0.68完成等到0.75，RigRun0.77完成再起飞。')],
 [mutation('understate-two-person-work','mission_process[id=RigRun]/steps/0/demands/Crew',1,['R-launch'])]))

m=model([air('UsageBird',turnround_hours=.1,pm=pm('flight',.8,.3))],[process(.1,[step(.1,{'Crew':1})])],[mission('ShortHop',.25,.1,.45),mission('LongHop',1.4,1.25,.4,priority=2)],resources=[resource('Crew',1)],horizon=2.4)
HOLD.append(make('C8','composition',[
 'UsageBird是唯一Utility型飞机；观察2.4小时、每0.1小时报告。Crew容量1，每次准备0.1小时独占Crew 1。ShortHop在0.1通知、0.25起飞、飞行0.45小时；LongHop在1.25通知、1.4起飞、飞行0.4小时、优先级2；均不能延误。',
 '维护按累计实际飞行小时计算，达到0.8小时于返航后维护0.3小时；地面等待不累计，未到阈值的余额跨航次保留，维护完成清零。普通成功返航周转0.1小时；若返航触发维护，则维护代替该次周转。'],m,
 [event('R-launch','mission_started',[[.25,'ShortHop'],[1.4,'LongHop']],('hour','mission')),ev('R-pm-start','pm_started',[1.8]),ev('R-pm-end','pm_finished',[2.1]),ev('R-turn','turnround_finished',[.8])],
 '首次飞0.45小时到0.7，周转到0.8。第二次1.4→1.8，总暴露0.85≥0.8，维护1.8→2.1；地面间隔不累计。',
 [intervention('below-usage-threshold',[change('missions[id=ShortHop]/duration_hours',.3)],[ev('I-pm','pm_started',[]),ev('I-turn','turnround_finished',[.65,1.9])],'累计飞行0.3+0.4=0.7未到0.8；两次普通周转分别到0.65、1.9。')],
 [mutation('calendar-instead-of-flight','aircraft[id=UsageBird]/pm/clock','calendar',['R-pm-start'])]))

# Four necessary-clarification requests with fixed follow-up answers.
m=model([air('QueryOne'),air('QueryTwo')],[process(.18,[step(.18,{'Crew':1})])],[mission('QueryPair',1,.8,.35,.3,2)],resources=[resource('Crew',2)],horizon=1.8)
HOLD.append(clarify('L1',[
 'QueryOne和QueryTwo是两架Utility型飞机，共同执行QueryPair，两架准备完成才起飞。观察1.8小时、每0.1小时报告。0.8通知、1小时计划起飞，最多延误0.3小时，飞行0.35小时。',
 '每架准备0.18小时且独占1名Crew；人员结束当前检查才可服务下一架。我希望计算现有检查班组是否能满足出动计划。'],m,
 [ev('R-prepared','preparation_finished',[.98,.98]),ev('R-launch','mission_started',[1]),ev('R-return','mission_returned',[1.35])],
 '人数影响并发准备，原需求未给。固定回答容量2后，两机并行0.8→0.98，1起飞1.35返航。','Crew capacity',
 [['Crew','人员','staff','检查班组'],['多少','几','容量','数量','capacity','many']],['resources/Crew/capacity'],
 'Crew检查班组共有2人，同时最多给两架各分配1人；其他要求保持。',
 [mutation('guess-one-person','resources[id=Crew]/capacity',1,['R-launch'])]))

m=model([air('DelayOne'),air('DelayTwo')],[process(.24,[step(.24,{'Crew':1})])],[mission('DelayedPair',.5,.3,.4,.3,2)],resources=[resource('Crew',1)],horizon=1.5)
HOLD.append(clarify('L2',[
 'DelayOne和DelayTwo为两架Utility型飞机，共同执行DelayedPair，必须凑齐两架准备完成的飞机。观察1.5小时、每0.1小时报告。Crew只有1名，每架连续准备0.24小时独占这1人。',
 '0.3小时通知开始准备，0.5小时计划起飞，飞行0.4小时。允许比计划晚一些起飞，但超过业务允许的延误就应取消，不能无期限等待。请建立这一出动模型。'],m,
 [ev('R-launch','mission_started',[.78]),ev('R-return','mission_returned',[1.18]),ev('R-cancel','mission_cancelled',[])],
 '原需求未给允许延误上限；固定答复0.3后截止0.8，串行准备0.3→0.54→0.78，可在0.78起飞。','maximum launch delay',
 [['延误','推迟','起飞','delay','launch'],['多久','多少','上限','截止','最大','maximum','limit']],['missions/DelayedPair/delay_hours'],
 '最多比计划起飞时间延误0.3小时，也就是最晚0.8小时起飞；其他要求不变。',
 [mutation('invent-zero-delay','missions[id=DelayedPair]/delay_hours',0,['R-launch'])]))

m=model([air('ClockBird',pm=pm('flight',.9,.25))],[process(0)],[mission('ClockFirst',.4,.4,.6),mission('ClockSecond',1.4,1.4,.45,priority=2)],horizon=2.4)
HOLD.append(clarify('L3',[
 'ClockBird为唯一Utility型飞机，观察2.4小时、每0.1小时报告。ClockFirst在0.4通知并起飞、飞行0.6小时；ClockSecond在1.4通知并起飞、飞行0.45小时、优先级2。两任务无需准备，不允许延误。',
 '维护间隔为0.9小时，维护本身耗时0.25小时。到期后只在地面维护，飞行不被中断，维护完成后重新计周期。请同时计算维护安排与任务执行。'],m,
 [event('R-launch','mission_started',[[.4,'ClockFirst'],[1.4,'ClockSecond']],('hour','mission')),ev('R-pm-start','pm_started',[1.85]),ev('R-pm-end','pm_finished',[2.1])],
 '0.9小时是何种时钟未明确。固定答复飞行时钟，则首次0.6未达阈值，二次结束累计1.05，于1.85维护到2.1。','maintenance clock',
 [['维护','保养','PM','maintenance'],['日历','飞行','clock','calendar','flight','计时']],['aircraft/ClockBird/pm/clock'],
 '0.9小时按实际累计飞行小时计算，地面等待不计入；跨航次累积，维护完成清零。',
 [mutation('assume-calendar-clock','aircraft[id=ClockBird]/pm/clock','calendar',['R-pm-start'])]))

m=model([air('DependencyScout','Recon',repair_mode='direct',repair_hours=.1),air('DependencyCargo','Cargo')],[process(0)],[mission('Front',.2,.2,.6,typ='Recon'),mission('Back',1,.95,.2,.2,typ='Cargo',priority=2,depends=['Front'])],horizon=1.5,events=[fault('FrontFault',.45,'DependencyScout')])
HOLD.append(clarify('L4',[
 'DependencyScout为Recon型、DependencyCargo为Cargo型；观察1.5小时、每0.1小时报告。各任务只用相应类型1架，均无需准备。Front在0.2通知并起飞、飞行0.6小时、不能延误；Back在0.95通知、1小时计划起飞、飞行0.2小时、最多延误0.2小时、优先级2。',
 'FrontFault是外部确定的故障，在0.45作用于DependencyScout，使Front记中止但按原计划返航；落地后直接维修0.1小时。Back的业务规则写着“等Front结束后才能起飞”。请据此建立任务先后关系。'],m,
 [event('R-return','mission_returned',[[.8,'Front','aborted']],('hour','mission','outcome')),event('R-launch','mission_started',[[.2,'Front']],('hour','mission')),event('R-cancel','mission_cancelled',[[1.2,'Back']],('hour','mission')),ev('R-repair','repair_finished',[.9])],
 '“结束”是否包含中止返航会改变Back能否飞行。固定答复要求成功，故Front虽0.8回来但依赖未满足，Back1.2取消。','successful predecessor completion',
 [['Front','前序','前一','依赖','predecessor'],['成功','中止','失败','success','abort','fail']],['missions/Back/depends_on'],
 'Back只有在Front成功完成并返航后才能起飞；中止或失败返航不能满足依赖，到Back截止仍未满足就取消。',
 [mutation('ignore-success-gate','missions[id=Back]/depends_on',[],['R-launch','R-cancel'])]))

# Four genuine capability gaps, without announcing the expected response class.
HOLD.append(unsupported('U1',[
 '希望使用当前有界飞机事件后端为RandomBird这架Utility型飞机建模。观察10小时，每0.1小时报告；RandomRun从0通知并起飞，原计划飞行8小时，无准备或共享资源、不允许延误；故障返航后直接维修0.3小时。',
 '故障必须由运行时按累计飞行暴露生成：相邻故障的飞行寿命服从均值2.3小时的指数分布，修复后重新采样，种子29可重复。不要提前给定故障时间表，要让引擎内生生成。'],
 [['随机','指数','random','stochastic','exponential'],['不支持','无法','缺少','未实现','unsupported','cannot'],['外生','内生','external','endogenous','RNG','rng']],
 'bounded profile只支持none/external-events/v1且operation random_requests为空；没有内生故障采样或可配置随机seed语义。'))

HOLD.append(unsupported('U2',[
 '希望使用当前有界飞机事件后端建模PreemptBird。观察2小时、每0.1小时报告，它按日历每0.5小时维护一次，维护本需0.6小时。',
 '在0.7小时收到UrgentRun紧急任务，要求立刻打断正在进行的维护、保存已完成的维护进度并马上起飞；飞行0.2小时后继续完成剩余维护。暂停期间维护进度不能增长，且不能重新从头维护。只有这一架Utility飞机，无共享资源或起飞准备。'],
 [['维护','PM','maintenance'],['中断','抢占','暂停','恢复','preempt','resume','interrupt'],['不支持','无法','缺少','未实现','unsupported','cannot']],
 '当前PM开始后只安排固定完成事件；没有暂停/取消PM令牌、保存剩余工期或恢复进度操作，不能通过零化维护时长忠实表达。'))

HOLD.append(unsupported('U3',[
 '希望使用当前有界飞机事件后端建模ParallelBird执行ParallelRun：观察1.5小时、每0.1小时报告，0.2小时通知、0.6计划起飞、飞行0.3小时、不允许延误。只有一架Utility飞机。',
 '准备在0.2小时同时启动两项独立工作：检查占Crew 1名连续0.2小时；设备校准占Rig 1台连续0.35小时。Crew容量1，Rig容量1。两项必须真实并行且各自完成就释放自己的资源，二者都完成才允许起飞。',
 '需要分别保留人员和设备的占用轨迹，不能将两项改成串行，不能把它们合为只记录总时长的一项。'],
 [['并行','parallel','同时'],['步骤','准备','资源','工作','step','process','resource'],['不支持','无法','缺少','未实现','unsupported','cannot']],
 'bounded profile对同一架同一任务只有单个顺序step索引，不提供并行DAG分叉/汇合；用max时长聚合会丢失要求的独立资源释放轨迹。'))

HOLD.append(unsupported('U4',[
 '希望使用当前有界飞机事件后端建模LiveRepairBird。观察2小时、每0.1小时报告。只有这一架Utility飞机；LiveRun在0.1通知并起飞，无准备、不能延误，飞行0.5小时。已知外生LiveFault在0.3发生，任务中止但仍于原计划时刻返航；落地后原定直接维修0.8小时。',
 '在维修已经开始后的0.9小时，NewTool投入使用：立即把正在执行维修的剩余时长改为0.2小时，因此要撤销原完成事件并改排新完成事件。这个变化只作用于当前维修，不是修改未来维修的默认时长。'],
 [['维修','repair'],['进行中','当前','剩余','in-progress','remaining','active','ongoing'],['不支持','无法','缺少','未实现','unsupported','cannot']],
 'set_repair_duration只允许没有正在维修时修改后续维修参数；运行中的直接维修duration已捕获，当前实现明确拒绝in-progress变化。'))

if __name__=='__main__':finalize()
