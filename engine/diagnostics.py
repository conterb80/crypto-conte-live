"""Descriptive audit only: does not choose assets or optimize strategy parameters."""
from collections import Counter

def diagnose(radar,paper,events,now):
    unique={e['id']:e for e in events}
    cohort={e['candidateId'] for e in unique.values() if e['status']=='OPPORTUNITA' and e['time']>=paper['startedAt']}
    cohort_events=[e for e in unique.values() if e['candidateId'] in cohort]
    counts=Counter(e['status'] for e in cohort_events)
    outcomes=Counter(e['reason'] for e in cohort_events if e['status'] not in ('OPPORTUNITA','CONFERMATO'))
    portfolios={}
    for key,p in paper['portfolios'].items():
        buys={e['candidateId']:e for e in p['ledger'] if e['type']=='ACQUISTO'}
        sales=[e for e in p['ledger'] if e['type']=='VENDITA']
        matched=[e for e in sales if e['candidateId'] in buys]
        # Same observed prices and contemporaneous FX, removing only assumed fees/slip.
        no_cost=sum(30*(e['observedPrice']/buys[e['candidateId']]['observedPrice'])*(e['eurRate']/buys[e['candidateId']]['eurRate'])-30 for e in matched)
        net=sum(e['pnlEUR'] for e in matched)
        last_trade=max((e['time'] for e in p['ledger'] if e['type'] in ('ACQUISTO','VENDITA')),default=None)
        reasons=Counter(e['reason'] for e in sales)
        review=[]
        if p.get('entryPause'):review.append('Nuovi ingressi sospesi: revisione richiesta prima della ripresa')
        elif p.get('closedCount',0)>=20:review.append('Campione di almeno 20 chiusure osservate: bilancio da rivedere')
        if key=='A' and now-paper['startedAt']>=7*86400 and p.get('closedCount',0)<5:
            review.append('Sette giorni con meno di 5 chiusure: verificare selettività e filtri')
        portfolios[key]=dict(lastTradeAt=last_trade,sales=len(sales),exitReasons=dict(reasons),netClosedEUR=net,
                             noCostClosedEUR=no_cost,assumedCostImpactEUR=no_cost-net,review=review)
    return dict(since=paper['startedAt'],asOf=now,opportunities=len(cohort),counts=dict(counts),outcomes=dict(outcomes),
                confirmationChecks=radar.get('confirmationDiagnostics'),portfolios=portfolios,
                limits='Le cause precise dei filtri vengono registrate dalla revisione 2.1; non sono ricostruite retroattivamente. I costi sono ipotesi del simulatore, non tariffe Revolut.')
