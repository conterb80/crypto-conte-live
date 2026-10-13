"""Public market analysis only. No credentials, accounts or order endpoints."""
import concurrent.futures
import datetime as dt
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
import urllib.error
import urllib.request

SYMS = ['BTC','ETH','SOL','XRP','LINK','AVAX','NEAR','ADA','DOGE','LTC','UNI','AAVE','DOT','ATOM','ARB','OP','SUI','INJ','FIL','RENDER']
VERSION = 'LIVE-4.0.0'
INTERVAL = 900
TERMINAL = {'FALLITO','SCADUTO','OBIETTIVO_TEORICO','INVALIDATO','INDETERMINATO'}

def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat().replace('+00:00','Z')

def request_json(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'CryptoConteLIVE/4 public-analysis','Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt == 2:
                raise RuntimeError(f'HTTP {exc.code}') from exc
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise RuntimeError(str(exc)) from exc
        time.sleep(1.5 * (attempt+1))

def validate(bars, interval, now):
    bars = sorted({b['t']:b for b in bars if b['t']+interval <= now}.values(), key=lambda b:b['t'])
    if len(bars) < 110:
        raise ValueError('Storico insufficiente')
    for b in bars:
        if not all(math.isfinite(b[k]) for k in ('t','o','h','l','c','v')) or min(b['o'],b['h'],b['l'],b['c']) <= 0 or b['v'] < 0:
            raise ValueError('Candela non valida')
        if b['h'] < max(b['o'],b['c'],b['l']) or b['l'] > min(b['o'],b['c'],b['h']):
            raise ValueError('OHLC incoerenti')
    if now - (bars[-1]['t']+interval) > interval + 120:
        raise ValueError('Fonte non aggiornata')
    if any(b['t']-a['t'] != interval for a,b in zip(bars[-110:],bars[-109:])):
        raise ValueError('Candele mancanti nello storico recente')
    return bars

def fetch_bars(symbol, provider, interval, now):
    if provider == 'Binance':
        granularity = '15m' if interval == 900 else '1h'
        raw = request_json(f'https://data-api.binance.vision/api/v3/klines?symbol={symbol}USDT&interval={granularity}&limit=300')
        if not isinstance(raw,list):
            raise ValueError('Risposta inattesa')
        bars = [dict(t=int(c[0])/1000,o=float(c[1]),h=float(c[2]),l=float(c[3]),c=float(c[4]),v=float(c[5]),q=float(c[7])) for c in raw]
    else:
        raw = request_json(f'https://api.exchange.coinbase.com/products/{symbol}-USD/candles?granularity={interval}')
        if not isinstance(raw,list):
            raise ValueError('Risposta inattesa')
        bars = [dict(t=int(c[0]),l=float(c[1]),h=float(c[2]),o=float(c[3]),c=float(c[4]),v=float(c[5]),q=float(c[5])*float(c[4])) for c in raw]
    return validate(bars,interval,now)

def fetch_market(symbol, provider, now):
    return {'symbol':symbol,'provider':provider,'quote':'USDT' if provider=='Binance' else 'USD',
            'bars':fetch_bars(symbol,provider,900,now),'hours':fetch_bars(symbol,provider,3600,now)}

def ema(values, period):
    value=values[0]
    for x in values[1:]:
        value=x*2/(period+1)+value*(1-2/(period+1))
    return value

def assess(market, btc, now):
    bars, hours = market['bars'], market['hours']
    last=bars[-1]; price=last['c']
    change=lambda n:(price/bars[-1-n]['c']-1)*100
    trend, trend4h, trend24h, momentum = change(4),change(16),change(96),change(1)
    average=statistics.mean(b['q'] for b in bars[-21:-1])
    ratio=last['q']/average if average>0 else 0
    comparable=btc and btc['bars'][-1]['t']==last['t'] and btc['provider']==market['provider']
    relative=trend4h-(btc['bars'][-1]['c']/btc['bars'][-17]['c']-1)*100 if comparable else None
    hcloses=[b['c'] for b in hours]
    uptrend=hcloses[-1]>ema(hcloses,20)>ema(hcloses,50)
    atr=statistics.mean(max(b['h']-b['l'],abs(b['h']-a['c']),abs(b['l']-a['c'])) for a,b in zip(bars[-15:-1],bars[-14:]))
    risk=max(2*atr,price*.006)
    stop=price-risk
    resistance=max(b['h'] for b in bars[-97:-1])
    target=max(resistance,price+2*risk)
    liquid=average>=25000
    strength=trend4h>.4 if market['symbol']=='BTC' else relative is not None and relative>.25
    flags=[('Trend orario positivo',uptrend,2),('Trend 4 ore positivo',trend4h>.4,1),
           ('Volumi in aumento',ratio>=1.5,2),('Forza rispetto a BTC',strength,1),
           ('Movimento moderato',0<momentum<3 and trend>.2,1),('Scambi sufficienti',liquid,1)]
    score=sum(weight for _,ok,weight in flags if ok)
    blocked=not comparable or not liquid or risk/price>.05 or momentum>=3 or trend24h>=15 or trend4h<-2 or stop<=0
    qualified=not blocked and score>=7 and uptrend and ratio>=1.5 and strength
    signal='SCARTA' if blocked else 'SETUP' if qualified else 'PRE-RADAR' if score>=5 and trend>0 else 'OSSERVA'
    reason='; '.join(label for label,ok,_ in flags if ok) or 'Nessuna combinazione sufficiente'
    if not comparable:
        reason='BTC non disponibile o non allineato: nuove opportunità sospese'
    elif blocked:
        reason='Filtro prudenziale: liquidità, estensione del movimento o trend sfavorevole'
    return {k:market[k] for k in ('symbol','provider','quote')} | dict(price=price,time=now,candleTime=last['t']+900,
           stale=False,signal=signal,score=score,qualified=qualified,ratio=ratio,trend=trend,trend4h=trend4h,
           trend24h=trend24h,relative=relative,entry=price,stop=stop,target=target,rr=(target-price)/risk,
           reason=reason,targetMethod='Massimo delle 24 ore oppure proiezione di 2 volte il rischio; non è una previsione')

def initial_state():
    return dict(schema=1,version=VERSION,cache={},active={},events=[],totals={},lastSuccess=None,runs=0)

def record(state,candidate,status,now,reason,price=None):
    event=dict(id=f"{candidate['id']}:{status}",candidateId=candidate['id'],symbol=candidate['symbol'],status=status,
               time=now,reason=reason,price=price,quote=candidate['quote'],provider=candidate['provider'],
               entry=candidate['entry'],stop=candidate['stop'],target=candidate['target'])
    if status in TERMINAL:
        state['totals'][status]=state['totals'].get(status,0)+1
        event['confirmed']=candidate['status']=='CONFERMATO'
        if status in {'OBIETTIVO_TEORICO','FALLITO','SCADUTO'} and candidate['status']=='CONFERMATO' and price:
            event['changePct']=(price/candidate['entry']-1)*100
    state['events'].insert(0,event)
    return event

def advance(state,row,bars,now):
    symbol=row['symbol']; candidate=state['active'].get(symbol); emitted=[]
    def end(status,reason,price=None):
        emitted.append(record(state,candidate,status,now,reason,price))
        del state['active'][symbol]
    if candidate:
        if row['provider']!=candidate['provider'] or row['quote']!=candidate['quote']:
            end('INDETERMINATO','Fonte o valuta cambiata: esito non confrontabile')
            return emitted
        if row['candleTime']<=candidate['checkedThrough']:
            candidate['lastSeen']=now
            return emitted
        pending=[b for b in bars if b['t']>=candidate['checkedThrough']]
        if pending and (pending[0]['t']>candidate['checkedThrough'] or any(b['t']-a['t']!=900 for a,b in zip(pending,pending[1:]))):
            end('INDETERMINATO','Intervallo senza dati: impossibile ricostruire l’esito')
            return emitted
        expires=candidate.get('confirmedAt',candidate['createdAt'])+(48*3600 if candidate['status']=='CONFERMATO' else 12*3600)
        for b in pending:
            if b['t']>=expires:
                end('SCADUTO','Finestra di osservazione terminata',b['o'])
                return emitted
            # OHLC cannot determine ordering if both boundaries are touched.
            hit_stop=b['l']<=candidate['stop']; hit_target=b['h']>=candidate['target']
            if (hit_stop or hit_target) and b['t']<candidate.get('eligibleAt',candidate['createdAt']):
                end('INDETERMINATO','Livello toccato nella candela parzialmente precedente alla rilevazione: ordine temporale sconosciuto')
                return emitted
            if hit_stop and hit_target:
                end('INDETERMINATO','Obiettivo e invalidazione nella stessa candela: ordine sconosciuto')
                return emitted
            if hit_stop:
                end('FALLITO' if candidate['status']=='CONFERMATO' else 'INVALIDATO','Livello di invalidazione toccato',min(b['o'],candidate['stop']))
                return emitted
            if hit_target:
                end('OBIETTIVO_TEORICO' if candidate['status']=='CONFERMATO' else 'SCADUTO',
                    'Obiettivo teorico toccato' if candidate['status']=='CONFERMATO' else 'Movimento già avvenuto prima della conferma',candidate['target'])
                return emitted
        candidate['checkedThrough']=row['candleTime']
        candidate['lastPrice']=row['price']; candidate['lastSeen']=now
        if row['candleTime']>=expires:
            end('SCADUTO','Finestra di osservazione terminata',row['price'])
            return emitted
        if candidate['status']=='OPPORTUNITA' and row['candleTime']>candidate['createdAt']:
            if row['signal']=='SCARTA':
                end('INVALIDATO','I filtri di mercato non sono più superati',row['price'])
            elif row['qualified'] and row['price']>candidate['stop'] and (candidate['target']-row['price'])/(row['price']-candidate['stop'])>=1.8:
                candidate.update(status='CONFERMATO',confirmedAt=row['candleTime'],eligibleAt=now,entry=row['price'])
                state['totals']['CONFERMATO']=state['totals'].get('CONFERMATO',0)+1
                emitted.append(record(state,candidate,'CONFERMATO',now,'Conferma su una candela successiva; livelli congelati',row['price']))
        return emitted
    if row['signal'] in ('PRE-RADAR','SETUP'):
        candidate=dict(id=f"{symbol}-{int(row['candleTime'])}",symbol=symbol,status='OPPORTUNITA',createdAt=row['candleTime'],
                       checkedThrough=row['candleTime'],lastSeen=now,lastPrice=row['price'],eligibleAt=now,
                       **{k:row[k] for k in ('entry','stop','target','provider','quote')})
        state['active'][symbol]=candidate
        state['totals']['OPPORTUNITA']=state['totals'].get('OPPORTUNITA',0)+1
        emitted.append(record(state,candidate,'OPPORTUNITA',now,row['reason'],row['price']))
    return emitted

def analyse(state,markets,errors,now):
    emitted=[]; btc=markets.get('BTC'); good=0
    for symbol in SYMS:
        if symbol not in markets:
            previous=state['cache'].get(symbol,{ 'symbol':symbol,'signal':'NON DISPONIBILE','time':now })
            state['cache'][symbol]=previous | dict(stale=True,error=errors.get(symbol,'Dati mancanti'))
            continue
        row=assess(markets[symbol],btc,now)
        emitted+=advance(state,row,markets[symbol]['bars'],now)
        candidate=state['active'].get(symbol)
        if candidate:
            row['candidate']=candidate.copy()
        state['cache'][symbol]=row; good+=1
    state['runs']+=1
    if good==len(SYMS):
        state['lastSuccess']=now
    state['events']=state['events'][:500]
    health='ok' if good==len(SYMS) else 'partial' if good else 'error'
    latest=dict(schema=1,version=VERSION,generatedAt=now,lastFullSuccess=state['lastSuccess'],runNumber=state['runs'],
                health=health,coverage=good,total=len(SYMS),intervalMinutes=15,errors=errors,
                runUrl=os.getenv('RUN_URL',''),markets=[state['cache'][s] for s in SYMS],
                active=list(state['active'].values()),totals=state['totals'],events=state['events'][:80])
    return latest,emitted

def save_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf8')
    tmp.replace(path)

def main():
    root=Path(os.getenv('DATA_DIR','data')); now=time.time(); state_path=root/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else initial_state()
    if state.get('schema')!=1:
        raise ValueError('Schema storico non supportato; nessun azzeramento automatico')
    markets={}; errors={}; provider=None; failures=[]
    for source in ('Binance','Coinbase'):
        try:
            markets['BTC']=fetch_market('BTC',source,now); provider=source; break
        except Exception as exc:
            failures.append(f'{source}: {exc}')
    if provider:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            tasks={pool.submit(fetch_market,s,provider,now):s for s in SYMS if s!='BTC'}
            for task in concurrent.futures.as_completed(tasks):
                symbol=tasks[task]
                try:
                    markets[symbol]=task.result()
                except Exception as exc:
                    errors[symbol]=f'{provider}: {exc}'
    else:
        errors={s:'; '.join(failures) for s in SYMS}
    latest,events=analyse(state,markets,errors,now)
    latest['sourceNotes']=failures
    for event in events:
        month=dt.datetime.fromtimestamp(event['time'],dt.timezone.utc).strftime('%Y-%m')
        archive=root/'archive'/f'{month}.jsonl'; archive.parent.mkdir(parents=True,exist_ok=True)
        with archive.open('a',encoding='utf8') as out:
            out.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
    save_json(state_path,state); save_json(root/'latest.json',latest)
    summary=f"{VERSION}: {latest['coverage']}/20 mercati; stato {latest['health']}; {len(events)} eventi; fonte {provider or 'non disponibile'}"
    print(summary)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:
            out.write('## Crypto Conte LIVE\n\n'+summary+'\n\n'+''.join(f'- {s}: {e}\n' for s,e in errors.items()))
    return 0 if latest['health']=='ok' else 1

if __name__=='__main__':
    sys.exit(main())
