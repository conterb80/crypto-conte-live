import unittest
from engine.paper import step
class PaperTests(unittest.TestCase):
 def data(self,t,status='OPPORTUNITA',sym='ETH'):
  c=dict(id=sym+'-'+str(t),symbol=sym,status=status,createdAt=t,entry=100,stop=90,target=120,provider='Binance',quote='USDT')
  if status=='CONFERMATO':c['confirmedAt']=t
  return dict(active=[c],markets=[dict(symbol=sym,signal='SETUP',stale=False)]),{sym:dict(bars=[dict(t=t-900,o=100,h=101,l=99,c=100)])},{sym:dict(price=100,quote='USDT',provider='Binance')}
 def test_no_retroactive_fill_and_next_observation(self):
  l,m,q=self.data(1000);s=step(None,l,m,q,{'USDT':.9},1000);self.assertFalse(s['portfolios']['B']['pending'])
  l,m,q=self.data(2000);step(s,l,m,q,{'USDT':.9},2000);self.assertIn('ETH',s['portfolios']['B']['pending']);self.assertFalse(s['portfolios']['A']['pending'])
  step(s,l,m,q,{'USDT':.9},2900);p=s['portfolios']['B'];self.assertAlmostEqual(p['cash'],120);self.assertLess(p['equity'],150)
 def test_confirmation_and_fx_required(self):
  l,m,q=self.data(1000);s=step(None,l,m,q,{},1000);l,m,q=self.data(2000,'CONFERMATO');step(s,l,m,q,{},2000);step(s,l,m,q,{},2900);self.assertFalse(s['portfolios']['A']['positions'])
  step(s,l,m,q,{'USDT':1},3000);self.assertIn('ETH',s['portfolios']['A']['positions'])
 def test_exit_at_observed_price_and_idempotence(self):
  l,m,q=self.data(1000);s=step(None,l,m,q,{'USDT':1},1000);l,m,q=self.data(2000);step(s,l,m,q,{'USDT':1},2000);step(s,l,m,q,{'USDT':1},2900)
  q['ETH']['price']=85;step(s,l,m,q,{'USDT':1},3800);p=s['portfolios']['B'];sell=[e for e in p['ledger'] if e['type']=='VENDITA'][0];self.assertAlmostEqual(sell['price'],84.915);self.assertLess(sell['pnlEUR'],0);n=len(p['ledger']);step(s,l,m,q,{'USDT':1},3800);self.assertEqual(n,len(p['ledger']))
 def test_capacity_and_expiry(self):
  l,m,q=self.data(1000);s=step(None,l,m,q,{'USDT':1},1000)
  for i,sym in enumerate(['ETH','SOL','XRP','ADA']):
   t=2000+i*2000;l,m,q=self.data(t,sym=sym);step(s,l,m,q,{'USDT':1},t);step(s,l,m,q,{'USDT':1},t+900)
  p=s['portfolios']['B'];self.assertEqual(len(p['positions']),3);self.assertAlmostEqual(p['cash'],60);self.assertTrue(any(e['type']=='SALTATO' for e in p['ledger']))
  l,m,q=self.data(100000);l['active']=[];step(s,l,m,q,{'USDT':1},100000);self.assertNotIn('ETH',p['positions'])

class PaperV2Tests(unittest.TestCase):
 def test_upgrade_preserves_old_exactly_and_starts_separate_capital(self):
  import copy
  from engine.paper import upgrade
  old={'version':'paper-1','startedAt':1,'lastRun':2,'portfolios':{k:{'equity':140,'cash':110,'realizedEUR':-10,'positions':{'BTC':{'mark':30}},'ledger':[]} for k in ('A','B')}}
  original=copy.deepcopy(old);new,archive=upgrade(old,3000)
  self.assertEqual(archive,original);self.assertEqual(old,original);self.assertEqual(new['portfolios']['A']['cash'],150);self.assertFalse(new['portfolios']['A']['positions']);self.assertEqual(new['previous']['portfolios']['A']['openPositions'],['BTC'])
  self.assertIsNone(upgrade(new,4000)[1])
 def test_entry_revalidates_rr_after_slippage_and_costs(self):
  from engine.paper import entry_check
  q={'price':101.8};order={'stop':99,'target':102}
  audit,error=entry_check(order,q,1);self.assertIsNotNone(error);self.assertLess(audit['rr'],1.8)
  audit,error=entry_check({'stop':99.99,'target':100.04},{'price':100},1);self.assertIsNotNone(error)
 def test_net_target_rejects_tiny_move_even_with_good_gross_rr(self):
  from engine.paper import entry_check
  # Fill=100.1, gross risk 0.02 and reward 0.05, but fees wipe the target.
  audit,error=entry_check({'stop':100.08,'target':100.15},{'price':100},1)
  self.assertGreater(audit['rr'],1.8);self.assertLess(audit['targetNetPct'],0);self.assertIn('costi',error)
 def test_first_partial_candle_touch_is_uncertain_not_silently_ignored(self):
  from engine.paper import exit_check
  pos=dict(openedAt=60,checkedThrough=0,stop=90,target=120)
  reason,t,uncertain,checked=exit_check(pos,[dict(t=0,l=85,h=101)],95,930)
  self.assertEqual(reason,'Invalidazione');self.assertTrue(uncertain);self.assertEqual(checked,900)
 def test_full_candle_double_touch_and_gap_are_uncertain(self):
  from engine.paper import exit_check
  pos=dict(openedAt=0,checkedThrough=0,stop=90,target=120)
  self.assertTrue(exit_check(pos,[dict(t=0,l=85,h=125)],100,930)[2])
  self.assertTrue(exit_check(pos,[dict(t=1800,l=99,h=101)],100,2730)[2])
 def test_expiry_precedes_later_candle_hit(self):
  from engine.paper import exit_check
  pos=dict(openedAt=0,checkedThrough=86400,stop=90,target=120)
  reason,_,_,_=exit_check(pos,[dict(t=86400,l=80,h=130)],80,87330)
  self.assertEqual(reason,'Scadenza 24 ore')
 def test_uncertain_cash_is_included_but_excluded_from_certain_statistics(self):
  from engine.paper import start,step
  s=start(0);p=s['portfolios']['B'];p['cash']=120
  p['positions']['ETH']=dict(candidateId='ETH-1',qty=.3,costEUR=30,openedAt=60,checkedThrough=0,provider='Binance',quote='USDT',entry=100,stop=90,target=120,mark=30,markedAt=60)
  step(s,{'active':[],'markets':[]},{'ETH':{'bars':[dict(t=0,l=85,h=101)]}},{'ETH':dict(price=95,provider='Binance',quote='USDT')},{'USDT':1},930)
  self.assertEqual(p['uncertainCount'],1);self.assertEqual(p['closedCount'],0);self.assertEqual(p['certainRealizedEUR'],0);self.assertAlmostEqual(p['cash']-150,p['uncertainRealizedEUR']);self.assertEqual(p['ledger'][-1]['quality'],'INCERTO')
 def test_unavailable_price_then_recovery_is_uncertain(self):
  from engine.paper import start,step
  s=start(0);p=s['portfolios']['B'];p['cash']=120
  p['positions']['ETH']=dict(candidateId='ETH-1',qty=.3,costEUR=30,openedAt=0,checkedThrough=0,provider='Binance',quote='USDT',entry=100,stop=90,target=120,mark=30,markedAt=0)
  l={'active':[],'markets':[]};step(s,l,{}, {},{},500)
  step(s,l,{'ETH':{'bars':[dict(t=0,l=99,h=101)]}},{'ETH':dict(price=100,provider='Binance',quote='USDT')},{'USDT':1},930)
  self.assertEqual(p['uncertainCount'],1);self.assertFalse(p['positions'])
