# HL7 Validator — Message Inspector

Tool web **standalone** per la validazione e analisi di messaggi HL7 v2.x.  
**Zero dipendenze esterne** — solo Flask. Parser scritto da zero in Python puro.

## Quickstart

```bash
git clone https://github.com/tuousername/hl7-validator
cd hl7-validator
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
# → http://localhost:5000
```

## Funzionalità

| Feature | Dettaglio |
|---|---|
| **Parser HL7 v2.x** | Supporta v2.1 → v2.8, tutti i separatori standard |
| **Tipi messaggio** | ADT, ORU, ORM, MDM, SIU, MFN, BAR, DFT, ACK, … |
| **Validazioni** | MSH, PID, OBX, EVN, segmenti obbligatori per tipo, ordine segmenti, duplicati |
| **Codici errore** | Ogni issue ha codice univoco (E0xx/W0xx/I0xx) + suggerimento correttivo |
| **Esempi integrati** | 6 messaggi campione (ORU, ADT, ORM, ACK, errori) |
| **Segment explorer** | Ogni segmento aperto campo per campo con label HL7 |
| **Raw colorato** | Visualizzazione syntax-highlighted del messaggio originale |
| **API REST** | `POST /validate` — risposta JSON per integrazioni |
| **Copy JSON** | Esporta il risultato completo come JSON |

## API

```bash
curl -X POST http://localhost:5000/validate \
  -H "Content-Type: application/json" \
  -d '{"message":"MSH|^~\\&|LIS|OSDAL|HIS|OSDAL|20240315||ORU^R01|MSG001|P|2.5\rPID|1||123||Rossi^Mario||19800315|M"}'
```

## Codici issue

| Codice | Tipo | Descrizione |
|---|---|---|
| E001 | ERROR | Messaggio vuoto |
| E002 | ERROR | Non inizia con MSH |
| E003 | ERROR | Separatore MSH non valido |
| E010 | ERROR | Tipo messaggio (MSH-9) mancante |
| E011 | ERROR | Versione HL7 (MSH-12) mancante |
| E012 | ERROR | Message Control ID (MSH-10) mancante |
| E020 | ERROR | Segmento obbligatorio mancante |
| E030 | ERROR | Patient ID (PID-3) mancante |
| W010 | WARNING | Tipo messaggio non standard |
| W011 | WARNING | Versione HL7 non riconosciuta |
| W031 | WARNING | Nome paziente (PID-5) mancante |
| W032 | WARNING | Data di nascita non valida |
| W034 | WARNING | Sesso non valido |
| W040 | WARNING | OBX result status non valido |
| W060 | WARNING | Segmento duplicato |

## Tech stack

Python 3.8+ · Flask 3 · HTML/CSS/JS vanilla (zero frontend deps)
