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
import datetime

import streamlit as st

import importlib as _il
import data as _data
_il.reload(_data)  # deploy-safe: vynúti čerstvý data modul (Streamlit cachuje moduly)

from data import (
    CAMPAIGN, CHAPTERS, CHAPTER_COLORS, chapter_by_id,
    PARTY_MALA, PARTY_VELKA_DOPLNOK, PARTY_ALL, CLANS, CLAN_OF,
    STATS, STAT_KEYS, STAT_LABELS, STAT_NAMES, stats_dict, start_vydrz,
    ABILITIES, SPECIAL_ABILITIES, STARTING_EQUIPMENT, LEGENDARY_ITEMS, WEAPONS_SHOP, EXPENSES,
    DC_SCALE, MILESTONE_POINTS, MILESTONE_LABELS, REGEN_RULES, ZISK_OSOBNE_PODIEL,
    WORLD_INTRO, GROUP_SCHEDULE,
    build_decisions, shop_for_day, gm_color_for_day, day_type_label,
    day_tier, TARGET_BEZNE, KIND_LABEL, target_bezne,
    normalize_item, item_allowed_for,
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
def inject_css(accent):
    st.markdown(f"""
    <style>
      .stApp {{ background: #0e1117; }}
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
SAVE_CORE = ["stats", "hp", "gold", "inventory", "milestone_points",
             "abilities", "active_effects", "temp_bonusy", "pending_ability"]
PROGRESS_PREFIXES = ("res_", "res2_", "crit1_", "predmet_done_", "nakup_done_",
                     "levelup20_", "balloons_", "zlato_done_",
                     "stastna_kocka_", "dvojita_odmena_", "bojovnik_hranica_", "skip_")


def serialize_state():
    ss = st.session_state
    core = {k: ss.get(k) for k in SAVE_CORE}
    progress = {k: ss[k] for k in ss
                if isinstance(k, str) and k.startswith(PROGRESS_PREFIXES)}
    payload = {
        "app": "svetlo-usvitu", "version": 1,
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
    if total >= dc:
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
    return render_skill_decision(n, ds, dec, accent, entry, positive=(t == "detske"))


def highest_attr(cid):
    s = st.session_state["stats"].get(cid, {})
    if not s:
        return 0, "sila"
    k = max(s, key=lambda x: s[x])
    return s[k], k


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
        # ── čakajúca špeciálna schopnosť, ktorá sa prejaví na tomto rozhodnutí ──
        dc_delta = 0
        if pend and not positive and pend["mechanika"] in NEXT_DECISION_MECHS:
            mech = pend["mechanika"]
            if mech == "zniz_dc":
                dc_delta = -int(pend.get("hodnota", 0))
                st.info(f"🎯 **{pend['nazov']}** aktívna — DC −{abs(dc_delta)} pre toto rozhodnutie.")
            elif mech == "skryta_moznost_d":
                if dec.get("option_d"):
                    st.success(f"🎁 **{pend['nazov']}** — odomknutá skrytá možnosť D!")
                else:
                    st.info(f"🎁 **{pend['nazov']}**: v tejto scéne nie je skrytá cesta.")
                    ss.pop("pending_ability", None)
                    pend = None
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

        # ── normálne možnosti (s prípadným znížením DC) ──
        opts = list(dec["options"])
        if dec.get("option_d") and pend and pend.get("mechanika") == "skryta_moznost_d":
            opts = opts + [dec["option_d"]]
        for idx, opt in enumerate(opts):
            opt_disp = dict(opt)
            if dc_delta:
                opt_disp["dc"] = max(1, opt["dc"] + dc_delta)
            render_option_panel(opt_disp, accent, is_combat, ds)
            if st.button(f"🎲 {opt['postava_ikona']} {opt['postava_nazov']} — hodiť kockou",
                         key=f"btn_{ds}_{dec['id']}_{idx}"):
                ph = st.empty()
                roll = animated_roll(ph, accent)
                res = evaluate(opt_disp, roll, opt["postava_id"], is_combat, ds)
                res["idx"] = idx
                if idx >= len(dec["options"]):       # použila sa skrytá možnosť D
                    res["option_d"] = True
                ss[reskey] = res
                if dc_delta or (pend and pend.get("mechanika") == "skryta_moznost_d"):
                    ss.pop("pending_ability", None)  # spotrebuj
                st.rerun()
        return False

    # ── už rozhodnuté ──
    res = ss[reskey]
    opts_all = list(dec["options"])
    if dec.get("option_d"):
        opts_all = opts_all + [dec["option_d"]]
    opt = opts_all[res["idx"]] if res["idx"] < len(opts_all) else dec["options"][0]
    st.markdown(f"➡️ **{opt['label']}** · {opt['postava_ikona']} {opt['postava_nazov']}")
    if res.get("auto"):
        st.success(f"✅ Automatický úspech — {res.get('auto_note', 'špeciálna schopnosť')} "
                   f"({'preskočené' if res.get('skipped') else 'bez hodu'}).")
    render_calc(res)
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

    # Hod 1 — kritický neúspech: −10 % Výdrže navyše (raz). Šťastná kocka / Prorocká vízia to rušia.
    if real and res["roll"] == 1 and res.get("roll_eff", 1) == 1 and not positive:
        critkey = f"crit1_{ds}_{dec['id']}"
        if not ss.get(critkey):
            hp = ss["hp"][opt["postava_id"]]
            strata = max(1, math.ceil(hp["max"] * 0.10))
            hp["current"] = max(0, hp["current"] - strata)
            ss[critkey] = True
            st.caption(f"💀 Kritický neúspech: {opt['postava_nazov']} −{strata} Výdrže.")

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

    # Veľký neúspech → druhá šanca (nie pri detskom / auto)
    if real and res["outcome"] == "fail" and not positive:
        render_second_chance(n, ds, dec, accent, entry)

    if st.button(f"↩️ Znova rozhodnutie {n}", key=f"reset_{ds}_{dec['id']}"):
        for k in (reskey, f"res2_{ds}_{dec['id']}", f"crit1_{ds}_{dec['id']}"):
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
        outcome = "success" if total >= dc else ("near" if total >= dc - 3 else "fail")
        ss[reskey] = {"idx": 0, "spoj": True, "spoj_rolls": rolls, "total": total, "dc": dc,
                      "diff": total - dc, "outcome": outcome, "postava": team[0],
                      "atribut": opt["atribut_key"], "roll": 0, "roll_eff": 0}
        ss.pop("pending_ability", None)
        st.rerun()
    st.caption("…alebo zruš schopnosť a hraj normálne (Reset dňa).")
    return False


def render_second_chance(n, ds, dec, accent, entry):
    ss = st.session_state
    res2key = f"res2_{ds}_{dec['id']}"
    base_dc = dec["options"][ss[f"res_{ds}_{dec['id']}"]["idx"]]["dc"]
    new_dc = base_dc + 5

    st.markdown("---")
    st.info(f"🎯 **Druhá šanca** — iná postava, iný atribút, DC +5 (**DC {new_dc}**).")

    if res2key in ss:
        r = ss[res2key]
        c = PARTY_ALL[r["postava"]]
        st.markdown(f"➡️ Druhý pokus: {c['icon']} {c['meno']} ({atr_name(r['atribut'])})")
        render_calc(r)
        st.markdown(f"**{outcome_label(r)}**")
        if r["total"] >= r["dc"]:
            st.success("Druhá šanca zabrala — príbeh pokračuje s úspechom.")
        else:
            st.error("Ani druhá šanca nevyšla — GM dotvorí následok.")
        return

    ids = active_ids(entry)
    col1, col2 = st.columns(2)
    with col1:
        pid = st.selectbox("Postava", ids,
                           format_func=lambda i: f"{PARTY_ALL[i]['icon']} {PARTY_ALL[i]['meno']}",
                           key=f"sc_p_{ds}_{dec['id']}")
    with col2:
        atr = st.selectbox("Atribút", STAT_KEYS,
                           format_func=lambda k: STAT_NAMES[STAT_KEYS.index(k)],
                           key=f"sc_a_{ds}_{dec['id']}")
    if st.button("🎲 Hodiť druhú šancu", key=f"sc_btn_{ds}_{dec['id']}"):
        ph = st.empty()
        roll = animated_roll(ph, accent)
        r = evaluate({"atribut": atr, "bonus": 0, "dc": new_dc}, roll, pid,
                     dec["typ"] == "fyzicke", ds)
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
    zahada = item.get("zahada")
    if not zahada and not item.get("mod") and not item.get("jednorazovy"):
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
        st.markdown(hp_bar_html(hp["current"], hp["max"]), unsafe_allow_html=True)
        st.markdown(f"🛡️ **Výdrž: {hp['current']} / {hp['max']}**")
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
            if st.button("🔮 Použiť vešteckú guľu (−20 % max Výdrže)", key=f"orb_{cid}"):
                strata = math.ceil(hp["max"] * 0.20)
                hp["max"] = max(1, hp["max"] - strata)
                hp["current"] = min(hp["current"], hp["max"])
                st.toast(f"Veštecká guľa: −{strata} max Výdrže", icon="🔮")
                st.rerun()

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
            ic = st.columns([5, 1])
            eff = f"  \n<span style='font-size:0.74rem;color:#9aa'>{ms}</span>" if ms else ""
            ic[0].markdown(f"- {name}{eff}", unsafe_allow_html=True)
            if ic[1].button("✖", key=f"rm_{cid}_{i}", help="Vyhodiť predmet"):
                inv.pop(i); st.rerun()

        # Presun predmetu k inej (vhodnej) postave — uvoľní miesto
        if inv:
            mc = st.columns([4, 4, 2])
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

        with st.expander("🌙 Nová noc (regenerácia)"):
            typ = st.selectbox("Typ prostredia", list(REGEN_RULES.keys()),
                               format_func=lambda k: REGEN_RULES[k]["label"], key="regen_typ")
            if st.button("Regenerovať Výdrž družiny", key="regen_btn"):
                rule = REGEN_RULES[typ]
                lines = []
                for cid in active_ids(entry):
                    hp = ss["hp"][cid]
                    gain = math.ceil(hp["max"] * rule["podiel"])
                    before = hp["current"]
                    hp["current"] = min(hp["max"], hp["current"] + gain)
                    if hp["current"] != before:
                        lines.append(f"{PARTY_ALL[cid]['icon']} +{hp['current']-before}")
                if rule["cena"] > 0:
                    ss["gold"]["klan"] = max(0, ss["gold"]["klan"] - rule["cena"])
                msg = f"Regenerácia {int(rule['podiel']*100)} %. " + (", ".join(lines) if lines else "Žiadna zmena.")
                if rule["cena"] > 0:
                    msg += f"  (−{rule['cena']} zl z klanu)"
                st.success(msg)

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
def use_ability(cid, ab, ds, entry, extra):
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
        msg = f"💚 {short_name(t)} obnovený na plnú Výdrž."
    elif mech == "obnov_zivoty_100_vsetci":
        for x in ids:
            ss["hp"][x]["current"] = ss["hp"][x]["max"]
        msg = "💚 Celá družina na plnej Výdrži."
    elif mech == "obnov_zivoty_50_dvaja":
        for t in extra.get("targets", []):
            hp = ss["hp"][t]
            hp["current"] = min(hp["max"], hp["current"] + math.ceil(hp["max"] * 0.5))
        msg = "💚 Dve postavy +50 % Výdrže."
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
        msg = f"🛡️ Obor prevzal {absorb} Výdrže za skupinu."
    elif mech in NEXT_DECISION_MECHS or mech in REROLL_MECHS:
        ss["pending_ability"] = {"postava": cid, "id": ab["id"], "mechanika": mech,
                                 "hodnota": ab.get("hodnota", 0), "nazov": ab["nazov"]}
        msg = f"{ab['ikona']} {ab['nazov']} pripravená — prejaví sa pri rozhodnutí."

    # ── ceny ──
    cena = ab.get("cena")
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


def render_special_abilities_panel(ds, entry):
    ss = st.session_state
    pend = ss.get("pending_ability")
    if pend:
        kde = ("použije sa na práve hodené rozhodnutie"
               if pend["mechanika"] in REROLL_MECHS else "prejaví sa pri nasledujúcom rozhodnutí")
        st.info(f"⚡ Pripravená schopnosť: **{pend['nazov']}** — {kde}.")
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
            st.markdown(f"**{PARTY_ALL[cid]['icon']} {PARTY_ALL[cid]['meno']}**")
            for ab in lst:
                rem = ss["abilities"].setdefault(cid, {}).get(ab["id"], ab["max_pouziti"])
                dots = "🟢" * rem + "⚪" * (ab["max_pouziti"] - rem)
                st.markdown(f"{ab['ikona']} **{ab['nazov']}** {dots}  \n"
                            f"<span style='font-size:0.83rem;color:#9aa'>{ab['popis']}</span>",
                            unsafe_allow_html=True)
                if ab.get("cena_popis"):
                    st.markdown(f"<span style='color:#f85149;font-size:0.8rem'>⚠️ Cena: {ab['cena_popis']}</span>",
                                unsafe_allow_html=True)
                extra = render_ability_targets(cid, ab, entry) if rem > 0 else {}
                if st.button("Použiť", key=f"useab_{ds}_{cid}_{ab['id']}", disabled=(rem <= 0)):
                    msg = use_ability(cid, ab, ds, entry, extra)
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
            bezne = sum(1 for d in decs if d["typ"] not in ("predmet", "nakup", "detske"))
            target = target_bezne(e)
            mark = "✅" if bezne >= target else f"⚠️ {bezne}/{target}"
            d = datetime.date.fromisoformat(ds)
            col = KIND_COLOR.get(tier, "#888")
            rows.append(
                f"<div style='border-left:4px solid {col};background:{col}1f;padding:3px 9px;"
                f"margin:3px 0 3px 12px;border-radius:5px;font-size:0.86rem'>"
                f"{KIND_LABEL.get(tier, '')} · <b>D{e['day']}</b> {d.strftime('%d.%m.')} — "
                f"{e['title']} · {bezne}/{target} {mark}</div>")
    with st.expander("🔒 GM kalendár — typy dní a počty rozhodnutí (táto + nasledujúca kapitola)",
                     expanded=False):
        st.caption("Cieľ bežných rozhodnutí: 🌿 Pokojný 3 · 🗺️ Bežný 4–5 · ⚡ Rušný 6 · "
                   "🟡 Ťažší 7 · 🟠 Mini-boss 8 · 🔴 Boss 9 (+ detské). Len pre GM.")
        st.markdown("".join(rows), unsafe_allow_html=True)


RESET_PREFIXES = ("res_", "res2_", "crit1_", "predmet_done_", "nakup_done_",
                  "buy_", "buyer_", "buyerr_", "pay_", "shopdone_", "give_",
                  "leave_", "levelup20_", "sc_", "balloons_", "zlato_done_",
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
    inject_css(accent)

    top = st.columns([3, 1])
    with top[0]:
        vybrany = st.date_input("📅 Dátum hry", value=sel_default,
                                min_value=MIN_DATE, max_value=MAX_DATE,
                                format="DD.MM.YYYY", key="sel_date")
    ds = vybrany.isoformat()
    entry = CAMPAIGN.get(ds)

    with top[1]:
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
