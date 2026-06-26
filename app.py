# -*- coding: utf-8 -*-
"""
Svetlo Úsvitu — prázdninová D&D kampaň (1.7. - 31.8.2026).
GM skript + interaktívna textová hra + sledovač postáv. Plne offline.
Všetok herný stav žije v st.session_state. Jazyk: slovenčina.
"""
import math
import time
import random
import datetime

import streamlit as st

from data import (
    CAMPAIGN, CHAPTERS, CHAPTER_COLORS, chapter_by_id,
    PARTY_MALA, PARTY_VELKA_DOPLNOK, PARTY_ALL, CLANS, CLAN_OF,
    STATS, STAT_KEYS, STAT_LABELS, STAT_NAMES, stats_dict, start_vydrz,
    ABILITIES, STARTING_EQUIPMENT, LEGENDARY_ITEMS, WEAPONS_SHOP, EXPENSES,
    DC_SCALE, MILESTONE_POINTS, MILESTONE_LABELS, REGEN_RULES, ZISK_OSOBNE_PODIEL,
    WORLD_INTRO, GROUP_SCHEDULE,
)

st.set_page_config(page_title="Svetlo Úsvitu", page_icon="🗡️", layout="centered")

MIN_DATE = datetime.date(2026, 6, 29)   # 29.-30.6. = skúšobné prológové dni
CAMPAIGN_START = datetime.date(2026, 7, 1)
MAX_DATE = datetime.date(2026, 8, 31)
INV_LIMIT = 5            # max predmetov nad štartovaciu výbavu
START_GOLD = 20         # štartovacie osobné zlato
START_KLAN = 40         # štartovacia klanová pokladnica

TYPE_BADGE = {
    "fyzicke":   "💪 Fyzické",
    "sociale":   "💬 Sociálne",
    "prieskumne":"🔍 Prieskumné",
    "takticke":  "♟️ Taktické",
    "prirodne":  "🌿 Prírodné",
    "tajomne":   "🔮 Tajomné",
    "humorne":   "😄 Humorné",
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
          min-height: 3.2em;
          white-space: normal;
          text-align: left;
          border: 1px solid {accent}55;
          border-radius: 10px;
          font-size: 1.02rem;
          line-height: 1.25rem;
          padding: 0.6em 0.9em;
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


def active_party(entry):
    if entry["group"] == "velka":
        return PARTY_MALA + PARTY_VELKA_DOPLNOK
    return PARTY_MALA


def active_ids(entry):
    return [p["id"] for p in active_party(entry)]


# =========================================================================
#  D20 MECHANIKA
# =========================================================================
def animated_roll(placeholder, accent):
    """Animovaný hod d20 — čísla sa preklikávajú, potom sa ustáli."""
    final = random.randint(1, 20)
    for _ in range(14):
        n = random.randint(1, 20)
        placeholder.markdown(
            f"<div style='text-align:center;font-size:2.6rem;color:{accent}'>🎲 {n}</div>",
            unsafe_allow_html=True)
        time.sleep(0.045)
    placeholder.markdown(
        f"<div style='text-align:center;font-size:3rem;color:{accent};font-weight:bold'>🎲 {final}</div>",
        unsafe_allow_html=True)
    time.sleep(0.2)
    return final


def evaluate(opt, roll, cid):
    atr = st.session_state["stats"][cid].get(opt["atribut"], 0)
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
        "idx": None, "postava": cid, "atribut": opt["atribut"],
        "roll": roll, "atr": atr, "bonus": bonus, "total": total,
        "dc": opt["dc"], "diff": diff, "outcome": outcome,
    }


def outcome_label(res):
    if res["roll"] == 20:
        return "💥 KRITICKÝ ÚSPECH (hod 20)!"
    return {
        "success": "✅ Úspech",
        "near": f"🟠 Tesný neúspech (chýbalo {abs(res['diff'])})",
        "fail": f"❌ Neúspech (chýbalo {abs(res['diff'])})",
    }[res["outcome"]]


def render_calc(res):
    znak = "+" if res["bonus"] >= 0 else "−"
    st.markdown(
        f"`{res['roll']} (hod) + {res['atr']} ({res['atribut']}) "
        f"{znak} {abs(res['bonus'])} (bonus) = {res['total']}`  vs  **DC {res['dc']}**"
    )


# =========================================================================
#  ROZHODNUTIA
# =========================================================================
def render_decision(n, ds, decision, accent):
    ss = st.session_state
    reskey = f"res{n}_{ds}"
    char = lambda cid: PARTY_ALL[cid]

    st.markdown(f"#### ⚔️ Rozhodnutie {n}")
    st.caption(TYPE_BADGE.get(decision.get("type", ""), ""))
    st.markdown(f"**{decision['prompt']}**")

    if reskey not in ss:
        for idx, opt in enumerate(decision["options"]):
            c = char(opt["postava"])
            label = f"{opt['label']}  \n{c['icon']} {STAT_NAMES[STAT_KEYS.index(opt['atribut'])]} · DC {opt['dc']}"
            if st.button(label, key=f"btn_d{n}_{ds}_{idx}"):
                ph = st.empty()
                roll = animated_roll(ph, accent)
                res = evaluate(opt, roll, opt["postava"])
                res["idx"] = idx
                ss[reskey] = res
                ss[f"d{n}_{ds}"] = idx
                st.rerun()
        return False

    # už rozhodnuté — zobraz výsledok
    res = ss[reskey]
    opt = decision["options"][res["idx"]]
    c = char(opt["postava"])

    st.markdown(f"➡️ **{opt['label']}**  · {c['icon']} {c['meno']}")
    render_calc(res)
    st.markdown(f"### {outcome_label(res)}")

    if res["outcome"] == "success":
        st.success(opt["result_success"])
    elif res["outcome"] == "near":
        st.warning(opt["result_near"])
    else:
        st.error(opt["result_fail"])

    # Levelup pri hode 20 (max 1× za deň na postavu)
    if res["roll"] == 20:
        lvlkey = f"levelup20_{ds}_{opt['postava']}"
        atr_name = STAT_NAMES[STAT_KEYS.index(opt["atribut"])]
        if ss.get(lvlkey):
            st.caption(f"⭐ {c['meno']} už dnes získal/a +1 {atr_name} za hod 20.")
        else:
            if st.button(f"⭐ Potvrdiť levelup: +1 {atr_name} pre {c['meno']}",
                         key=f"lvl_{n}_{ds}"):
                ss["stats"][opt["postava"]][opt["atribut"]] += 1
                ss[lvlkey] = True
                st.toast(f"{c['meno']}: +1 {atr_name}!", icon="⭐")
                st.rerun()

    # Veľký neúspech (−4+) → druhá šanca: iná postava, iný atribút, DC +5
    if res["outcome"] == "fail":
        render_second_chance(n, ds, decision, accent)

    # Reset tohto rozhodnutia
    if st.button(f"↩️ Znova rozhodnutie {n}", key=f"reset_d{n}_{ds}"):
        for k in (reskey, f"d{n}_{ds}", f"res{n}_{ds}_2"):
            ss.pop(k, None)
        st.rerun()

    return True


def render_second_chance(n, ds, decision, accent):
    ss = st.session_state
    res2key = f"res{n}_{ds}_2"
    base_dc = decision["options"][ss[f"res{n}_{ds}"]["idx"]]["dc"]
    new_dc = base_dc + 5

    st.markdown("---")
    st.info(f"🎯 **Druhá šanca** — iná postava, iný atribút, DC +5 (**DC {new_dc}**). "
            "GM vyberie, kto sa o to pokúsi.")

    if res2key in ss:
        r = ss[res2key]
        c = PARTY_ALL[r["postava"]]
        st.markdown(f"➡️ Druhý pokus: {c['icon']} {c['meno']} ({STAT_NAMES[STAT_KEYS.index(r['atribut'])]})")
        render_calc(r)
        st.markdown(f"**{outcome_label(r)}**")
        if r["total"] >= r["dc"]:
            st.success("Druhá šanca zabrala — príbeh pokračuje s úspechom.")
        else:
            st.error("Ani druhá šanca nevyšla — GM dotvorí následok.")
        return

    entry = CAMPAIGN[ds]
    ids = active_ids(entry)
    col1, col2 = st.columns(2)
    with col1:
        pid = st.selectbox("Postava", ids,
                           format_func=lambda i: f"{PARTY_ALL[i]['icon']} {PARTY_ALL[i]['meno']}",
                           key=f"sc_p_{n}_{ds}")
    with col2:
        atr = st.selectbox("Atribút", STAT_KEYS,
                           format_func=lambda k: STAT_NAMES[STAT_KEYS.index(k)],
                           key=f"sc_a_{n}_{ds}")
    if st.button("🎲 Hodiť druhú šancu", key=f"sc_btn_{n}_{ds}"):
        ph = st.empty()
        roll = animated_roll(ph, accent)
        fake_opt = {"atribut": atr, "bonus": 0, "dc": new_dc}
        r = evaluate(fake_opt, roll, pid)
        ss[res2key] = r
        st.rerun()


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


def render_char_card(cid, entry, accent):
    ss = st.session_state
    p = PARTY_ALL[cid]
    s = ss["stats"][cid]
    hp = ss["hp"][cid]
    total = sum(s.values())

    with st.expander(f"{p['icon']} {p['meno']} — {p['zbran']}"):
        st.caption(p["rola"])

        # Atribúty
        for key in STAT_KEYS:
            lbl = STAT_LABELS[STAT_KEYS.index(key)]
            name = STAT_NAMES[STAT_KEYS.index(key)]
            val = s[key]
            cols = st.columns([3.4, 3.4, 1])
            cols[0].markdown(f"<span class='su-stat'>{lbl} {name}</span>", unsafe_allow_html=True)
            cols[1].markdown(stat_bar_html(val, accent), unsafe_allow_html=True)
            cols[2].markdown(f"<span class='su-stat'><b>{val}</b></span>", unsafe_allow_html=True)
        st.caption(f"Σ celkovo: **{total}**")

        # Míľnikové body — rozdelenie (+1 za bod, bez stropu)
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
        # Výdrž (životy)
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

        # Veštecká guľa pre Vedmu — −20 % max Výdrže
        if cid == "vedma":
            if st.button("🔮 Použiť vešteckú guľu (−20 % Výdrže)", key=f"orb_{cid}"):
                strata = math.ceil(hp["max"] * 0.20)
                hp["max"] = max(1, hp["max"] - strata)
                hp["current"] = min(hp["current"], hp["max"])
                st.toast(f"Veštecká guľa: −{strata} max Výdrže", icon="🔮")
                st.rerun()

        st.markdown("---")
        # Zlato (osobné)
        new_gold = st.number_input("💰 Osobné zlato", min_value=0, step=5,
                                   value=int(ss["gold"][cid]), key=f"gold_{cid}")
        ss["gold"][cid] = int(new_gold)

        st.markdown("---")
        # Štartovacia výbava (pevná)
        st.markdown("**🎒 Štartovacia výbava** *(pevná)*")
        for it in STARTING_EQUIPMENT.get(cid, []):
            st.markdown(f"- {it['nazov']}  \n  <span style='font-size:0.78rem;color:#9aa'>➕ {it['vyhoda']} · ➖ {it['nevyhoda']}</span>",
                        unsafe_allow_html=True)

        # Inventár (max 5)
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
#  SIDEBAR — KLAN, MÍĽNIKY, NOVÁ NOC
# =========================================================================
def render_sidebar(entry, accent):
    ss = st.session_state
    is_velka = entry["group"] == "velka"

    with st.sidebar:
        st.title("🗡️ Svetlo Úsvitu")
        st.caption("Prázdninová kampaň · 1.7. – 31.8.2026")

        # Karty postáv
        st.markdown(f"### 🌳 {CLANS['mala']['nazov']}")
        for p in PARTY_MALA:
            render_char_card(p["id"], entry, accent)

        if is_velka:
            st.markdown(f"### ☀️ {CLANS['velka']['nazov']}")
            st.caption("Aktívny počas Talianska (18.–25.7.)")
            for p in PARTY_VELKA_DOPLNOK:
                render_char_card(p["id"], entry, accent)

        st.markdown("---")
        # Klanová pokladnica
        st.markdown("### 🏦 Klanová pokladnica")
        kd = st.number_input(f"🌳 {CLANS['mala']['nazov']}", min_value=0, step=5,
                             value=int(ss["gold"]["klan"]), key="gold_klan")
        ss["gold"]["klan"] = int(kd)
        if is_velka:
            ks = st.number_input(f"☀️ {CLANS['velka']['nazov']}", min_value=0, step=5,
                                 value=int(ss["gold"]["klan_slnko"]), key="gold_klan_slnko")
            ss["gold"]["klan_slnko"] = int(ks)
            st.caption("Počas Talianska majú obe klanové pokladnice spoločný cieľ.")

        st.markdown("---")
        # Míľnikové body
        with st.expander("🎖️ Pridať míľnikové body"):
            st.caption("Ťažší nepriateľ 1 · Mini-boss 2 · Hlavný boss 5 · Kapitola 3")
            cnt = st.number_input("Počet bodov pre každú aktívnu postavu", min_value=1, value=1, step=1,
                                  key="mp_count")
            if st.button("Udeliť body celej družine", key="mp_give"):
                for cid in active_ids(entry):
                    ss["milestone_points"][cid] += int(cnt)
                st.toast(f"+{int(cnt)} bodov pre každú postavu", icon="🎖️")
                st.rerun()

        # Nová noc — regenerácia
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
        # Kapitoly
        with st.expander("📅 Kapitoly kampane"):
            for ch in CHAPTERS:
                iko = "🌳+☀️" if ch["skupina"] == "velka" else "🌳"
                st.markdown(
                    f"<div class='su-chapter' style='border-color:{ch['farba']}'>"
                    f"<b>{ch['nazov']}</b><br><span style='font-size:0.8rem'>{ch['od']} – {ch['do']} {iko}</span></div>",
                    unsafe_allow_html=True)

        # Legendárne predmety
        with st.expander("✨ Legendárne predmety"):
            for li in LEGENDARY_ITEMS:
                kedy = f"Deň {li['den']}" if li["den"] else "Priebeh kampane"
                st.markdown(f"**{li['nazov']}** — {li['nositel']} ({kedy})  \n"
                            f"<span style='font-size:0.8rem;color:#9aa'>➕ {li['vyhody']} · ➖ {li['nevyhody']}</span>",
                            unsafe_allow_html=True)

        # O svete
        with st.expander("📖 O svete Eldorea"):
            st.write(WORLD_INTRO)


# =========================================================================
#  HLAVNÁ PLOCHA
# =========================================================================
def render_items_and_shop(entry):
    items = entry.get("items_day", [])
    if not items:
        return
    st.markdown("#### 🎁 Predmety dňa")
    najst = [it for it in items if it.get("kde", "najst") in ("najst", "nájsť")]
    kupit = [it for it in items if it.get("kde") == "kupit"]

    if najst:
        st.markdown("**Nájsť:**")
        for it in najst:
            jed = " · *jednorazový*" if it.get("jednorazovy") else ""
            st.markdown(f"- **{it['nazov']}** — ➕ {it['vyhody']} · ➖ {it['nevyhody']}{jed}")
    if kupit:
        st.markdown("**Kúpiť (Obchod):**")
        for it in kupit:
            st.markdown(f"- **{it['nazov']}** — {it['cena']} zl · ➕ {it['vyhody']} · ➖ {it['nevyhody']}")
    st.caption("Predmety pridávaš postavám v ich karte v paneli vľavo.")


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


def reset_day(ds):
    ss = st.session_state
    prefixes = ("d1_", "d2_", "d3_", "res1_", "res2_", "res3_", "levelup20_", "ability_")
    for k in list(ss.keys()):
        if isinstance(k, str) and ds in k and k.startswith(prefixes):
            ss.pop(k, None)


def main():
    init_state()

    today = datetime.date.today()
    default = today if MIN_DATE <= today <= MAX_DATE else MIN_DATE

    # Prvotné určenie dátumu (pre accent farbu pred injektovaním CSS)
    sel_default = st.session_state.get("sel_date", default)
    entry0 = CAMPAIGN.get(sel_default.isoformat())
    accent = CHAPTER_COLORS.get(entry0["chapter"], "#f4c430") if entry0 else "#f4c430"
    inject_css(accent)

    # Dátumový prepínač + reset
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

    # Sidebar
    render_sidebar(entry, accent)

    # Progress + badge
    is_test = entry["day"] < 1
    if is_test:
        st.progress(0.0, text="🌱 Skúšobný deň (pred štartom kampane 1.7.)")
    else:
        st.progress(entry["day"] / 62, text=f"Deň {entry['day']} / 62")
    clan_badge = (f"🌳☀️ VEĽKÁ DRUŽINA (15) — {CLANS['mala']['nazov']} + {CLANS['velka']['nazov']}"
                  if is_velka else f"🌳 MALÁ DRUŽINA (7) — {CLANS['mala']['nazov']}")
    st.markdown(
        f"<div class='su-chapter' style='border-color:{accent}'>"
        f"<b>{chapter['nazov']}</b> · {clan_badge}</div>", unsafe_allow_html=True)
    if is_test:
        st.info("🌱 **Skúšobný deň** — nezáväzný nácvik pred štartom kampane (1.7.). "
                "Vyskúšajte si hod kockou, levelovanie v karte postavy, predmety a zlato. Nič sa nepokazí.")
    if is_velka:
        st.warning("💡 Dnes hrá veľká skupina (15 osôb) — zvážte rozdelenie na 2–3 menšie tímy.")

    # Nadpis + intro
    st.markdown(f"## {entry['title']}")
    st.markdown("##### 📖 Prečítaj nahlas")
    st.markdown(f"<div class='su-quote'>{entry['intro']}</div>", unsafe_allow_html=True)
    st.markdown("---")

    # Rozhodnutia 1 → 2 → 3 (sekvenčne)
    done1 = render_decision(1, ds, entry["decision1"], accent)
    all_done = False
    if done1:
        st.markdown("---")
        done2 = render_decision(2, ds, entry["decision2"], accent)
        if done2:
            st.markdown("---")
            done3 = render_decision(3, ds, entry["decision3"], accent)
            all_done = done3

    st.markdown("---")
    render_milnik(entry)
    render_items_and_shop(entry)

    if all_done:
        # Outro + odkaz na zajtra
        st.markdown("---")
        zajtra = vybrany + datetime.timedelta(days=1)
        nxt = CAMPAIGN.get(zajtra.isoformat())
        nxt_t = f" — *{entry.get('next_hint') or (nxt['title'] if nxt else '')}*"
        st.markdown(f"#### 🌅 Záver dňa")
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
