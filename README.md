# D100 Card Printer

Tool locale (web app su `localhost`) per impaginare PDF/immagini di carte da
gioco su etichette per la stampante termica cinese **D100** (100mm larghezza,
etichette tipiche 100x150mm o rullo continuo) e stamparle via Bluetooth da
un Mac.

Invece di reimplementare da zero il protocollo Bluetooth della D100 (non ha
un brand ufficiale, è un modello clone comune su Alibaba/AliExpress), questo
progetto si appoggia a **[TiMini-Print](https://github.com/Dejniel/TiMini-Print)**
(Apache-2.0), che ha già un profilo D100 verificato (Bluetooth Classic SPP,
200dpi, protocollo "tiny", larghezza stampa ~864 dot / 108mm) e gira anche su
macOS. Il valore aggiunto di questo progetto è il **layout engine**: prendi N
carte (PDF/immagini), definisci la dimensione dell'etichetta e della carta, e
lui calcola automaticamente quante carte entrano per pagina/etichetta e le
dispone in griglia (con rotazione automatica se conviene), invece di stampare
una carta sprecata per etichetta.

## Architettura

```
Browser (Mac, localhost:8000)
   │  upload PDF/immagini, imposta dimensioni pagina/carta
   ▼
FastAPI backend (app/)
   │  app/layout.py   → calcola griglia (colonne/righe, rotazione, paginazione)
   │  app/pdfgen.py   → compone il PDF finale con PyMuPDF + genera anteprime PNG
   │  app/printer.py  → invoca la CLI di TiMini-Print via subprocess
   ▼
TiMini-Print CLI (installato separatamente dall'utente)
   │  Bluetooth Classic SPP
   ▼
Stampante D100
```

## Setup (sul Mac M1)

1. **Questo progetto**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
   Apri http://localhost:8000

2. **TiMini-Print** (per la stampa Bluetooth vera e propria)
   ```bash
   git clone https://github.com/Dejniel/TiMini-Print.git
   cd TiMini-Print
   pip install -r requirements.txt
   python timiniprint_command_line.py --help
   ```
   Verifica con `--help` i flag esatti della tua versione (possono cambiare
   tra release): nell'app, sotto "5. Stampante", imposta il percorso dello
   script e il nome/indirizzo Bluetooth della tua D100 (es. `D100-XXXX` o il
   MAC address). Se i flag della CLI installata sono diversi da
   `--bluetooth <nome> --printer-model d100`, modifica `cli_args_template`
   in `data/config.json` (creato al primo salvataggio) di conseguenza.

   Nota: la D100 usa Bluetooth Classic (SPP), non BLE — sul Mac potrebbe
   essere necessario accoppiarla prima nelle Preferenze di Sistema, come hai
   già fatto con l'app proprietaria.

## Uso

1. Scegli dimensione pagina (preset 100x150mm, A4, o rullo continuo) o
   valori custom.
2. Imposta la dimensione della carta (default 63x88mm, formato standard da
   gioco tipo poker/MTG) — modificabile.
3. Trascina i PDF/immagini delle carte (drag&drop o selezione file). Per
   ogni file puoi impostare quante copie stampare.
4. "Genera anteprima": vedi quante carte entrano per pagina, se conviene
   ruotarle, quante pagine servono, e lo spreco di area stimato.
5. "Stampa via Bluetooth" invia il PDF generato alla D100 tramite
   TiMini-Print. Puoi anche scaricare il PDF e stamparlo diversamente.

## Roadmap

- **v1 (questa versione)**: layout a griglia uniforme (una dimensione di
  carta per volta), form-based UI, stampa via TiMini-Print CLI.
- **v2**: editor drag-n-drop (canvas HTML5) per aggiustare manualmente la
  disposizione generata automaticamente.
- **v2/v3**: bin-packing con carte di dimensioni miste sulla stessa pagina;
  rilevamento automatico bordo/dimensione carta dalle immagini scansionate;
  integrazione diretta con l'API Python di TiMini-Print invece della CLI, se
  si rivela più affidabile dopo test su hardware reale.

## Limiti noti

- Sviluppato e testato in un ambiente Linux senza hardware Bluetooth/D100
  reale: il layout engine e la generazione PDF sono testati (vedi
  `tests/test_layout.py` e verifica manuale del rendering), ma
  l'integrazione con la CLI di TiMini-Print va validata sul Mac con la
  stampante vera — i flag esatti della CLI potrebbero necessitare di un
  aggiustamento in `data/config.json`.
- v1 assume carte tutte della stessa dimensione per singolo job di stampa.
