"""Forward-only paper simulation v2. Never submits real orders."""
import math
FEE=.0025
SLIP=.001
VERSION='paper-2'
MIN_RR=1.8
MAX_DRAWDOWN_PCT=8
REVIEW_AT=1792937700  # 25 October 2026, 14:15 UTC; prospective policy for this experiment.

def start(now):
    return {'version':VERSION,'startedAt':now,'lastRun':None,'portfolios':{k:{'name':name,'cash':150.,'positions':{},'pending':{},'seen':[],'ledger':[],'equity':150.,'peak':150.,'maxDrawdownPct':0.,'history':[]} for k,name in [('A','Conferme'),('B','Anticipato')]}}

def upgrade(state,now):
    """Return new independent experiment plus exact old state for archival."""
    if state is None:return start(now),None
    if state.get('version')==VERSION:return state,None
    if state.get('version')!='paper-1':raise ValueError('Versione paper non supportata: nessun azzeramento')
    new=start(now)
    new['previous']={'version':'paper-1','startedAt':state['startedAt'],'frozenAt':now,'lastValuationAt':state['lastRun'],'archive':'data/paper-v1-final.json','portfolios':{k:{'equity':v['equity'],'cash':v['cash'],'realizedEUR':v.get('realizedEUR',0),'openPositions':list(v['positions']),'closed':sum(e['type']=='VENDITA' for e in v['ledger'])} for k,v in state['portfolios'].items()}}
    return new,state

def valid_quote(q,provider,quote):
    return q and q.get('provider')==provider and q.get('quote')==quote and math.isfinite(q.get('price',0)) and q['price']>0

def entry_check(order,q,rate):
    fill=q['price']*(1+SLIP)
    stop,target=order['stop'],order['target']
    if not all(math.isfinite(x) and x>0 for x in (fill,stop,target,rate)) or not stop<fill<target:
        return None,'Prezzo fuori dai livelli al momento dell’ingresso'
    risk=(fill-stop)/fill;reward=(target-fill)/fill;rr=reward/risk
    # Same explicit gross RR floor for both arms; hypothetical FX held constant.
    target_net=target*(1-SLIP)*(1-FEE)/(fill*(1+FEE))-1
    stop_net=stop*(1-SLIP)*(1-FEE)/(fill*(1+FEE))-1
    audit=dict(entry=fill,stop=stop,target=target,riskPct=risk*100,rewardPct=reward*100,rr=rr,targetNetPct=target_net*100,stopNetPct=stop_net*100,eurRate=rate,fxAssumption='Cambio invariato solo per la stima dei livelli netti')
    if rr<MIN_RR:return audit,'Rapporto rischio/obiettivo al prezzo eseguito inferiore a 1,8'
    if target_net<=0:return audit,'Obiettivo insufficiente a coprire costi e slittamento ipotizzati'
    return audit,None

def exit_check(pos,bars,price,now):
    """Closed OHLC can establish a touch, but not its order inside a partial bar."""
    pending=sorted([b for b in bars if b['t']+900>pos['checkedThrough'] and b['t']+900>pos['openedAt']],key=lambda b:b['t'])
    expected=pos['checkedThrough'];uncertain=[];trigger=None;trigger_at=None
    expires=pos['openedAt']+86400
    for b in pending:
        if b['t']>=expires:
            trigger='Scadenza 24 ore';trigger_at=expires;break
        if b['t']>expected:uncertain.append('Intervallo di candele non disponibile')
        expected=max(expected,b['t']+900)
        hs=b['l']<=pos['stop'];ht=b['h']>=pos['target']
        if not (hs or ht):continue
        if b['t']<expires<b['t']+900:
            uncertain.append('Livello toccato nella candela a cavallo della scadenza: sequenza non ricostruibile')
        if b['t']<pos['openedAt']:
            uncertain.append('Livello toccato nella prima candela parziale: prima/dopo ingresso non ricostruibile')
        elif hs and ht:
            uncertain.append('Entrambi i livelli nella stessa candela: sequenza non ricostruibile')
        trigger='Invalidazione' if hs else 'Obiettivo';trigger_at=b['t']+900
        break
    if not trigger and now>=expires:trigger='Scadenza 24 ore';trigger_at=expires
    if not trigger and price<=pos['stop']:trigger='Invalidazione';trigger_at=now
    if not trigger and price>=pos['target']:trigger='Obiettivo';trigger_at=now
    if not trigger and now-pos['openedAt']>=86400:trigger='Scadenza 24 ore';trigger_at=now
    # A gap closes conservatively at current observed price with uncertain attribution.
    if uncertain and not trigger:trigger='Chiusura per dati non ricostruibili';trigger_at=now
    return trigger,trigger_at,uncertain,max([pos['checkedThrough']]+[b['t']+900 for b in pending])

def step(state,latest,markets,quotes,eur_rates,now):
    state=state or start(now)
    if state['version']!=VERSION:raise ValueError('Eseguire migrazione esplicita prima del paper v2')
    if state.get('lastRun') is not None and now<=state['lastRun']:return state
    for key,p in state['portfolios'].items():
        def log(kind,**kw):p['ledger'].append(dict(time=now,type=kind,version=VERSION,revision='paper-2.1',**kw))
        if state.get('revision')!='paper-2.1':
            log('REVISIONE',reason='Revisione 2.1: storico e capitale conservati; A invariato, nuovi ingressi B sospesi, limite calo 8% e diagnosi dei filtri attivati.')
        # Prospective intervention: keep balances, ledger and existing exits intact.
        # No automatic resumption or parameter fitting to past trades.
        if key=='B' and now>=REVIEW_AT and not p.get('entryPause'):
            p['entryPause']=dict(at=now,reason='Diagnosi 25/10: sospesi nuovi anticipi dopo 24 esiti osservati, 1 positivo e 23 negativi. Posizioni già aperte gestite fino all’uscita.')
            log('PAUSA_INGRESSI',reason=p['entryPause']['reason'])
        if p.get('maxDrawdownPct',0)>=MAX_DRAWDOWN_PCT and not p.get('entryPause'):
            p['entryPause']=dict(at=now,reason='Limite sperimentale di calo del capitale dell’8% raggiunto; nuovi ingressi sospesi per revisione.')
            log('PAUSA_INGRESSI',reason=p['entryPause']['reason'])
        for symbol,pos in list(p['positions'].items()):
            m=markets.get(symbol);q=quotes.get(symbol);rate=eur_rates.get(pos['quote'])
            if not m or m.get('provider',pos['provider'])!=pos['provider'] or not valid_quote(q,pos['provider'],pos['quote']) or not rate or not math.isfinite(rate) or rate<=0:
                pos['dataInterrupted']=True
                log('DATI_MANCANTI',symbol=symbol,reason='Uscita e valorizzazione sospese: fonte/prezzo/cambio non disponibili');continue
            reason,trigger_at,uncertain,checked=exit_check(pos,m['bars'],q['price'],now)
            if pos.pop('dataInterrupted',False):
                uncertain.append('Una o più scansioni senza prezzo/cambio: esecuzione intermedia non verificabile')
                reason=reason or 'Chiusura dopo interruzione dati';trigger_at=trigger_at or now
            pos['checkedThrough']=checked
            pos['mark']=pos['qty']*q['price']*(1-SLIP)*rate*(1-FEE);pos['markedAt']=now
            if reason:
                gross=pos['qty']*q['price']*(1-SLIP)*rate;net=gross*(1-FEE);p['cash']+=net
                log('VENDITA',symbol=symbol,candidateId=pos['candidateId'],reason=reason,price=q['price']*(1-SLIP),observedPrice=q['price'],quote=pos['quote'],eurRate=rate,netEUR=net,feeEUR=gross*FEE,pnlEUR=net-pos['costEUR'],ambiguous=bool(uncertain),quality='INCERTO' if uncertain else 'OSSERVATO',uncertainty=uncertain,openedAt=pos['openedAt'],triggerAt=trigger_at,entry=pos['entry'],stop=pos['stop'],target=pos['target'])
                del p['positions'][symbol]
        equity=p['cash']+sum(x['mark'] for x in p['positions'].values())
        drawdown=(1-equity/max(p['peak'],equity))*100
        if drawdown>=MAX_DRAWDOWN_PCT and not p.get('entryPause'):
            p['entryPause']=dict(at=now,reason='Limite sperimentale di calo del capitale dell’8% raggiunto; nuovi ingressi sospesi per revisione.')
            log('PAUSA_INGRESSI',reason=p['entryPause']['reason'])
        for symbol,order in list(p['pending'].items()):
            if p.get('entryPause'):
                log('SALTATO',symbol=symbol,candidateId=order['id'],reason='Nuovi ingressi sospesi per revisione del test');del p['pending'][symbol];continue
            if now<=order['queuedAt']:continue
            q=quotes.get(symbol);rate=eur_rates.get(order['quote']);row=next((r for r in latest['markets'] if r['symbol']==symbol),{})
            if not any(c['id']==order['id'] for c in latest['active']) or now-order['queuedAt']>3600 or row.get('stale') or row.get('signal')=='SCARTA':
                log('SALTATO',symbol=symbol,candidateId=order['id'],reason='Segnale scaduto o dati/filtri non validi');del p['pending'][symbol];continue
            if not valid_quote(q,order['provider'],order['quote']) or not rate:continue
            if symbol in p['positions'] or len(p['positions'])>=3 or p['cash']<30-1e-8:
                log('SALTATO',symbol=symbol,candidateId=order['id'],reason='Capitale o posti impegnati');del p['pending'][symbol];continue
            audit,rejection=entry_check(order,q,rate)
            if rejection:
                log('SALTATO',symbol=symbol,candidateId=order['id'],reason=rejection,entryCheck=audit);del p['pending'][symbol];continue
            fill=audit['entry'];qty=30/(1+FEE)/(fill*rate)
            p['cash']-=30;p['positions'][symbol]=dict(candidateId=order['id'],qty=qty,costEUR=30,openedAt=now,checkedThrough=math.floor(now/900)*900,provider=order['provider'],quote=order['quote'],entry=fill,stop=order['stop'],target=order['target'],mark=qty*q['price']*(1-SLIP)*rate*(1-FEE),markedAt=now,entryCheck=audit)
            log('ACQUISTO',symbol=symbol,candidateId=order['id'],price=fill,observedPrice=q['price'],quote=order['quote'],eurRate=rate,costEUR=30,feeEUR=30-30/(1+FEE),qty=qty,entryCheck=audit,signalAt=order.get('confirmedAt',order['createdAt']),queuedAt=order['queuedAt'])
            del p['pending'][symbol]
        eligible=[c for c in latest['active'] if key=='B' or c['status']=='CONFERMATO']
        eligible.sort(key=lambda c:(c.get('confirmedAt',c['createdAt']),c['symbol']))
        for c in eligible:
            if p.get('entryPause'):continue
            identity=c['id']+(':'+c['status'] if key=='A' else '')
            if identity in p['seen']:continue
            p['seen'].append(identity)
            if c.get('confirmedAt',c['createdAt'])<=state['startedAt']:continue
            if c['symbol'] in p['positions'] or c['symbol'] in p['pending']:continue
            p['pending'][c['symbol']]=dict(c,queuedAt=now)
            log('IN_ATTESA',symbol=c['symbol'],candidateId=c['id'],reason='Esecuzione dalla prossima osservazione disponibile',signalAt=c.get('confirmedAt',c['createdAt']),stop=c['stop'],target=c['target'])
        sales=[e for e in p['ledger'] if e['type']=='VENDITA']
        certain=[e for e in sales if e['quality']=='OSSERVATO']
        p['realizedEUR']=sum(e['pnlEUR'] for e in sales)
        p['certainRealizedEUR']=sum(e['pnlEUR'] for e in certain)
        p['uncertainRealizedEUR']=p['realizedEUR']-p['certainRealizedEUR']
        p['closedCount']=len(certain);p['uncertainCount']=len(sales)-len(certain)
        p['wins']=sum(e['pnlEUR']>0 for e in certain);p['losses']=sum(e['pnlEUR']<0 for e in certain)
        p['equity']=p['cash']+sum(x['mark'] for x in p['positions'].values());p['peak']=max(p['peak'],p['equity']);p['maxDrawdownPct']=max(p['maxDrawdownPct'],(1-p['equity']/p['peak'])*100)
        p['history'].append({'time':now,'equity':p['equity'],'cash':p['cash']})
        # Catch the threshold reached by this scan before any subsequent scan can buy.
        if p['maxDrawdownPct']>=MAX_DRAWDOWN_PCT and not p.get('entryPause'):
            p['entryPause']=dict(at=now,reason='Limite sperimentale di calo del capitale dell’8% raggiunto; nuovi ingressi sospesi per revisione.')
            log('PAUSA_INGRESSI',reason=p['entryPause']['reason'])
        p['activity']=('INGRESSI SOSPESI' if p.get('entryPause') else 'POSIZIONI APERTE' if p['positions'] else 'INGRESSO IN ATTESA' if p['pending'] else 'IN ATTESA DI CONFERME' if key=='A' else 'IN ATTESA DI OPPORTUNITÀ')
    state['lastRun']=now
    state['rules']={'initialEUR':150,'orderEUR':30,'maxPositions':3,'feePct':.25,'slippagePct':.1,'expiryHours':24,'minExecutedRR':MIN_RR,'positiveNetTargetRequired':True,'execution':'Prima osservazione successiva; ticker corrente con costi, mai livello storico','priority':'Ordine temporale del segnale; simbolo a parità','fx':'Cambio contemporaneo EUR/USDT Binance o EUR/USD Coinbase; nessuna parità presunta','uncertainty':'Prima candela parziale, entrambi i livelli o interruzione dati: chiusura al prezzo osservato, esito separato dalle statistiche certe'}
    state['fxAt']=now;state['eurRates']=eur_rates
    state['revision']='paper-2.1'
    state['rules']['maxDrawdownPausePct']=MAX_DRAWDOWN_PCT
    return state
