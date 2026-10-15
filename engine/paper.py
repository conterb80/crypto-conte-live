"""Forward-only virtual portfolios. No order endpoints or account credentials."""
import math
FEE=.0025
SLIP=.001
VERSION='paper-1'

def start(now):
    return {'version':VERSION,'startedAt':now,'lastRun':None,'portfolios':{k:{'name':name,'cash':150.,'positions':{},'pending':{},'seen':[],'ledger':[],'equity':150.,'peak':150.,'maxDrawdownPct':0.,'history':[]} for k,name in [('A','Conferme'),('B','Anticipato')]}}

def step(state,latest,markets,quotes,eur_rates,now):
    state=state or start(now)
    if state['version']!=VERSION: raise ValueError('Versione paper non supportata')
    if state.get('lastRun')==now:return state
    for key,p in state['portfolios'].items():
        def log(kind,**kw):p['ledger'].append(dict(time=now,type=kind,**kw))
        for symbol,pos in list(p['positions'].items()):
            m=markets.get(symbol);q=quotes.get(symbol);rate=eur_rates.get(pos['quote'])
            if not m or not q or q['provider']!=pos['provider'] or q['quote']!=pos['quote'] or not rate:
                log('DATI_MANCANTI',symbol=symbol,reason='Uscita e valorizzazione sospese: fonte/prezzo/cambio non disponibili');continue
            bars=[b for b in m['bars'] if b['t']>=pos['checkedThrough'] and b['t']>=pos['openedAt']]
            reason=pos.get('exitPending');ambiguous=False
            if bars and bars[0]['t']>pos['checkedThrough']+900:log('INTERVALLO_MANCANTE',symbol=symbol,reason='Movimenti intermedi non ricostruibili')
            for b in bars:
                stop=b['l']<=pos['stop'];target=b['h']>=pos['target']
                if stop or target:
                    reason='Invalidazione' if stop else 'Obiettivo';ambiguous=stop and target;break
            if now-pos['openedAt']>=86400 and not reason:reason='Scadenza 24 ore'
            # The current observation is the executable simulation price, never a historical boundary.
            if q['price']<=pos['stop']:reason=reason or 'Invalidazione'
            if q['price']>=pos['target']:reason=reason or 'Obiettivo'
            pos['checkedThrough']=m['bars'][-1]['t']+900
            pos['mark']=pos['qty']*q['price']*(1-SLIP)*rate*(1-FEE);pos['markedAt']=now
            if reason:
                gross=pos['qty']*q['price']*(1-SLIP)*rate;net=gross*(1-FEE);p['cash']+=net
                log('VENDITA',symbol=symbol,candidateId=pos['candidateId'],reason=reason,price=q['price']*(1-SLIP),quote=pos['quote'],eurRate=rate,netEUR=net,feeEUR=gross*FEE,pnlEUR=net-30,ambiguous=ambiguous,openedAt=pos['openedAt'])
                del p['positions'][symbol]
        # Only pending signals observed in a previous run may be filled.
        for symbol,order in list(p['pending'].items()):
            q=quotes.get(symbol);rate=eur_rates.get(order['quote']);row=next((r for r in latest['markets'] if r['symbol']==symbol),{})
            if now-order['queuedAt']>3600 or row.get('stale') or row.get('signal')=='SCARTA':
                log('SALTATO',symbol=symbol,reason='Segnale scaduto o dati/filtri non validi');del p['pending'][symbol];continue
            if not q or q['provider']!=order['provider'] or q['quote']!=order['quote'] or not rate:continue
            if not order['stop']<q['price']<order['target']:
                log('SALTATO',symbol=symbol,reason='Prezzo già oltre i livelli prima dell’ingresso');del p['pending'][symbol];continue
            if symbol in p['positions'] or len(p['positions'])>=3 or p['cash']<30-1e-8:
                log('SALTATO',symbol=symbol,reason='Capitale o posti impegnati');del p['pending'][symbol];continue
            fill=q['price']*(1+SLIP);qty=(30/(1+FEE))/(fill*rate)
            if fill>=order['target']:
                log('SALTATO',symbol=symbol,reason='Slittamento oltre obiettivo');del p['pending'][symbol];continue
            p['cash']-=30;p['positions'][symbol]=dict(candidateId=order['id'],qty=qty,openedAt=now,checkedThrough=math.ceil(now/900)*900,provider=order['provider'],quote=order['quote'],entry=fill,stop=order['stop'],target=order['target'],mark=qty*q['price']*(1-SLIP)*rate*(1-FEE),markedAt=now)
            log('ACQUISTO',symbol=symbol,candidateId=order['id'],price=fill,quote=order['quote'],eurRate=rate,costEUR=30,feeEUR=30-30/(1+FEE),qty=qty)
            del p['pending'][symbol]
        # Seed all existing candidates at activation: no retroactive entries.
        eligible=[c for c in latest['active'] if key=='B' or c['status']=='CONFERMATO']
        eligible.sort(key=lambda c:(c.get('confirmedAt',c['createdAt']),c['symbol']))
        for c in eligible:
            identity=c['id']+(':'+c['status'] if key=='A' else '')
            if identity in p['seen']:continue
            p['seen'].append(identity)
            if c.get('confirmedAt',c['createdAt'])<=state['startedAt']:continue
            if c['symbol'] in p['positions'] or c['symbol'] in p['pending']:continue
            p['pending'][c['symbol']]=dict(c,queuedAt=now)
            log('IN_ATTESA',symbol=c['symbol'],candidateId=c['id'],reason='Esecuzione dalla prossima osservazione disponibile')
        p['equity']=p['cash']+sum(x['mark'] for x in p['positions'].values());p['peak']=max(p['peak'],p['equity']);p['maxDrawdownPct']=max(p['maxDrawdownPct'],(1-p['equity']/p['peak'])*100)
        p['history'].append({'time':now,'equity':p['equity'],'cash':p['cash']})
    state['lastRun']=now
    state['rules']={'initialEUR':150,'orderEUR':30,'maxPositions':3,'feePct':.25,'slippagePct':.1,'expiryHours':24,'execution':'Prima osservazione successiva; prezzo corrente, mai livello storico','priority':'Ordine temporale del segnale; simbolo a parità','fx':'Cambio contemporaneo EUR/USDT Binance o EUR/USD Coinbase; senza cambio nessun acquisto','gaps':'Valori conservati e anomalie registrate; uscita al primo prezzo osservato disponibile'}
    state['fxAt']=now;state['eurRates']=eur_rates
    return state
