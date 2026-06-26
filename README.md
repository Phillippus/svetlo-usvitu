# 🗡️ Svetlo Úsvitu — prázdninová D&D kampaň

Streamlit aplikácia pre rodinnú letnú kampaň **Svetlo Úsvitu** (1. 7. – 31. 8. 2026, 62 dní).
Slúži ako **GM skript + interaktívna textová hra + sledovač postáv**. Funguje plne **offline**
aj na mobile/tablete. Celý obsah je v **slovenčine**.

## Spustenie

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Súbory

- **`app.py`** — UI a herná logika (d20 engine, karty postáv, regenerácia, zlato, inventár, míľniky).
- **`data.py`** — všetok obsah: 62 dní scenárov (nová schéma), atribúty, schopnosti, výbava,
  legendárne predmety, obchod, pravidlá.
- **`requirements.txt`** — `streamlit>=1.40` (na Streamlit Cloud / Python 3.13 je `>=1.40` nutné
  kvôli `pillow` wheelu).

## Herné mechaniky

- **d20 skill check:** `hod_d20 + aktuálny_atribút + bonus ≥ DC → úspech`. Animovaný hod,
  rozlíšenie Úspech / Tesný neúspech (−1 až −3, `result_near`) / Neúspech (−4+, druhá šanca DC +5).
- **Hod 20:** ponúkne `+1` k danému atribútu (max 1× za deň na postavu).
- **Míľniky:** Ťažší nepriateľ 1 · Mini-boss 2 · Hlavný boss 5 · Kapitola 3 — body sa rozdeľujú
  v kartách postáv (bez stropu).
- **Výdrž = životy:** štart = atribút Výdrž; farebný progress bar (zelená/oranžová/červená).
  Vedma: veštecká guľa = −20 % max Výdrže.
- **Nová noc:** automatická regenerácia podľa prostredia (bezpečný +20 %, nebezpečný +10 %,
  bez jedla +0 %, krčma +30 % a −10 zl z klanu).
- **Zlato:** osobné + klanová pokladnica (Železný Dub vždy, Zlaté Slnko počas Talianska).
- **Inventár:** štartovacia výbava (pevná) + max 5 predmetov.

## Schéma dňa (`data.py`)

Každý z 62 dní: `day`, `chapter`, `group` (`mala`/`velka`), `title`, `intro`,
`decision1/2/3` (každé `prompt`, `type`, 3 možnosti s `postava`/`atribut`/`bonus`/`dc`/
`result_success`/`result_near`/`result_fail`), `items_day`, `zlato_odmena`, `milnik`,
`outro`, `next_hint`.

## Kapitoly

| # | Názov | Dni | Skupina |
|---|-------|-----|---------|
| I | Volanie z hmly | 1.–9. 7. | 🌳 malá |
| II | Cesta na juh | 10.–17. 7. | 🌳 malá |
| III | Bratstvo dvoch rodov | 18.–25. 7. | 🌳+☀️ veľká (Taliansko) |
| IV | Návrat a tieň | 26. 7. – 5. 8. | 🌳 malá |
| V | Plamene východu | 6.–12. 8. | 🌳 malá |
| VI | Posledná bitka o Svetlo | 13.–31. 8. | 🌳 malá |
