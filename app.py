# -*- coding: utf-8 -*-
"""
Svetlo Úsvitu — prázdninová D&D kampaň (1.7. - 31.8.2026).
GM skript + interaktívna textová hra + sledovač postáv. Plne offline.
Všetok herný stav žije v st.session_state. Jazyk: slovenčina.
"""
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
    ABILITIES, STARTING_EQUIPMENT, LEGENDARY_ITEMS, WEAPONS_SHOP, EXPENSES,
    DC_SCALE, MILESTONE_POINTS, MILESTONE_LABELS, REGEN_RULES, ZISK_OSOBNE_PODIEL,
    WORLD_INTRO, GROUP_SCHEDULE,
    build_decisions, shop_for_day, gm_color_for_day, day_type_label,
    day_tier, TARGET_BEZNE, KIND_LABEL, target_bezne,
)

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


# =========================================================================
#  UKLADANIE / NAČÍTANIE POSTUPU (JSON súbor — offline, bez DB)
# =========================================================================
SAVE_CORE = ["stats", "hp", "gold", "inventory", "milestone_points"]
PROGRESS_PREFIXES = ("res_", "res2_", "crit1_", "predmet_done_", "nakup_done_",
                     "levelup20_", "balloons_")


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


def evaluate(opt, roll, cid):
    akey = _atr_key(opt)
    atr = st.session_state["stats"][cid].get(akey, 0)
    bonus = opt.get("bonus", 0)
    total = roll + atr + bonus
    diff = total - opt["dc"]
    if total >= opt["dc"]:
        outcome = "success"
    elif diff >= -3:
        outcome = "near"
    else:
        outcome = "fail"
    return {
        "idx": None, "postava": cid, "atribut": akey,
        "roll": roll, "atr": atr, "bonus": bonus, "total": total,
        "dc": opt["dc"], "diff": diff, "outcome": outcome,
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


def render_calc(res):
    znak = "+" if res["bonus"] >= 0 else "−"
    st.markdown(
        f"`{res['roll']} (hod) + {res['atr']} ({atr_name(res['atribut'])}) "
        f"{znak} {abs(res['bonus'])} (bonus) = {res['total']}`  vs  **DC {res['dc']}**"
    )


def render_option_panel(opt, accent):
    """Detailný rozpis: postava, aktuálny atribút, bonus, DC, koľko treba hodiť."""
    ss = st.session_state
    pid = opt["postava_id"]
    akey = opt["atribut_key"]
    emoji = STAT_LABELS[STAT_KEYS.index(akey)] if akey in STAT_KEYS else "•"
    atr = ss["stats"][pid].get(akey, 0)
    bonus = opt["bonus"]
    total = atr + bonus
    dc = opt["dc"]
    need = dc - total
    if need <= 1:
        need_txt = "stačí hodiť <b>1+</b>"
    elif need <= 20:
        need_txt = f"treba hodiť <b>{need}+</b>"
    else:
        need_txt = "<b>len kritická 20</b> (+ šťastie)"
    bonus_html = (f"<br>&nbsp;&nbsp;&nbsp;<span style='color:#9aa'>+ {bonus} bonus z výbavy/situácie</span>"
                  f"<br>= <b>{total}</b> celkový základ") if bonus else ""
    html = (f"<div class='su-opt' style='border-color:{accent}55'>"
            f"<b>{opt['label']}</b><br>"
            f"👤 {opt['postava_ikona']} {opt['postava_nazov']}<br>"
            f"{emoji} {opt['atribut_nazov']}: <b>{atr}</b> (aktuálna){bonus_html}<br>"
            f"🎯 DC {dc} · 📊 d20 + {total} ≥ {dc} → {need_txt}</div>")
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


def render_skill_decision(n, ds, dec, accent, entry, positive=False):
    ss = st.session_state
    reskey = f"res_{ds}_{dec['id']}"
    badge = TYPE_BADGE.get(dec["typ"], "")

    st.markdown(f"#### {badge} · Rozhodnutie {n}")
    st.markdown(f"**{dec['prompt']}**")

    if reskey not in ss:
        for idx, opt in enumerate(dec["options"]):
            render_option_panel(opt, accent)
            if st.button(f"🎲 {opt['postava_ikona']} {opt['postava_nazov']} — hodiť kockou",
                         key=f"btn_{ds}_{dec['id']}_{idx}"):
                ph = st.empty()
                roll = animated_roll(ph, accent)
                res = evaluate(opt, roll, opt["postava_id"])
                res["idx"] = idx
                ss[reskey] = res
                st.rerun()
        return False

    # už rozhodnuté
    res = ss[reskey]
    opt = dec["options"][res["idx"]]
    st.markdown(f"➡️ **{opt['label']}** · {opt['postava_ikona']} {opt['postava_nazov']}")
    render_calc(res)

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

    # Hod 1 — kritický neúspech: −10 % Výdrže navyše (raz)
    if res["roll"] == 1 and not positive:
        critkey = f"crit1_{ds}_{dec['id']}"
        if not ss.get(critkey):
            hp = ss["hp"][opt["postava_id"]]
            strata = max(1, math.ceil(hp["max"] * 0.10))
            hp["current"] = max(0, hp["current"] - strata)
            ss[critkey] = True
            st.caption(f"💀 Kritický neúspech: {opt['postava_nazov']} −{strata} Výdrže.")

    # Levelup pri hode 20 (max 1× za deň na postavu)
    if res["roll"] == 20:
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

    # Veľký neúspech → druhá šanca (nie pri detskom)
    if res["outcome"] == "fail" and not positive:
        render_second_chance(n, ds, dec, accent, entry)

    if st.button(f"↩️ Znova rozhodnutie {n}", key=f"reset_{ds}_{dec['id']}"):
        for k in (reskey, f"res2_{ds}_{dec['id']}", f"crit1_{ds}_{dec['id']}"):
            ss.pop(k, None)
        st.rerun()
    return True


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
        r = evaluate({"atribut": atr, "bonus": 0, "dc": new_dc}, roll, pid)
        ss[res2key] = r
        st.rerun()


def render_predmet_decision(n, ds, dec, entry, gm):
    ss = st.session_state
    it = dec["predmet"]
    donekey = f"predmet_done_{ds}_{dec['id']}"

    st.markdown(f"#### 🎁 · Rozhodnutie {n} — Nájdený predmet")
    zahada = it.get("zahada")
    extra = ""
    if zahada:
        extra += f"<br>🌀 <i>{zahada}</i>"
    jed = " · <span style='color:#d29922'>jednorazový</span>" if it.get("jednorazovy") else ""
    html = (f"<div class='su-item'><b>{it['nazov']}</b>{jed}<br>"
            f"✨ {it.get('vyhody','—')}<br>"
            f"⚠️ {it.get('nevyhody','—')}{extra}</div>")
    st.markdown(html, unsafe_allow_html=True)
    if gm and it.get("gm_poznamka"):
        st.markdown(f"<div class='su-gm'>🔒 GM: {it['gm_poznamka']}</div>", unsafe_allow_html=True)

    if donekey not in ss:
        st.caption("Komu predmet pridelíte?")
        ids = active_ids(entry)
        cols = st.columns(3)
        for i, cid in enumerate(ids):
            full = len(ss["inventory"][cid]) >= INV_LIMIT
            lbl = f"{PARTY_ALL[cid]['icon']} {short_name(cid)}" + (" (plný)" if full else "")
            if cols[i % 3].button(lbl, key=f"give_{ds}_{dec['id']}_{cid}", disabled=full):
                ss["inventory"][cid].append(it["nazov"])
                ss[donekey] = cid
                st.toast(f"{it['nazov']} → {short_name(cid)}", icon="🎁")
                st.rerun()
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
        if who not in (None, "_none") and it["nazov"] in ss["inventory"].get(who, []):
            ss["inventory"][who].remove(it["nazov"])
        ss.pop(donekey, None)
        st.rerun()
    return True


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
        ss["inventory"][buyer].append(p["nazov"])
    # odznač vybrané checkboxy
    for i in range(50):
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
        jed = " · jednorazový" if p.get("jednorazovy") else ""
        lab = (f"{p.get('ikona', '🛒')} **{p['nazov']}** — ➕ {p['vyhoda']} · ➖ {p['nevyhoda']} · "
               f"**{p['cena']} zl**{jed}")
        if st.checkbox(lab, key=f"buy_{ds}_{did}_{i}"):
            sel.append(p)

    total = sum(p["cena"] for p in sel)
    clan_key = "klan" if CLAN_OF.get(buyer) == "mala" else "klan_slnko"
    osob = ss["gold"][buyer]
    klan = ss["gold"][clan_key]
    klan_nazov = CLANS["mala"]["nazov"] if clan_key == "klan" else CLANS["velka"]["nazov"]
    st.markdown(f"💰 Osobné ({short_name(buyer)}): **{osob} zl** · 🏦 {klan_nazov}: **{klan} zl** · "
                f"🧾 Vybrané: **{total} zl**")
    zdroj = st.radio("Zaplatiť z", ["Osobné", "Klanové", "Kombinácia"], horizontal=True,
                     key=f"pay_{ds}_{did}")

    cols = st.columns(2)
    if cols[0].button("✅ Kúpiť vybrané", key=f"buybtn_{ds}_{did}", disabled=(not sel)):
        ok, msg = do_purchase(buyer, sel, total, zdroj, clan_key, ds, did)
        if ok:
            st.toast(msg, icon="🛒")
        else:
            st.session_state[f"buyerr_{ds}_{did}"] = msg
        st.rerun()
    if cols[1].button("➡️ Pokračovať (obchod hotový)", key=f"shopdone_{ds}_{did}"):
        ss[donekey] = True
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
        st.markdown(f"**📦 Inventár ({len(inv)}/{INV_LIMIT})**")
        for i, item in enumerate(list(inv)):
            ic = st.columns([5, 1])
            ic[0].markdown(f"- {item}")
            if ic[1].button("🗑️", key=f"rm_{cid}_{i}"):
                inv.pop(i); st.rerun()

        if len(inv) < INV_LIMIT:
            day_items = [it["nazov"] for it in entry.get("items_day", [])]
            options = ["— vyber —"] + day_items + ["✏️ vlastný…"]
            sel = st.selectbox("Pridať predmet", options, key=f"addsel_{cid}")
            custom = ""
            if sel == "✏️ vlastný…":
                custom = st.text_input("Názov predmetu", key=f"addtxt_{cid}")
            if st.button("➕ Pridať do inventára", key=f"addbtn_{cid}"):
                name = custom.strip() if sel == "✏️ vlastný…" else (sel if sel != "— vyber —" else "")
                if name:
                    inv.append(name); st.rerun()
        else:
            st.caption("Inventár je plný (max 5).")


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
            st.caption("Stiahni si súbor s postupom a uschovaj ho (mail, telefón). "
                       "Keď budeš chcieť pokračovať — aj na inom zariadení — nahraj ho späť. "
                       "⚠️ Postup sa inak po zatvorení/uspaní appky stratí.")
            st.download_button(
                "💾 Uložiť hru (stiahnuť súbor)", data=serialize_state(),
                file_name=f"svetlo-usvitu_{datetime.date.today().isoformat()}.json",
                mime="application/json", use_container_width=True)
            up = st.file_uploader("📂 Načítať hru (nahraj súbor)", type=["json"], key="load_file")
            if up is not None and ss.get("_loaded_id") != up.file_id:
                try:
                    load_state(up.getvalue().decode("utf-8"))
                    ss["_loaded_id"] = up.file_id
                    st.success("✅ Hra načítaná — postup obnovený.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Súbor sa nepodarilo načítať: {e}")

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
                  "leave_", "levelup20_", "sc_", "balloons_",
                  "d1_", "d2_", "d3_", "res1_", "res3_")


def reset_day(ds):
    ss = st.session_state
    for k in list(ss.keys()):
        if isinstance(k, str) and ds in k and k.startswith(RESET_PREFIXES):
            ss.pop(k, None)


def main():
    init_state()

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

    st.markdown("---")
    st.caption("GM skript pre rodičov · Klan Železného Dubu & Klan Zlatého Slnka · Eldorea 2026")


if __name__ == "__main__":
    main()
