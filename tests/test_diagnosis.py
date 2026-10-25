import copy
import unittest
from engine.paper import start, step, REVIEW_AT
from engine.diagnostics import diagnose
from engine.scanner import initial_state, advance
from test_engine import row, NOW

class InterventionTests(unittest.TestCase):
    def test_b_pause_preserves_capital_and_still_manages_exit(self):
        s=start(REVIEW_AT-1000);p=s['portfolios']['B'];p['cash']=120
        p['positions']['ETH']=dict(candidateId='old',qty=.3,costEUR=30,openedAt=REVIEW_AT-900,checkedThrough=REVIEW_AT-900,provider='Binance',quote='USDT',entry=100,stop=90,target=120,mark=30,markedAt=REVIEW_AT-900)
        p['pending']['SOL']=dict(id='queued')
        l={'active':[],'markets':[]};m={'ETH':{'bars':[]}};q={'ETH':dict(price=85,provider='Binance',quote='USDT')}
        step(s,l,m,q,{'USDT':1},REVIEW_AT+1)
        self.assertTrue(p['entryPause']);self.assertFalse(p['pending']);self.assertFalse(p['positions'])
        self.assertEqual(sum(e['type']=='VENDITA' for e in p['ledger']),1)
        self.assertLess(p['cash'],150);self.assertEqual(s['startedAt'],REVIEW_AT-1000)
        n=sum(e['type']=='PAUSA_INGRESSI' for e in p['ledger'])
        step(s,l,m,q,{'USDT':1},REVIEW_AT+901)
        self.assertEqual(sum(e['type']=='PAUSA_INGRESSI' for e in p['ledger']),n)

    def test_a_continues_and_b_does_not_queue_new_signals(self):
        s=start(REVIEW_AT-1000)
        c=dict(id='ETH-new',symbol='ETH',status='CONFERMATO',createdAt=REVIEW_AT,confirmedAt=REVIEW_AT,provider='Binance',quote='USDT',entry=100,stop=95,target=115)
        l={'active':[c],'markets':[dict(symbol='ETH',stale=False,signal='SETUP')]}
        q={'ETH':dict(price=100,provider='Binance',quote='USDT')}
        step(s,l,{},q,{'USDT':1},REVIEW_AT+1)
        self.assertIn('ETH',s['portfolios']['A']['pending']);self.assertFalse(s['portfolios']['B']['pending'])
        step(s,l,{},q,{'USDT':1},REVIEW_AT+901)
        self.assertIn('ETH',s['portfolios']['A']['positions']);self.assertFalse(s['portfolios']['B']['positions'])

    def test_drawdown_blocks_pending_buy_on_same_scan(self):
        s=start(0);p=s['portfolios']['A'];p['cash']=137
        p['pending']['ETH']=dict(id='new',queuedAt=1,provider='Binance',quote='USDT',stop=90,target=120)
        l={'active':[dict(id='new',symbol='ETH',status='CONFERMATO',createdAt=1,stop=90,target=120)],'markets':[dict(symbol='ETH')]}
        step(s,l,{}, {'ETH':dict(price=100,provider='Binance',quote='USDT')},{'USDT':1},1000)
        self.assertTrue(p['entryPause']);self.assertFalse(p['positions']);self.assertEqual(p['cash'],137)

    def test_confirmation_diagnostics_deduplicate_same_candle(self):
        s=initial_state();advance(s,row(),[],NOW)
        r=dict(row(NOW+900),confirmationFilters={'volume':False,'trendOrario':True})
        advance(s,r,[dict(t=NOW,o=100,h=101,l=99,c=100)],NOW+900)
        advance(s,r,[],NOW+950)
        self.assertEqual(s['confirmationDiagnostics']['checks'],1)
        self.assertEqual(s['confirmationDiagnostics']['reasons'],{'volume':1})
        self.assertEqual(s['active']['SOL']['status'],'OPPORTUNITA')

    def test_audit_cohort_dedup_costs_and_no_retroactive_filters(self):
        s=start(0);p=s['portfolios']['A']
        p['ledger']=[dict(type='ACQUISTO',time=1,candidateId='new',observedPrice=100,eurRate=1),dict(type='VENDITA',time=2,candidateId='new',observedPrice=110,eurRate=1,pnlEUR=2.8,reason='Obiettivo')]
        events=[dict(id='new:OPPORTUNITA',candidateId='new',status='OPPORTUNITA',time=1),dict(id='old:CONFERMATO',candidateId='old',status='CONFERMATO',time=2)]
        before=copy.deepcopy(s);d=diagnose({},s,events+events,100)
        self.assertEqual(s,before);self.assertEqual(d['opportunities'],1);self.assertNotIn('CONFERMATO',d['counts'])
        self.assertIsNone(d['confirmationChecks']);self.assertAlmostEqual(d['portfolios']['A']['noCostClosedEUR'],3)
        self.assertAlmostEqual(d['portfolios']['A']['assumedCostImpactEUR'],.2)

    def test_review_after_seven_days_without_changing_strategy(self):
        s=start(0);d=diagnose({},s,[],7*86400)
        self.assertTrue(d['portfolios']['A']['review']);self.assertNotIn('entryPause',s['portfolios']['A'])
