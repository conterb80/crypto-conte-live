"""C / Ripartenza v1: causal, separate EUR paper experiment. No order APIs."""
import math
import statistics
from engine.scanner import ema
from engine.paper import FEE, SLIP, exit_check, valid_quote

VERSION='ripartenza-1'
RULES=dict(initialEUR=150,orderCapEUR=40,minOrderEUR=10,maxPositions=2,riskPct=.5,
           riskCapEUR=.75,portfolioRiskPct=1,minNetRR=1.5,minNetTargetPct=1,
           expiryHours=24,maxDrawdownPct=8,reviewClosed=30,reviewDays=28,
           maxSignalAgeSeconds=300,feePct=.25,slippagePct=.1)

def fresh_quote(q,provider,quote,now):
    return (valid_quote(q,provider,quote) and isinstance(q.get('observedAt'),(int,float))
            and 0<=now-q['observedAt']<=120)

def start(now,control):
    return dict(version=VERSION,startedAt=now,lastRun=None,rules=dict(RULES),cash=150.,equity=150.,peak=150.,
                maxDrawdownPct=0.,positions={},processed={},lastEntry={},ledger=[],history=[],checks={},
                controlA=dict(equityAtStart=control['equity'],closedAtStart=control.get('closedCount',0)),
                realizedEUR=0.,certainRealizedEUR=0.,uncertainRealizedEUR=0.,closedCount=0,
                uncertainCount=0,wins=0,losses=0)

def setup(m,btc):
    """All pivots, trend and pullback are known at the last closed 15m candle."""
    bars=m['bars'];hours=m['hours'];last=bars[-1];price=last['c']
    if len(bars)<110 or len(hours)<110 or not btc:return None,'Storico/BTC non disponibile'
    if m['provider']!=btc['provider'] or btc['bars'][-1]['t']!=last['t']:
        return None,'BTC non allineato'
    closes=[b['c'] for b in hours];btc_closes=[b['c'] for b in btc['hours']]
    if not (closes[-1]>ema(closes,20)>ema(closes,50) and btc_closes[-1]>ema(btc_closes,20)>ema(btc_closes,50)):
        return None,'Trend orario asset/BTC non positivo'
    average=statistics.mean(b['q'] for b in bars[-21:-1])
    if average<25000 or last['q']<average:return None,'Scambi o volume della ripresa insufficienti'
    atr=statistics.mean(max(b['h']-b['l'],abs(b['h']-a['c']),abs(b['l']-a['c'])) for a,b in zip(bars[-15:-1],bars[-14:]))
    pullback=bars[-4:-1]
    mean20=ema([b['c'] for b in bars[:-1]],20)
    if not (min(b['l'] for b in pullback)<=mean20 and any(b['c']<b['o'] for b in pullback)):
        return None,'Manca rientro verso EMA20 nelle tre candele precedenti'
    if not (price>last['o'] and price>bars[-2]['h'] and price>mean20):
        return None,'Ripartenza sopra il massimo precedente non confermata'
    stop=min(b['l'] for b in bars[-4:])-.25*atr
    risk=price-stop
    if not .008<=risk/price<=.04:return None,'Stop fuori intervallo 0,8–4%'
    # Nearest already-confirmed local high above entry, never a future pivot.
    pivots=[b['h'] for a,b,c in zip(bars[-98:-2],bars[-97:-1],bars[-96:])
            if b['h']>a['h'] and b['h']>=c['h'] and b['h']>price]
    target=min([price+2.5*risk]+pivots)
    return dict(symbol=m['symbol'],provider=m['provider'],quote=m['quote'],signalAt=last['t']+900,
                stop=stop,target=target,signalPrice=price,atr=atr,volumeRatio=last['q']/average,
                reason='Trend orario asset/BTC positivo; rientro EMA20; ripartenza sopra il massimo precedente'),None

def size_order(signal,quote,rate,equity,cash,committed):
    if not rate or not math.isfinite(rate) or rate<=0:return None,'Cambio non valido'
    entry=quote['price']*(1+SLIP);stop=signal['stop'];target=signal['target']
    if not 0<stop<entry<target:return None,'Prezzo eseguito fuori dai livelli'
    loss=1-stop*(1-SLIP)*(1-FEE)/(entry*(1+FEE))
    gain=target*(1-SLIP)*(1-FEE)/(entry*(1+FEE))-1
    if gain<RULES['minNetTargetPct']/100 or gain/loss<RULES['minNetRR']:
        return None,'Margine netto o rapporto guadagno/perdita netto insufficiente'
    budget=min(RULES['riskCapEUR'],equity*RULES['riskPct']/100,
               max(0,equity*RULES['portfolioRiskPct']/100-committed))
    amount=min(RULES['orderCapEUR'],cash,budget/loss)
    if amount<RULES['minOrderEUR']:return None,'Budget di rischio o liquidità insufficiente'
    return dict(entry=entry,amountEUR=amount,riskEUR=amount*loss,netRiskPct=loss*100,
                netTargetPct=gain*100,netRR=gain/loss,eurRate=rate,
                qty=amount/(1+FEE)/(entry*rate)),None

def checkpoint(state,paper,now):
    """Snapshot exact pre-existing V2 once; never overwrite it or reset A/B."""
    return start(now,paper['portfolios']['A']) if state is None else state

def step(state,markets,quotes,rates,now):
    if state['version']!=VERSION:raise ValueError('Esperimento C non supportato: nessun reset')
    if state['lastRun'] is not None and now<=state['lastRun']:return state
    def log(kind,**kw):state['ledger'].append(dict(time=now,type=kind,version=VERSION,**kw))
    if not state['ledger']:log('AVVIO',reason='150 EUR virtuali separati; protocollo RIPARTENZA-1 fissato prima del test')
    def pause(reason):
        if not state.get('entryPause'):
            state['entryPause']=dict(at=now,reason=reason);log('PAUSA_INGRESSI',reason=reason)
    def limits():
        if state['closedCount']>=30:pause('30 chiusure osservate: revisione del test')
        if now-state['startedAt']>=28*86400:pause('Quattro settimane: revisione del test anche con pochi ingressi')
        value=state['cash']+sum(p['mark'] for p in state['positions'].values())
        if (1-value/max(state['peak'],value))*100>=8:pause('Calo dell’8% dal massimo osservato: revisione del test')
    limits()
    for symbol,p in list(state['positions'].items()):
        m=markets.get(symbol);q=quotes.get(symbol);rate=rates.get(p['quote'])
        if not m or m['provider']!=p['provider'] or m['quote']!=p['quote'] or not fresh_quote(q,p['provider'],p['quote'],now) or not rate or not math.isfinite(rate) or rate<=0:
            p['dataInterrupted']=True;log('DATI_MANCANTI',symbol=symbol,reason='Prezzo/fonte/cambio non utilizzabile: valorizzazione conservata');continue
        bars=[b for b in m['bars'] if b['t']+900<=now]
        pending=[b for b in bars if b['t']+900>p['checkedThrough'] and b['t']+900>p['openedAt']]
        # Use full post-entry bars only; first partial bar extrema may precede entry.
        full=[b for b in pending if b['t']>=p['openedAt']]
        p['maxObservedPrice']=max([p['maxObservedPrice'],q['price']]+[b['h'] for b in full])
        p['minObservedPrice']=min([p['minObservedPrice'],q['price']]+[b['l'] for b in full])
        p['fullBars']+=len(full)
        reason,trigger_at,uncertain,checked=exit_check(p,bars,q['price'],now)
        if p.pop('dataInterrupted',False):
            uncertain.append('Una o più osservazioni senza dati utilizzabili');reason=reason or 'Chiusura dopo interruzione dati';trigger_at=trigger_at or now
        p['checkedThrough']=checked
        p['mark']=p['qty']*q['price']*(1-SLIP)*rate*(1-FEE);p['markedAt']=now
        if reason:
            net=p['mark'];state['cash']+=net
            touch=next((b for b in pending if b['l']<=p['stop'] or b['h']>=p['target']),None)
            boundary=p['stop'] if reason=='Invalidazione' else p['target'] if reason=='Obiettivo' else None
            log('VENDITA',symbol=symbol,reason=reason,netEUR=net,pnlEUR=net-p['costEUR'],
                quality='INCERTO' if uncertain else 'OSSERVATO',uncertainty=uncertain,
                openedAt=p['openedAt'],signalAt=p['signalAt'],entry=p['entry'],stop=p['stop'],target=p['target'],
                price=q['price']*(1-SLIP),observedPrice=q['price'],quote=p['quote'],eurRate=rate,
                maxRisePct=(p['maxObservedPrice']/p['entry']-1)*100,
                maxFallPct=(p['minObservedPrice']/p['entry']-1)*100,fullBars=p['fullBars'],
                entryDelaySeconds=p['openedAt']-p['signalAt'],holdSeconds=now-p['openedAt'],
                triggerAt=trigger_at,touchWindow=[max(touch['t'],p['openedAt']),touch['t']+900] if touch else None,
                boundary=boundary,exitVsBoundaryPct=(q['price']/boundary-1)*100 if boundary else None,
                plannedRiskEUR=p['riskEUR'],plannedNetRR=p['netRR'],
                noCostPnLEUR=p['costEUR']*(q['price']/p['entryObservedPrice'])*(rate/p['entryEURRate'])-p['costEUR'])
            del state['positions'][symbol]
    sales=[e for e in state['ledger'] if e['type']=='VENDITA'];certain=[e for e in sales if e['quality']=='OSSERVATO']
    state.update(realizedEUR=sum(e['pnlEUR'] for e in sales),certainRealizedEUR=sum(e['pnlEUR'] for e in certain),
                 uncertainRealizedEUR=sum(e['pnlEUR'] for e in sales if e['quality']=='INCERTO'),closedCount=len(certain),
                 uncertainCount=len(sales)-len(certain),wins=sum(e['pnlEUR']>0 for e in certain),losses=sum(e['pnlEUR']<0 for e in certain))
    state['noCostRealizedEUR']=sum(e['noCostPnLEUR'] for e in sales)
    state['costImpactEUR']=state['noCostRealizedEUR']-state['realizedEUR']
    limits()
    for symbol,m in sorted(markets.items()):
        closed=[b for b in m['bars'] if b['t']+900<=now]
        if not closed:continue
        end=closed[-1]['t']+900;identity=m['provider']+':'+symbol
        if end<=state['processed'].get(identity,0):continue
        state['processed'][identity]=end
        # Bootstrap and recovery never buy a signal that existed before test startup.
        if end<=state['startedAt'] or state.get('entryPause'):continue
        if symbol in state['positions']:continue
        if now-state['lastEntry'].get(symbol,0)<86400:continue
        if now-end>300:reason='Candela oltre cinque minuti: ingresso non inseguito';signal=None
        else:signal,reason=setup(dict(m,bars=closed),markets.get('BTC'))
        state['checks'][reason or 'Setup rilevato']=state['checks'].get(reason or 'Setup rilevato',0)+1
        if not signal:continue
        log('SEGNALE',symbol=symbol,**{k:v for k,v in signal.items() if k!='symbol'})
        q=quotes.get(symbol);rate=rates.get(m['quote'])
        if not fresh_quote(q,m['provider'],m['quote'],now):
            log('SALTATO',symbol=symbol,reason='Primo prezzo non disponibile o vecchio: nessun ingresso retroattivo');continue
        if len(state['positions'])>=2:
            log('SALTATO',symbol=symbol,reason='Due posizioni già aperte');continue
        equity=state['cash']+sum(p['mark'] for p in state['positions'].values())
        order,reason=size_order(signal,q,rate,equity,state['cash'],sum(p['riskEUR'] for p in state['positions'].values()))
        if reason:log('SALTATO',symbol=symbol,reason=reason);continue
        state['cash']-=order['amountEUR'];state['lastEntry'][symbol]=now
        state['positions'][symbol]=dict(order,provider=m['provider'],quote=m['quote'],signalAt=signal['signalAt'],
                    stop=signal['stop'],target=signal['target'],costEUR=order['amountEUR'],openedAt=now,
                    entryObservedPrice=q['price'],entryEURRate=rate,
                    checkedThrough=math.floor(now/900)*900,mark=order['qty']*q['price']*(1-SLIP)*rate*(1-FEE),
                    markedAt=now,maxObservedPrice=q['price'],minObservedPrice=q['price'],fullBars=0)
        log('ACQUISTO',symbol=symbol,signalAt=signal['signalAt'],entryDelaySeconds=now-signal['signalAt'],
            observedPrice=q['price'],price=order['entry'],stop=signal['stop'],target=signal['target'],quote=m['quote'],**order)
        limits()
    state['equity']=state['cash']+sum(p['mark'] for p in state['positions'].values())
    state['peak']=max(state['peak'],state['equity']);state['maxDrawdownPct']=max(state['maxDrawdownPct'],(1-state['equity']/state['peak'])*100)
    state['history'].append(dict(time=now,equity=state['equity'],cash=state['cash']))
    state['lastRun']=now
    state['activity']='INGRESSI SOSPESI' if state.get('entryPause') else 'POSIZIONI APERTE' if state['positions'] else 'IN ATTESA DI RIPARTENZE'
    state['dataCoverage']=len(markets)
    return state
