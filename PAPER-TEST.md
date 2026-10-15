# Laboratorio virtuale — paper-1

Due portafogli indipendenti da 150 EUR, senza reintegri: A conferme, B prime opportunità. Nessun ordine reale o credenziale di trading.

30 EUR per acquisto, commissione inclusa; massimo 3 posizioni e una per simbolo. Commissione ipotetica 0,25% e slittamento sfavorevole 0,10% su entrambi i lati. Uscita per invalidazione, obiettivo oppure dopo 24 ore. I livelli restano quelli del candidato all'accodamento.

Solo nuovi segnali dopo l'attivazione. La scansione successiva al segnale usa un ticker corrente pubblico, non il vecchio prezzo di chiusura; i segnali accodati scadono dopo un'ora. Priorità cronologica, simbolo a parità. Prezzi già oltre i livelli, filtri SCARTA, capacità e dati mancanti producono rinunce registrate. Nessuna operazione retroattiva.

Cambio contemporaneo: EURUSDT su Binance (inverso per ottenere EUR per USDT), EUR/USD pubblico Coinbase se la fonte è Coinbase. Senza cambio o fonte coerente non si esegue. Non si assume parità EUR/USD o USD/USDT.

Le uscite usano il primo prezzo corrente osservato dopo il trigger, con costi: non si garantisce esecuzione allo stop o al target. Le candele interamente successive all'ingresso aiutano a rilevare tocchi tra scansioni; movimenti nella prima candela parziale possono non essere ricostruibili. Se entrambi i livelli sono toccati, viene annotata la sequenza incerta; non viene inventata una vittoria al target. Dati mancanti conservano l'ultima valutazione, che può risultare vecchia. Drawdown misurato alle scansioni, non intrabar.

Stato e registro completo: data/paper-state.json, separato da data/state.json. Estratto pubblico in data/latest.json.paper (ultime 100 decisioni per portafoglio); nessun cambiamento alla strategia radar LIVE-4.0.0. Storico capitale completo nello stato; estratto dashboard massimo 2880 punti. Test unitari verificano assenza di retroattività, rinvio dell'esecuzione, necessità del cambio, costi, prezzo di uscita, idempotenza, capacità e scadenza.
