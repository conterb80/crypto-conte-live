# C · Ripartenza — protocollo 1, fissato il 2 novembre 2026

## Scopo e confronto

Ipotesi da verificare: una ripresa dopo un breve rientro in un trend orario positivo, con filtro economico netto, può produrre ingressi più utili del precedente radar. Non è un metodo validato. Nessuna IA, notizia, leva o operazione reale.

V2 viene fotografata integralmente in `data/paper-v2-checkpoint.json` prima dell'avvio di C. Il file non è sovrascritto alle scansioni successive. A continua dal suo capitale effettivo come riferimento, B resta sospeso; C ha un capitale indipendente di 150 EUR, senza reintegri. Il confronto prospettico con A usa la variazione del suo capitale dalla medesima data di avvio di C, non il risultato precedente di A. Il radar, V3 e RC9 non sono modificati nelle loro regole.

## Regole causali del segnale

- Stessi 20 mercati del radar, candele chiuse 15 minuti e 1 ora, stessa fonte per asset e BTC. Avvio solo su nuove candele chiuse dopo l'inizio del test; nessun segnale storico comprato retroattivamente.
- Asset e BTC: ultima chiusura oraria > EMA20 > EMA50.
- Volume monetario medio delle 20 candele 15m precedenti almeno 25.000 USD/USDT; ultima candela almeno pari a quella media.
- Nelle tre candele 15m precedenti: almeno una ribassista e minimo che raggiunge o attraversa EMA20 15m, calcolata prima della candela di ripresa.
- Ripresa: candela rialzista, chiusura sopra il massimo della precedente e sopra la stessa EMA20.
- Stop = minimo delle quattro candele (tre di rientro più ripresa) meno 0,25 ATR14. Distanza dal riferimento tra 0,8% e 4%.
- Obiettivo = riferimento + 2,5 volte la distanza allo stop, limitato al più vicino massimo locale già confermato sopra il riferimento nelle ultime 96 candele. Un massimo locale supera il precedente e non è inferiore al successivo, entrambi già chiusi. Nessun aumento dell'obiettivo per far superare il filtro.

## Prezzo ed economia dell'ingresso

Ingresso al primo ticker disponibile nella scansione che rileva il segnale, con acquisto simulato peggiorato dello 0,10%. Non al prezzo della chiusura storica. Candela più vecchia di 5 minuti: segnale non inseguito; ticker più vecchio di 120 secondi o fonte/cambio mancante: nessun ingresso. Una sola valutazione per asset/fonte/candela; nessun riempimento retroattivo nelle scansioni successive.

Commissione 0,25% e slittamento 0,10% per ciascun lato. Sono ipotesi sperimentali, non tariffe Revolut. Confronto netto stimato a cambio EUR invariato: guadagno all'obiettivo almeno 1% dell'importo e rapporto guadagno netto / perdita netta allo stop almeno 1,5. Prezzo eseguito, stop e obiettivo devono essere ordinati correttamente.

Rischio previsto allo stop: minore tra 0,75 EUR, 0,5% del capitale corrente e budget residuo di rischio del portafoglio (1% del capitale). Importo massimo 40 EUR per posizione, minimo 10 EUR; massimo due posizioni. Massimo un ingresso per simbolo in 24 ore. Il rischio previsto non è un limite garantito: gap, prezzi e cambio possono peggiorarlo.

Se più segnali arrivano nella stessa scansione, priorità alfabetica del simbolo fissata prima del test; i segnali esclusi per capacità sono registrati. Non si selezionano a posteriori quelli risultati migliori.

## Uscita e percorso

Le uscite conservano la convenzione osservabile di A: livelli controllati su candele chiuse e ticker, esecuzione al ticker disponibile meno slittamento, non al livello storico. Scadenza 24 ore. Il tocco di un obiettivo non è chiamato incasso dell'obiettivo. Un'uscita può avvenire dopo un ritracciamento.

Prima candela parziale con tocco, doppio tocco nella stessa candela, intervalli non ricostruibili o interruzione di dati: esito incerto separato dalle statistiche osservate, ma sempre incluso nel bilancio. Le posizioni esistenti sono gestite anche durante una sospensione degli ingressi.

Per posizione: massimi/minimi sui ticker osservati e sulle sole candele interamente successive all'ingresso; esclusi gli estremi della prima candela parziale. Sono misure parziali del percorso del prezzo, non massimi/minimi certi continui, né rendimenti netti EUR. Registro di ritardo segnale-ingresso, durata, intervallo possibile del tocco e scarto ticker-livello. Non si confonde il ritardo dalla chiusura della candela con il tempo esatto trascorso dal tocco, ignoto dentro la candela.

## Decisione fissata prima della raccolta

Pausa dei nuovi ingressi dopo 30 chiusure osservate, oppure dopo 28 giorni, oppure con calo dell'8% dal massimo osservato alle scansioni; restano gestite le uscite. Stato esplicito in dashboard. Nessuna modifica automatica dei parametri, nessun reintegro, nessuna ripartenza automatica.

Alla revisione: risultato netto e senza costi ipotizzati, frequenza, guadagno/perdita medi, esiti incerti, calo del capitale, percorso dei prezzi e confronto contemporaneo con A. Le operazioni correlate non sono prove indipendenti. Un campione piccolo o una sola fase di mercato non valida un metodo; quattro settimane con pochi segnali indicano insufficiente attività per questo obiettivo. Le regole formano un unico pacchetto sperimentale: il confronto non isola causalmente il contributo di ogni filtro.

Verifiche prima dell'avvio: 48 test passati, inclusa integrazione della scansione con archivio immutabile e persistenza separata di C; controllo sintattico JavaScript. Regole radar di A e codice del simulatore V2 invariati.
