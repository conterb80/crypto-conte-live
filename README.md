# Crypto Conte LIVE

Dashboard pubblica di analisi sperimentale. Non invia ordini e non usa chiavi di trading.
Crypto Conte RC9 è un progetto separato e non viene modificato.

## Funzionamento

- 20 mercati originali: BTC, ETH, SOL, XRP, LINK, AVAX, NEAR, ADA, DOGE, LTC, UNI, AAVE, DOT, ATOM, ARB, OP, SUI, INJ, FIL, RENDER.
- GitHub Actions programma una scansione ai minuti 07, 22, 37, 52 di ogni ora UTC, anche con telefono spento. GitHub può ritardare o saltare esecuzioni: non è un servizio in tempo reale garantito.
- Candele chiuse a 15 minuti e 1 ora. Fonte Binance Market Data; ripiego globale su Coinbase Exchange se BTC Binance è irraggiungibile. USD e USDT vengono dichiarati, mai convertiti in euro.
- Analisi: EMA 20/50 orarie, trend 1h/4h/24h, rapporto volumi sulle ultime 20 candele, forza relativa a BTC, liquidità e filtro contro movimenti eccessivi.
- Opportunità con punteggio >=5, trend 1h positivo e filtri superati; setup con punteggio >=7 e conferme di trend, volume e forza. È un sistema di regole, non un modello AI addestrato né un servizio di notizie.
- Conferma soltanto su una candela successiva, setup ancora valido e rapporto teorico obiettivo/rischio >=1,8 rispetto ai livelli iniziali. Il prezzo di riferimento diventa la chiusura di conferma.
- Stop iniziale = prezzo meno il maggiore tra 2 ATR(14) e 0,6% del prezzo. Target = maggiore tra massimo delle 24h precedenti e prezzo +2 volte il rischio. È una proiezione tecnica, non una probabilità di profitto.
- Livelli congelati; opportunità scadono dopo 12 ore, conferme dopo 48. Si ricostruiscono le candele chiuse tra scansioni per verificare invalidazione/obiettivo. Un gap non recuperabile, cambio di fonte o stop e target nella stessa candela produce INDETERMINATO, mai un successo inventato.
- Esiti teorici senza commissioni, spread o slippage. Nessun risultato equivale a guadagno reale. Un target raggiunto prima della conferma non conta come successo.
- Errori API conservano gli ultimi dati e sospendono la valutazione dell'asset. BTC mancante sospende nuove opportunità. I candidati non vengono eliminati a causa di un semplice errore API.

## Dati e controlli

`data/state.json`: stato persistente e ultime 500 transizioni. `data/latest.json`: snapshot della dashboard con stato, copertura, errori e link all'esecuzione. `data/archive/YYYY-MM.jsonl`: archivio completo delle transizioni per mese, senza eliminazione automatica.

La dashboard rilegge i risultati ogni minuto mentre è aperta; il pulsante rilegge i dati e non avvia una scansione sul server. Mostra dati vecchi oltre 45 minuti. V3 originale disponibile in `v3.html`, con chiave locale originale preservata.

In GitHub > Actions > **Crypto Conte LIVE - motore autonomo**, ogni esecuzione mostra test, copertura, salvataggio e pubblicazione. Un errore o copertura parziale rende il workflow rosso e pubblica comunque il messaggio di stato se possibile. Un fallimento della pubblicazione può lasciare il sito precedente: il link alle esecuzioni e il timestamp permettono di accorgersene.

L'archivio è pubblicato automaticamente su Pages con `actions/deploy-pages`, anche se i commit del `GITHUB_TOKEN` non attivano il normale build Pages. Il token effimero GitHub è limitato alla repository; non è una chiave di trading. Le scansioni non modificano file dell'app fuori da questa repository.

GitHub Actions su runner Linux standard per repository pubbliche è soggetto alle condizioni e limiti gratuiti GitHub; nessun servizio a pagamento o abbonamento viene attivato. I workflow programmati possono essere disabilitati da GitHub dopo 60 giorni senza attività nella repository.

## Sviluppo e verifica

`python -m unittest discover -s tests -v` (nessuna dipendenza Python esterna).
`python -m engine.scanner` esegue una scansione pubblica. `DATA_DIR` consente di isolare i dati di prova. Le prove sintetiche non alimentano il registro pubblicato.
