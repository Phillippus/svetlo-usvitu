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

- **d20 skill check:** `hod_d20 + aktuálny_atribút + bonus ≥ DC → úspech`. Animovaný hod
  (trase → spomalenie → finále). Pri každej možnosti je **rozpis bonusov** a *„potrebuješ hodiť X+"*.
- **Neúspech = strata Životov** podľa toho, o koľko chýbalo k DC: **1–3** tesný neúspech (žiadna
  strata) · **4–8** −1 · **9–12** −2 · **13–16** −3 · **17–20** −5 · **21+** smrť (eliminácia).
- **Druhá šanca** (tá istá postava, max 1 pokus): tesný neúspech s **rovnakým DC**, neúspech 4+ s
  **DC +2** (a stráca životy). Družina pokračuje pri úspechu alebo po dvoch neúspechoch.
- **Hod 20 = okamžitý úspech** (bez ohľadu na DC) + ponúkne `+1` k danému atribútu (max 1× za deň
  na postavu). **Hod 1:** −1 život navyše.
- **Variabilný počet rozhodnutí:** bežné (decision1/2/3) + 🎁 nájdený predmet + 🛒 nákup (ak je trh)
  + 👶 detské rozhodnutie (vždy posledné, nízke DC, vždy aspoň čiastočne pozitívne).
- **🛒 Trhy (10 typov):** Dedinský, Lesný druidov, Alchymistický, Klanový (Taliansko), Prístavný,
  Kováč, Tajomný obchodník, Putovná karavána, Hradný arzenál, Chrámový — nákup s platbou
  **osobné / klanové / kombinácia**.
- **🎁 Predmet:** rozhodnutie „komu ho dáte" — pridelí sa do inventára vybranej postavy.
- **⚙️ GM mód:** diskrétny prepínač úplne dole v sidebari. Zapne **GM kalendár** s farbami dní
  (🔴 Boss · 🟠 Mini-boss · 🟡 Silnejší nepriateľ) a skryté GM poznámky. Hráčom ostáva skryté.
- **Míľniky:** Ťažší nepriateľ 1 · Mini-boss 2 · Hlavný boss 5 · Kapitola 3 — body sa rozdeľujú
  v kartách postáv (bez stropu).
- **Výdrž je atribút; Životy sú samostatné:** počet Životov = hodnota atribútu Výdrž. Farebný
  progress bar. **0 Životov = eliminácia** — postava už nemôže hrať (jej možnosti sú zablokované),
  kým ju GM neoživí. Vedma: veštecká guľa = −20 % max Životov. **Úprava životov (±) aj Oživiť sú
  len v ⚙️ GM móde.**
- **Nocľah = regenerácia (koniec dňa):** výber, kde družina prenocuje (ako rozhodnutie/nákup).
  **V spoločnosti** (deň s trhom / Taliansko): 🏘️ krčma +4 každému (10 zl/os. z klanu) · ⚕️ lekár
  +5 jednej vybranej za 15 zl (ostatní tábor +3) · 🏕️ tábor medzi ľuďmi +3. **Mimo civilizácie:**
  🌲 divočina/les +2 · ⛺ provizórny nocľah +1 · 🏜️ nehostinné prostredie +0. Eliminovaní sa
  neregenerujú (najprv Oživiť).
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
