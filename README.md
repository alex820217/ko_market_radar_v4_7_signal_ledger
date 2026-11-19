# KO Market Radar V4.7 Signal Ledger
Main file: `app.py`

## Kernverbesserung
Jeder relevante Radarzustand wird mit UTC-Zeitstempel unveränderlich gespeichert. Beim Trade werden Kaufdatum und Kaufzeit eingegeben. Der Scanner verknüpft ausschließlich das letzte passende Signal vor dem Kauf, maximal 20 Minuten alt. Ein späteres WAIT/HOT/LATE-Signal kann den Entry-Snapshot nicht mehr überschreiben.

## Lernen
Nur Trades, deren vorgeschlagenes Signal ausdrücklich bestätigt wurde, erscheinen im verifizierten Lerndatensatz. Unverifizierte oder historische Trades bleiben in P/L und Gesamtjournal, beeinflussen aber nicht die Signalstatistik.
