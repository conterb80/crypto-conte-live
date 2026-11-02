import copy
import unittest
from unittest.mock import patch
from engine.pullback import start, setup, size_order, step

T=1800000000

def market(symbol='ETH'):
    bars=[dict(t=T-(110-i)*900,o=100+i*.1,c=100+i*.1+.03,h=100+i*.1+.12,l=100+i*.1-.12,q=100000,v=1000) for i in range(110)]
    bars[-3].update(o=110.5,c=110.2,h=110.6,l=109.7)
    bars[-2].update(o=110.3,c=110.2,h=110.5,l=110.0)
    bars[-1].update(o=110.4,c=111.3,h=111.6,l=110.3,q=200000)
    hours=[dict(t=T-(110-i)*3600,c=80+i*.3) for i in range(110)]
    return dict(symbol=symbol,provider='Binance',quote='USDT',bars=bars,hours=hours)

def signal(symbol='ETH'):
    return dict(symbol=symbol,provider='Binance',quote='USDT',signalAt=T,stop=98,target=106,signalPrice=100,reason='test')

def quote(price=100,at=T+30):
    return dict(price=price,provider='Binance',quote='USDT',observedAt=at)

def state():return start(T-1800,dict(equity=143,closedCount=17))

class PullbackTests(unittest.TestCase):
    def test_setup_is_causal_and_requires_rientro_then_break(self):
        m=market();sig,reason=setup(m,market('BTC'))
        self.assertIsNone(reason);self.assertGreater(sig['target'],sig['signalPrice'])
        self.assertLess(sig['stop'],sig['signalPrice'])
        m['bars'][-1]['c']=110.4
        self.assertIsNone(setup(m,market('BTC'))[0])

    def test_trend_btc_volume_and_risk_filters(self):
        m=market();btc=market('BTC');btc['hours'][-1]['c']=10
        self.assertIn('Trend',setup(m,btc)[1])
        m['bars'][-1]['q']=1
        self.assertIn('volume',setup(m,market('BTC'))[1])
        m=market();m['bars'][-3]['l']=10
        self.assertIn('Stop',setup(m,market('BTC'))[1])

    def test_nearest_known_resistance_caps_target(self):
        m=market();m['bars'][-10]['h']=112
        sig,_=setup(m,market('BTC'));self.assertEqual(sig['target'],112)

    def test_net_costs_risk_and_position_caps(self):
        order,error=size_order(signal(),quote(),.9,150,150,0)
        self.assertIsNone(error);self.assertLessEqual(order['amountEUR'],40)
        self.assertLessEqual(order['riskEUR'],.75+1e-9);self.assertGreaterEqual(order['netRR'],1.5)
        self.assertIsNotNone(size_order(dict(signal(),target=100.3),quote(),1,150,150,0)[1])
        self.assertIsNotNone(size_order(signal(),quote(),1,150,150,1.5)[1])
        self.assertIsNotNone(size_order(signal(),quote(),None,150,150,0)[1])
        self.assertIsNotNone(size_order(signal(),quote(110),1,150,150,0)[1])

    @patch('engine.pullback.setup',side_effect=lambda m,b:(signal(m['symbol']),None))
    def test_first_live_quote_no_extra_candle_wait_and_no_duplicates(self,_):
        s=state();m={'ETH':market(),'BTC':market('BTC')}
        # BTC absent quote does not get a fictional fill.
        step(s,m,{'ETH':quote()},{'USDT':1},T+30)
        self.assertIn('ETH',s['positions']);self.assertEqual(s['positions']['ETH']['openedAt'],T+30)
        buys=sum(e['type']=='ACQUISTO' for e in s['ledger'])
        step(s,m,{'ETH':quote(at=T+50)},{'USDT':1},T+50)
        self.assertEqual(sum(e['type']=='ACQUISTO' for e in s['ledger']),buys)
        self.assertEqual(s['positions']['ETH']['costEUR']+s['cash'],150)

    def test_bootstrap_and_stale_signal_never_backfill(self):
        s=start(T+10,dict(equity=143));step(s,{'ETH':market()}, {'ETH':quote()}, {'USDT':1},T+30)
        self.assertFalse(s['positions'])
        s=state();step(s,{'ETH':market()}, {'ETH':quote(at=T+600)}, {'USDT':1},T+600)
        self.assertFalse(s['positions']);self.assertTrue(any('cinque minuti' in k for k in s['checks']))

    @patch('engine.pullback.setup',return_value=(signal(),None))
    def test_stale_quote_rejected_without_future_fill(self,_):
        s=state();step(s,{'ETH':market()}, {'ETH':quote(at=T-200)}, {'USDT':1},T+30)
        self.assertFalse(s['positions']);self.assertEqual(s['ledger'][-1]['type'],'SALTATO')

    @patch('engine.pullback.setup',return_value=(signal(),None))
    def opened(self,_):
        s=state();step(s,{'ETH':market()}, {'ETH':quote()}, {'USDT':1},T+30);return s

    def test_exit_observed_not_historical_and_partial_extrema_excluded(self):
        s=self.opened();m=market();m['bars'].append(dict(t=T,o=100,h=108,l=99,c=102))
        step(s,{'ETH':m},{'ETH':quote(102,T+930)},{'USDT':1},T+930)
        sale=[e for e in s['ledger'] if e['type']=='VENDITA'][0]
        self.assertEqual(sale['quality'],'INCERTO');self.assertAlmostEqual(sale['price'],101.898)
        self.assertLess(sale['maxRisePct'],2);self.assertEqual(sale['fullBars'],0)
        self.assertEqual(s['closedCount'],0);self.assertEqual(s['uncertainCount'],1)
        self.assertEqual(sale['touchWindow'],[T+30,T+900])

    def test_full_bar_path_includes_high_low_and_double_touch_uncertain(self):
        s=self.opened();m=market()
        m['bars'] += [dict(t=T,o=100,h=101,l=99,c=100),dict(t=T+900,o=100,h=107,l=97,c=103)]
        step(s,{'ETH':m},{'ETH':quote(103,T+1830)},{'USDT':1},T+1830)
        sale=[e for e in s['ledger'] if e['type']=='VENDITA'][0]
        self.assertEqual(sale['fullBars'],1);self.assertGreater(sale['maxRisePct'],6)
        self.assertLess(sale['maxFallPct'],-3);self.assertEqual(sale['quality'],'INCERTO')

    def test_pause_preserves_existing_exit_and_capital(self):
        s=self.opened();s['entryPause']=dict(at=T+40,reason='review')
        m=market();m['bars'].append(dict(t=T,o=100,h=101,l=99,c=100))
        step(s,{'ETH':m},{'ETH':quote(97,T+930)},{'USDT':1},T+930)
        self.assertFalse(s['positions']);self.assertLess(s['cash'],150)
        self.assertEqual(s['activity'],'INGRESSI SOSPESI')

    def test_missing_data_recovery_is_uncertain(self):
        s=self.opened();step(s,{}, {},{},T+100)
        step(s,{'ETH':market()},{'ETH':quote(100,T+200)},{'USDT':1},T+200)
        self.assertFalse(s['positions']);self.assertEqual(s['uncertainCount'],1)

    def test_all_three_review_thresholds_and_idempotence(self):
        for mode in ('days','drawdown','count'):
            s=state();now=T+30
            if mode=='days':now=s['startedAt']+28*86400
            if mode=='drawdown':s['cash']=137
            if mode=='count':s['closedCount']=30
            step(s,{}, {},{},now);self.assertIn('entryPause',s)
            before=copy.deepcopy(s);step(s,{}, {},{},now);self.assertEqual(s,before)

    def test_new_experiment_does_not_mutate_control(self):
        a=dict(equity=143,closedCount=17);original=copy.deepcopy(a);s=start(T,a)
        self.assertEqual(s['cash'],150);self.assertEqual(a,original)
        self.assertEqual(s['controlA']['equityAtStart'],143)

    @patch('engine.pullback.setup',side_effect=lambda m,b:(signal(m['symbol']),None))
    def test_two_position_and_total_risk_limit(self,_):
        s=state();markets={k:market(k) for k in ('ETH','SOL','XRP')};quotes={k:quote() for k in markets}
        step(s,markets,quotes,{'USDT':1},T+30)
        self.assertEqual(len(s['positions']),2)
        self.assertLessEqual(sum(p['riskEUR'] for p in s['positions'].values()),1.5)
        self.assertTrue(any(e['type']=='SALTATO' and 'Due' in e['reason'] for e in s['ledger']))

    @patch('engine.pullback.setup',return_value=(signal(),None))
    def test_future_or_untimestamped_quote_is_not_an_execution(self,_):
        for q in (quote(at=T+60),dict(price=100,provider='Binance',quote='USDT')):
            s=state();step(s,{'ETH':market()},{'ETH':q},{'USDT':1},T+30)
            self.assertFalse(s['positions'])

    def test_expiry_closes_at_observed_price_with_costs(self):
        s=self.opened();m=market()
        m['bars']=[dict(t=T+86400,o=100,h=101,l=99,c=100)]
        step(s,{'ETH':m},{'ETH':quote(100,T+87330)},{'USDT':1},T+87330)
        sale=[e for e in s['ledger'] if e['type']=='VENDITA'][0]
        self.assertEqual(sale['reason'],'Scadenza 24 ore');self.assertLess(sale['pnlEUR'],0)

class ScannerCutoverTests(unittest.TestCase):
    def test_scanner_archives_once_preserves_control_and_persists_c(self):
        import contextlib,io,json,os,tempfile
        from pathlib import Path
        from engine.paper import start as old_start
        from engine.scanner import main,SYMS
        old=old_start(T-86400);old['lastRun']=T-900;old['portfolios']['A'].update(cash=143,equity=143)
        ticks=[dict(symbol=s+'USDT',price='111.3') for s in SYMS]+[dict(symbol='EURUSDT',price='1.1')]
        def fetch(sym,provider,now):return market(sym)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'DATA_DIR':tmp}),patch('engine.scanner.fetch_market',side_effect=fetch),patch('engine.scanner.request_json',return_value=ticks),patch('engine.scanner.time.time',return_value=T+30),contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);(root/'paper-state.json').write_text(json.dumps(old))
            self.assertEqual(main(),0)
            archive=(root/'paper-v2-checkpoint.json').read_text()
            self.assertEqual(json.loads(archive),old)
            c=json.loads((root/'pullback-state.json').read_text());self.assertEqual(c['cash'],150)
            self.assertEqual(c['controlA']['equityAtStart'],143)
            a=json.loads((root/'paper-state.json').read_text());self.assertEqual(a['portfolios']['A']['cash'],143)
            self.assertEqual(main(),0);self.assertEqual((root/'paper-v2-checkpoint.json').read_text(),archive)
            latest=json.loads((root/'latest.json').read_text());self.assertEqual(latest['pullback']['version'],'ripartenza-1')

if __name__=='__main__':unittest.main()
