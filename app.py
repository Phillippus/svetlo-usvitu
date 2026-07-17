# -*- coding: utf-8 -*-
"""
Svetlo Úsvitu — prázdninová D&D kampaň (1.7. - 31.8.2026).
GM skript + interaktívna textová hra + sledovač postáv. Plne offline.
Všetok herný stav žije v st.session_state. Jazyk: slovenčina.
"""
import os
import json
import math
import time
import random
import re
import datetime
import urllib.parse

import streamlit as st

import importlib as _il
import data as _data
_il.reload(_data)  # deploy-safe: vynúti čerstvý data modul (Streamlit cachuje moduly)

from data import (
    CAMPAIGN, CHAPTERS, CHAPTER_COLORS, chapter_by_id,
    PARTY_MALA, PARTY_VELKA_DOPLNOK, PARTY_ALL, CLANS, CLAN_OF,
    STATS, STAT_KEYS, STAT_LABELS, STAT_NAMES, stats_dict, start_vydrz,
    ABILITIES, SPECIAL_ABILITIES, STARTING_EQUIPMENT, LEGENDARY_ITEMS, WEAPONS_SHOP, EXPENSES,
    DC_SCALE, MILESTONE_POINTS, MILESTONE_LABELS, ZISK_OSOBNE_PODIEL,
    WORLD_INTRO, GROUP_SCHEDULE,
    build_decisions, shop_for_day, gm_color_for_day, day_type_label,
    day_tier, TARGET_BEZNE, KIND_LABEL, target_bezne,
    normalize_item, item_allowed_for, MARKET_DAYS,
)

try:
    from streamlit_local_storage import LocalStorage
    _LS_OK = True
except Exception:
    _LS_OK = False

st.set_page_config(page_title="Svetlo Úsvitu", page_icon="🗡️", layout="centered")

MIN_DATE = datetime.date(2026, 6, 29)   # 29.-30.6. = skúšobné prológové dni
CAMPAIGN_START = datetime.date(2026, 7, 1)
MAX_DATE = datetime.date(2026, 8, 31)
INV_LIMIT = 5            # max predmetov nad štartovaciu výbavu
START_GOLD = 20         # štartovacie osobné zlato
START_KLAN = 40         # štartovacia klanová pokladnica

TYPE_BADGE = {
    "fyzicke":    "💪 Fyzické",
    "sociale":    "💬 Sociálne",
    "prieskumne": "🔍 Prieskumné",
    "takticke":   "♟️ Taktické",
    "prirodne":   "🌿 Prírodné",
    "tajomne":    "🔮 Tajomné",
    "humorne":    "😄 Humorné",
    "detske":     "👶 Detské",
}

GM_DOT = {"red": "🔴", "orange": "🟠", "yellow": "🟡"}
GM_DOT_LABEL = {"red": "Boss", "orange": "Mini-boss", "yellow": "Silnejší nepriateľ"}

# Farby typov dní pre GM kalendár
KIND_COLOR = {
    "skusobny": "#4f9d9d", "pokojny": "#3fb950", "bezny": "#3a7ca5", "rusny": "#d29922",
    "tazsi_nepriatel": "#d4a017", "mini_boss": "#e0822a", "hlavny_boss": "#f85149",
}


# =========================================================================
#  CSS — tmavý high-fantasy motív, veľké tlačidlá pre mobil
# =========================================================================
# ── Kapitolové témy pozadia (CSS gradienty — plne offline, bez obrázkov) ──
BASE_BG = "#0e1117"


# ── Kapitolové „obrázkové" pozadia — inline SVG siluety (plne offline) ──
def _sky(cid, top, bot):
    return (f"<defs><linearGradient id='{cid}' x1='0' y1='0' x2='0' y2='1'>"
            f"<stop offset='0' stop-color='{top}'/><stop offset='1' stop-color='{bot}'/>"
            f"</linearGradient></defs><rect width='1200' height='400' fill='url(#{cid})'/>")


def _pines(y, n, w, h, fill, op):
    s = 1200 / n
    tris = "".join(f"<polygon points='{i*s:.0f},{y-h} {i*s-w:.0f},{y} {i*s+w:.0f},{y}'/>"
                   for i in range(n + 1))
    return f"<g fill='{fill}' opacity='{op}'>{tris}</g>"


def _stars(pts, fill="#dfe6ff"):
    return "<g fill='" + fill + "'>" + "".join(
        f"<circle cx='{x}' cy='{y}' r='{r}'/>" for x, y, r in pts) + "</g>"


def _wrap(inner):
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 400' "
            "preserveAspectRatio='xMidYMid slice'>" + inner + "</svg>")


_SCENES = {
    0: _wrap(_sky("k", "#1d6a6f", "#123236")
             + _stars([(140, 60, 1.4), (360, 80, 1), (540, 50, 1.3), (720, 90, 1), (1050, 120, 1)], "#d4f2f2")
             + "<circle cx='980' cy='95' r='48' fill='#eafcfc' opacity='0.95'/>"
             + "<circle cx='980' cy='95' r='74' fill='#bfeaea' opacity='0.22'/>"
             + "<rect y='255' width='1200' height='145' fill='#123f42' opacity='0.6'/>"
             + "<g stroke='#a6e0e0' stroke-width='3' opacity='0.32'>"
               "<line x1='915' y1='300' x2='1045' y2='300'/><line x1='935' y1='330' x2='1025' y2='330'/>"
               "<line x1='955' y1='360' x2='1005' y2='360'/></g>"),
    1: _wrap(_sky("f", "#356a4c", "#16281e")
             + "<rect y='150' width='1200' height='62' fill='#aadcbc' opacity='0.15'/>"
             + "<rect y='226' width='1200' height='80' fill='#aadcbc' opacity='0.12'/>"
             + _pines(300, 9, 70, 150, "#174433", 0.6)
             + _pines(400, 7, 95, 210, "#0e2c1e", 0.92)),
    2: _wrap(_sky("r", "#6aa6d6", "#d0e3ef")
             + "<circle cx='1010' cy='78' r='68' fill='#fff0b8' opacity='0.22'/>"
             + "<circle cx='1010' cy='78' r='40' fill='#fff3c8'/>"
             + "<g fill='#f3f8fc'><ellipse cx='180' cy='80' rx='30' ry='16'/><ellipse cx='214' cy='70' rx='28' ry='20'/>"
               "<ellipse cx='250' cy='78' rx='32' ry='17'/><ellipse cx='216' cy='86' rx='58' ry='13'/></g>"
             + "<ellipse cx='216' cy='91' rx='60' ry='7' fill='#cfe0ec' opacity='0.5'/>"
             + "<g fill='#f3f8fc'><ellipse cx='620' cy='58' rx='26' ry='14'/><ellipse cx='650' cy='50' rx='24' ry='17'/>"
               "<ellipse cx='680' cy='58' rx='28' ry='14'/><ellipse cx='650' cy='64' rx='48' ry='11'/></g>"
             + "<ellipse cx='650' cy='68' rx='50' ry='6' fill='#cfe0ec' opacity='0.45'/>"
             + "<g fill='#eef4fb' opacity='0.85'><ellipse cx='430' cy='40' rx='22' ry='9'/>"
               "<ellipse cx='455' cy='36' rx='18' ry='11'/><ellipse cx='478' cy='42' rx='20' ry='8'/></g>"
             + "<g fill='none' stroke='#42606f' stroke-width='2' opacity='0.5'>"
               "<path d='M320,118 q7,-6 14,0 q7,-6 14,0'/><path d='M360,106 q6,-5 12,0 q6,-5 12,0'/>"
               "<path d='M398,120 q6,-5 12,0 q6,-5 12,0'/><path d='M292,132 q6,-5 12,0 q6,-5 12,0'/>"
               "<path d='M430,110 q5,-4 10,0 q5,-4 10,0'/></g>"
             + "<path d='M0,210 L100,150 L190,185 L300,120 L400,170 L510,110 L620,165 L740,118 L860,165 "
               "L970,124 L1090,168 L1200,140 L1200,235 L0,235 Z' fill='#a9c2d8' opacity='0.62'/>"
             + "<g fill='#eef4fa'>"
               "<path d='M300,120 L360,150 L330,153 L300,149 L272,154 L249,150 Z'/>"
               "<path d='M510,110 L574,142 L544,145 L510,141 L482,146 L451,142 Z'/>"
               "<path d='M740,118 L817,148 L784,151 L740,147 L698,152 L663,148 Z'/>"
               "<path d='M970,124 L1046,152 L1012,155 L970,151 L930,156 L895,152 Z'/></g>"
             + "<path d='M0,236 L120,180 L240,214 L360,176 L470,204 L520,176 L556,240 L600,250 L644,240 L680,176 "
               "L740,204 L860,172 L980,210 L1100,182 L1200,206 L1200,256 L0,256 Z' fill='#7d9bb0'/>"
             + "<g fill='#96b0c3' opacity='0.8'><path d='M360,176 L470,204 L415,204 Z'/><path d='M860,172 L980,210 L920,210 Z'/></g>"
             + "<path d='M0,256 L200,230 L420,254 L560,250 L600,270 L640,250 L880,256 L1100,232 L1200,250 L1200,300 L0,300 Z' fill='#557a5f'/>"
             + "<path d='M0,400 L0,296 Q300,290 600,300 Q900,290 1200,296 L1200,400 Z' fill='#5c9070'/>"
             + "<path d='M0,400 L0,338 Q300,330 600,348 Q900,330 1200,338 L1200,400 Z' fill='#4c815f' opacity='0.5'/>"
             + "<ellipse cx='148' cy='326' rx='120' ry='22' fill='#8fbdd8'/>"
             + "<ellipse cx='148' cy='322' rx='92' ry='7' fill='#d6ecf6' opacity='0.5'/>"
             + "<defs><linearGradient id='w2' x1='0' y1='0' x2='0' y2='1'>"
               "<stop offset='0' stop-color='#bfe3f1'/><stop offset='0.5' stop-color='#a9d4e6'/><stop offset='1' stop-color='#1d3c44'/></linearGradient></defs>"
             + "<path d='M588,250 C582,268 574,296 566,314 C561,326 558,335 560,345 C558,375 556,390 556,400 "
               "L686,400 C686,388 664,375 662,345 C664,335 660,326 650,314 C640,290 628,268 612,250 "
               "C606,244 594,244 588,250 Z' fill='url(#w2)'/>"
             + "<g fill='#26452f'><polygon points='323.3,245.2 312.7,257.8 333.8,257.8'/><polygon points='323.3,238.2 315.6,249.7 330.9,249.7'/><polygon points='323.3,232.6 318.4,242.7 328.1,242.7'/><polygon points='370.3,245.7 359.8,258.1 380.7,258.1'/><polygon points='370.3,238.7 362.7,250.1 377.8,250.1'/><polygon points='370.3,233.2 365.4,243.2 375.1,243.2'/><polygon points='496.2,248.5 487.5,258.8 505.0,258.8'/><polygon points='496.2,242.7 490.0,252.2 502.5,252.2'/><polygon points='496.2,238.1 492.2,246.4 500.2,246.4'/><polygon points='458.5,245.6 447.2,259.0 469.8,259.0'/><polygon points='458.5,238.0 450.3,250.4 466.6,250.4'/><polygon points='458.5,232.1 453.3,242.9 463.7,242.9'/><polygon points='458.9,248.6 449.8,259.5 468.1,259.5'/><polygon points='458.9,242.5 452.3,252.5 465.5,252.5'/><polygon points='458.9,237.7 454.7,246.4 463.1,246.4'/><polygon points='487.5,249.4 479.0,259.5 496.0,259.5'/><polygon points='487.5,243.8 481.4,253.1 493.6,253.1'/><polygon points='487.5,239.3 483.6,247.4 491.4,247.4'/><polygon points='345.6,254.1 337.9,263.3 353.2,263.3'/><polygon points='345.6,249.0 340.0,257.4 351.1,257.4'/><polygon points='345.6,245.0 342.0,252.3 349.1,252.3'/><polygon points='351.2,250.7 340.0,264.1 362.4,264.1'/><polygon points='351.2,243.2 343.1,255.5 359.3,255.5'/><polygon points='351.2,237.4 346.1,248.1 356.4,248.1'/><polygon points='498.9,252.1 487.9,265.1 509.8,265.1'/><polygon points='498.9,244.9 491.0,256.8 506.7,256.8'/><polygon points='498.9,239.2 493.8,249.5 503.9,249.5'/><polygon points='475.0,255.4 466.5,265.5 483.4,265.5'/><polygon points='475.0,249.8 468.9,259.0 481.0,259.0'/><polygon points='475.0,245.4 471.1,253.4 478.8,253.4'/><polygon points='319.8,252.6 308.6,266.0 331.0,266.0'/><polygon points='319.8,245.2 311.7,257.4 327.9,257.4'/><polygon points='319.8,239.3 314.6,250.0 324.9,250.0'/><polygon points='350.7,255.0 339.9,267.8 361.5,267.8'/><polygon points='350.7,247.8 342.9,259.6 358.4,259.6'/><polygon points='350.7,242.1 345.7,252.4 355.6,252.4'/><polygon points='543.1,258.6 535.3,267.9 550.9,267.9'/><polygon points='543.1,253.4 537.4,262.0 548.7,262.0'/><polygon points='543.1,249.3 539.5,256.7 546.7,256.7'/><polygon points='414.0,256.4 403.2,269.2 424.7,269.2'/><polygon points='414.0,249.3 406.2,261.0 421.7,261.0'/><polygon points='414.0,243.6 409.0,253.9 418.9,253.9'/><polygon points='463.6,259.5 455.0,269.7 472.2,269.7'/><polygon points='463.6,253.7 457.4,263.2 469.8,263.2'/><polygon points='463.6,249.2 459.7,257.4 467.6,257.4'/><polygon points='414.4,259.6 404.6,271.2 424.2,271.2'/><polygon points='414.4,253.1 407.4,263.8 421.5,263.8'/><polygon points='414.4,247.9 409.9,257.3 418.9,257.3'/><polygon points='344.2,259.5 334.2,271.4 354.1,271.4'/><polygon points='344.2,252.9 337.0,263.8 351.3,263.8'/><polygon points='344.2,247.7 339.6,257.2 348.7,257.2'/><polygon points='301.8,262.6 294.0,271.9 309.5,271.9'/><polygon points='301.8,257.4 296.1,265.9 307.4,265.9'/><polygon points='301.8,253.3 298.2,260.7 305.3,260.7'/><polygon points='342.4,261.8 333.2,272.8 351.7,272.8'/><polygon points='342.4,255.6 335.8,265.7 349.1,265.7'/><polygon points='342.4,250.8 338.2,259.6 346.7,259.6'/><polygon points='411.1,259.6 400.0,272.8 422.1,272.8'/><polygon points='411.1,252.3 403.1,264.4 419.1,264.4'/><polygon points='411.1,246.5 406.0,257.0 416.2,257.0'/><polygon points='461.5,264.8 453.3,274.5 469.6,274.5'/><polygon points='461.5,259.3 455.6,268.3 467.4,268.3'/><polygon points='461.5,255.0 457.7,262.8 465.2,262.8'/><polygon points='427.8,264.0 418.3,275.2 437.2,275.2'/><polygon points='427.8,257.7 421.0,268.0 434.6,268.0'/><polygon points='427.8,252.7 423.4,261.7 432.1,261.7'/><polygon points='345.7,268.4 337.6,278.0 353.7,278.0'/><polygon points='345.7,263.0 339.9,271.8 351.5,271.8'/><polygon points='345.7,258.8 342.0,266.4 349.4,266.4'/><polygon points='455.4,269.1 446.8,279.4 463.9,279.4'/><polygon points='455.4,263.4 449.2,272.8 461.5,272.8'/><polygon points='455.4,258.9 451.4,267.1 459.3,267.1'/><polygon points='320.7,268.2 310.5,280.3 330.8,280.3'/><polygon points='320.7,261.4 313.3,272.5 328.0,272.5'/><polygon points='320.7,256.0 316.0,265.7 325.4,265.7'/><polygon points='398.1,270.7 389.1,281.4 407.1,281.4'/><polygon points='398.1,264.6 391.6,274.5 404.6,274.5'/><polygon points='398.1,259.9 394.0,268.5 402.2,268.5'/><polygon points='537.5,272.4 529.9,281.4 545.1,281.4'/><polygon points='537.5,267.4 532.1,275.7 543.0,275.7'/><polygon points='537.5,263.4 534.0,270.6 541.0,270.6'/><polygon points='350.4,272.2 341.1,283.3 359.8,283.3'/><polygon points='350.4,266.0 343.7,276.2 357.2,276.2'/><polygon points='350.4,261.1 346.1,270.0 354.7,270.0'/><polygon points='308.5,272.1 297.3,285.5 319.7,285.5'/><polygon points='308.5,264.7 300.4,276.9 316.5,276.9'/><polygon points='308.5,258.8 303.3,269.5 313.6,269.5'/><polygon points='547.4,273.1 536.7,285.9 558.2,285.9'/><polygon points='547.4,265.9 539.7,277.7 555.1,277.7'/><polygon points='547.4,260.3 542.5,270.5 552.4,270.5'/></g><g fill='#356b47'><polygon points='304.9,252.5 290.8,268.5 319.0,268.5'/><polygon points='304.9,243.5 294.8,258.3 315.1,258.3'/><polygon points='304.9,236.5 298.4,249.3 311.4,249.3'/><polygon points='479.0,257.7 468.2,269.9 489.8,269.9'/><polygon points='479.0,250.8 471.2,262.1 486.7,262.1'/><polygon points='479.0,245.4 474.0,255.2 483.9,255.2'/><polygon points='441.3,258.7 429.9,271.7 452.8,271.7'/><polygon points='441.3,251.4 433.1,263.4 449.6,263.4'/><polygon points='441.3,245.7 436.1,256.1 446.6,256.1'/><polygon points='311.4,259.9 299.9,272.9 322.8,272.9'/><polygon points='311.4,252.6 303.1,264.6 319.6,264.6'/><polygon points='311.4,246.9 306.1,257.3 316.6,257.3'/><polygon points='516.1,261.3 505.7,273.1 526.5,273.1'/><polygon points='516.1,254.6 508.6,265.5 523.6,265.5'/><polygon points='516.1,249.4 511.3,258.9 520.9,258.9'/><polygon points='475.0,259.7 461.3,275.2 488.6,275.2'/><polygon points='475.0,251.0 465.1,265.3 484.8,265.3'/><polygon points='475.0,244.1 468.7,256.6 481.2,256.6'/><polygon points='350.2,260.0 336.7,275.2 363.6,275.2'/><polygon points='350.2,251.4 340.5,265.5 359.8,265.5'/><polygon points='350.2,244.7 344.0,256.9 356.3,256.9'/><polygon points='300.2,262.1 288.4,275.5 312.0,275.5'/><polygon points='300.2,254.6 291.7,266.9 308.7,266.9'/><polygon points='300.2,248.6 294.8,259.4 305.7,259.4'/><polygon points='447.5,264.3 437.0,276.2 458.0,276.2'/><polygon points='447.5,257.6 439.9,268.6 455.1,268.6'/><polygon points='447.5,252.3 442.7,261.9 452.3,261.9'/><polygon points='379.6,264.9 369.5,276.3 389.6,276.3'/><polygon points='379.6,258.5 372.3,269.0 386.8,269.0'/><polygon points='379.6,253.5 374.9,262.6 384.2,262.6'/><polygon points='448.7,264.9 436.9,278.4 460.6,278.4'/><polygon points='448.7,257.4 440.2,269.8 457.3,269.8'/><polygon points='448.7,251.4 443.3,262.2 454.2,262.2'/><polygon points='449.3,268.2 439.1,279.8 459.5,279.8'/><polygon points='449.3,261.7 442.0,272.4 456.6,272.4'/><polygon points='449.3,256.7 444.6,265.9 454.0,265.9'/><polygon points='457.6,266.5 444.4,281.5 470.8,281.5'/><polygon points='457.6,258.1 448.1,271.9 467.1,271.9'/><polygon points='457.6,251.5 451.5,263.5 463.7,263.5'/><polygon points='539.6,267.4 527.2,281.5 552.1,281.5'/><polygon points='539.6,259.5 530.6,272.5 548.6,272.5'/><polygon points='539.6,253.2 533.9,264.6 545.4,264.6'/><polygon points='318.9,272.0 308.0,284.3 329.7,284.3'/><polygon points='318.9,265.1 311.1,276.4 326.7,276.4'/><polygon points='318.9,259.6 313.9,269.5 323.9,269.5'/><polygon points='471.6,272.6 461.2,284.4 481.9,284.4'/><polygon points='471.6,266.0 464.1,276.8 479.0,276.8'/><polygon points='471.6,260.8 466.8,270.2 476.3,270.2'/><polygon points='344.2,272.5 330.0,288.7 358.4,288.7'/><polygon points='344.2,263.5 334.0,278.4 354.5,278.4'/><polygon points='344.2,256.4 337.7,269.3 350.8,269.3'/><polygon points='526.7,278.5 515.9,290.9 537.6,290.9'/><polygon points='526.7,271.6 518.9,283.0 534.6,283.0'/><polygon points='526.7,266.2 521.7,276.1 531.7,276.1'/><polygon points='438.1,277.5 425.4,291.9 450.7,291.9'/><polygon points='438.1,269.4 429.0,282.7 447.2,282.7'/><polygon points='438.1,263.1 432.3,274.6 443.9,274.6'/><polygon points='367.2,281.6 356.5,293.7 377.8,293.7'/><polygon points='367.2,274.8 359.5,285.9 374.9,285.9'/><polygon points='367.2,269.4 362.3,279.1 372.1,279.1'/><polygon points='345.9,278.8 332.0,294.6 359.9,294.6'/><polygon points='345.9,269.9 335.9,284.5 356.0,284.5'/><polygon points='345.9,262.9 339.5,275.6 352.4,275.6'/><polygon points='305.8,282.6 295.0,295.0 316.7,295.0'/><polygon points='305.8,275.7 298.0,287.1 313.6,287.1'/><polygon points='305.8,270.3 300.8,280.2 310.8,280.2'/><polygon points='474.0,283.8 464.3,295.0 483.8,295.0'/><polygon points='474.0,277.6 467.0,287.8 481.1,287.8'/><polygon points='474.0,272.7 469.5,281.6 478.5,281.6'/><polygon points='522.3,280.8 509.4,295.5 535.2,295.5'/><polygon points='522.3,272.7 513.0,286.1 531.6,286.1'/><polygon points='522.3,266.2 516.4,277.9 528.2,277.9'/></g><g fill='#4c8a60' opacity='0.45'><polygon points='304.9,236.5 298.4,249.3 311.4,249.3'/><polygon points='441.3,245.7 436.1,256.1 446.6,256.1'/><polygon points='516.1,249.4 511.3,258.9 520.9,258.9'/><polygon points='350.2,244.7 344.0,256.9 356.3,256.9'/><polygon points='447.5,252.3 442.7,261.9 452.3,261.9'/><polygon points='448.7,251.4 443.3,262.2 454.2,262.2'/><polygon points='457.6,251.5 451.5,263.5 463.7,263.5'/><polygon points='318.9,259.6 313.9,269.5 323.9,269.5'/><polygon points='344.2,256.4 337.7,269.3 350.8,269.3'/><polygon points='438.1,263.1 432.3,274.6 443.9,274.6'/><polygon points='345.9,262.9 339.5,275.6 352.4,275.6'/><polygon points='474.0,272.7 469.5,281.6 478.5,281.6'/></g>"
             + "<g fill='#26452f'><polygon points='663.3,245.2 652.8,257.7 673.8,257.7'/><polygon points='663.3,238.2 655.7,249.7 670.9,249.7'/><polygon points='663.3,232.7 658.4,242.7 668.1,242.7'/><polygon points='659.9,247.4 650.5,258.6 669.2,258.6'/><polygon points='659.9,241.2 653.2,251.4 666.6,251.4'/><polygon points='659.9,236.3 655.6,245.2 664.2,245.2'/><polygon points='637.9,246.4 627.6,258.6 648.1,258.6'/><polygon points='637.9,239.5 630.5,250.8 645.3,250.8'/><polygon points='637.9,234.2 633.2,243.9 642.6,243.9'/><polygon points='676.3,250.0 668.0,259.9 684.6,259.9'/><polygon points='676.3,244.5 670.3,253.6 682.3,253.6'/><polygon points='676.3,240.2 672.5,248.1 680.1,248.1'/><polygon points='684.8,251.7 676.6,261.5 693.1,261.5'/><polygon points='684.8,246.2 678.9,255.2 690.7,255.2'/><polygon points='684.8,241.9 681.0,249.7 688.6,249.7'/><polygon points='669.8,251.6 660.5,262.6 679.1,262.6'/><polygon points='669.8,245.4 663.1,255.6 676.5,255.6'/><polygon points='669.8,240.5 665.5,249.4 674.1,249.4'/><polygon points='709.8,254.5 699.3,266.9 720.2,266.9'/><polygon points='709.8,247.5 702.3,258.9 717.3,258.9'/><polygon points='709.8,242.0 705.0,252.0 714.6,252.0'/><polygon points='668.0,259.1 657.7,271.4 678.4,271.4'/><polygon points='668.0,252.2 660.6,263.5 675.5,263.5'/><polygon points='668.0,246.8 663.3,256.6 672.8,256.6'/><polygon points='664.0,261.2 654.0,273.2 674.1,273.2'/><polygon points='664.0,254.5 656.8,265.5 671.3,265.5'/><polygon points='664.0,249.2 659.4,258.8 668.6,258.8'/><polygon points='690.6,262.7 681.3,273.7 699.8,273.7'/><polygon points='690.6,256.5 683.9,266.7 697.2,266.7'/><polygon points='690.6,251.7 686.3,260.5 694.8,260.5'/><polygon points='642.3,262.9 633.2,273.8 651.5,273.8'/><polygon points='642.3,256.7 635.8,266.8 648.9,266.8'/><polygon points='642.3,251.9 638.1,260.7 646.6,260.7'/><polygon points='680.8,263.9 670.9,275.7 690.7,275.7'/><polygon points='680.8,257.3 673.6,268.2 687.9,268.2'/><polygon points='680.8,252.1 676.2,261.6 685.3,261.6'/><polygon points='660.6,270.6 652.3,280.5 668.9,280.5'/><polygon points='660.6,265.1 654.6,274.2 666.6,274.2'/><polygon points='660.6,260.7 656.8,268.6 664.4,268.6'/><polygon points='706.3,271.4 695.4,284.5 717.2,284.5'/><polygon points='706.3,264.2 698.4,276.1 714.2,276.1'/><polygon points='706.3,258.4 701.3,268.8 711.3,268.8'/></g><g fill='#356b47'><polygon points='643.1,259.5 633.3,270.8 653.0,270.8'/><polygon points='643.1,253.3 636.0,263.6 650.2,263.6'/><polygon points='643.1,248.3 638.6,257.3 647.7,257.3'/><polygon points='654.7,255.7 641.2,271.0 668.1,271.0'/><polygon points='654.7,247.1 645.0,261.2 664.4,261.2'/><polygon points='654.7,240.4 648.5,252.6 660.9,252.6'/><polygon points='709.6,256.3 695.2,272.7 724.0,272.7'/><polygon points='709.6,247.2 699.3,262.2 720.0,262.2'/><polygon points='709.6,240.0 703.0,253.0 716.3,253.0'/><polygon points='660.5,265.8 649.4,278.4 671.5,278.4'/><polygon points='660.5,258.7 652.5,270.3 668.4,270.3'/><polygon points='660.5,253.2 655.4,263.2 665.6,263.2'/><polygon points='638.5,268.5 628.7,279.7 648.3,279.7'/><polygon points='638.5,262.3 631.4,272.5 645.5,272.5'/><polygon points='638.5,257.4 634.0,266.3 643.0,266.3'/><polygon points='656.0,268.5 642.4,284.0 669.7,284.0'/><polygon points='656.0,259.8 646.2,274.1 665.9,274.1'/><polygon points='656.0,253.0 649.8,265.4 662.3,265.4'/><polygon points='698.8,270.9 684.4,287.2 713.2,287.2'/><polygon points='698.8,261.7 688.4,276.8 709.1,276.8'/><polygon points='698.8,254.5 692.1,267.6 705.4,267.6'/><polygon points='658.4,275.8 646.0,289.8 670.7,289.8'/><polygon points='658.4,267.9 649.5,280.8 667.3,280.8'/><polygon points='658.4,261.7 652.7,272.9 664.1,272.9'/><polygon points='690.6,278.9 679.7,291.2 701.4,291.2'/><polygon points='690.6,272.0 682.8,283.3 698.4,283.3'/><polygon points='690.6,266.6 685.6,276.4 695.6,276.4'/><polygon points='677.6,279.5 665.1,293.7 690.2,293.7'/><polygon points='677.6,271.5 668.6,284.6 686.7,284.6'/><polygon points='677.6,265.2 671.9,276.6 683.4,276.6'/><polygon points='698.4,280.6 686.1,294.6 710.7,294.6'/><polygon points='698.4,272.8 689.6,285.6 707.2,285.6'/><polygon points='698.4,266.6 692.7,277.8 704.0,277.8'/></g><g fill='#4c8a60' opacity='0.45'><polygon points='643.1,248.3 638.6,257.3 647.7,257.3'/><polygon points='709.6,240.0 703.0,253.0 716.3,253.0'/><polygon points='638.5,257.4 634.0,266.3 643.0,266.3'/><polygon points='698.8,254.5 692.1,267.6 705.4,267.6'/><polygon points='690.6,266.6 685.6,276.4 695.6,276.4'/><polygon points='698.4,266.6 692.7,277.8 704.0,277.8'/></g>"
             + "<g fill='#5c4a34'><rect x='78' y='300' width='4' height='12'/><rect x='120' y='296' width='4' height='14'/>"
               "<rect x='168' y='302' width='4' height='11'/><rect x='202' y='298' width='4' height='12'/></g>"
             + "<g fill='#8f9d64'><ellipse cx='80' cy='296' rx='18' ry='14'/><ellipse cx='122' cy='290' rx='21' ry='16'/>"
               "<ellipse cx='168' cy='298' rx='17' ry='13'/><ellipse cx='202' cy='294' rx='16' ry='12'/></g>"
             + "<g fill='#aab884' opacity='0.5'><ellipse cx='118' cy='285' rx='9' ry='6'/><ellipse cx='200' cy='290' rx='7' ry='5'/></g>"
             + "<path d='M842,292 Q1000,284 1162,289 L1170,342 Q1010,350 848,346 Z' fill='#6f9760'/>"
             + "<g fill='none' stroke='#375c3d' stroke-width='3' stroke-dasharray='2 7' stroke-linecap='round' opacity='0.9'>"
               "<path d='M852,301 Q1006,295 1160,300'/><path d='M854,313 Q1008,307 1162,312'/>"
               "<path d='M856,325 Q1010,319 1164,324'/><path d='M858,337 Q1012,331 1166,336'/></g>"
             + "<g fill='#2f5e3f'><path d='M812,306 C803,303 802,270 812,252 C822,270 821,303 812,306 Z'/>"
               "<path d='M1140,300 C1131,297 1130,266 1140,248 C1150,266 1149,297 1140,300 Z'/></g>"
             + "<g fill='#eaf6fc' opacity='0.5'><ellipse cx='600' cy='384' rx='30' ry='2.5'/>"
               "<ellipse cx='625' cy='392' rx='36' ry='3'/><ellipse cx='612' cy='368' rx='20' ry='2'/>"
               "<ellipse cx='598' cy='300' rx='9' ry='1.4'/></g>"
             + "<g fill='none' stroke='#8a7b64' stroke-width='4'><path d='M554,349 Q570,362 586,349'/>"
               "<path d='M594,349 Q611,364 628,349'/><path d='M636,349 Q652,362 668,349'/></g>"
             + "<g fill='#8f8069'><rect x='582' y='349' width='12' height='31'/><rect x='628' y='349' width='12' height='31'/></g>"
             + "<rect x='550' y='338' width='122' height='11' rx='2' fill='#b0a086'/>"
             + "<g fill='#c6b493'><rect x='552' y='331' width='4' height='8'/><rect x='590' y='331' width='4' height='8'/>"
               "<rect x='628' y='331' width='4' height='8'/><rect x='666' y='331' width='4' height='8'/></g>"
             + "<g fill='#2c3a24'><rect x='300' y='330' width='5' height='13'/><rect x='1085' y='264' width='5' height='14'/></g>"
             + "<g fill='#3f7150'><circle cx='302' cy='318' r='15'/><circle cx='1087' cy='250' r='18'/></g>"),
    3: _wrap(_sky("b", "#43b6de", "#bfe6f2")
             + "<circle cx='270' cy='88' r='74' fill='#fff2b8' opacity='0.22'/>"
             + "<circle cx='270' cy='88' r='42' fill='#fff5cc'/>"
             + "<g fill='#f4fbff'><ellipse cx='560' cy='60' rx='30' ry='14'/><ellipse cx='592' cy='52' rx='26' ry='17'/>"
               "<ellipse cx='624' cy='60' rx='30' ry='15'/><ellipse cx='592' cy='66' rx='52' ry='11'/></g>"
             + "<ellipse cx='592' cy='70' rx='54' ry='6' fill='#d6e6f0' opacity='0.45'/>"
             + "<g fill='#f4fbff'><ellipse cx='840' cy='96' rx='24' ry='12'/><ellipse cx='866' cy='88' rx='22' ry='15'/>"
               "<ellipse cx='892' cy='96' rx='26' ry='12'/></g>"
             + "<g fill='none' stroke='#5a7488' stroke-width='2' opacity='0.5'>"
               "<path d='M430,84 q7,-6 14,0 q7,-6 14,0'/><path d='M470,74 q6,-5 12,0 q6,-5 12,0'/>"
               "<path d='M508,90 q6,-5 12,0 q6,-5 12,0'/><path d='M400,98 q6,-5 12,0 q6,-5 12,0'/></g>"
             + "<defs><linearGradient id='sea' x1='0' y1='0' x2='0' y2='1'>"
               "<stop offset='0' stop-color='#5fbcda'/><stop offset='1' stop-color='#1c86ac'/></linearGradient>"
               "<linearGradient id='snd' x1='0' y1='0' x2='0' y2='1'>"
               "<stop offset='0' stop-color='#f0d68f'/><stop offset='1' stop-color='#c9a862'/></linearGradient></defs>"
             + "<rect y='212' width='1200' height='188' fill='url(#sea)'/>"
             + "<rect y='212' width='1200' height='2' fill='#cdeaf4' opacity='0.6'/>"
             + "<ellipse cx='268' cy='228' rx='20' ry='2.4' fill='#fdffe8' opacity='0.55'/><ellipse cx='272' cy='244' rx='26' ry='2.4' fill='#fdffe8' opacity='0.55'/><ellipse cx='266' cy='262' rx='32' ry='2.4' fill='#fdffe8' opacity='0.55'/><ellipse cx='272' cy='282' rx='40' ry='2.4' fill='#fdffe8' opacity='0.55'/><ellipse cx='264' cy='302' rx='48' ry='2.4' fill='#fdffe8' opacity='0.55'/>"
             + "<g stroke='#dff4fb' stroke-width='2.5' stroke-linecap='round' opacity='0.5'>"
               "<path d='M70,244 q26,-6 52,0'/><path d='M420,262 q30,-6 60,0'/><path d='M760,250 q26,-6 52,0'/>"
               "<path d='M520,296 q30,-6 60,0'/><path d='M120,300 q26,-6 52,0'/><path d='M900,286 q26,-6 52,0'/></g>"
             + "<path d='M1082,240 Q1140,228 1200,236 L1200,262 L1082,262 Z' fill='#9fb2a6' opacity='0.55'/>"
             + "<path d='M998,332 L1002,298 Q1090,288 1200,298 L1200,332 Z' fill='#c2b391'/>"
             + "<g stroke='#a89577' stroke-width='2' opacity='0.55' fill='none'><path d='M1004,308 Q1090,301 1200,308'/>"
               "<path d='M1010,320 Q1090,314 1200,320'/></g>"
             + "<path d='M998,331 Q1090,323 1200,331' stroke='#ffffff' stroke-width='3' fill='none' opacity='0.6'/>"
             + "<path d='M1000,300 L1006,262 Q1055,246 1112,258 L1200,250 L1200,300 Q1090,289 1002,300 Z' fill='#6f8f66'/>"
             + "<g stroke='#5c7a52' stroke-width='1.5' opacity='0.55' fill='none'><path d='M1010,278 Q1090,270 1200,276'/>"
               "<path d='M1014,290 Q1090,283 1200,289'/></g>"
             + "<g fill='#2f5540'><path d='M1022,270 C1017,268 1016,248 1022,238 C1028,248 1027,268 1022,270 Z'/>"
               "<path d='M1044,276 C1039,274 1038,256 1044,246 C1050,256 1049,274 1044,276 Z'/></g>"
             + "<rect x='1024' y='258' width='26' height='30' fill='#d9885a'/><polygon points='1022,258 1052,258 1037,251' fill='#b3502f'/><rect x='1030' y='271' width='4' height='6' fill='#3a4a5a'/><rect x='1040' y='271' width='4' height='6' fill='#3a4a5a'/><rect x='1056' y='266' width='24' height='28' fill='#e6c98a'/><polygon points='1054,266 1082,266 1068,259' fill='#b3502f'/><rect x='1061' y='278' width='4' height='6' fill='#3a4a5a'/><rect x='1071' y='278' width='4' height='6' fill='#3a4a5a'/><rect x='1088' y='256' width='26' height='32' fill='#cf7a68'/><polygon points='1086,256 1116,256 1101,249' fill='#b3502f'/><rect x='1094' y='269' width='4' height='6' fill='#3a4a5a'/><rect x='1104' y='269' width='4' height='6' fill='#3a4a5a'/><rect x='1150' y='260' width='24' height='30' fill='#d9a95f'/><polygon points='1148,260 1176,260 1162,253' fill='#b3502f'/><rect x='1155' y='273' width='4' height='6' fill='#3a4a5a'/><rect x='1165' y='273' width='4' height='6' fill='#3a4a5a'/><rect x='1046' y='240' width='24' height='26' fill='#e0d3a0'/><polygon points='1044,240 1072,240 1058,233' fill='#b3502f'/><rect x='1051' y='251' width='4' height='6' fill='#3a4a5a'/><rect x='1061' y='251' width='4' height='6' fill='#3a4a5a'/><rect x='1078' y='238' width='22' height='24' fill='#d98a6a'/><polygon points='1076,238 1102,238 1089,231' fill='#b3502f'/><rect x='1083' y='248' width='4' height='6' fill='#3a4a5a'/><rect x='1092' y='248' width='4' height='6' fill='#3a4a5a'/><rect x='1112' y='244' width='24' height='28' fill='#e6c98a'/><polygon points='1110,244 1138,244 1124,237' fill='#b3502f'/><rect x='1117' y='256' width='4' height='6' fill='#3a4a5a'/><rect x='1127' y='256' width='4' height='6' fill='#3a4a5a'/><rect x='1176' y='258' width='20' height='32' fill='#cf8a5a'/><polygon points='1174,258 1198,258 1186,251' fill='#b3502f'/><rect x='1180' y='271' width='4' height='6' fill='#3a4a5a'/><rect x='1188' y='271' width='4' height='6' fill='#3a4a5a'/><rect x='1128' y='224' width='15' height='44' fill='#ece0b8'/><polygon points='1126,224 1145,224 1135,214' fill='#b3502f'/><rect x='1132' y='232' width='7' height='9' rx='3' fill='#5a4636'/><rect x='1134' y='250' width='5' height='6' fill='#3a4a5a'/>"
             + "<g fill='#5a4a3a'><path d='M588,258 L614,258 L607,266 L595,266 Z'/></g>"
             + "<polygon points='601,230 601,257 618,257' fill='#f7fbff'/><polygon points='599,234 599,257 585,257' fill='#e6eef4'/>"
             + "<g fill='#5a4a3a'><path d='M760,268 L780,268 L775,274 L765,274 Z'/></g>"
             + "<polygon points='770,248 770,267 783,267' fill='#f7fbff'/>"
             + "<path d='M0,400 L0,320 Q300,306 600,324 T1200,318 L1200,400 Z' fill='url(#snd)'/>"
             + "<path d='M0,320 Q300,306 600,324 T1200,318' fill='none' stroke='#ffffff' stroke-width='4' opacity='0.7'/>"
             + "<path d='M0,340 Q300,328 600,344 T1200,338' fill='none' stroke='#e6c07a' stroke-width='6' opacity='0.4'/>"
             + "<path d='M148,344 Q154,286 160,208' fill='none' stroke='#8a6a44' stroke-width='9' stroke-linecap='round'/><g fill='#2e7d4f'><path d='M160,208 Q104,196 66,216 Q110,206 160,222 Z'/><path d='M160,208 Q216,194 254,214 Q210,206 160,222 Z'/><path d='M160,208 Q120,180 96,150 Q142,182 164,214 Z'/><path d='M160,208 Q200,180 226,152 Q178,182 160,214 Z'/></g><g fill='#3f9d63'><path d='M160,208 Q110,206 82,232 Q124,214 162,222 Z'/><path d='M160,208 Q210,206 240,232 Q196,214 160,222 Z'/></g><circle cx='160' cy='208' r='7' fill='#8a6a44'/><path d='M470,352 Q475,329 480,286' fill='none' stroke='#8a6a44' stroke-width='8' stroke-linecap='round'/><g fill='#2e7d4f'><path d='M480,286 Q432,276 400,293 Q438,284 480,298 Z'/><path d='M480,286 Q528,274 560,291 Q522,284 480,298 Z'/><path d='M480,286 Q446,262 426,237 Q465,264 483,291 Z'/><path d='M480,286 Q514,262 536,238 Q495,264 480,291 Z'/></g><g fill='#3f9d63'><path d='M480,286 Q438,284 414,306 Q449,291 482,298 Z'/><path d='M480,286 Q522,284 548,306 Q511,291 480,298 Z'/></g><circle cx='480' cy='286' r='6' fill='#8a6a44'/><path d='M690,340 Q695,314 700,268' fill='none' stroke='#8a6a44' stroke-width='8' stroke-linecap='round'/><g fill='#2e7d4f'><path d='M700,268 Q650,257 615,275 Q655,266 700,281 Z'/><path d='M700,268 Q750,255 785,273 Q745,266 700,281 Z'/><path d='M700,268 Q664,243 642,216 Q684,245 704,273 Z'/><path d='M700,268 Q736,243 759,218 Q716,245 700,273 Z'/></g><g fill='#3f9d63'><path d='M700,268 Q655,266 630,290 Q668,273 702,281 Z'/><path d='M700,268 Q745,266 772,290 Q732,273 700,281 Z'/></g><circle cx='700' cy='268' r='6' fill='#8a6a44'/><path d='M336,360 Q340,341 345,302' fill='none' stroke='#8a6a44' stroke-width='6' stroke-linecap='round'/><g fill='#2e7d4f'><path d='M345,302 Q306,294 279,308 Q310,301 345,312 Z'/><path d='M345,302 Q384,292 411,306 Q380,301 345,312 Z'/><path d='M345,302 Q317,282 300,261 Q332,284 348,306 Z'/><path d='M345,302 Q373,282 391,263 Q358,284 345,306 Z'/></g><g fill='#3f9d63'><path d='M345,302 Q310,301 290,319 Q320,306 346,312 Z'/><path d='M345,302 Q380,301 401,319 Q370,306 345,312 Z'/></g><circle cx='345' cy='302' r='5' fill='#8a6a44'/>"
             + "<rect x='831' y='306' width='3' height='66' fill='#7a5a3a'/>"
             + "<polygon points='833,304 795,330 814,337' fill='#e04a3a'/>"
             + "<polygon points='833,304 814,337 833,330' fill='#f7f2ec'/>"
             + "<polygon points='833,304 833,330 852,337' fill='#e04a3a'/>"
             + "<polygon points='833,304 852,337 871,330' fill='#f7f2ec'/>"
             + "<circle cx='833' cy='303' r='3' fill='#c53a2c'/>"),
    4: _wrap(_sky("d", "#b06a90", "#1a1024")
             + "<circle cx='260' cy='120' r='46' fill='#ffd9c2' opacity='0.75'/>"
             + "<path d='M0,400 L0,300 Q350,250 700,300 T1200,285 L1200,400 Z' fill='#2a1c3a' opacity='0.9'/>"
             + "<g fill='#140c1e' opacity='0.95'><rect x='860' y='210' width='9' height='190'/>"
               "<path d='M864,215 C820,190 800,200 780,175 M864,220 C910,195 930,205 950,180 "
               "M864,250 C825,235 810,245 792,230 M864,255 C905,240 922,248 940,235' "
               "stroke='#140c1e' stroke-width='6' fill='none'/></g>"),
    5: _wrap(_sky("s", "#ffc24a", "#f07d24")
             + "<circle cx='600' cy='140' r='82' fill='#fff3b0'/>"
             + "<circle cx='600' cy='140' r='140' fill='#ffe07a' opacity='0.30'/>"
             + "<path d='M0,400 L0,300 Q250,252 500,300 T1200,290 L1200,400 Z' fill='#f0a856'/>"
             + "<path d='M0,400 L0,345 Q300,308 650,352 T1200,335 L1200,400 Z' fill='#d68b32'/>"
             + "<g fill='#1e3a1e' opacity='0.92'><rect x='980' y='248' width='18' height='97'/>"
               "<path d='M989,283 q-42,-5 -42,-46 q0,31 42,31 Z'/>"
               "<path d='M989,300 q44,-5 44,-50 q0,33 -44,33 Z'/></g>"),
    6: _wrap(_sky("n", "#5b2a8f", "#12061f")
             + "<ellipse cx='600' cy='406' rx='820' ry='185' fill='#a03bd8' opacity='0.55'/>"
             + "<ellipse cx='600' cy='412' rx='520' ry='120' fill='#c94fe8' opacity='0.4'/>"
             + _stars([(120, 70, 1.5), (300, 50, 1), (480, 90, 1.5), (700, 60, 1), (860, 100, 1.5),
                       (1040, 70, 1), (200, 130, 1), (620, 130, 1), (960, 45, 1.5), (400, 140, 1)], "#e6d8f5")
             + "<circle cx='250' cy='92' r='52' fill='#e05bc0' opacity='0.35'/>"
             + "<circle cx='250' cy='92' r='44' fill='#d94a8a'/>"
             + "<circle cx='250' cy='92' r='44' fill='#7a1250' opacity='0.35'/>"
             + "<ellipse cx='600' cy='214' rx='220' ry='190' fill='#8a2fb0' opacity='0.20'/>"
             + "<g fill='#0a0413'>"
               "<rect x='430' y='262' width='340' height='138'/>"
               "<rect x='392' y='214' width='54' height='186'/><rect x='754' y='214' width='54' height='186'/>"
               "<polygon points='413,204 425,204 419,182'/><polygon points='775,204 787,204 781,182'/>"
               "<rect x='474' y='190' width='46' height='210'/><polygon points='470,192 524,192 497,110'/>"
               "<rect x='680' y='190' width='46' height='210'/><polygon points='676,192 730,192 703,110'/>"
               "<rect x='532' y='176' width='10' height='224'/><polygon points='528,178 546,178 537,118'/>"
               "<rect x='658' y='176' width='10' height='224'/><polygon points='654,178 672,178 663,118'/>"
               "<rect x='558' y='168' width='84' height='232'/><polygon points='552,170 648,170 600,62'/>"
               "<rect x='597' y='36' width='6' height='30'/>"
             + "".join(f"<rect x='{x}' y='250' width='16' height='14'/>" for x in range(436, 760, 40))
             + "".join(f"<rect x='{x}' y='204' width='12' height='12'/>" for x in (394, 431, 756, 793))
             + "</g>"
             + "<polygon points='603,40 634,49 603,60' fill='#b3243f'/>"
             + "<path d='M582,400 L582,344 Q600,318 618,344 L618,400 Z' fill='#3a0a16'/>"
             + "<path d='M591,400 L591,352 Q600,335 609,352 L609,400 Z' fill='#ff3350' opacity='0.5'/>"
             + "<g fill='#ff2e5f'>"
               "<ellipse cx='600' cy='214' rx='17' ry='24' opacity='0.30'/>"
               "<path d='M592,232 L592,212 Q600,197 608,212 L608,232 Z'/>"
               "<rect x='494' y='214' width='6' height='22'/><rect x='703' y='214' width='6' height='22'/>"
               "<rect x='414' y='252' width='6' height='18'/><rect x='781' y='252' width='6' height='18'/>"
             + "".join(f"<rect x='{x}' y='252' width='5' height='16'/>" for x in (570, 584, 616, 630))
             + "</g>"
             + "<g fill='#e468f0'>"
               "<rect x='533' y='210' width='8' height='18'/><rect x='659' y='210' width='8' height='18'/>"
               "<rect x='494' y='250' width='5' height='16'/><rect x='703' y='250' width='5' height='16'/>"
               "<rect x='566' y='300' width='6' height='20'/><rect x='628' y='300' width='6' height='20'/></g>"),
}

# štítky do prepínača
CHAPTER_BG = {
    0: "🌱 Prológ — pokojná noc", 1: "🌫️ I. Volanie z hmly (hmlistý les)",
    2: "🏞️ II. Cesta na juh (rieky)", 3: "🏖️ III. Bratstvo (pláž, Taliansko)",
    4: "🌘 IV. Návrat a tieň (súmrak)", 5: "🏜️ V. Plamene východu (púšť)",
    6: "🌌 VI. Posledná bitka (nočný hrad)",
}


# Sila prekryvu nad scénou (kvôli čitateľnosti). Veselé kapitoly (pláž, púšť) = jemnejší
# → jasnejšie farby; VI = tmavší s červeným nádychom → zlovestnejšie.
_OVERLAY = {
    2: "rgba(16,34,38,0.10) 0%, rgba(16,34,38,0.30) 45%, rgba(16,34,38,0.54) 72%",
    3: "rgba(40,30,12,0.12) 0%, rgba(40,30,12,0.34) 45%, rgba(40,30,12,0.56) 72%",
    5: "rgba(45,28,8,0.12) 0%, rgba(45,28,8,0.34) 45%, rgba(45,28,8,0.56) 72%",
    6: "rgba(45,15,70,0.22) 0%, rgba(30,10,50,0.46) 42%, rgba(18,8,32,0.7) 72%",
}
_OVERLAY_DEFAULT = "rgba(10,12,18,0.14) 0%, rgba(10,12,18,0.38) 45%, rgba(10,12,18,0.62) 72%"

# Ladiaca farba kapitoly — vyplni plochu pod scenou (namiesto ciernej) a zjednoti vzhlad.
_BASE = {
    0: "#102f31", 1: "#0d1f18", 2: "#1d3c44", 3: "#c9a862",
    4: "#181022", 5: "#cf9040", 6: "#0c0618",
}


def _scene_bg(ch):
    """Zloží CSS pozadie: SVG scéna hore + prekryv (kvôli čitateľnosti) + základ."""
    svg = _SCENES.get(ch)
    if not svg:
        return None
    url = 'url("data:image/svg+xml,' + urllib.parse.quote(svg) + '")'
    base = _BASE.get(ch, BASE_BG)
    stops = _OVERLAY.get(ch, _OVERLAY_DEFAULT)
    overlay = f"linear-gradient(180deg, {stops}, {base} 86%)"
    return f"{overlay}, {url} top center / 100% auto no-repeat, {base}"


def theme_bg(entry0):
    """Pozadie podľa voľby hore: auto = podľa kapitoly dňa, zakladne = pôvodné, N = kapitola N."""
    choice = st.session_state.get("theme_sel", "auto")
    if choice == "zakladne":
        return None
    if choice == "auto":
        ch = entry0.get("chapter") if entry0 else None
        return _scene_bg(ch) if ch is not None else None
    return _scene_bg(choice)


def inject_css(accent, bg=None):
    st.markdown(f"""
    <style>
      .stApp {{ background: {bg or BASE_BG}; background-attachment: fixed; }}
      .su-accent {{ color:{accent}; }}
      div.stButton > button {{
          width: 100%;
          min-height: 3.0em;
          white-space: normal;
          text-align: left;
          border: 1px solid {accent}55;
          border-radius: 10px;
          font-size: 1.0rem;
          line-height: 1.25rem;
          padding: 0.55em 0.9em;
      }}
      div.stButton > button:hover {{ border-color: {accent}; }}
      .su-quote {{
          border-left: 4px solid {accent};
          background: #1c2230;
          padding: 0.9em 1.1em;
          border-radius: 8px;
          font-style: italic;
          font-size: 1.08rem;
      }}
      .su-chapter {{
          background: linear-gradient(90deg, {accent}33, transparent);
          border-left: 5px solid {accent};
          padding: 0.5em 0.9em; border-radius: 6px; margin-bottom: 0.4em;
      }}
      .su-opt {{
          border: 1px solid {accent}55; border-radius: 10px;
          padding: 0.7em 0.9em; margin: 0.25em 0 0.45em;
          background: #161b26; font-size: 0.95rem; line-height: 1.5rem;
      }}
      .su-item {{
          border: 1px dashed {accent}88; border-radius: 10px;
          padding: 0.7em 0.9em; margin: 0.2em 0 0.6em;
          background: #1a1f2b;
      }}
      .su-gm {{
          border-left: 4px solid #f85149; background: #2a1a1c;
          padding: 0.5em 0.8em; border-radius: 6px; font-size: 0.85rem; margin-top: 0.4em;
      }}
      .su-bar-bg {{ background:#2b3242; border-radius:6px; height:14px; width:100%; overflow:hidden; }}
      .su-bar-fill {{ height:14px; border-radius:6px; }}
      .su-stat {{ font-size:0.8rem; margin:1px 0; white-space:nowrap; }}
      /* inventárna bublina okolo predmetu */
      .su-inv {{
          border: 1px solid {accent}44; border-radius: 9px;
          padding: 0.45em 0.7em; margin: 0.1em 0 0.3em; background: #171c28;
      }}
      /* kompaktné ikonové tlačidlá (✖ vyhodiť, ↪ presunúť) — nie veľké boxy */
      [class*="st-key-rm_"] button,
      [class*="st-key-mvbtn_"] button {{
          min-height: 2.1em; padding: 0.1em 0.2em;
          text-align: center; line-height: 1.1rem; font-size: 0.95rem;
      }}
    </style>
    """, unsafe_allow_html=True)


# =========================================================================
#  STAV HRY
# =========================================================================
def init_state():
    ss = st.session_state
    if "stats" not in ss:
        ss["stats"] = {cid: stats_dict(cid) for cid in STATS}
    if "hp" not in ss:
        ss["hp"] = {cid: {"current": start_vydrz(cid), "max": start_vydrz(cid)} for cid in STATS}
    if "gold" not in ss:
        ss["gold"] = {cid: START_GOLD for cid in STATS}
        ss["gold"]["klan"] = START_KLAN          # Klan Železného Dubu
        ss["gold"]["klan_slnko"] = START_KLAN    # Klan Zlatého Slnka (Taliansko)
    if "inventory" not in ss:
        ss["inventory"] = {cid: [] for cid in STATS}
    if "milestone_points" not in ss:
        ss["milestone_points"] = {cid: 0 for cid in STATS}
    if "abilities" not in ss:
        ss["abilities"] = {pid: {a["id"]: a["max_pouziti"] for a in lst}
                           for pid, lst in SPECIAL_ABILITIES.items()}
    if "active_effects" not in ss:
        ss["active_effects"] = {}      # {date_str: [{postava, efekt, hodnota, popis}]}
    if "temp_bonusy" not in ss:
        ss["temp_bonusy"] = {}         # {date_str: [{postava, atribut, hodnota, zdroj}]}


# =========================================================================
#  UKLADANIE / NAČÍTANIE POSTUPU (JSON súbor — offline, bez DB)
# =========================================================================
SAVE_VERSION = 2
# migrácia v2: zvýšené počty použití skrytej cesty (Vedma temnozrak 1→3, Druid zvierací prieskum 1→2)
_ABILITY_USE_BUMP = {"temnozrak": 2, "zvieraci_prieskum": 1}

SAVE_CORE = ["stats", "hp", "gold", "inventory", "milestone_points",
             "abilities", "active_effects", "temp_bonusy", "pending_ability"]
PROGRESS_PREFIXES = ("res_", "res2_", "crit1_", "zloss_", "tcrit_", "tloss_", "armorleft_",
                     "armorsaved_", "armortry_", "armorroll_", "regen_done_", "regen_zone_",
                     "predmet_done_", "nakup_done_", "levelup20_", "balloons_", "zlato_done_",
                     "orb_used_", "stastna_kocka_", "dvojita_odmena_", "bojovnik_hranica_",
                     "skip_", "skryta_den_", "prehp_", "guardsaved_")


def serialize_state():
    ss = st.session_state
    core = {k: ss.get(k) for k in SAVE_CORE}
    progress = {k: ss[k] for k in ss
                if isinstance(k, str) and k.startswith(PROGRESS_PREFIXES)}
    payload = {
        "app": "svetlo-usvitu", "version": SAVE_VERSION,
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "core": core, "progress": progress,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def load_state(raw):
    obj = json.loads(raw)
    ss = st.session_state
    core = obj.get("core", {})
    for k in SAVE_CORE:
        if core.get(k) is not None:
            ss[k] = core[k]
    # kompatibilita: staré uloženia mali inventár ako reťazce → preveď na objekty
    for cid, items in ss.get("inventory", {}).items():
        ss["inventory"][cid] = [it if isinstance(it, dict) else normalize_item({"nazov": str(it)})
                                for it in items]
    # migrácia v2: dorovnaj zvýšené počty použití skrytej cesty aj rozohraným hrám
    if obj.get("version", 1) < 2:
        ab = ss.get("abilities") or {}
        for pid, lst in SPECIAL_ABILITIES.items():
            for a in lst:
                bump = _ABILITY_USE_BUMP.get(a["id"])
                if bump and pid in ab and a["id"] in ab[pid]:
                    ab[pid][a["id"]] = min(a["max_pouziti"], ab[pid][a["id"]] + bump)
    # nahraď progress kľúče uloženými
    for k in [k for k in ss if isinstance(k, str) and k.startswith(PROGRESS_PREFIXES)]:
        ss.pop(k, None)
    for k, v in obj.get("progress", {}).items():
        ss[k] = v
    # vynúť synchronizáciu zlatých widgetov s načítanými hodnotami
    for k in [k for k in ss if isinstance(k, str) and k.startswith("goldw_set_")]:
        ss.pop(k, None)


def active_party(entry):
    if entry["group"] == "velka":
        return PARTY_MALA + PARTY_VELKA_DOPLNOK
    return PARTY_MALA


def active_ids(entry):
    return [p["id"] for p in active_party(entry)]


def short_name(cid):
    return PARTY_ALL[cid]["meno"].split(" (")[0]


# =========================================================================
#  D20 MECHANIKA
# =========================================================================
def animated_roll(placeholder, accent):
    """Animovaný hod d20 — dlhý dramatický efekt: trasu → spomaľovanie → záblesk → finále."""
    final = random.randint(1, 20)

    def frame(label, lab_color, n, size, color, glow=""):
        shadow = f"text-shadow:0 0 22px {glow};" if glow else ""
        placeholder.markdown(
            f"<div style='text-align:center;padding:0.3em 0'>"
            f"<div style='font-size:1.0rem;color:{lab_color};letter-spacing:3px'>{label}</div>"
            f"<div style='font-size:{size};color:{color};font-weight:900;{shadow}'>🎲 {n}</div>"
            f"</div>", unsafe_allow_html=True)

    # FÁZA TRESU — ~1.9 s, rýchle striedanie, červená, postupne rastie
    for i in range(24):
        size = "2.8rem" if i < 12 else "3.2rem"
        frame("🎲 HÁDŽEŠ…", "#9aa", random.randint(1, 20), size, "#f85149")
        time.sleep(0.075)

    # FÁZA SPOMAĽOVANIA — ~1.4 s, červená → oranžová → zlatá, čoraz pomalšie
    steps = [("#f85149", 0.16), ("#e9692c", 0.21), ("#e0822a", 0.27),
             ("#d9962a", 0.34), (accent, 0.44)]
    for color, delay in steps:
        frame("🎲 SPOMAĽUJE…", "#9aa", random.randint(1, 20), "3.6rem", color)
        time.sleep(delay)

    # ZÁBLESK — krátke biele bliknutie okolo finálneho čísla
    for col in ("#ffffff", accent, "#ffffff", accent):
        frame("", accent, final, "4.8rem", col, glow=accent)
        time.sleep(0.12)

    # FINÁLE — veľké zlaté číslo + popis
    crit = ""
    if final == 20:
        crit = " — 💥 KRITICKÝ ÚSPECH!"
    elif final == 1:
        crit = " — 💀 kritický neúspech"
    placeholder.markdown(
        f"<div style='text-align:center;padding:0.3em 0'>"
        f"<div style='font-size:5.0rem;color:{accent};font-weight:900;text-shadow:0 0 26px {accent}aa'>🎲 {final}</div>"
        f"<div style='font-size:1.15rem;color:{accent};font-weight:bold'>Hodil/a si: {final}{crit}</div>"
        f"</div>", unsafe_allow_html=True)
    time.sleep(0.5)
    return final


def _atr_key(opt):
    return opt.get("atribut_key") or opt.get("atribut")


def item_attr_bonus(cid, akey, is_combat):
    """(suma, detaily) bonusov z predmetov v inventári pre atribút a kontext (boj/stále)."""
    total = 0
    detail = []
    for it in st.session_state["inventory"].get(cid, []):
        if not isinstance(it, dict):
            continue
        for m in it.get("mod", []):
            if m.get("atribut") != akey:
                continue
            if m.get("kedy") == "vzdy" or (m.get("kedy") == "boj" and is_combat):
                total += m["hodnota"]
                detail.append((it.get("nazov", "?"), m["hodnota"], m.get("kedy")))
    return total, detail


def special_mods(cid, akey, ds):
    """(suma, detaily) z dočasných bonusov a denných postihov zo špeciálnych schopností."""
    ss = st.session_state
    total = 0
    detail = []
    for b in ss.get("temp_bonusy", {}).get(ds, []):
        if b.get("postava") in ("all", cid) and b.get("atribut") in ("all", akey):
            total += b["hodnota"]
            detail.append((b.get("zdroj", "bonus"), b["hodnota"]))
    for e in ss.get("active_effects", {}).get(ds, []):
        if e.get("efekt") == "minus_hody" and e.get("postava") in ("all", cid):
            total += e["hodnota"]
            detail.append((e.get("popis", "postih"), e["hodnota"]))
    return total, detail


def evaluate(opt, roll, cid, is_combat=False, ds=None):
    ss = st.session_state
    akey = _atr_key(opt)
    atr = ss["stats"][cid].get(akey, 0)
    bonus = opt.get("bonus", 0)
    item_b, item_detail = item_attr_bonus(cid, akey, is_combat)
    spec_b, spec_detail = special_mods(cid, akey, ds)
    roll_eff = roll
    if ds and ss.get(f"stastna_kocka_{ds}"):       # Goblin — Šťastná kocka
        roll_eff = max(roll, 10)
    total = roll_eff + atr + bonus + item_b + spec_b
    dc = opt["dc"]
    diff = total - dc
    if roll == 20:                 # prirodzená 20 = okamžitý úspech (bez ohľadu na DC)
        outcome = "success"
    elif total >= dc:
        outcome = "success"
    elif diff >= -3:
        outcome = "near"
    else:
        outcome = "fail"
    return {
        "idx": None, "postava": cid, "atribut": akey,
        "roll": roll, "roll_eff": roll_eff, "atr": atr, "bonus": bonus,
        "item_bonus": item_b, "item_detail": item_detail,
        "spec_bonus": spec_b, "spec_detail": spec_detail,
        "total": total, "dc": dc, "diff": diff, "outcome": outcome,
    }


def outcome_label(res):
    if res["roll"] == 20:
        return "💥 KRITICKÝ ÚSPECH (hod 20)!"
    if res["roll"] == 1:
        return "💀 KRITICKÝ NEÚSPECH (hod 1)!"
    return {
        "success": "✅ Úspech",
        "near": f"🟠 Tesný neúspech (chýbalo {abs(res['diff'])})",
        "fail": f"❌ Neúspech (chýbalo {abs(res['diff'])})",
    }[res["outcome"]]


def zivoty_za_rozdiel(margin):
    """Koľko životov postava stratí podľa veľkosti neúspechu (margin = DC − celkový hod).
    1–3 tesný neúspech (0, len druhá šanca) · 4–8 →1 · 9–12 →2 · 13–16 →3 · 17–20 →5 · 21+ → smrť."""
    if margin >= 21:
        return "smrt"
    if margin >= 17:
        return 5
    if margin >= 13:
        return 3
    if margin >= 9:
        return 2
    if margin >= 4:
        return 1
    return 0


def zivoty_slovo(n):
    """Slovenské skloňovanie: 1 život, 2–4 životy, inak životov."""
    return "život" if n == 1 else ("životy" if 2 <= n <= 4 else "životov")


def apply_life_loss(ds, dec, opt, res, attempt):
    """Aplikuje stratu životov za JEDEN neúspešný hod (raz na daný pokus).
    Vráti (strata, eliminovaný_bool). strata je 0 / int / 'smrt'."""
    ss = st.session_state
    strata = zivoty_za_rozdiel(-res["diff"])
    cid = opt["postava_id"]
    hp = ss["hp"][cid]
    if strata == 0:
        return 0, hp["current"] <= 0
    lkey = f"zloss_{ds}_{dec['id']}_{attempt}"
    if ss.get(lkey):
        return strata, hp["current"] <= 0
    ss[f"prehp_{ds}_{dec['id']}_{attempt}"] = hp["current"]   # HP pred zásahom (pre Štít Prvého strážcu)
    hp["current"] = 0 if strata == "smrt" else max(0, hp["current"] - strata)
    ss[lkey] = True
    return strata, hp["current"] <= 0


# Kvalita brnenia → (prah hodu, počet použití). Lepšia zbroj = nižší prah + viac použití.
# Kľúč = podreťazec názvu. Štíty osobitne (najslabšie). Neznáme brnenie → generický tier.
_ARMOR_QUALITY = [
    ("prvého strážcu", 7, 7),       # legendárna — najlepšia (najnižší prah)
    ("zlat",           11, 5),      # zlatá zbroj
    ("rytiersk",       12, 4),
    ("náčelník",       12, 4), ("nacelnik", 12, 4),
    ("kožen",          12, 3), ("kozen", 12, 3),   # kožená
    ("ľahká",          13, 3), ("lahka", 13, 3),
]


def _armor_quality(nazov):
    """Vráti (prah, max_použití) pre brnenie/štít podľa názvu, alebo None ak to nie je zbroj/štít."""
    low = (nazov or "").lower()
    if "štít" in low or "stit" in low:
        return (15, 2)                               # štíty — min 15, 2 použitia
    if not any(h in low for h in ("zbroj", "brnenie", "pancier")):
        return None
    for kw, thr, uses in _ARMOR_QUALITY:
        if kw in low:
            return (thr, uses)
    return (13, 3)                                   # generické brnenie


def _armor_save_best(cid):
    """Najlepší (najnižší prah) POUŽITEĽNÝ kus obrannej výbavy postavy — každý kus má
    vlastný zostatok použití (`armorleft_{cid}_{nazov}`). Vráti (prah, názov, zostatok) alebo None."""
    ss = st.session_state
    best = None
    names = [it.get("nazov", "") for it in ss["inventory"].get(cid, []) if isinstance(it, dict)]
    names += [it.get("nazov", "") for it in STARTING_EQUIPMENT.get(cid, [])]
    seen = set()
    for nazov in names:
        if not nazov or nazov in seen:
            continue
        seen.add(nazov)
        q = _armor_quality(nazov)
        if not q:
            continue
        thr, maxu = q
        remaining = ss.get(f"armorleft_{cid}_{nazov}", maxu)
        if remaining <= 0:
            continue
        if best is None or thr < best[0]:
            best = (thr, nazov, remaining)
    return best


def _guard_saver(entry):
    """Nájde nositeľa Zbroje Prvého strážcu (schopnosť plna_ochrana) s aspoň 1 nábojom.
    Vráti (cid_nositeľa, item, zostatok) alebo None."""
    ss = st.session_state
    for c in active_ids(entry):
        for it in ss["inventory"].get(c, []):
            if not isinstance(it, dict):
                continue
            if (it.get("pouzitie") or {}).get("typ") == "plna_ochrana" and (it.get("pocet_pouziti") or 0) > 0:
                return c, it, it["pocet_pouziti"]
    return None


def render_life_loss(strata, opt, eliminated):
    """Zobrazí hlášku o strate životov / eliminácii."""
    if strata == "smrt":
        st.error(f"💀 Smrteľný neúspech — {opt['postava_nazov']} je **ELIMINOVANÝ/Á**!")
    elif strata:
        chvost = " — a tým **ELIMINOVANÝ/Á** ☠️" if eliminated else ""
        st.markdown(f"💔 **{opt['postava_nazov']} stráca {strata} {zivoty_slovo(strata)}**{chvost}.")


def atr_name(akey):
    return STAT_NAMES[STAT_KEYS.index(akey)] if akey in STAT_KEYS else akey


def _signed(val, label):
    znak = "+" if val >= 0 else "−"
    return f" {znak} {abs(val)} ({label})"


def render_calc(res):
    if res.get("auto") or res.get("skipped") or res.get("spoj"):
        return
    re = res.get("roll_eff", res["roll"])
    rolltxt = f"{re} (hod)"
    if res.get("roll_eff") is not None and res["roll_eff"] != res["roll"]:
        rolltxt = f"{res['roll']}→{re} (hod · Šťastná kocka)"
    line = f"{rolltxt} + {res['atr']} ({atr_name(res['atribut'])})"
    if res.get("bonus"):
        line += _signed(res["bonus"], "situácia")
    if res.get("item_bonus"):
        line += _signed(res["item_bonus"], "výbava")
    if res.get("spec_bonus"):
        line += _signed(res["spec_bonus"], "schopnosť")
    line += f" = {res['total']}"
    st.markdown(f"`{line}`  vs  **DC {res['dc']}**")
    chips = [f"{nm} {'+' if v >= 0 else '−'}{abs(v)}{' ⚔️' if k == 'boj' else ''}"
             for nm, v, k in res.get("item_detail", [])]
    chips += [f"{nm} {'+' if v >= 0 else '−'}{abs(v)}" for nm, v in res.get("spec_detail", [])]
    if chips:
        st.caption("🎒 " + " · ".join(chips))


def render_option_panel(opt, accent, is_combat=False, ds=None):
    """Detailný rozpis: postava, atribút, situačný bonus, bonusy z výbavy, DC, koľko treba hodiť."""
    ss = st.session_state
    pid = opt["postava_id"]
    akey = opt["atribut_key"]
    emoji = STAT_LABELS[STAT_KEYS.index(akey)] if akey in STAT_KEYS else "•"
    atr = ss["stats"][pid].get(akey, 0)
    bonus = opt["bonus"]
    item_b, item_detail = item_attr_bonus(pid, akey, is_combat)
    spec_b, spec_detail = special_mods(pid, akey, ds)
    floor10 = bool(ds and ss.get(f"stastna_kocka_{ds}"))
    total = atr + bonus + item_b + spec_b
    dc = opt["dc"]
    need = dc - total
    if floor10:
        need = min(need, 10)        # vďaka Šťastnej kocke nikdy netreba hodiť viac než 10
    if need <= 1:
        need_txt = "stačí hodiť <b>1+</b>"
    elif need <= 20:
        need_txt = f"treba hodiť <b>{need}+</b>"
    else:
        need_txt = "<b>len kritická 20</b> (+ šťastie)"

    extra = ""
    if bonus:
        extra += f"<br>&nbsp;&nbsp;&nbsp;<span style='color:#9aa'>{'+' if bonus >= 0 else '−'} {abs(bonus)} situačný bonus</span>"
    for nm, v, k in item_detail:
        tag = " ⚔️v boji" if k == "boj" else ""
        extra += (f"<br>&nbsp;&nbsp;&nbsp;<span style='color:#9aa'>"
                  f"{'+' if v >= 0 else '−'} {abs(v)} {nm}{tag}</span>")
    for nm, v in spec_detail:
        extra += (f"<br>&nbsp;&nbsp;&nbsp;<span style='color:#9aa'>"
                  f"{'+' if v >= 0 else '−'} {abs(v)} {nm}</span>")
    if bonus or item_b or spec_b:
        extra += f"<br>= <b>{total}</b> celkový základ"
    floor_txt = " · 🎲 <span style='color:#d4a017'>Šťastná kocka (min 10)</span>" if floor10 else ""

    html = (f"<div class='su-opt' style='border-color:{accent}55'>"
            f"<b>{opt['label']}</b><br>"
            f"👤 {opt['postava_ikona']} {opt['postava_nazov']}<br>"
            f"{emoji} {opt['atribut_nazov']}: <b>{atr}</b> (aktuálna){extra}<br>"
            f"🎯 DC {dc} · 📊 d20 + {total} ≥ {dc} → {need_txt}{floor_txt}</div>")
    st.markdown(html, unsafe_allow_html=True)


# =========================================================================
#  ROZHODNUTIA — jednotný dispatcher
# =========================================================================
def decision_done(ds, dec):
    ss = st.session_state
    t = dec["typ"]
    did = dec["id"]
    if t == "predmet":
        return f"predmet_done_{ds}_{did}" in ss
    if t == "nakup":
        return f"nakup_done_{ds}_{did}" in ss
    return f"res_{ds}_{did}" in ss


def render_decision(n, ds, dec, accent, entry, gm):
    t = dec["typ"]
    if t == "predmet":
        return render_predmet_decision(n, ds, dec, entry, gm)
    if t == "nakup":
        return render_nakup_decision(n, ds, dec, entry)
    if t == "timova":
        return render_team_decision(n, ds, dec, accent)
    return render_skill_decision(n, ds, dec, accent, entry, positive=(t == "detske"))


def render_team_decision(n, ds, dec, accent):
    """Tímová scéna — viac postáv spojí atribúty, hádže sa JEDNOU kockou proti vysokému DC."""
    ss = st.session_state
    reskey = f"res_{ds}_{dec['id']}"
    st.markdown(f"#### 🤝 · Tímová scéna {n}")
    st.markdown(f"**{dec['prompt']}**")
    parts, suma = [], 0
    for c in dec["contribs"]:
        val = ss["stats"].get(c["postava_id"], {}).get(c["atribut_key"], 0)
        suma += val
        parts.append(f"{c['postava_ikona']} {short_name(c['postava_id'])} "
                     f"{atr_name(c['atribut_key'])} **{val}**")
    dc = dec["dc"]
    st.markdown("🤝 **Spojené sily:** " + "  +  ".join(parts) + f"  =  **{suma}**")
    treba = max(1, dc - suma)
    st.caption(f"🎯 Cieľ **DC {dc}** · jeden spoločný hod d20 · "
               + (f"potrebujete hodiť **{treba}+** (alebo 20 = istý úspech)." if treba <= 20
                  else f"súčet je nízky — uspejete len hodom **20**. Zvýšte atribúty (míľnikové body)!"))

    if reskey not in ss:
        if st.button("🎲 Hodiť tímovo (jedna kocka)", key=f"tbtn_{ds}_{dec['id']}"):
            ph = st.empty()
            roll = animated_roll(ph, accent)
            total = suma + roll
            if roll == 20 or total >= dc:
                outcome = "success"
            elif total >= dc - 3:
                outcome = "near"
            else:
                outcome = "fail"
            ss[reskey] = {"roll": roll, "suma": suma, "total": total, "dc": dc, "outcome": outcome}
            st.rerun()
        return False

    r = ss[reskey]
    krit = " 💥 **hod 20!**" if r["roll"] == 20 else ""
    st.markdown(f"🎲 Hod **{r['roll']}** + spojené **{r['suma']}** = **{r['total']}**  vs  DC {r['dc']}{krit}")
    if r["outcome"] == "success":
        st.success(dec["result_success"])
    elif r["outcome"] == "near":
        st.warning(dec["result_near"])
        st.caption("🟠 Tesný neúspech — GM môže dať družine ešte jeden spoločný pokus (bez postihu).")
    else:
        st.error(dec["result_fail"])

    # 💥 kritický úspech (hod 20) → +1 k danému atribútu KAŽDEJ zúčastnenej postave
    if r["roll"] == 20:
        ckey = f"tcrit_{ds}_{dec['id']}"
        if not ss.get(ckey):
            for c in dec["contribs"]:
                ss["stats"][c["postava_id"]][c["atribut_key"]] = \
                    ss["stats"][c["postava_id"]].get(c["atribut_key"], 0) + 1
            ss[ckey] = True
        zisk = ", ".join(f"{c['postava_ikona']} +1 {atr_name(c['atribut_key'])}" for c in dec["contribs"])
        st.success(f"💥 **Dokonalá súhra!** Každá postava rastie: {zisk}")

    # ❌ neúspech → −1 život každému; ak bol súčet o 20+ menej ako DC (pokus nad ich sily),
    #    celá zúčastnená skupina PADNE (koniec — treba znova, alebo GM oživí).
    if r["outcome"] == "fail":
        wipe = (r["dc"] - r["suma"]) >= 20
        lkey = f"tloss_{ds}_{dec['id']}"
        if not ss.get(lkey):
            for c in dec["contribs"]:
                hp = ss["hp"][c["postava_id"]]
                hp["current"] = 0 if wipe else max(0, hp["current"] - 1)
            ss[lkey] = True
        if wipe:
            konec = dec.get("finale")
            st.markdown(
                "<div style='text-align:center;padding:0.9em;margin-top:6px;background:#5c000033;"
                "border:2px solid #f85149;border-radius:10px'>"
                f"<div style='font-size:1.35rem;color:#f85149;font-weight:bold'>"
                f"{'💀 KONIEC — SVETLO POHASLO 💀' if konec else '☠️ CELÁ SKUPINA PADLA ☠️'}</div>"
                "<div style='color:#ddd;margin-top:6px'>Pokus bol ďaleko nad ich sily — spojený úder "
                "sa zlomil a tieň zmietol celú skupinu k zemi.</div>"
                "<div style='color:#f4c430;margin-top:8px'>Kým bije čo i len jedno srdce, nádej žije — "
                "<b>zomknite sa a skúste to znova</b> (alebo nech GM oživí padlých). "
                "Nabudúce najprv posilnite atribúty míľnikovými bodmi! 🎖️</div></div>",
                unsafe_allow_html=True)
        else:
            elim = [short_name(c["postava_id"]) for c in dec["contribs"]
                    if ss["hp"][c["postava_id"]]["current"] <= 0]
            chvost = f" — eliminovaní: {', '.join(elim)} ☠️" if elim else ""
            st.markdown(f"💔 **Odrazený nápor:** každá zúčastnená postava **−1 život**{chvost}.")

    if st.button(f"↩️ Znova tímovú scénu {n}", key=f"treset_{ds}_{dec['id']}"):
        for k in (reskey, f"tcrit_{ds}_{dec['id']}", f"tloss_{ds}_{dec['id']}"):
            ss.pop(k, None)
        st.rerun()
    return True


def highest_attr(cid):
    s = st.session_state["stats"].get(cid, {})
    if not s:
        return 0, "sila"
    k = max(s, key=lambda x: s[x])
    return s[k], k


def fallback_option_d(pend, dec):
    """Vygeneruje skrytú možnosť D, ak ju scéna v dátach nemá (napr. pri bossoch).

    DC je odvodené od atribútu (treba hodiť ~8) — silná, ale NIE okamžitá výhra.
    """
    cid = pend["postava"]
    p = PARTY_ALL.get(cid, {"meno": cid, "icon": "❔"})
    hv, hk = highest_attr(cid)
    dcs = [o["dc"] for o in dec.get("options", [])] or [hv + 10]
    m = min(dcs)
    dc = max(3, m - (1 if m % 3 == 0 else 2))     # o 1-2 nižšie než najľahšia bežná
    return {
        "label": f"D) {pend['nazov']} — {p['meno']} zažiari silou relikvie",
        "postava_id": cid, "postava_nazov": p["meno"], "postava_ikona": p["icon"],
        "atribut_key": hk, "atribut_nazov": atr_name(hk), "bonus": 0, "dc": dc,
        "result_success": "Svetlo Úsvitu prežiari scénu — cesta sa otvára a tieň ustupuje pred jasom.",
        "result_near": "Svetlo zažiari, no len nakrátko — stačí to tak-tak.",
        "result_fail": "Svetlo bliklo a zhaslo skôr, než naplno zabralo.",
    }


NEXT_DECISION_MECHS = ("zniz_dc", "skryta_moznost_d", "auto_uspech", "auto_uspech_skupina",
                       "preskocit_rozhodnutie", "spoj_hody_vsetci", "spoj_hody_dvaja")
REROLL_MECHS = ("prehodenie_hodu", "prehodenie_hodu_plus5")


def _success_res(opt, note):
    return {"idx": 0, "postava": opt["postava_id"], "atribut": opt["atribut_key"],
            "roll": 20, "roll_eff": 20, "atr": 0, "bonus": 0, "item_bonus": 0, "item_detail": [],
            "spec_bonus": 0, "spec_detail": [], "total": 0, "dc": opt["dc"], "diff": 0,
            "outcome": "success", "auto": True, "auto_note": note}


def render_skill_decision(n, ds, dec, accent, entry, positive=False):
    ss = st.session_state
    reskey = f"res_{ds}_{dec['id']}"
    badge = TYPE_BADGE.get(dec["typ"], "")
    is_combat = dec["typ"] == "fyzicke"
    pend = ss.get("pending_ability")

    st.markdown(f"#### {badge} · Rozhodnutie {n}")
    st.markdown(f"**{dec['prompt']}**")

    if reskey not in ss:
        dc_delta = 0
        active_od = None
        # skrytá cesta je aktívna na CELÝ deň (denný flag) → možnosť D v každom rozhodnutí
        sd = ss.get(f"skryta_den_{ds}")
        if sd and not positive:
            active_od = dec.get("option_d") or fallback_option_d(
                {"postava": sd["postava"], "nazov": sd["nazov"]}, dec)
            st.success(f"🎁 **{sd['nazov']}** aktívna dnes — skrytá možnosť D je v každom rozhodnutí.")
        # ── čakajúca špeciálna schopnosť, ktorá sa prejaví na tomto rozhodnutí ──
        if pend and not positive and pend["mechanika"] in NEXT_DECISION_MECHS:
            mech = pend["mechanika"]
            if mech == "zniz_dc":
                dc_delta = -int(pend.get("hodnota", 0))
                st.info(f"🎯 **{pend['nazov']}** aktívna — DC −{abs(dc_delta)} pre toto rozhodnutie.")
            elif mech in ("auto_uspech", "auto_uspech_skupina"):
                koho = "celej skupiny" if mech == "auto_uspech_skupina" else PARTY_ALL[pend['postava']]['meno']
                st.success(f"✅ **{pend['nazov']}** — vyber možnosť a potvrď automatický úspech ({koho}).")
                for idx, opt in enumerate(dec["options"]):
                    if st.button(f"✅ Automatický úspech: {opt['label']}", key=f"autosucc_{ds}_{dec['id']}_{idx}"):
                        r = _success_res(opt, pend["nazov"]); r["idx"] = idx
                        ss[reskey] = r
                        ss.pop("pending_ability", None)
                        st.rerun()
                st.caption("…alebo hoď normálne nižšie (schopnosť ostane pripravená).")
            elif mech == "preskocit_rozhodnutie":
                st.success(f"⏭️ **{pend['nazov']}** — preskočiť toto rozhodnutie bez následkov?")
                if st.button("⏭️ Preskočiť (úspech bez hodu)", key=f"skipbtn_{ds}_{dec['id']}"):
                    opt = dec["options"][0]
                    r = _success_res(opt, pend["nazov"]); r["skipped"] = True
                    ss[reskey] = r
                    ss.pop("pending_ability", None)
                    st.rerun()
                st.caption("…alebo hoď normálne nižšie.")
            elif mech in ("spoj_hody_vsetci", "spoj_hody_dvaja"):
                return render_spoj_decision(n, ds, dec, accent, entry, pend)

        # ── Hviezdny vietor (výhoda) — hod danej postavy sa hodí dvakrát, počíta vyššia ──
        if pend and not positive and pend.get("mechanika") == "vyhoda_hodu":
            st.info(f"🏹 **{pend['nazov']}** pripravený — hod postavy "
                    f"{short_name(pend['postava'])} bude s výhodou (2 kocky, počíta sa vyššia).")
        # ── Priazeň hviezd — ak hod danej postavy padne 15+, ráta sa ako 20 (kritický úspech) ──
        if pend and not positive and pend.get("mechanika") == "priazen_hviezd":
            st.info(f"🌌 **{pend['nazov']}** pripravená — ak hod postavy {short_name(pend['postava'])} "
                    f"padne **15+**, ráta sa ako kritický úspech (20).")

        # ── normálne možnosti (s prípadným znížením DC + skrytou možnosťou D) ──
        opts = list(dec["options"])
        if active_od:
            opts = opts + [active_od]
        for idx, opt in enumerate(opts):
            opt_disp = dict(opt)
            if dc_delta:
                opt_disp["dc"] = max(1, opt["dc"] + dc_delta)
            render_option_panel(opt_disp, accent, is_combat, ds)
            eliminovana = ss["hp"].get(opt["postava_id"], {}).get("current", 1) <= 0
            if eliminovana:
                st.caption(f"☠️ {opt['postava_nazov']} je eliminovaný/á — túto možnosť teraz nemôže hrať.")
            if st.button(f"🎲 {opt['postava_ikona']} {opt['postava_nazov']} — hodiť kockou",
                         key=f"btn_{ds}_{dec['id']}_{idx}", disabled=eliminovana):
                adv = (pend and pend.get("mechanika") == "vyhoda_hodu"
                       and pend.get("postava") == opt["postava_id"])
                priazen = (pend and pend.get("mechanika") == "priazen_hviezd"
                           and pend.get("postava") == opt["postava_id"])
                ph = st.empty()
                roll = animated_roll(ph, accent)
                eff = roll
                if adv:                        # Hviezdny vietor — druhá kocka, počíta sa vyššia
                    roll2 = animated_roll(ph, accent)
                    eff = max(roll, roll2)
                if priazen and eff >= 15:       # Priazeň hviezd — 15+ ráta ako prirodzená 20
                    res = evaluate(opt_disp, 20, opt["postava_id"], is_combat, ds)
                else:
                    res = evaluate(opt_disp, eff, opt["postava_id"], is_combat, ds)
                if adv:
                    res["adv"] = [roll, roll2]
                if priazen:
                    res["priazen"] = eff
                    ss.pop("pending_ability", None)
                elif adv:
                    ss.pop("pending_ability", None)
                res["idx"] = idx
                res["opt"] = opt_disp          # snapshot pre zobrazenie (aj pri generovanej D)
                ss[reskey] = res
                if dc_delta:                   # zníženie DC platí len na toto rozhodnutie
                    ss.pop("pending_ability", None)
                st.rerun()
        return False

    # ── už rozhodnuté ──
    res = ss[reskey]
    opts_all = list(dec["options"])
    if dec.get("option_d"):
        opts_all = opts_all + [dec["option_d"]]
    opt = res.get("opt") or (opts_all[res["idx"]] if res["idx"] < len(opts_all) else dec["options"][0])
    st.markdown(f"➡️ **{opt['label']}** · {opt['postava_ikona']} {opt['postava_nazov']}")
    if res.get("auto"):
        st.success(f"✅ Automatický úspech — {res.get('auto_note', 'špeciálna schopnosť')} "
                   f"({'preskočené' if res.get('skipped') else 'bez hodu'}).")
    render_calc(res)
    if res.get("adv"):
        a, b = res["adv"]
        st.caption(f"🏹 Výhoda (Hviezdny vietor): hody **{a}** a **{b}** → počíta sa **{max(a, b)}**.")
    if res.get("priazen") is not None:
        e = res["priazen"]
        if e >= 15:
            st.caption(f"🌌 Priazeň hviezd: hod **{e}** (15+) → ráta sa ako **20** — kritický úspech!")
        else:
            st.caption(f"🌌 Priazeň hviezd: hod **{e}** nedosiahol 15 — hviezdy sa tentokrát nezarovnali.")
    if res.get("spoj"):
        lines = " + ".join(f"{PARTY_ALL[c]['icon']}{short_name(c)} ({roll}+{hv} {atr_name(hk)})"
                           for c, roll, hv, hk in res["spoj_rolls"])
        st.markdown(f"🔗 **Spoločný hod:** {lines} = **{res['total']}**  vs  **DC {res['dc']}**")

    if positive:
        # detské — vždy aspoň čiastočne pozitívne
        head = "💥 Kritický úspech!" if res["roll"] == 20 else "🎈 Hotovo!"
        st.markdown(f"### {head}")
        txt = (opt["result_success"] if res["outcome"] == "success"
               else opt["result_near"] if res["outcome"] == "near" else opt["result_fail"])
        st.success(txt)
    else:
        st.markdown(f"### {outcome_label(res)}")
        if res["outcome"] == "success":
            st.success(opt["result_success"])
        elif res["outcome"] == "near":
            st.warning(opt["result_near"])
        else:
            st.error(opt["result_fail"])

    real = not (res.get("auto") or res.get("skipped") or res.get("spoj"))

    # Hod 1 — kritický neúspech: −1 život navyše (raz). Šťastná kocka / Prorocká vízia to rušia.
    if real and res["roll"] == 1 and res.get("roll_eff", 1) == 1 and not positive:
        critkey = f"crit1_{ds}_{dec['id']}"
        hp = ss["hp"][opt["postava_id"]]
        if not ss.get(critkey):
            hp["current"] = max(0, hp["current"] - 1)
            ss[critkey] = True
        chvost = " — **ELIMINOVANÝ/Á** ☠️" if hp["current"] <= 0 else ""
        st.caption(f"💀 Kritický neúspech (hod 1): {opt['postava_nazov']} −1 život navyše{chvost}.")

    # Levelup pri hode 20 (max 1× za deň na postavu)
    if real and res["roll"] == 20:
        lvlkey = f"levelup20_{ds}_{opt['postava_id']}"
        an = atr_name(res["atribut"])
        if ss.get(lvlkey):
            st.caption(f"⭐ {opt['postava_nazov']} už dnes získal/a +1 {an} za hod 20.")
        else:
            if st.button(f"⭐ Potvrdiť levelup: +1 {an} pre {opt['postava_nazov']}",
                         key=f"lvl_{ds}_{dec['id']}"):
                ss["stats"][opt["postava_id"]][res["atribut"]] += 1
                ss[lvlkey] = True
                st.toast(f"{opt['postava_nazov']}: +1 {an}!", icon="⭐")
                st.rerun()

    # Prehodenie (Časová slučka / Druhý pokus) — ak je pripravená a hodilo sa naozaj
    if real and pend and pend.get("mechanika") in REROLL_MECHS:
        plus = int(pend.get("hodnota", 0))
        lbl = f"🔄 {pend['nazov']} — prehodiť" + (f" (+{plus})" if plus else "")
        if st.button(lbl, key=f"reroll_{ds}_{dec['id']}"):
            opt_re = dict(opt)
            opt_re["bonus"] = opt.get("bonus", 0) + plus
            ph = st.empty()
            roll = animated_roll(ph, accent)
            r = evaluate(opt_re, roll, opt["postava_id"], is_combat, ds)
            r["idx"] = res["idx"]
            ss[reskey] = r
            ss.pop(f"crit1_{ds}_{dec['id']}", None)
            ss.pop("pending_ability", None)
            st.rerun()

    # Strata životov za prvý hod (len neúspech 4+; tesný neúspech 1–3 nič nestráca)
    if real and res["outcome"] == "fail" and not positive:
        cid = opt["postava_id"]
        savedkey = f"armorsaved_{ds}_{dec['id']}"
        tryedkey = f"armortry_{ds}_{dec['id']}"
        rollkey = f"armorroll_{ds}_{dec['id']}"
        strata, elim = apply_life_loss(ds, dec, opt, res, attempt=1)
        render_life_loss(strata, opt, elim)
        # 🛡️ brnenie/štít „zachráni život" — len vo FYZICKOM boji; samostatný hod, prah aj
        #    počet použití podľa KVALITY, KAŽDÝ KUS má vlastný zostatok (armorleft_{cid}_{názov}).
        if is_combat and isinstance(strata, int) and strata > 0:
            if ss.get(tryedkey):                       # pokus už prebehol → výsledok
                rr = ss.get(rollkey) or [0, 0, "Zbroj"]
                sroll, thr_u, nazov_u = rr[0], rr[1], rr[2]
                if ss.get(savedkey):
                    st.success(f"🛡️ **{nazov_u}** — hod **{sroll}** ≥ {thr_u}: zachránený **1 život**!")
                else:
                    st.markdown(f"🛡️ {nazov_u} — hod **{sroll}** < {thr_u}: nezachránila (život ostáva stratený).")
            else:
                info = _armor_save_best(cid)           # (prah, názov, zostatok) alebo None
                if info:
                    thr, nazov, left = info
                    if st.button(f"🛡️ {nazov} — hod o záchranu 1 života (treba {thr}+, zostáva {left}×)",
                                 key=f"asavebtn_{ds}_{dec['id']}"):
                        ph = st.empty()
                        sroll = animated_roll(ph, accent)
                        ss[f"armorleft_{cid}_{nazov}"] = left - 1
                        ss[tryedkey] = True
                        ss[rollkey] = [sroll, thr, nazov]
                        if sroll >= thr:
                            hp = ss["hp"][cid]
                            hp["current"] = min(hp["max"], hp["current"] + 1)
                            ss[savedkey] = True
                        st.rerun()

        # 🛡️ Štít Prvého strážcu — REAKTÍVNA úplná záchrana: zruší celý tento zásah (aj smrť),
        #    funguje aj mimo fyzického boja; čerpá z nábojov Zbroje ktoréhokoľvek nositeľa v družine.
        if strata == "smrt" or (isinstance(strata, int) and strata > 0):
            gkey = f"guardsaved_{ds}_{dec['id']}"
            if ss.get(gkey):
                st.success(f"🛡️ **Štít Prvého strážcu** už úplne zachránil {opt['postava_nazov']} "
                           f"(zásah zrušený).")
            else:
                saver = _guard_saver(entry)
                if saver:
                    scid, gitem, left = saver
                    nm = "" if scid == cid else f" ({short_name(scid)})"
                    if st.button(f"🛡️ Štít Prvého strážcu{nm} — úplne zachrániť {opt['postava_nazov']} "
                                 f"(zostáva {left}×)", key=f"guardbtn_{ds}_{dec['id']}"):
                        prehp = ss.get(f"prehp_{ds}_{dec['id']}_1", ss["hp"][cid]["max"])
                        if ss.get(f"crit1_{ds}_{dec['id']}"):     # vráť aj −1 za hod 1
                            prehp = min(ss["hp"][cid]["max"], prehp + 1)
                        ss["hp"][cid]["current"] = prehp
                        gitem["pocet_pouziti"] = left - 1
                        ss[gkey] = True
                        st.rerun()

    # Druhá šanca — každý neúspech (tesný aj veľký) dostane 1 pokus tou istou postavou.
    # Tesný neúspech (1–3): rovnaké DC. Neúspech 4+: DC +2. Smrť (21+) druhú šancu nedá.
    if real and res["outcome"] in ("near", "fail") and not positive and not res.get("is_second"):
        smrtelny = res["outcome"] == "fail" and zivoty_za_rozdiel(-res["diff"]) == "smrt"
        zachraneny = ss.get(f"guardsaved_{ds}_{dec['id']}")     # Štít Prvého strážcu zrušil zásah
        if (smrtelny or ss["hp"][opt["postava_id"]]["current"] <= 0) and not zachraneny:
            st.info("☠️ Postava je eliminovaná — družina pokračuje ďalej.")
        elif not smrtelny:
            render_second_chance(n, ds, dec, accent, entry, opt, res)

    if st.button(f"↩️ Znova rozhodnutie {n}", key=f"reset_{ds}_{dec['id']}"):
        for k in (reskey, f"res2_{ds}_{dec['id']}", f"crit1_{ds}_{dec['id']}",
                  f"zloss_{ds}_{dec['id']}_1", f"zloss_{ds}_{dec['id']}_2",
                  f"armorsaved_{ds}_{dec['id']}", f"armortry_{ds}_{dec['id']}",
                  f"armorroll_{ds}_{dec['id']}", f"guardsaved_{ds}_{dec['id']}",
                  f"prehp_{ds}_{dec['id']}_1", f"prehp_{ds}_{dec['id']}_2"):
            ss.pop(k, None)
        st.rerun()
    return True


def render_spoj_decision(n, ds, dec, accent, entry, pend):
    """Spojené hody (Posledný strážca / Elfská synergia) — výsledky sa sčítajú."""
    ss = st.session_state
    reskey = f"res_{ds}_{dec['id']}"
    opt = dec["options"][0]            # rámec rozhodnutia (DC, výsledkový text)
    dc = opt["dc"]
    mech = pend["mechanika"]
    if mech == "spoj_hody_vsetci":
        st.success(f"🔗 **{pend['nazov']}** — všetky postavy hodia, ich hod + najvyšší atribút sa sčíta "
                   f"(cieľ DC {dc}).")
        team = active_ids(entry)
    else:
        others = [c for c in active_ids(entry) if c != "elf"] or active_ids(entry)
        druhy = st.selectbox("Spojiť Elfa s:", others,
                             format_func=lambda c: f"{PARTY_ALL[c]['icon']} {short_name(c)}",
                             key=f"spoj_{ds}_{dec['id']}")
        st.success(f"🔗 **{pend['nazov']}** — Elf + {short_name(druhy)} hodia spoločne (cieľ DC {dc}).")
        team = ["elf", druhy]
    if st.button("🔗 Hodiť spoločne", key=f"spojbtn_{ds}_{dec['id']}"):
        ph = st.empty()
        rolls, total = [], 0
        for c in team:
            roll = animated_roll(ph, accent)
            hv, hk = highest_attr(c)
            rolls.append((c, roll, hv, hk))
            total += roll + hv
        krit20 = any(r == 20 for _, r, _, _ in rolls)     # ktorákoľvek 20 = úspech
        outcome = ("success" if (krit20 or total >= dc)
                   else ("near" if total >= dc - 3 else "fail"))
        ss[reskey] = {"idx": 0, "spoj": True, "spoj_rolls": rolls, "total": total, "dc": dc,
                      "diff": total - dc, "outcome": outcome, "postava": team[0],
                      "atribut": opt["atribut_key"], "roll": 0, "roll_eff": 0}
        ss.pop("pending_ability", None)
        st.rerun()
    st.caption("…alebo zruš schopnosť a hraj normálne (Reset dňa).")
    return False


def render_second_chance(n, ds, dec, accent, entry, opt, first_res):
    """Druhá šanca tou istou postavou. Tesný neúspech (1–3) → rovnaké DC;
    neúspech 4+ → DC +2. Ak aj druhý hod padne 4+, stráca životy znova.
    Družina pokračuje pri úspechu alebo po dvoch neúspechoch."""
    ss = st.session_state
    res2key = f"res2_{ds}_{dec['id']}"
    dc_delta = 2 if first_res["outcome"] == "fail" else 0
    new_dc = opt["dc"] + dc_delta
    cid = opt["postava_id"]
    is_combat = dec["typ"] == "fyzicke"

    st.markdown("---")
    delta_txt = "DC +2" if dc_delta else "rovnaké DC"
    st.info(f"🎯 **Druhá šanca** — {opt['postava_ikona']} {opt['postava_nazov']}, "
            f"{delta_txt} (**DC {new_dc}**).")

    if res2key in ss:
        r = ss[res2key]
        render_calc(r)
        st.markdown(f"**{outcome_label(r)}**")
        if r["total"] >= r["dc"]:
            st.success("Druhá šanca zabrala — družina pokračuje s úspechom.")
        else:
            strata, elim = apply_life_loss(ds, dec, r["opt"], r, attempt=2)
            render_life_loss(strata, opt, elim)
            st.error("Ani druhá šanca nevyšla — družina pokračuje ďalej.")
        return

    if ss["hp"][cid]["current"] <= 0:
        st.error(f"{opt['postava_nazov']} je eliminovaný/á — družina pokračuje ďalej.")
        return

    if st.button(f"🎲 {opt['postava_ikona']} {opt['postava_nazov']} — druhá šanca",
                 key=f"sc_btn_{ds}_{dec['id']}"):
        opt2 = dict(opt)
        opt2["dc"] = new_dc
        ph = st.empty()
        roll = animated_roll(ph, accent)
        r = evaluate(opt2, roll, cid, is_combat, ds)
        r["idx"] = first_res.get("idx")
        r["opt"] = opt2
        r["is_second"] = True
        ss[res2key] = r
        st.rerun()


def mods_summary(item):
    """Textový súhrn efektov predmetu na atribúty (s označením v boji/stále)."""
    parts = []
    for m in item.get("mod", []):
        nm = STAT_NAMES[STAT_KEYS.index(m["atribut"])] if m["atribut"] in STAT_KEYS else m["atribut"]
        tag = " <span style='color:#d4a017'>(v boji)</span>" if m.get("kedy") == "boj" else ""
        parts.append(f"{'+' if m['hodnota'] >= 0 else '−'}{abs(m['hodnota'])} {nm}{tag}")
    return ", ".join(parts)


def render_item_box(item, gm=False, raw=None):
    """Vykreslí predmet (názov, výhody, nevýhody, efekty na atribúty, záhada, GM)."""
    jed = " · <span style='color:#d29922'>jednorazový</span>" if item.get("jednorazovy") else ""
    extra = ""
    ms = mods_summary(item)
    if ms:
        extra += f"<br>🎒 <b>Efekt:</b> {ms}"
    pouzitie = item.get("pouzitie")
    if pouzitie:
        pocet = item.get("pocet_pouziti") or 1
        extra += (f"<br>✨ <b>Použiť:</b> {pouzitie.get('popis','')} "
                  f"<span style='color:#9aa'>(použití: {pocet})</span>")
    zahada = item.get("zahada")
    if not zahada and not item.get("mod") and not pouzitie and not item.get("jednorazovy"):
        # spomienkové/príbehové predmety bez mechaniky → náznak budúceho využitia
        zahada = "Čas ukáže jeho význam…"
    if zahada:
        extra += f"<br>🌀 <i>{zahada}</i>"
    html = (f"<div class='su-item'><b>{item.get('ikona', '')} {item['nazov']}</b>{jed}<br>"
            f"✨ {item.get('vyhody') or '—'}<br>"
            f"⚠️ {item.get('nevyhody') or '—'}{extra}</div>")
    st.markdown(html, unsafe_allow_html=True)
    if gm and (raw or {}).get("gm_poznamka"):
        st.markdown(f"<div class='su-gm'>🔒 GM: {raw['gm_poznamka']}</div>", unsafe_allow_html=True)


def render_predmet_decision(n, ds, dec, entry, gm):
    ss = st.session_state
    raw = dec["predmet"]
    item = normalize_item(raw)
    donekey = f"predmet_done_{ds}_{dec['id']}"

    st.markdown(f"#### 🎁 · Rozhodnutie {n} — Nájdený predmet")
    render_item_box(item, gm, raw)

    ids = active_ids(entry)
    eligible = [cid for cid in ids if item_allowed_for(item, cid)]
    restricted = len(eligible) < len(ids)
    if restricted:
        kto = ", ".join(short_name(c) for c in eligible) or "nikto z prítomných"
        st.caption(f"🔒 Tento predmet môže niesť len: **{kto}**")

    if donekey not in ss:
        st.caption("Komu predmet pridelíte?")
        cols = st.columns(3)
        any_free = False
        for i, cid in enumerate(eligible):
            full = len(ss["inventory"][cid]) >= INV_LIMIT
            any_free = any_free or not full
            lbl = f"{PARTY_ALL[cid]['icon']} {short_name(cid)}" + (" · plný" if full else "")
            if cols[i % 3].button(lbl, key=f"give_{ds}_{dec['id']}_{cid}", disabled=full):
                ss["inventory"][cid].append(item)
                ss[donekey] = cid
                st.toast(f"{item['nazov']} → {short_name(cid)}", icon="🎁")
                st.rerun()
        if eligible and not any_free:
            st.warning("Všetci oprávnení majú plný inventár (5/5). Uvoľni miesto v karte postavy "
                       "(presuň alebo vyhoď predmet) a skús znova.")
        if st.button("🚫 Nechať ležať (nebrať)", key=f"leave_{ds}_{dec['id']}"):
            ss[donekey] = "_none"
            st.rerun()
        return False

    who = ss[donekey]
    if who == "_none":
        st.info("Predmet ste nechali ležať.")
    else:
        st.success(f"Predmet dostal/a {PARTY_ALL[who]['icon']} {PARTY_ALL[who]['meno']}.")
    if st.button(f"↩️ Znova rozhodnutie {n}", key=f"reset_{ds}_{dec['id']}"):
        if who not in (None, "_none"):
            inv = ss["inventory"].get(who, [])
            for j, x in enumerate(inv):
                if isinstance(x, dict) and x.get("nazov") == item["nazov"]:
                    inv.pop(j)
                    break
        ss.pop(donekey, None)
        st.rerun()
    return True


SELL_RATIO = 0.5   # predaj vráti polovicu ceny


def do_purchase(buyer, sel, total, zdroj, clan_key, ds, did):
    ss = st.session_state
    osob = ss["gold"][buyer]
    klan = ss["gold"][clan_key]
    free = INV_LIMIT - len(ss["inventory"][buyer])
    if len(sel) > free:
        return False, f"Inventár {short_name(buyer)} nemá dosť miesta ({free} voľných)."
    if zdroj == "Osobné":
        if osob < total:
            return False, "Málo osobného zlata."
        ss["gold"][buyer] -= total
    elif zdroj == "Klanové":
        if klan < total:
            return False, "Málo v klanovej pokladnici."
        ss["gold"][clan_key] -= total
    else:  # Kombinácia — najprv osobné, zvyšok z klanu
        if osob + klan < total:
            return False, "Málo zlata spolu (osobné + klanové)."
        from_osob = min(osob, total)
        ss["gold"][buyer] -= from_osob
        ss["gold"][clan_key] -= (total - from_osob)
    for p in sel:
        ss["inventory"][buyer].append(normalize_item(p))
    for i in range(50):                       # odznač vybrané checkboxy
        ss.pop(f"buy_{ds}_{did}_{i}", None)
    return True, f"Kúpené ({total} zl) pre {short_name(buyer)}."


def render_nakup_decision(n, ds, dec, entry):
    ss = st.session_state
    market = dec["market"]
    polozky = dec["polozky"]
    did = dec["id"]
    donekey = f"nakup_done_{ds}_{did}"

    st.markdown(f"#### {market['ikona']} · Rozhodnutie {n} — {market['nazov']}")
    st.caption(market["popis"])

    ids = active_ids(entry)
    buyer = st.selectbox("Kupujúci", ids,
                         format_func=lambda i: f"{PARTY_ALL[i]['icon']} {PARTY_ALL[i]['meno']}",
                         key=f"buyer_{ds}_{did}")

    sel = []
    for i, p in enumerate(polozky):
        if not item_allowed_for(p, buyer):       # obmedz tovar na vhodnú postavu
            continue
        jed = " · jednorazový" if p.get("jednorazovy") else ""
        lab = (f"{p.get('ikona', '🛒')} **{p['nazov']}** — ➕ {p.get('vyhoda', '')} · "
               f"➖ {p.get('nevyhoda', '')} · **{p['cena']} zl**{jed}")
        if st.checkbox(lab, key=f"buy_{ds}_{did}_{i}"):
            sel.append(p)
    skryte = [p for p in polozky if not item_allowed_for(p, buyer)]
    if skryte:
        st.caption("🔒 Niektoré zbrane sú vhodné pre iné postavy (skryté) — vyber správneho kupujúceho.")

    total = sum(p["cena"] for p in sel)
    clan_key = "klan" if CLAN_OF.get(buyer) == "mala" else "klan_slnko"
    osob = ss["gold"][buyer]
    klan = ss["gold"][clan_key]
    klan_nazov = CLANS["mala"]["nazov"] if clan_key == "klan" else CLANS["velka"]["nazov"]
    free = INV_LIMIT - len(ss["inventory"][buyer])

    zdroj = st.radio("Zaplatiť z", ["Osobné", "Klanové", "Kombinácia"], horizontal=True,
                     key=f"pay_{ds}_{did}")
    # prehľad ceny a zostatku po nákupe
    if zdroj == "Osobné":
        po_osob, po_klan = osob - total, klan
    elif zdroj == "Klanové":
        po_osob, po_klan = osob, klan - total
    else:
        from_osob = min(osob, total)
        po_osob, po_klan = osob - from_osob, klan - (total - from_osob)
    dost = po_osob >= 0 and po_klan >= 0
    miesto_ok = len(sel) <= free
    st.markdown(
        f"🧾 Vybrané: **{total} zl** ({len(sel)} ks, voľné miesto {free}/{INV_LIMIT})  \n"
        f"💰 Osobné ({short_name(buyer)}): {osob} → **{po_osob} zl** · "
        f"🏦 {klan_nazov}: {klan} → **{po_klan} zl**")
    if sel and not dost:
        st.warning("Nemáš dosť zlata na tento výber pri zvolenom zdroji.")
    if sel and not miesto_ok:
        st.warning(f"Inventár {short_name(buyer)} nemá dosť miesta ({free} voľných).")

    cols = st.columns(2)
    can_buy = bool(sel) and dost and miesto_ok
    if cols[0].button("✅ Kúpiť vybrané", key=f"buybtn_{ds}_{did}", disabled=not can_buy):
        ok, msg = do_purchase(buyer, sel, total, zdroj, clan_key, ds, did)
        if ok:
            st.toast(msg, icon="🛒")
        else:
            ss[f"buyerr_{ds}_{did}"] = msg
        st.rerun()
    if cols[1].button("➡️ Pokračovať (obchod hotový)", key=f"shopdone_{ds}_{did}"):
        ss[donekey] = True
        st.rerun()

    # Predaj / vrátenie predmetu z inventára kupujúceho (vráti polovicu ceny do osobného)
    inv = ss["inventory"][buyer]
    sellable = [k for k, it in enumerate(inv) if isinstance(it, dict) and it.get("cena", 0) > 0]
    if sellable:
        with st.expander("💱 Predať predmet (vráti pol ceny)"):
            k = st.selectbox("Predmet", sellable,
                             format_func=lambda j: f"{inv[j]['nazov']} ({inv[j].get('cena', 0)} zl)",
                             key=f"sell_{ds}_{did}")
            vrat = int(inv[k].get("cena", 0) * SELL_RATIO)
            if st.button(f"💱 Predať za {vrat} zl", key=f"sellbtn_{ds}_{did}"):
                ss["gold"][buyer] += vrat
                inv.pop(k)
                st.toast(f"Predané za {vrat} zl", icon="💱")
                st.rerun()

    err = ss.pop(f"buyerr_{ds}_{did}", None)
    if err:
        st.warning(err)

    if donekey in ss:
        st.success("Obchod uzavretý.")
        if st.button(f"↩️ Znova rozhodnutie {n}", key=f"reset_{ds}_{did}"):
            ss.pop(donekey, None)
            st.rerun()
        return True
    return False


# =========================================================================
#  SIDEBAR — KARTY POSTÁV
# =========================================================================
def stat_bar_html(val, accent):
    pct = max(0, min(100, round(val / 20 * 100)))
    return (f"<div class='su-bar-bg'><div class='su-bar-fill' "
            f"style='width:{pct}%;background:{accent}'></div></div>")


def hp_color(pct):
    if pct > 0.6:
        return "#3fb950"      # zelená
    if pct >= 0.3:
        return "#d29922"      # oranžová
    return "#f85149"          # červená


def hp_bar_html(cur, mx):
    pct = (cur / mx) if mx else 0
    width = max(0, min(100, round(pct * 100)))
    col = hp_color(pct)
    return (f"<div class='su-bar-bg'><div class='su-bar-fill' "
            f"style='width:{width}%;background:{col}'></div></div>")


def gold_input(label, store_key):
    """Number_input pre zlato, ktorý rešpektuje aj programové zmeny (nákup, regenerácia).

    ss['gold'][store_key] je kanonický zdroj. Widget-key sa zosynchronizuje pred
    renderom, takže manuálna úprava aj nákup/regenerácia sa správne prejavia.
    """
    ss = st.session_state
    wkey = f"goldw_{store_key}"
    setflag = f"goldw_set_{store_key}"
    cur = int(ss["gold"].get(store_key, 0))
    if ss.get(setflag) != cur:           # programová zmena → premietni do widgetu
        ss[wkey] = cur
        ss[setflag] = cur
    st.number_input(label, min_value=0, step=5, key=wkey)
    ss["gold"][store_key] = int(ss[wkey])
    ss[setflag] = int(ss[wkey])


def _regen_heal(cid, amt):
    """Doplní postave životy (max = jej maximum). Vráti reálny prírastok."""
    hp = st.session_state["hp"][cid]
    before = hp["current"]
    hp["current"] = min(hp["max"], hp["current"] + amt)
    return hp["current"] - before


# Prostredie nocľahu — určuje, ktoré možnosti regenerácie sú logické.
_HARSH_KW = ("púšť", "púšt", "piesk", "pevnos", "hrad", "aškar", "morgrath",
             "tieňov", "sopk", "ľadov", "mráz", "žiariac", "spálen", "vyprahnut")
ZONE_LABEL = {"dedina": "🏘️ Dedina / spoločnosť", "divocina": "🌲 Divočina",
              "nehostinne": "🏜️ Nehostinné prostredie"}
ZONE_HINT = {"dedina": "Ste medzi ľuďmi — krčma, lekár, tábor v dedine.",
             "divocina": "Táborenie v prírode — les alebo provizórny nocľah.",
             "nehostinne": "Žiadna dedina nablízku — len provizórny prístrešok, či holá zem."}


def regen_zone(ds, entry):
    """Prostredie nocľahu: 'dedina' (trh/Taliansko), 'nehostinne' (púšť/pevnosť/tieň),
    inak 'divocina'. GM to môže prepísať cez ss['regen_zone_{ds}']."""
    ss = st.session_state
    override = ss.get(f"regen_zone_{ds}")
    if override in ZONE_LABEL:
        return override
    if (ds in MARKET_DAYS) or entry.get("group") == "velka":
        return "dedina"
    blob = (entry.get("title", "") + " " + entry.get("intro", "")).lower()
    if any(k in blob for k in _HARSH_KW):
        return "nehostinne"
    return "divocina"


def render_regen_decision(ds, entry):
    """Koniec dňa: kde družina strávi noc → regenerácia životov. Možnosti závisia od
    prostredia (dedina/divočina/nehostinné). Pasívne 'zásoby' pridajú +N navyše.
    Eliminovaní sa neregenerujú (najprv GM oživenie)."""
    ss = st.session_state
    donekey = f"regen_done_{ds}"
    st.markdown("#### 🌙 Nocľah — regenerácia životov")

    if ss.get(donekey):
        st.success(f"🌙 Nocľah: {ss[donekey]}")
        if ss.get("gm_mode") and st.button("↩️ Zmeniť nocľah (GM)", key=f"regen_reset_{ds}"):
            ss.pop(donekey, None)
            st.rerun()
        return

    zivi = [c for c in active_ids(entry) if ss["hp"][c]["current"] > 0]
    if not zivi:
        st.info("Nikto zo živých — regenerácia sa preskočí.")
        return

    zone = regen_zone(ds, entry)
    st.caption(f"Miesto: **{ZONE_LABEL[zone]}**. {ZONE_HINT[zone]} "
               "Eliminovaní sa neregenerujú (najprv GM oživenie).")
    # GM smie prostredie prepísať (ak inferencia sedí zle)
    if ss.get("gm_mode"):
        zopts = list(ZONE_LABEL.keys())
        gz = st.selectbox("🔒 Prostredie (GM prepis)", zopts, index=zopts.index(zone),
                          format_func=lambda z: ZONE_LABEL[z], key=f"regen_zonesel_{ds}")
        if gz != zone:
            ss[f"regen_zone_{ds}"] = gz
            st.rerun()

    def _apply(base_map, label, cost=0):
        lines = []
        for c in zivi:
            _regen_heal(c, base_map.get(c, 0))
            b = apply_regen_bonuses(c)          # pasívne zásoby jedla atď.
            if b:
                lines.append(f"{PARTY_ALL[c]['icon']}+{b}")
        if cost:
            ss["gold"]["klan"] = max(0, ss["gold"]["klan"] - cost)
        if lines:
            label += "  ·  🍖 zásoby: " + ", ".join(lines)
        ss[donekey] = label
        st.rerun()

    if zone == "dedina":
        CENA_OS = 10                                   # každý platí za seba z vlastného
        moze = [c for c in zivi if ss["gold"].get(c, 0) >= CENA_OS]
        chudobni = [short_name(c) for c in zivi if ss["gold"].get(c, 0) < CENA_OS]
        if st.button(f"🏘️ Krčma / hostinec — {CENA_OS} zl za seba (z vlastného) → **+4** kto zaplatí",
                     key=f"regen_krcma_{ds}", disabled=not moze):
            lines = []
            for c in zivi:
                if ss["gold"].get(c, 0) >= CENA_OS:    # zaplatí sám za seba
                    ss["gold"][c] -= CENA_OS
                    _regen_heal(c, 4)
                b = apply_regen_bonuses(c)
                if b:
                    lines.append(f"{PARTY_ALL[c]['icon']}+{b}")
            popis = f"Krčma (+4 kto zaplatil {CENA_OS} zl z vlastného"
            if chudobni:
                popis += f"; bez peňazí táborili: {', '.join(chudobni)}"
            popis += ")"
            if lines:
                popis += "  ·  🍖 zásoby: " + ", ".join(lines)
            ss[donekey] = popis
            st.rerun()
        if chudobni:
            st.caption(f"⚠️ Nemajú {CENA_OS} zl a do krčmy nejdú: {', '.join(chudobni)} "
                       "(prespia v tábore — zvoľ nižšie tábor pre nich, alebo im GM dá zlato).")
        if st.button("🏕️ Tábor medzi ľuďmi (dedina) — zdarma → **+3** každému",
                     key=f"regen_tabor_ludia_{ds}"):
            _apply({c: 3 for c in zivi}, "Tábor medzi ľuďmi (+3 každému)")
        st.markdown("**⚕️ Lekár** — 15 zl z vlastného za jednu postavu (**+5**), ostatní tábor (**+3**):")
        _zlato = {c: ss["gold"].get(c, 0) for c in zivi}
        lc = st.selectbox("Koho k lekárovi", zivi,
                          format_func=lambda c: f"{PARTY_ALL[c]['icon']} {short_name(c)} ({_zlato[c]} zl)",
                          key=f"regen_lekar_sel_{ds}")
        dost_lekar = ss["gold"].get(lc, 0) >= 15
        if st.button(f"⚕️ K lekárovi: {short_name(lc)} (+5, −15 zl z vlastného), ostatní tábor (+3)",
                     key=f"regen_lekar_{ds}", disabled=not dost_lekar):
            ss["gold"][lc] -= 15
            lines = []
            for c in zivi:
                _regen_heal(c, 5 if c == lc else 3)
                b = apply_regen_bonuses(c)
                if b:
                    lines.append(f"{PARTY_ALL[c]['icon']}+{b}")
            popis = f"Lekár: {short_name(lc)} +5 (−15 zl z vlastného), ostatní +3"
            if lines:
                popis += "  ·  🍖 zásoby: " + ", ".join(lines)
            ss[donekey] = popis
            st.rerun()
        if not dost_lekar:
            st.caption(f"⚠️ {short_name(lc)} nemá 15 zl na lekára (má {ss['gold'].get(lc, 0)} zl).")

    elif zone == "divocina":
        if st.button("🌲 Tábor v divočine / lese — zdarma → **+2** každému", key=f"regen_les_{ds}"):
            _apply({c: 2 for c in zivi}, "Divočina / les (+2 každému)")
        if st.button("⛺ Provizórny nocľah (dážď, hliadky) — zdarma → **+1** každému",
                     key=f"regen_provizorny_{ds}"):
            _apply({c: 1 for c in zivi}, "Provizórny nocľah (+1 každému)")

    else:  # nehostinne
        if st.button("⛺ Provizórny prístrešok (skala, ruina) — zdarma → **+1** každému",
                     key=f"regen_provizorny_{ds}"):
            _apply({c: 1 for c in zivi}, "Provizórny prístrešok (+1 každému)")
        if st.button("🏜️ Holá nehostinná zem (púšť, pevnosť, tieň) — bez oddychu (**+0**)",
                     key=f"regen_nehostinne_{ds}"):
            _apply({c: 0 for c in zivi}, "Nehostinné prostredie (+0)")


def use_consumable(cid, item, target=None):
    """Aplikuje efekt spotrebného predmetu. `target` = na koho (pri cielených schopnostiach),
    inak sám nositeľ. Vráti (hláška, minulo_sa_bool)."""
    ss = st.session_state
    p = item.get("pouzitie") or {}
    typ = p.get("typ")
    val = p.get("hodnota", 0)
    tgt = target or cid
    hp = ss["hp"][cid]
    if typ == "heal":
        pred = hp["current"]
        hp["current"] = min(hp["max"], hp["current"] + val)
        msg = f"❤️ +{hp['current'] - pred} život pre {short_name(cid)}."
    elif typ == "heal_pct":
        amt = max(1, math.ceil(hp["max"] * val))
        pred = hp["current"]
        hp["current"] = min(hp["max"], hp["current"] + amt)
        msg = f"❤️ +{hp['current'] - pred} život pre {short_name(cid)}."
    elif typ == "hod_bonus_zajtra":
        sel = ss.get("sel_date")
        base = sel if hasattr(sel, "isoformat") else datetime.date.today()
        tom = (base + datetime.timedelta(days=1)).isoformat()
        ss["temp_bonusy"].setdefault(tom, []).append(
            {"postava": cid, "atribut": "all", "hodnota": val, "zdroj": item["nazov"]})
        msg = f"🍪 {short_name(cid)}: +{val} ku všetkým hodom zajtra."
    elif typ == "hod_bonus_dnes":
        sel = ss.get("sel_date")
        dnes = sel.isoformat() if hasattr(sel, "isoformat") else datetime.date.today().isoformat()
        ss["temp_bonusy"].setdefault(dnes, []).append(
            {"postava": cid, "atribut": "all", "hodnota": val, "zdroj": item["nazov"]})
        msg = f"✨ {short_name(cid)}: +{val} ku všetkým hodom dnes."
    elif typ == "denny_atribut":               # lektvar „na deň" — bonus na konkrétne atribúty, len dnes
        sel = ss.get("sel_date")
        dnes = sel.isoformat() if hasattr(sel, "isoformat") else datetime.date.today().isoformat()
        for m in p.get("mody", []):
            ss["temp_bonusy"].setdefault(dnes, []).append(
                {"postava": cid, "atribut": m["atribut"], "hodnota": m["hodnota"], "zdroj": item["nazov"]})
        msg = f"🧪 {short_name(cid)} vypil {item['nazov']} — {p.get('popis', 'bonus na dnes')}."
    elif typ == "auto_uspech":
        sel = ss.get("sel_date")
        dnes = sel.isoformat() if hasattr(sel, "isoformat") else datetime.date.today().isoformat()
        ss["pending_ability"] = {"mechanika": "auto_uspech", "nazov": item["nazov"],
                                 "postava": cid, "ds": dnes, "hodnota": 0}
        msg = f"⭐ {item['nazov']} pripravená — v ďalšom rozhodnutí potvrď automatický úspech."
    elif typ == "priazen_hviezd":
        sel = ss.get("sel_date")
        dnes = sel.isoformat() if hasattr(sel, "isoformat") else datetime.date.today().isoformat()
        ss["pending_ability"] = {"mechanika": "priazen_hviezd", "nazov": item["nazov"],
                                 "postava": tgt, "ds": dnes, "hodnota": 0}
        msg = (f"🌌 {item['nazov']} pripravený — ak ďalší hod {short_name(tgt)} padne 15+, "
               f"ráta sa ako kritický úspech (20).")
    elif typ == "vyhoda_hodu":
        sel = ss.get("sel_date")
        dnes = sel.isoformat() if hasattr(sel, "isoformat") else datetime.date.today().isoformat()
        ss["pending_ability"] = {"mechanika": "vyhoda_hodu", "nazov": item["nazov"],
                                 "postava": cid, "ds": dnes, "hodnota": 0}
        msg = f"🏹 {item['nazov']} pripravený — ďalší hod {short_name(cid)} je s výhodou (2 kocky, vyššia)."
    else:
        msg = "Predmet použitý."
    left = (item.get("pocet_pouziti") or 1) - 1
    item["pocet_pouziti"] = left
    return msg, left <= 0


def apply_regen_bonuses(cid):
    """Pasívne predmety s efektom 'regen_bonus' pridajú životy pri nocľahu a minú použitie.
    Vráti počet životov navyše z týchto predmetov."""
    ss = st.session_state
    hp = ss["hp"][cid]
    extra = 0
    for it in list(ss["inventory"].get(cid, [])):
        if not isinstance(it, dict):
            continue
        p = it.get("pouzitie") or {}
        if p.get("typ") != "regen_bonus" or (it.get("pocet_pouziti") or 0) <= 0:
            continue
        got = min(hp["max"], hp["current"] + p.get("hodnota", 1)) - hp["current"]
        hp["current"] += got
        extra += got
        it["pocet_pouziti"] = (it.get("pocet_pouziti") or 1) - 1
    # minuté predmety odstráň
    ss["inventory"][cid] = [it for it in ss["inventory"].get(cid, [])
                            if not (isinstance(it, dict) and (it.get("pouzitie") or {}).get("typ") == "regen_bonus"
                                    and (it.get("pocet_pouziti") or 0) <= 0)]
    return extra


def render_char_card(cid, entry, accent):
    ss = st.session_state
    p = PARTY_ALL[cid]
    s = ss["stats"][cid]
    hp = ss["hp"][cid]
    total = sum(s.values())

    with st.expander(f"{p['icon']} {p['meno']} — {p['zbran']}"):
        st.caption(p["rola"])

        for key in STAT_KEYS:
            lbl = STAT_LABELS[STAT_KEYS.index(key)]
            name = STAT_NAMES[STAT_KEYS.index(key)]
            val = s[key]
            cols = st.columns([3.4, 3.4, 1])
            cols[0].markdown(f"<span class='su-stat'>{lbl} {name}</span>", unsafe_allow_html=True)
            cols[1].markdown(stat_bar_html(val, accent), unsafe_allow_html=True)
            cols[2].markdown(f"<span class='su-stat'><b>{val}</b></span>", unsafe_allow_html=True)
        st.caption(f"Σ celkovo: **{total}**")

        mp = ss["milestone_points"][cid]
        if mp > 0:
            st.markdown(f"🎖️ **Body na rozdelenie: {mp}**")
            bcols = st.columns(4)
            for i, key in enumerate(STAT_KEYS):
                if bcols[i % 4].button(f"+{STAT_LABELS[STAT_KEYS.index(key)]}",
                                       key=f"mp_{cid}_{key}", help=f"+1 {STAT_NAMES[i]}"):
                    ss["stats"][cid][key] += 1
                    ss["milestone_points"][cid] -= 1
                    st.rerun()

        st.markdown("---")
        gm = ss.get("gm_mode", False)
        st.markdown(hp_bar_html(hp["current"], hp["max"]), unsafe_allow_html=True)
        if hp["current"] <= 0:
            st.markdown(f"☠️ **ELIMINOVANÁ postava** — 0 / {hp['max']} životov")
            if gm and st.button("✨ Oživiť — plné životy", key=f"revive_{cid}"):
                hp["current"] = hp["max"]; st.rerun()
        else:
            st.markdown(f"❤️ **Životy: {hp['current']} / {hp['max']}**")
        # Ručná úprava životov je len pre GM (⚙️ GM mód)
        if gm:
            h = st.columns(4)
            if h[0].button("−5", key=f"hp_m5_{cid}"):
                hp["current"] = max(0, hp["current"] - 5); st.rerun()
            if h[1].button("−1", key=f"hp_m1_{cid}"):
                hp["current"] = max(0, hp["current"] - 1); st.rerun()
            if h[2].button("+1", key=f"hp_p1_{cid}"):
                hp["current"] = min(hp["max"], hp["current"] + 1); st.rerun()
            if h[3].button("+5", key=f"hp_p5_{cid}"):
                hp["current"] = min(hp["max"], hp["current"] + 5); st.rerun()

        if cid == "vedma":
            _sel = ss.get("sel_date")
            ds_today = _sel.isoformat() if hasattr(_sel, "isoformat") else datetime.date.today().isoformat()
            orbkey = f"orb_used_{ds_today}"
            used = ss.get(orbkey, False)
            if st.button("🔮 Veštecká guľa — prorocká vízia (+3 k hodom dnes, −20 % max životov)",
                         key=f"orb_{cid}", disabled=used):
                strata = math.ceil(hp["max"] * 0.20)
                hp["max"] = max(1, hp["max"] - strata)
                hp["current"] = min(hp["current"], hp["max"])
                ss["temp_bonusy"].setdefault(ds_today, []).append(
                    {"postava": "vedma", "atribut": "all", "hodnota": 3, "zdroj": "Veštecká guľa"})
                ss[orbkey] = True
                st.toast(f"Veštecká guľa: +3 k hodom dnes, −{strata} max životov", icon="🔮")
                st.rerun()
            if used:
                st.caption("🔮 Veštecká guľa dnes už použitá (+3 k hodom aktívne).")

        st.markdown("---")
        gold_input("💰 Osobné zlato", cid)

        st.markdown("---")
        st.markdown("**🎒 Štartovacia výbava** *(pevná)*")
        for it in STARTING_EQUIPMENT.get(cid, []):
            st.markdown(
                f"- {it['nazov']}  \n  <span style='font-size:0.78rem;color:#9aa'>➕ {it['vyhoda']} · ➖ {it['nevyhoda']}</span>",
                unsafe_allow_html=True)

        inv = ss["inventory"][cid]
        st.markdown(f"**📦 Inventár ({len(inv)}/{INV_LIMIT})** *(nad rámec štartovacej výbavy)*")
        for i, item in enumerate(list(inv)):
            name = item["nazov"] if isinstance(item, dict) else str(item)
            ms = mods_summary(item) if isinstance(item, dict) else ""
            pouzitie = item.get("pouzitie") if isinstance(item, dict) else None
            pocet = item.get("pocet_pouziti") if isinstance(item, dict) else None
            ic = st.columns([5, 1], vertical_alignment="center")
            pasivny = bool(pouzitie) and pouzitie.get("typ") == "regen_bonus"
            riadky = [f"<b>{name}</b>"]
            if ms:
                riadky.append(f"<span style='font-size:0.74rem;color:#9aa'>{ms}</span>")
            if pouzitie:
                znak = "🍖 pasívne (pri nocľahu)" if pasivny else "✨"
                riadky.append(f"<span style='font-size:0.74rem;color:#7fb069'>{znak} "
                              f"{pouzitie.get('popis','')} · použití: {pocet}</span>")
            ic[0].markdown("<div class='su-inv'>" + "<br>".join(riadky) + "</div>",
                           unsafe_allow_html=True)
            if ic[1].button("✖", key=f"rm_{cid}_{i}", help="Vyhodiť predmet"):
                inv.pop(i); st.rerun()
            # Štít Prvého strážcu (plna_ochrana) sa NEpoužíva tlačidlom — je to reaktívna záchrana,
            # ktorá sa ponúkne priamo v rozhodnutí pri strate života. Tu len info.
            if pouzitie and pouzitie.get("typ") == "plna_ochrana" and (pocet or 0) > 0:
                st.caption("🛡️ Aktivuje sa ako záchrana priamo v rozhodnutí, keď niekto stráca život "
                           f"(zostáva {pocet}×).")
            # ostatné aktívne spotrebné majú tlačidlo Použiť; pasívne (regen_bonus) sa aplikujú pri nocľahu
            elif pouzitie and not pasivny and (pocet or 0) > 0:
                cielene = pouzitie.get("typ") == "priazen_hviezd"
                tgt = cid
                if cielene:
                    ciele = active_ids(entry)
                    tgt = st.selectbox("Na koho použiť?", ciele,
                                       index=ciele.index(cid) if cid in ciele else 0,
                                       format_func=lambda c: f"{PARTY_ALL[c]['icon']} {short_name(c)}",
                                       key=f"usetgt_{cid}_{i}")
                if st.button(f"✅ Použiť — {pouzitie.get('popis','')}", key=f"use_{cid}_{i}"):
                    msg, minulo = use_consumable(cid, item, target=tgt)
                    if minulo and not item.get("trvaly"):
                        inv.pop(i)
                    st.toast(msg, icon="✨")
                    st.rerun()

        # Presun predmetu k inej (vhodnej) postave — uvoľní miesto
        if inv:
            mc = st.columns([4, 4, 2], vertical_alignment="center")
            j = mc[0].selectbox("Presunúť", list(range(len(inv))),
                                format_func=lambda k: (inv[k]["nazov"] if isinstance(inv[k], dict)
                                                       else str(inv[k]))[:16],
                                key=f"mvitem_{cid}", label_visibility="collapsed")
            sel_item = inv[j]
            targets = [c for c in active_ids(entry)
                       if c != cid and item_allowed_for(sel_item, c)
                       and len(ss["inventory"][c]) < INV_LIMIT]
            if targets:
                to = mc[1].selectbox("komu", targets,
                                     format_func=lambda c: f"{PARTY_ALL[c]['icon']} {short_name(c)}",
                                     key=f"mvto_{cid}", label_visibility="collapsed")
                if mc[2].button("↪", key=f"mvbtn_{cid}", help="Presunúť k vybranej postave"):
                    ss["inventory"][to].append(inv.pop(j))
                    st.toast("Predmet presunutý", icon="↪️")
                    st.rerun()
            else:
                mc[1].caption("niet vhodného cieľa")

        if len(inv) < INV_LIMIT:
            day_raw = entry.get("items_day", [])
            day_names = [it["nazov"] for it in day_raw]
            options = ["— vyber —"] + day_names + ["✏️ vlastný…"]
            sel = st.selectbox("Pridať predmet", options, key=f"addsel_{cid}")
            custom = ""
            if sel == "✏️ vlastný…":
                custom = st.text_input("Názov predmetu", key=f"addtxt_{cid}")
            if st.button("➕ Pridať do inventára", key=f"addbtn_{cid}"):
                if sel == "✏️ vlastný…" and custom.strip():
                    inv.append(normalize_item({"nazov": custom.strip()})); st.rerun()
                elif sel not in ("— vyber —", "✏️ vlastný…"):
                    raw = next((it for it in day_raw if it["nazov"] == sel), None)
                    if raw:
                        inv.append(normalize_item(raw)); st.rerun()
        else:
            st.caption("Inventár je plný (max 5) — vyhoď alebo presuň predmet.")


# =========================================================================
#  SIDEBAR — KLAN, MÍĽNIKY, NOVÁ NOC, GM
# =========================================================================
@st.cache_data(show_spinner=False)
def _build_id():
    """Krátky git commit hash aktuálneho nasadenia (na rozlíšenie deploy vs. cache)."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL, timeout=3).decode().strip() or "local"
    except Exception:
        return "local"


def render_sidebar(entry, accent):
    ss = st.session_state
    is_velka = entry["group"] == "velka"

    with st.sidebar:
        st.title("🗡️ Svetlo Úsvitu")
        st.caption("Prázdninová kampaň · 1.7. – 31.8.2026")

        with st.expander("💾 Uloženie / načítanie hry", expanded=False):
            if _LS_OK:
                st.caption("✅ Postup sa automaticky ukladá v tomto prehliadači "
                           "(prežije obnovenie stránky aj uspanie appky). Na prenos medzi "
                           "zariadeniami použi súbor nižšie.")
            else:
                st.caption("⚠️ Postup sa po zatvorení/uspaní appky stratí — priebežne si ho "
                           "ukladaj do súboru nižšie.")
            st.download_button(
                "💾 Uložiť do súboru (záloha / prenos)", data=serialize_state(),
                file_name=f"svetlo-usvitu_{datetime.date.today().isoformat()}.json",
                mime="application/json", use_container_width=True)
            up = st.file_uploader("📂 Načítať zo súboru", type=["json"], key="load_file")
            if up is not None and ss.get("_loaded_id") != up.file_id:
                try:
                    load_state(up.getvalue().decode("utf-8"))
                    ss["_loaded_id"] = up.file_id
                    ss["_ls_last"] = None   # premietne sa aj do auto-uloženia
                    st.success("✅ Hra načítaná — postup obnovený.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Súbor sa nepodarilo načítať: {e}")
            if st.button("🗑️ Nová hra (vymazať postup)", use_container_width=True):
                for k in (SAVE_CORE
                          + [k for k in list(ss) if isinstance(k, str) and k.startswith(PROGRESS_PREFIXES)]
                          + [k for k in list(ss) if isinstance(k, str) and k.startswith("goldw_")]):
                    ss.pop(k, None)
                ss["_ls_last"] = None
                ss.pop("_loaded_id", None)
                st.rerun()

        st.markdown(f"### 🌳 {CLANS['mala']['nazov']}")
        for p in PARTY_MALA:
            render_char_card(p["id"], entry, accent)

        if is_velka:
            st.markdown(f"### ☀️ {CLANS['velka']['nazov']}")
            st.caption("Aktívny počas Talianska (18.–25.7.)")
            for p in PARTY_VELKA_DOPLNOK:
                render_char_card(p["id"], entry, accent)

        st.markdown("---")
        st.markdown("### 🏦 Klanová pokladnica")
        gold_input(f"🌳 {CLANS['mala']['nazov']}", "klan")
        if is_velka:
            gold_input(f"☀️ {CLANS['velka']['nazov']}", "klan_slnko")
            st.caption("Počas Talianska majú obe klanové pokladnice spoločný cieľ.")

        st.markdown("---")
        with st.expander("🎖️ Pridať míľnikové body"):
            st.caption("Ťažší nepriateľ 1 · Mini-boss 2 · Hlavný boss 5 · Kapitola 3")
            cnt = st.number_input("Počet bodov pre každú aktívnu postavu", min_value=1, value=1, step=1,
                                  key="mp_count")
            if st.button("Udeliť body celej družine", key="mp_give"):
                for cid in active_ids(entry):
                    ss["milestone_points"][cid] += int(cnt)
                st.toast(f"+{int(cnt)} bodov pre každú postavu", icon="🎖️")
                st.rerun()

        st.caption("🌙 Regenerácia životov je teraz na **konci dňa** ako výber nocľahu "
                   "(krčma / lekár / tábor / divočina…), nie tu v GM paneli.")

        st.markdown("---")
        with st.expander("📅 Kapitoly kampane"):
            for ch in CHAPTERS:
                iko = "🌳+☀️" if ch["skupina"] == "velka" else "🌳"
                st.markdown(
                    f"<div class='su-chapter' style='border-color:{ch['farba']}'>"
                    f"<b>{ch['nazov']}</b><br><span style='font-size:0.8rem'>{ch['od']} – {ch['do']} {iko}</span></div>",
                    unsafe_allow_html=True)

        with st.expander("✨ Legendárne predmety"):
            for li in LEGENDARY_ITEMS:
                kedy = f"Deň {li['den']}" if li["den"] else "Priebeh kampane"
                st.markdown(f"**{li['nazov']}** — {li['nositel']} ({kedy})  \n"
                            f"<span style='font-size:0.8rem;color:#9aa'>➕ {li['vyhody']} · ➖ {li['nevyhody']}</span>",
                            unsafe_allow_html=True)

        with st.expander("📖 O svete Eldorea"):
            st.write(WORLD_INTRO)

        # ⚙️ diskrétny GM prepínač — úplne dole, bez popisu
        st.markdown("<div style='height:1.5em'></div>", unsafe_allow_html=True)
        st.toggle("⚙️", value=ss.get("gm_mode", False), key="gm_mode",
                  help="GM režim (farby dní, skryté poznámky)")

        # build štítok — mení sa pri každom nasadení (deploy vs. cache)
        st.markdown(
            f"<div style='text-align:center;color:#667;font-size:0.68rem;margin-top:0.6em'>"
            f"build {_build_id()}</div>", unsafe_allow_html=True)


# =========================================================================
#  HLAVNÁ PLOCHA
# =========================================================================
def render_milnik(entry):
    m = entry.get("milnik")
    if not m:
        return
    body = m.get("body", MILESTONE_POINTS.get(m["typ"], 1))
    st.markdown(
        f"<div class='su-chapter'>🎖️ <b>Míľnik dňa:</b> {MILESTONE_LABELS.get(m['typ'], m['typ'])} "
        f"— {m['popis']} (<b>{body}</b> bodov)</div>", unsafe_allow_html=True)
    if st.button(f"🎖️ Udeliť {body} bodov celej družine za míľnik"):
        for cid in active_ids(entry):
            st.session_state["milestone_points"][cid] += body
        st.toast(f"+{body} bodov za míľnik!", icon="🎖️")
        st.rerun()


def render_zlato_odmena(ds, entry):
    z = entry.get("zlato_odmena")
    if not z:
        return
    ss = st.session_state
    osobne = int(z.get("osobne", 0))
    klanove = int(z.get("klanove", 0))
    dovod = z.get("dovod", "")
    dvojnasobok = bool(ss.get(f"dvojita_odmena_{ds}"))
    if dvojnasobok:
        osobne *= 2
        klanove *= 2
    donekey = f"zlato_done_{ds}"
    st.markdown(
        f"<div class='su-chapter'>💰 <b>Odmena dňa:</b> +{osobne} osobné každej postave · "
        f"+{klanove} do klanu{' · 💰 <b>×2 (Zlatý nos)</b>' if dvojnasobok else ''}"
        f"{(' — <i>' + dovod + '</i>') if dovod else ''}</div>",
        unsafe_allow_html=True)
    if ss.get(donekey):
        st.caption("✅ Odmena dňa už bola pripísaná.")
        return
    if st.button(f"💰 Pripísať odmenu dňa (+{osobne} každému, +{klanove} klan)"):
        for cid in active_ids(entry):
            ss["gold"][cid] = ss["gold"].get(cid, 0) + osobne
        ss["gold"]["klan"] = ss["gold"].get("klan", 0) + klanove
        ss[donekey] = True
        st.toast(f"Odmena pripísaná: +{osobne} každému, +{klanove} klan", icon="💰")
        st.rerun()


# =========================================================================
#  ŠPECIÁLNE SCHOPNOSTI — panel + vykonanie
# =========================================================================
def use_ability(cid, ab, ds, entry, extra, free=False):
    ss = st.session_state
    mech = ab["mechanika"]
    ids = active_ids(entry)
    msg = f"{ab['nazov']} použitá."

    if mech == "minimum_hodu":
        ss[f"stastna_kocka_{ds}"] = True
        msg = "🎲 Šťastná kocka — dnes žiaden hod neklesne pod 10."
    elif mech == "dvojita_odmena":
        ss[f"dvojita_odmena_{ds}"] = True
        msg = "💰 Zlatý nos — odmena dňa sa zdvojnásobí."
    elif mech == "obnov_zivoty_100":
        t = extra.get("target", cid)
        ss["hp"][t]["current"] = ss["hp"][t]["max"]
        msg = f"💚 {short_name(t)} obnovený/á na plné životy."
    elif mech == "obnov_zivoty_100_vsetci":
        for x in ids:
            ss["hp"][x]["current"] = ss["hp"][x]["max"]
        msg = "💚 Celá družina na plných životoch."
    elif mech == "obnov_zivoty_50_dvaja":
        for t in extra.get("targets", []):
            hp = ss["hp"][t]
            hp["current"] = min(hp["max"], hp["current"] + math.ceil(hp["max"] * 0.5))
        msg = "💚 Dve postavy +50 % životov."
    elif mech == "bonus_atribut_vsetci":
        at = extra.get("atribut", "sila")
        ss["temp_bonusy"].setdefault(ds, []).append(
            {"postava": "all", "atribut": at, "hodnota": ab.get("hodnota", 3), "zdroj": ab["nazov"]})
        msg = f"➕ +{ab.get('hodnota', 3)} {atr_name(at)} pre všetkých dnes."
    elif mech == "prebrat_zasah_skupina":
        absorb = 0
        for x in ids:
            if x == cid:
                continue
            hp = ss["hp"][x]
            absorb += hp["max"] - hp["current"]
            hp["current"] = hp["max"]
        oh = ss["hp"][cid]
        oh["current"] = max(0, oh["current"] - absorb)
        msg = f"🛡️ Obor prevzal {absorb} {zivoty_slovo(absorb)} za skupinu."
    elif mech == "skryta_moznost_d":
        ss[f"skryta_den_{ds}"] = {"postava": cid, "nazov": ab["nazov"]}
        msg = f"🎁 {ab['nazov']} — skrytá cesta odomknutá na CELÝ deň, v každom rozhodnutí."
    elif mech in NEXT_DECISION_MECHS or mech in REROLL_MECHS:
        ss["pending_ability"] = {"postava": cid, "id": ab["id"], "mechanika": mech,
                                 "hodnota": ab.get("hodnota", 0), "nazov": ab["nazov"], "ds": ds}
        msg = f"{ab['ikona']} {ab['nazov']} pripravená — prejaví sa pri rozhodnutí."

    # ── ceny (na boss dňoch je Svetlo Úsvitu zadarmo → free) ──
    cena = None if free else ab.get("cena")
    if cena == "minus3_hody_dalsi_den":
        tom = (datetime.date.fromisoformat(ds) + datetime.timedelta(days=1)).isoformat()
        ss["active_effects"].setdefault(tom, []).append(
            {"postava": cid, "efekt": "minus_hody", "hodnota": -3, "popis": f"{ab['nazov']} (cena)"})
    elif cena == "bojovnik_1_zivot":
        ss["hp"]["bojovnik"]["current"] = 1
        ss[f"bojovnik_hranica_{ds}"] = True
    elif cena == "liecitelka_10_percent":
        hp = ss["hp"]["liecitelka"]
        hp["current"] = max(1, round(hp["max"] * 0.1))
    return msg


def render_ability_targets(cid, ab, entry):
    """Vykreslí výber cieľa (ak ho schopnosť potrebuje) a vráti extra parametre."""
    ids = active_ids(entry)
    mech = ab["mechanika"]
    extra = {}
    fmt = lambda c: f"{PARTY_ALL[c]['icon']} {short_name(c)}"
    if mech == "obnov_zivoty_100":
        extra["target"] = st.selectbox("Komu", ids, format_func=fmt, key=f"abt_{cid}_{ab['id']}")
    elif mech == "obnov_zivoty_50_dvaja":
        c = st.columns(2)
        t1 = c[0].selectbox("1. postava", ids, format_func=fmt, key=f"abt1_{cid}_{ab['id']}")
        rest = [x for x in ids if x != t1]
        t2 = c[1].selectbox("2. postava", rest, format_func=fmt, key=f"abt2_{cid}_{ab['id']}")
        extra["targets"] = [t1, t2]
    elif mech == "bonus_atribut_vsetci":
        extra["atribut"] = st.selectbox("Atribút", STAT_KEYS,
                                        format_func=lambda k: STAT_NAMES[STAT_KEYS.index(k)],
                                        key=f"aba_{cid}_{ab['id']}")
    return extra


def day_has_hidden_path_for(entry, cid):
    """Má daný deň ručne písanú skrytú cestu (option_d) pre túto postavu?"""
    return any((entry.get(f"decision{i}") or {}).get("option_d", {}).get("postava") == cid
               for i in (1, 2, 3))


def render_special_abilities_panel(ds, entry):
    ss = st.session_state
    # čakajúca schopnosť z iného dňa sa zruší (aby „neostala všade")
    pend = ss.get("pending_ability")
    if pend and pend.get("ds") not in (None, ds):
        ss.pop("pending_ability", None)
        pend = None
    if pend:
        kde = ("použije sa na práve hodené rozhodnutie"
               if pend["mechanika"] in REROLL_MECHS else "prejaví sa pri nasledujúcom rozhodnutí")
        c1, c2 = st.columns([4, 1])
        c1.info(f"⚡ Pripravená schopnosť: **{pend['nazov']}** — {kde}.")
        if c2.button("✖ Zrušiť", key=f"cancel_pending_{ds}"):
            ss.pop("pending_ability", None)
            st.rerun()
    if ss.get(f"bojovnik_hranica_{ds}"):
        st.warning("🛡️ Bojovník je na hranici (1 život) — ďalší zásah ho dnes vyradí z boja.")
    with st.expander("⚡ Špeciálne schopnosti", expanded=False):
        st.caption("Silné schopnosti — každá len párkrát za celú kampaň. 🟢 dostupné · ⚪ vyčerpané.")
        if ss.get("gm_mode"):
            if st.button("🔄 Dobiť všetky schopnosti (GM test)", key=f"recharge_ab_{ds}"):
                ss["abilities"] = {pid: {a["id"]: a["max_pouziti"] for a in lst}
                                   for pid, lst in SPECIAL_ABILITIES.items()}
                ss.pop("pending_ability", None)
                for k in (f"stastna_kocka_{ds}", f"dvojita_odmena_{ds}", f"bojovnik_hranica_{ds}"):
                    ss.pop(k, None)
                st.toast("Schopnosti dobité na plné použitia.", icon="🔄")
                st.rerun()
        for cid in active_ids(entry):
            lst = SPECIAL_ABILITIES.get(cid, [])
            if not lst:
                continue
            is_boss = day_tier(entry) == "hlavny_boss"
            st.markdown(f"**{PARTY_ALL[cid]['icon']} {PARTY_ALL[cid]['meno']}**")
            for ab in lst:
                rem = ss["abilities"].setdefault(cid, {}).get(ab["id"], ab["max_pouziti"])
                unlimited = bool(ab.get("boss_unlimited") and is_boss)
                is_skryta = ab["mechanika"] == "skryta_moznost_d"
                eligible_day = (not is_skryta) or day_has_hidden_path_for(entry, cid)
                active_today = is_skryta and ss.get(f"skryta_den_{ds}", {}).get("postava") == cid
                dots = "♾️ <span style='color:#d4a017'>(boss — bez limitu)</span>" if unlimited \
                    else "🟢" * rem + "⚪" * (ab["max_pouziti"] - rem)
                st.markdown(f"{ab['ikona']} **{ab['nazov']}** {dots}  \n"
                            f"<span style='font-size:0.83rem;color:#9aa'>{ab['popis']}</span>",
                            unsafe_allow_html=True)
                if ab.get("tip"):
                    st.markdown(f"<span style='font-size:0.78rem;color:#5b8c5a'>🗓️ {ab['tip']}</span>",
                                unsafe_allow_html=True)
                if ab.get("cena_popis") and not unlimited:
                    st.markdown(f"<span style='color:#f85149;font-size:0.8rem'>⚠️ Cena: {ab['cena_popis']}</span>",
                                unsafe_allow_html=True)
                if is_skryta and not eligible_day:
                    st.markdown("<span style='color:#f85149;font-size:0.78rem'>🔒 Dnes nedostupné — "
                                "skrytá cesta funguje len vo vybraných dňoch (viď 🗓️).</span>",
                                unsafe_allow_html=True)
                if active_today:
                    st.markdown("<span style='color:#3fb950;font-size:0.78rem'>✅ Aktívna dnes — "
                                "skrytá možnosť D je v každom rozhodnutí.</span>", unsafe_allow_html=True)
                enabled = (unlimited or rem > 0) and eligible_day and not active_today
                extra = render_ability_targets(cid, ab, entry) if enabled else {}
                if st.button("Použiť", key=f"useab_{ds}_{cid}_{ab['id']}", disabled=not enabled):
                    msg = use_ability(cid, ab, ds, entry, extra, free=unlimited)
                    if not unlimited:
                        ss["abilities"][cid][ab["id"]] = rem - 1
                    st.toast(msg, icon="⚡")
                    st.rerun()
            st.markdown("<hr style='margin:3px 0;opacity:0.2'>", unsafe_allow_html=True)


def render_gm_calendar(entry):
    """Typy dní a počty rozhodnutí v tejto + nasledujúcej kapitole — len v GM móde."""
    cur_ch = entry["chapter"]
    rows = []
    for ch_id in (cur_ch, cur_ch + 1):
        ch = chapter_by_id(ch_id)
        if not ch:
            continue
        days = [(ds, e) for ds, e in sorted(CAMPAIGN.items())
                if e["chapter"] == ch_id and e["day"] >= 1]
        if not days:
            continue
        # hlavička kapitoly s jej farbou
        rows.append(
            f"<div style='background:linear-gradient(90deg,{ch['farba']}44,transparent);"
            f"border-left:6px solid {ch['farba']};padding:6px 10px;margin:10px 0 4px;"
            f"border-radius:6px;font-weight:bold'>{ch['nazov']}</div>")
        for ds, e in days:
            tier = day_tier(e)
            decs = build_decisions(ds, e)
            bezne = sum(1 for d in decs if d["typ"] not in ("predmet", "nakup", "detske", "timova"))
            tim = sum(1 for d in decs if d["typ"] == "timova")
            target = target_bezne(e)
            mark = "✅" if bezne >= target else f"⚠️ {bezne}/{target}"
            d = datetime.date.fromisoformat(ds)
            col = KIND_COLOR.get(tier, "#888")
            # Taliansko (velka) — exkluzívne 2× rozhodnutí; typ dňa (pokojný/bežný…) ostáva
            tal = ("<span style='background:#d4a01733;color:#d4a017;border:1px solid #d4a01766;"
                   "border-radius:4px;padding:0 4px;font-size:0.72rem;margin-left:4px'>"
                   "🇮🇹 Taliansko ×2</span>") if e.get("group") == "velka" else ""
            # počet tímových scén (bossovia / mini-bossovia)
            tm = (f"<span style='background:#6a4c9333;color:#b39ddb;border:1px solid #6a4c9366;"
                  f"border-radius:4px;padding:0 4px;font-size:0.72rem;margin-left:4px'>"
                  f"🤝 {tim}× tímová</span>") if tim else ""
            rows.append(
                f"<div style='border-left:4px solid {col};background:{col}1f;padding:3px 9px;"
                f"margin:3px 0 3px 12px;border-radius:5px;font-size:0.86rem'>"
                f"{KIND_LABEL.get(tier, '')} · <b>D{e['day']}</b> {d.strftime('%d.%m.')} — "
                f"{e['title']} · {bezne}/{target} {mark}{tal}{tm}</div>")
    with st.expander("🔒 GM kalendár — typy dní a počty rozhodnutí (táto + nasledujúca kapitola)",
                     expanded=False):
        st.caption("Cieľ bežných rozhodnutí: 🌿 Pokojný 3 · 🗺️ Bežný 4–5 · ⚡ Rušný 6 · "
                   "🟡 Ťažší 7 · 🟠 Mini-boss 8 · 🔴 Boss 9 (+ detské). "
                   "🇮🇹 Taliansko (velka dni) má EXKLUZÍVNE 2× cieľ (typ dňa ostáva). Len pre GM.")
        st.markdown("".join(rows), unsafe_allow_html=True)


RESET_PREFIXES = ("res_", "res2_", "crit1_", "zloss_", "regen_", "predmet_done_", "nakup_done_",
                  "buy_", "buyer_", "buyerr_", "pay_", "shopdone_", "give_",
                  "leave_", "levelup20_", "sc_", "balloons_", "zlato_done_", "skryta_den_",
                  "d1_", "d2_", "d3_", "res1_", "res3_")


def reset_day(ds):
    ss = st.session_state
    for k in list(ss.keys()):
        if isinstance(k, str) and ds in k and k.startswith(RESET_PREFIXES):
            ss.pop(k, None)


def main():
    init_state()

    # Automatické obnovenie postupu z localStorage prehliadača (rovnaké zariadenie).
    # SU_DISABLE_LS vypne localStorage (pre headless testy — komponent vyžaduje prehliadač).
    localS = LocalStorage() if (_LS_OK and not os.environ.get("SU_DISABLE_LS")) else None
    if localS is not None and not st.session_state.get("_ls_restored"):
        st.session_state["_ls_tries"] = st.session_state.get("_ls_tries", 0) + 1
        try:
            saved = localS.getItem("su_save")
        except Exception:
            saved = None
        if saved and saved not in ("null", ""):
            try:
                load_state(saved)
            except Exception:
                pass
            st.session_state["_ls_restored"] = True
            st.session_state["_ls_last"] = None
            st.rerun()
        elif st.session_state["_ls_tries"] >= 4:
            st.session_state["_ls_restored"] = True   # nič uložené / nedostupné
        else:
            # daj komponentu v prehliadači šancu načítať localStorage a odpovedať
            time.sleep(0.18)
            st.rerun()

    today = datetime.date.today()
    default = today if MIN_DATE <= today <= MAX_DATE else MIN_DATE

    sel_default = st.session_state.get("sel_date", default)
    entry0 = CAMPAIGN.get(sel_default.isoformat())
    accent = CHAPTER_COLORS.get(entry0["chapter"], "#f4c430") if entry0 else "#f4c430"
    inject_css(accent, theme_bg(entry0))

    top = st.columns([2.4, 1.9, 0.9])
    with top[0]:
        vybrany = st.date_input("📅 Dátum hry", value=sel_default,
                                min_value=MIN_DATE, max_value=MAX_DATE,
                                format="DD.MM.YYYY", key="sel_date")
    ds = vybrany.isoformat()
    entry = CAMPAIGN.get(ds)

    with top[1]:
        _theme_lbl = {"auto": "✨ Automatické (podľa kapitoly)", "zakladne": "⬛ Základné"}
        _theme_lbl.update(CHAPTER_BG)
        st.selectbox("🎨 Pozadie", ["auto", "zakladne"] + list(CHAPTER_BG.keys()),
                     format_func=lambda v: _theme_lbl[v], key="theme_sel")

    with top[2]:
        st.write(""); st.write("")
        if st.button("🔄 Reset dňa"):
            reset_day(ds)
            st.rerun()

    if entry is None:
        st.warning("Pre tento dátum nie je pripravený scenár.")
        st.stop()

    accent = CHAPTER_COLORS.get(entry["chapter"], "#f4c430")
    chapter = chapter_by_id(entry["chapter"])
    is_velka = entry["group"] == "velka"
    gm = st.session_state.get("gm_mode", False)

    render_sidebar(entry, accent)

    # Progress + badge
    is_test = entry["day"] < 1
    if is_test:
        st.progress(0.0, text="🌱 Skúšobný deň (pred štartom kampane 1.7.)")
    else:
        st.progress(entry["day"] / 62, text=f"Deň {entry['day']} / 62")

    clan_badge = (f"🌳☀️ VEĽKÁ DRUŽINA (15) — {CLANS['mala']['nazov']} + {CLANS['velka']['nazov']}"
                  if is_velka else f"🌳 MALÁ DRUŽINA (7) — {CLANS['mala']['nazov']}")
    gmcol = gm_color_for_day(entry)
    gm_tag = f" · {GM_DOT[gmcol]} {GM_DOT_LABEL[gmcol]}" if (gm and gmcol) else ""
    st.markdown(
        f"<div class='su-chapter' style='border-color:{accent}'>"
        f"<b>{chapter['nazov']}</b> · {clan_badge}<br>"
        f"<span style='font-size:0.82rem;color:#9aa'>{day_type_label(entry)}{gm_tag}</span></div>",
        unsafe_allow_html=True)

    if is_test:
        st.info("🌱 **Skúšobný deň** — nezáväzný nácvik pred štartom kampane (1.7.). "
                "Vyskúšajte si hod kockou, levelovanie, predmety, obchod aj detskú úlohu. Nič sa nepokazí.")
    if is_velka:
        st.warning("💡 Dnes hrá veľká skupina (15 osôb) — zvážte rozdelenie na 2–3 menšie tímy.")
    if gm:
        render_gm_calendar(entry)

    # Nadpis + intro
    st.markdown(f"## {entry['title']}")
    render_special_abilities_panel(ds, entry)
    st.markdown("##### 📖 Prečítaj nahlas")
    st.markdown(f"<div class='su-quote'>{entry['intro']}</div>", unsafe_allow_html=True)

    # Rozhodnutia — sekvenčne (bežné → predmet → nákup → detské)
    decisions = build_decisions(ds, entry)
    all_done = True
    for i, dec in enumerate(decisions, start=1):
        st.markdown("---")
        done = render_decision(i, ds, dec, accent, entry, gm)
        if not done:
            all_done = False
            break

    st.markdown("---")
    render_zlato_odmena(ds, entry)
    render_milnik(entry)

    if all_done:
        st.markdown("---")
        render_regen_decision(ds, entry)
        st.markdown("---")
        zajtra = vybrany + datetime.timedelta(days=1)
        nxt = CAMPAIGN.get(zajtra.isoformat())
        nxt_t = f" — *{entry.get('next_hint') or (nxt['title'] if nxt else '')}*"
        st.markdown("#### 🌅 Záver dňa")
        st.markdown(f"<div class='su-quote'>{entry['outro']}{nxt_t}</div>", unsafe_allow_html=True)
        if not st.session_state.get(f"balloons_{ds}"):
            st.balloons()
            st.session_state[f"balloons_{ds}"] = True
        if nxt:
            st.caption(f"➡️ Zajtra: deň {nxt['day']} — {nxt['title']}")
        else:
            st.success("🎉 Koniec kampane! Svetlo Úsvitu sa vrátilo do sveta.")

    # Automatické uloženie postupu do localStorage (pri každej zmene stavu).
    # Pozor: streamlit-local-storage zapíše len pri ZMENE key komponentu, preto
    # používame rotujúci kľúč — inak by sa uložil len prvý stav za reláciu.
    if localS is not None and st.session_state.get("_ls_restored"):
        cur = serialize_state()
        if st.session_state.get("_ls_last") != cur:
            st.session_state["_ls_seq"] = st.session_state.get("_ls_seq", 0) + 1
            try:
                localS.setItem("su_save", cur, key=f"su_set_{st.session_state['_ls_seq']}")
            except Exception:
                pass
            st.session_state["_ls_last"] = cur

    st.markdown("---")
    st.caption("GM skript pre rodičov · Klan Železného Dubu & Klan Zlatého Slnka · Eldorea 2026")


if __name__ == "__main__":
    main()
