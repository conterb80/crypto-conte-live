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
