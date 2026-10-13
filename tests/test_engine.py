import copy
import unittest
from unittest.mock import patch
from engine.scanner import SYMS, advance, analyse, assess, initial_state, validate

NOW=1800000000

def bars(count=300, interval=900):
    end=NOW//interval*interval
    return [dict(t=end-(count-i)*interval,o=100+i*.01,h=100.3+i*.01,l=99.7+i*.01,c=100.1+i*.01,v=1000,q=100000) for i in range(count)]

def row(t=NOW,price=100,qualified=False):
    return dict(symbol='SOL',provider='Binance',quote='USDT',price=price,candleTime=t,time=t,signal='SETUP' if qualified else 'PRE-RADAR',
                qualified=qualified,entry=100,stop=95,target=110,reason='test',stale=False)

class EngineTests(unittest.TestCase):
    def test_twenty_original_markets(self):
        self.assertEqual(len(SYMS),20)
        self.assertEqual(len(set(SYMS)),20)

    def test_open_candle_excluded_and_gap_rejected(self):
        b=bars(); b.append(dict(b[-1],t=NOW))
        result=validate(b,900,NOW)
        self.assertEqual(len(result),300)
        del result[-10]
        with self.assertRaisesRegex(ValueError,'mancanti'):
            validate(result,900,NOW)

    def test_stale_and_invalid_rejected(self):
        with self.assertRaisesRegex(ValueError,'aggiornata'):
            validate(bars(),900,NOW+3600)
        b=bars(); b[-1]['c']=float('nan')
        with self.assertRaises(ValueError):
            validate(b,900,NOW)

    def test_confirm_requires_later_candle_and_freezes_levels(self):
        state=initial_state(); advance(state,row(qualified=True),[],NOW)
        advance(state,row(qualified=True),[],NOW+10)
        self.assertEqual(state['active']['SOL']['status'],'OPPORTUNITA')
        candle=dict(t=NOW,o=100,h=101,l=99,c=100,v=1,q=100)
        advance(state,row(NOW+900,qualified=True),[candle],NOW+900)
        self.assertEqual(state['active']['SOL']['status'],'CONFERMATO')
        self.assertEqual(state['active']['SOL']['stop'],95)
        self.assertEqual(state['totals']['CONFERMATO'],1)

    def confirmed(self):
        state=initial_state(); advance(state,row(),[],NOW)
        state['active']['SOL'].update(status='CONFERMATO',confirmedAt=NOW)
        return state

    def test_recovery_evaluates_missed_candles(self):
        state=self.confirmed()
        candles=[dict(t=NOW,o=100,h=101,l=99,c=100),dict(t=NOW+900,o=100,h=111,l=99,c=100)]
        events=advance(state,row(NOW+1800),candles,NOW+1800)
        self.assertEqual(events[0]['status'],'OBIETTIVO_TEORICO')
        self.assertNotIn('SOL',state['active'])
        self.assertEqual(state['totals']['OBIETTIVO_TEORICO'],1)
        advance(state,dict(row(NOW+1800),signal='OSSERVA'),candles,NOW+1800)
        self.assertEqual(state['totals']['OBIETTIVO_TEORICO'],1)

    def test_stop_and_target_same_bar_is_not_a_win(self):
        state=self.confirmed()
        events=advance(state,row(NOW+900),[dict(t=NOW,o=100,h=111,l=94,c=100)],NOW+900)
        self.assertEqual(events[0]['status'],'INDETERMINATO')

    def test_gap_or_source_change_is_unknown(self):
        state=self.confirmed()
        events=advance(state,row(NOW+1800),[dict(t=NOW+900,o=100,h=111,l=99,c=100)],NOW+1800)
        self.assertEqual(events[0]['status'],'INDETERMINATO')
        state=self.confirmed()
        events=advance(state,dict(row(),provider='Coinbase',quote='USD'),[],NOW)
        self.assertEqual(events[0]['status'],'INDETERMINATO')

    def test_preconfirmation_move_never_counts_as_success(self):
        state=initial_state(); advance(state,row(),[],NOW)
        events=advance(state,row(NOW+900),[dict(t=NOW,o=100,h=111,l=99,c=100)],NOW+900)
        self.assertEqual(events[0]['status'],'SCADUTO')
        self.assertFalse(events[0]['confirmed'])

    def test_partial_candle_before_detection_is_unknown(self):
        state=self.confirmed(); state['active']['SOL']['eligibleAt']=NOW+100
        events=advance(state,row(NOW+900),[dict(t=NOW,o=100,h=111,l=99,c=100)],NOW+900)
        self.assertEqual(events[0]['status'],'INDETERMINATO')

    def test_repeated_or_older_snapshot_cannot_rewind_candidate(self):
        state=self.confirmed()
        advance(state,row(NOW-900),[],NOW+100)
        self.assertEqual(state['active']['SOL']['checkedThrough'],NOW)

    def test_no_data_preserves_candidate_and_last_valid_price(self):
        state=self.confirmed(); state['cache']['SOL']=row()
        latest,events=analyse(state,{},dict.fromkeys(SYMS,'HTTP 503'),NOW+900)
        self.assertEqual(latest['health'],'error')
        self.assertEqual(state['active']['SOL']['checkedThrough'],NOW)
        self.assertEqual(state['cache']['SOL']['price'],100)
        self.assertTrue(state['cache']['SOL']['stale'])
        self.assertEqual(events,[])

    def test_missing_btc_blocks_new_signals(self):
        market=dict(symbol='SOL',provider='Binance',quote='USDT',bars=bars(),hours=bars(interval=3600))
        r=assess(market,None,NOW)
        self.assertFalse(r['qualified'])
        self.assertEqual(r['signal'],'SCARTA')

    def test_expiry_precedes_later_price_hit(self):
        state=self.confirmed()
        state['active']['SOL']['confirmedAt']=NOW-48*3600
        events=advance(state,row(NOW+900),[dict(t=NOW,o=100,h=111,l=99,c=100)],NOW+900)
        self.assertEqual(events[0]['status'],'SCADUTO')

if __name__=='__main__':
    unittest.main()
