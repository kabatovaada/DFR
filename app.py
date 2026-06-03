import streamlit as st
import pandas as pd
import math
from datetime import datetime

st.set_page_config(
    page_title="Spracovanie DFR cez AS",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.block-container { padding-top: 1rem; max-width: 1400px; }

.savings-hero {
    background: linear-gradient(135deg, #1E5631 0%, #2E7D32 100%);
    border-radius: 14px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
}
.savings-hero .sh-label  { font-size: 14px; color: #d4edda; margin: 0 0 4px; }
.savings-hero .sh-amount { font-size: 52px; font-weight: 700; color: #ffffff; margin: 0; line-height: 1.1; }
.savings-hero .sh-sub    { font-size: 20px; color: #d4edda; margin: 4px 0 0; }
.savings-hero .sh-pct    {
    background: rgba(255,255,255,0.25);
    border-radius: 8px;
    padding: 4px 14px;
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    display: inline-block;
    margin-top: 10px;
}

.cost-box { border-radius: 10px; padding: 1.1rem 1.3rem; }
.cost-box.old { background: #fff5f5; border: 1.5px solid #feb2b2; }
.cost-box.new { background: #f0fff4; border: 1.5px solid #9ae6b4; }
.cost-box .clabel { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; margin: 0 0 6px; }
.cost-box.old .clabel { color: #9b2c2c; }
.cost-box.new .clabel { color: #276749; }
.cost-box .cval  { font-size: 30px; font-weight: 700; margin: 0; line-height: 1.1; }
.cost-box.old .cval { color: #9b2c2c; }
.cost-box.new .cval { color: #276749; }
.cost-box .csub  { font-size: 14px; color: #555; margin: 4px 0 0; }
.cost-box .cdetail { font-size: 12px; color: #666; margin: 3px 0; }

.breakdown-row { margin: 8px 0; }
.breakdown-label { font-size: 12px; color: #333; display: flex; justify-content: space-between; margin-bottom: 4px; font-weight: 500; }
.bar-track { background: #e2e8f0; border-radius: 4px; height: 22px; overflow: hidden; }
.bar-fill  { height: 22px; border-radius: 4px; display: flex; align-items: center; padding-left: 10px; font-size: 12px; font-weight: 700; color: #ffffff; white-space: nowrap; overflow: hidden; }

.mini-kpi { background: #f7fafc; border-radius: 8px; padding: 0.7rem 0.9rem; border: 1px solid #e2e8f0; text-align: center; }
.mini-kpi .ml { font-size: 11px; color: #718096; margin: 0 0 3px; }
.mini-kpi .mv { font-size: 18px; font-weight: 700; color: #2d3748; margin: 0; }
.mini-kpi .ms { font-size: 10px; color: #a0aec0; margin: 2px 0 0; }

.section-title {
    font-size: 12px; font-weight: 700; color: #2d3748; text-transform: uppercase;
    letter-spacing: .8px; border-bottom: 2px solid #4a5568;
    padding-bottom: 4px; margin: 1.5rem 0 0.75rem;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
KLT_M3        = 0.05
KLT_PER_PAL   = 24
PAL_M3_NEW    = KLT_PER_PAL * KLT_M3
FILL_FACTOR   = 0.70
PAL_M3_OLD    = PAL_M3_NEW * FILL_FACTOR
VYKON_STD     = 70
VYKON_DIST    = 60

def dir_cost(t_s, rate):   return (t_s / 3600) * rate
def opp_cost(t_s, rate):   return (t_s / 3600) * (VYKON_STD - VYKON_DIST) / VYKON_STD * rate

def compute(df_raw, thresh, rate, czk, price_czk):
    price_eur = price_czk / czk
    df = df_raw.copy()
    df['Počet ks']   = pd.to_numeric(df['Počet ks'],   errors='coerce').fillna(0)
    df['Objem [m3]'] = pd.to_numeric(df['Objem [m3]'], errors='coerce').fillna(0)
    df['preprava']   = df['Počet ks'].apply(lambda x: 'Paleta' if x >= thresh else 'KLT')
    df['month']      = pd.to_datetime(df['Date']).dt.strftime('%Y-%m')

    klt = df[df['preprava']=='KLT']; pal = df[df['preprava']=='Paleta']
    n_total=len(df); n_klt=len(klt); n_pal=len(pal)

    og = df.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index()
    og['np'] = og['Objem [m3]'].apply(lambda v: math.ceil(v / PAL_M3_OLD))
    n_pal_old = int(og['np'].sum())

    kg = klt.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index() if n_klt>0 else pd.DataFrame({'Objem [m3]':[]})
    if len(kg)>0: kg['nk'] = kg['Objem [m3]'].apply(lambda v: math.ceil(v/KLT_M3))
    n_klts = int(kg['nk'].sum()) if len(kg)>0 else 0

    pg = pal.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index() if n_pal>0 else pd.DataFrame({'Objem [m3]':[]})
    if len(pg)>0: pg['np'] = pg['Objem [m3]'].apply(lambda v: math.ceil(v/PAL_M3_NEW))
    n_pal_new = int(pg['np'].sum()) if len(pg)>0 else 0

    t_old = n_total*223 + n_pal_old*300  # 20+15+180+8=223s
    t_new = n_klt*20 + n_klt*8 + n_klts*15 + n_pal*223 + n_pal_new*300  # KLT:20+8+15s/KLT, Pal:223s

    c_dir_old=dir_cost(t_old,rate); c_oc_old=opp_cost(t_old,rate)
    c_dir_new=dir_cost(t_new,rate); c_oc_new=opp_cost(t_new,rate)
    c_mzd_old=round(c_dir_old+c_oc_old,2); c_mzd_new=round(c_dir_new+c_oc_new,2)
    c_pal_old=round(n_pal_old*price_eur,2); c_pal_new=round(n_pal_new*price_eur,2)
    c_tot_old=round(c_mzd_old+c_pal_old,2); c_tot_new=round(c_mzd_new+c_pal_new,2)
    sav=round(c_tot_old-c_tot_new,2)
    sav_pct=round(sav/c_tot_old*100,1) if c_tot_old>0 else 0
    sav_mzd=round(c_mzd_old-c_mzd_new,2); sav_pal=round(c_pal_old-c_pal_new,2)

    monthly=[]
    for month,grp in df.groupby('month'):
        mk=grp[grp['preprava']=='KLT']; mp=grp[grp['preprava']=='Paleta']
        og_=grp.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index()
        og_['np']=og_['Objem [m3]'].apply(lambda v:math.ceil(v/PAL_M3_OLD))
        kg_=mk.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index() if len(mk)>0 else pd.DataFrame({'Objem [m3]':[]})
        if len(kg_)>0: kg_['nk']=kg_['Objem [m3]'].apply(lambda v:math.ceil(v/KLT_M3))
        pg_=mp.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index() if len(mp)>0 else pd.DataFrame({'Objem [m3]':[]})
        if len(pg_)>0: pg_['np']=pg_['Objem [m3]'].apply(lambda v:math.ceil(v/PAL_M3_NEW))
        nk_=int(kg_['nk'].sum()) if len(kg_)>0 else 0
        npo_=int(pg_['np'].sum()) if len(pg_)>0 else 0
        npa_=int(og_['np'].sum())
        tso=len(grp)*216+npa_*300; tsn=len(mk)*20+len(mk)*15+nk_*15+len(mp)*216+npo_*300
        cm_o=dir_cost(tso,rate)+opp_cost(tso,rate); cm_n=dir_cost(tsn,rate)+opp_cost(tsn,rate)
        cp_o=npa_*price_eur; cp_n=npo_*price_eur
        ct_o=round(cm_o+cp_o,2); ct_n=round(cm_n+cp_n,2); us=round(ct_o-ct_n,2)
        monthly.append({'Mesiac':month,'Záznamy':len(grp),'KLT záz.':len(mk),'KLT ks':nk_,'Pal. záz.':len(mp),
            'Palety starý':npa_,'Palety nový':npo_,
            'Nákl. starý (€)':ct_o,'Nákl. nový (€)':ct_n,'Úspora (€)':us,'Úspora (Kč)':round(us*czk,2),
            'Úspora proces (€)':round(cm_o-cm_n,2),'Úspora doprava (€)':round(cp_o-cp_n,2),
            'Pal. nákl. starý (€)':round(cp_o,2),'Pal. nákl. nový (€)':round(cp_n,2)})

    return dict(n_total=n_total,n_klt=n_klt,n_pal=n_pal,n_klts=n_klts,
                n_pal_old=n_pal_old,n_pal_new=n_pal_new,
                c_dir_old=round(c_dir_old,2),c_oc_old=round(c_oc_old,2),
                c_dir_new=round(c_dir_new,2),c_oc_new=round(c_oc_new,2),
                c_mzd_old=c_mzd_old,c_mzd_new=c_mzd_new,
                c_pal_old=c_pal_old,c_pal_new=c_pal_new,
                c_tot_old=c_tot_old,c_tot_new=c_tot_new,
                sav=sav,sav_czk=round(sav*czk,2),sav_pct=sav_pct,
                sav_mzd=sav_mzd,sav_pal=sav_pal,
                monthly=pd.DataFrame(monthly))

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Parametre")
    thresh    = st.slider("Limit spracovania cez AS (ks)", 1, 100, 20)
    price_czk = st.number_input("Cena za paletu (Kč)", value=561.0, step=10.0)
    rate      = st.number_input("Sadzba práce (€/hod)", value=15.0, step=0.5)
    czk       = st.number_input("Kurz EUR/CZK", value=24.29, step=0.01)

    st.markdown("---")
    st.caption("📂 Dáta: Zošit2.xlsx (pribalené)")

    st.markdown("---")
    st.caption(f"Paleta: {KLT_PER_PAL} KLT = {PAL_M3_NEW:.2f} m³  \nStarý fill: 70 % → {PAL_M3_OLD:.3f} m³  \nFiltre: SPO + DFR")

# ── Load data ──────────────────────────────────────────────────────────────────
import os

BASE = os.path.dirname(__file__)

DATA_SOURCES = [
    {"file": "DFR_Q1_2026_CZLC4-SKLC3.xlsx",  "header": 2,    "label": "CZLC4→SKLC3 Q1 2026"},
    {"file": "DFR_Q1_2026_SKLC3-CZLC4.xlsx",  "header": 2,    "label": "SKLC3→CZLC4 Q1 2026"},
]

def load_source(src):
    fpath = os.path.join(BASE, src["file"])
    if not os.path.exists(fpath):
        return None, src["label"]
    if src["header"] is None:
        df = pd.read_excel(fpath, header=None)
        df.columns = df.iloc[0]; df = df.iloc[1:].reset_index(drop=True)
    else:
        df = pd.read_excel(fpath, header=src["header"])
    df['Počet ks']   = pd.to_numeric(df['Počet ks'],   errors='coerce').fillna(0)
    df['Objem [m3]'] = pd.to_numeric(df['Objem [m3]'], errors='coerce').fillna(0)
    filtered = df[(df['Geosize']=='SPO') & (df['Typ distribuce']=='DFR')].copy()
    filtered['_source'] = src["label"]
    return filtered if len(filtered) > 0 else None, src["label"]

# Load all sources
frames = []; loaded = []; missing = []
for src in DATA_SOURCES:
    df_s, label = load_source(src)
    if df_s is not None:
        frames.append(df_s); loaded.append(label)
    else:
        missing.append(label)

df_raw = pd.concat(frames, ignore_index=True) if frames else None

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 📦 Spracovanie DFR cez AS")

# Source info bar
if frames:
    src_parts = []
    for src_label in loaded:
        n = int((df_raw['_source'] == src_label).sum())
        src_parts.append(f"**{src_label}**: {n:,} záz.")
    st.markdown(
        '<div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:8px;'
        'padding:8px 14px;font-size:12px;color:#3730a3;margin-bottom:8px">'
        '📂 Načítané zdroje: ' + '  ·  '.join(src_parts) + '</div>',
        unsafe_allow_html=True
    )

# Show data source status in sidebar
with st.sidebar:
    st.markdown("### 📂 Zdroje dát")
    for lbl in loaded:
        st.markdown(f"✅ {lbl}")
    for lbl in missing:
        st.markdown(f"⚠️ {lbl} *(nenájdený)*")

if df_raw is None:
    st.error("Žiadne dátové súbory sa nenašli. Skontrolujte priečinok.")
    st.stop()

# ── Compute ────────────────────────────────────────────────────────────────────
r = compute(df_raw, thresh, rate, czk, price_czk)
mdf = r['monthly']

# ══════════════════════════════════════════════════════════════════════════════
# HERO: ÚSPORA — veľká zelená karta
# ══════════════════════════════════════════════════════════════════════════════
col_hero, col_costs = st.columns([1.4, 1])

with col_hero:
    st.markdown(f"""
    <div class="savings-hero">
        <p class="sh-label">CELKOVÁ ÚSPORA  ·  celé obdobie  ·  {r['n_total']:,} záznamov</p>
        <p class="sh-amount">{r['sav']:,.0f} €</p>
        <p class="sh-sub">{r['sav_czk']:,.0f} Kč</p>
        <span class="sh-pct">−{r['sav_pct']} %</span>
        &nbsp;&nbsp;
        <span style="font-size:15px;opacity:0.75">oproti súčasnému procesu</span>
    </div>
    """, unsafe_allow_html=True)

    # Breakdown bars under the hero
    pct_proc = round(r['sav_mzd']/r['sav']*100,1) if r['sav']>0 else 0
    pct_dop  = round(r['sav_pal']/r['sav']*100,1) if r['sav']>0 else 0

    for label, pct, color, eur_val, czk_val in [
        ("Proces (mzdové náklady)", pct_proc, "#2E75B6", r['sav_mzd'], round(r['sav_mzd']*czk,0)),
        ("Doprava (náklady na palety)", pct_dop, "#E67E22", r['sav_pal'], round(r['sav_pal']*czk,0)),
    ]:
        st.markdown(f"""
        <div class="breakdown-row">
            <div class="breakdown-label">
                <span>{label}</span>
                <span style="font-weight:600">{eur_val:,.0f} €  ·  {czk_val:,.0f} Kč  ·  {pct}%</span>
            </div>
            <div class="bar-track">
                <div class="bar-fill" style="width:{pct}%;background:{color}">{pct}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with col_costs:
    st.markdown(f"""
    <div class="cost-box old">
        <p class="clabel">🔴 Súčasný proces</p>
        <p class="cval">{r['c_tot_old']:,.0f} €</p>
        <p class="csub">{r['c_tot_old']*czk:,.0f} Kč</p>
        <hr style="border-color:#F09595;margin:10px 0">
        <p class="cdetail">Mzdové: {r['c_mzd_old']:,.0f} €</p>
        <p class="cdetail">Palety ({r['n_pal_old']} ks): {r['c_pal_old']:,.0f} €</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="cost-box new">
        <p class="clabel">🟢 Nový proces  (limit {thresh} ks)</p>
        <p class="cval">{r['c_tot_new']:,.0f} €</p>
        <p class="csub">{r['c_tot_new']*czk:,.0f} Kč</p>
        <hr style="border-color:#5DCAA5;margin:10px 0">
        <p class="cdetail">Mzdové: {r['c_mzd_new']:,.0f} €</p>
        <p class="cdetail">Palety ({r['n_pal_new']} ks): {r['c_pal_new']:,.0f} €</p>
    </div>
    """, unsafe_allow_html=True)

# ── Mini KPIs ──────────────────────────────────────────────────────────────────

# ── Vývojové diagramy procesov ────────────────────────────────────────────────
st.markdown('<p class="section-title">VÝVOJOVÉ DIAGRAMY PROCESOV</p>', unsafe_allow_html=True)

tab_d1, tab_d2 = st.tabs(["🔴 Súčasný proces", "🟢 Nový proces"])

with tab_d1:
    st.markdown("""
    <svg width="100%" viewBox="0 0 680 520" role="img" style="max-width:680px;display:block;margin:0 auto">
    <title>Súčasný proces DFR — 5 krokov</title>
    <defs><marker id="a1" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#888" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>
    <rect x="40" y="12" width="600" height="36" rx="8" fill="#9B2C2C"/>
    <text x="340" y="30" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#FFFFFF">Súčasný proces — 5 krokov  ·  223 s / záz. + odvoz</text>
    <rect x="200" y="72" width="280" height="52" rx="8" fill="#F1EFE8" stroke="#B4B2A9" stroke-width="0.5"/>
    <text x="340" y="92" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">1. Naskladnenie + štítok</text>
    <text x="340" y="110" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">20 s / záznam</text>
    <line x1="340" y1="124" x2="340" y2="144" stroke="#888" stroke-width="1" marker-end="url(#a1)"/>
    <rect x="200" y="144" width="280" height="52" rx="8" fill="#F1EFE8" stroke="#B4B2A9" stroke-width="0.5"/>
    <text x="340" y="164" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">2. Uloženie do regálu</text>
    <text x="340" y="182" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">15 s / záznam</text>
    <line x1="340" y1="196" x2="340" y2="216" stroke="#888" stroke-width="1" marker-end="url(#a1)"/>
    <rect x="200" y="216" width="280" height="52" rx="8" fill="#FCE8E8" stroke="#E24B4A" stroke-width="1.5"/>
    <text x="340" y="236" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#9B2C2C">3. Zozbieranie z portov ⚠</text>
    <text x="340" y="254" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#A32D2D">180 s / záz.  ·  83 % celkového času</text>
    <line x1="340" y1="268" x2="340" y2="288" stroke="#888" stroke-width="1" marker-end="url(#a1)"/>
    <rect x="200" y="288" width="280" height="52" rx="8" fill="#F1EFE8" stroke="#B4B2A9" stroke-width="0.5"/>
    <text x="340" y="308" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">4. Skenovanie + paleta</text>
    <text x="340" y="326" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">8 s / záznam</text>
    <line x1="340" y1="340" x2="340" y2="360" stroke="#888" stroke-width="1" marker-end="url(#a1)"/>
    <rect x="200" y="360" width="280" height="52" rx="8" fill="#FAEEDA" stroke="#EF9F27" stroke-width="0.5"/>
    <text x="340" y="380" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#633806">5. Odvoz palety</text>
    <text x="340" y="398" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#854F0B">300 s / paletu  ·  fill faktor 70 %</text>
    <rect x="200" y="432" width="280" height="36" rx="18" fill="#9B2C2C"/>
    <text x="340" y="450" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="13" font-weight="500" fill="#FFFFFF">Celk. náklady:  28 544 €  ·  693 338 Kč</text>
    </svg>
    """, unsafe_allow_html=True)

with tab_d2:
    st.markdown("""
    <svg width="100%" viewBox="0 0 680 820" role="img">
    <title>Novy proces DFR cez AS</title>
    <defs><marker id="a2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#888" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>

    <!-- IT priprava -->
    <rect x="40" y="12" width="600" height="150" rx="10" fill="none" stroke="#888" stroke-width="1" stroke-dasharray="5 4" opacity="0.5"/>
    <text x="56" y="28" font-family="sans-serif" font-size="11" fill="#888">Jednorazova priprava</text>
    <rect x="56" y="36" width="568" height="34" rx="7" fill="#534AB7"/>
    <text x="340" y="53" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="13" font-weight="500" fill="#FFFFFF">IT priprava systemu</text>
    <rect x="80" y="84" width="210" height="50" rx="7" fill="#EEEDFE" stroke="#AFA9EC" stroke-width="0.5"/>
    <text x="185" y="103" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="13" font-weight="500" fill="#3C3489">Nastavenie BINov</text>
    <text x="185" y="121" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#534AB7">IT zmena konfigurácie</text>
    <line x1="290" y1="109" x2="328" y2="109" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>
    <rect x="328" y="84" width="232" height="50" rx="7" fill="#EEEDFE" stroke="#AFA9EC" stroke-width="0.5"/>
    <text x="444" y="103" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="13" font-weight="500" fill="#3C3489">Expedicna jobline</text>
    <text x="444" y="121" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#534AB7">Vytvorenie v systeme</text>
    <line x1="340" y1="162" x2="340" y2="182" stroke="#888" stroke-width="1" stroke-dasharray="4 3" marker-end="url(#a2)" opacity="0.5"/>
    <text x="356" y="174" font-family="sans-serif" font-size="11" fill="#888">system pripraveny</text>

    <!-- Operacny proces header -->
    <rect x="40" y="188" width="600" height="604" rx="10" fill="none" stroke="#888" stroke-width="1" stroke-dasharray="5 4" opacity="0.5"/>
    <text x="56" y="204" font-family="sans-serif" font-size="11" fill="#888">Opakovany proces</text>
    <rect x="56" y="210" width="568" height="34" rx="7" fill="#085041"/>
    <text x="340" y="227" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="13" font-weight="500" fill="#FFFFFF">Novy operacny proces — AS system</text>

    <!-- Step 1 -->
    <rect x="200" y="262" width="280" height="50" rx="8" fill="#F1EFE8" stroke="#B4B2A9" stroke-width="0.5"/>
    <text x="340" y="281" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="13" font-weight="500" fill="#444441">1. Naskladnenie do AS</text>
    <text x="340" y="299" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#5F5E5A">20 s / zaznam — vsetky zaznamy</text>
    <line x1="340" y1="312" x2="340" y2="330" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>

    <!-- Decision diamond -->
    <polygon points="340,330 430,366 340,402 250,366" fill="#FFFBE6" stroke="#F59F00" stroke-width="1.5"/>
    <text x="340" y="360" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="13" font-weight="500" fill="#2d3748">Pocet kusov?</text>
    <text x="340" y="378" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#666">limit AS</text>

    <!-- Branch labels -->
    <text x="148" y="412" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#085041" font-weight="500">pod limit</text>
    <text x="532" y="412" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#744210" font-weight="500">na limite / nad</text>
    <path d="M250 366 L130 366 L130 440" fill="none" stroke="#888" stroke-width="1" marker-end="url(#a2)" opacity="0.6"/>
    <path d="M430 366 L550 366 L550 440" fill="none" stroke="#888" stroke-width="1" marker-end="url(#a2)" opacity="0.6"/>

    <!-- KLT vetva -->
    <rect x="58" y="420" width="144" height="22" rx="5" fill="#085041"/>
    <text x="130" y="431" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" font-weight="500" fill="#9FE1CB">KLT vetva</text>

    <rect x="58" y="440" width="144" height="50" rx="7" fill="#E1F5EE" stroke="#5DCAA5" stroke-width="0.5"/>
    <text x="130" y="459" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" font-weight="500" fill="#085041">2. Pikovanie do BINu</text>
    <text x="130" y="477" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#0F6E56">8 s / zaznam</text>
    <line x1="130" y1="490" x2="130" y2="506" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>

    <rect x="58" y="506" width="144" height="50" rx="7" fill="#E1F5EE" stroke="#5DCAA5" stroke-width="0.5"/>
    <text x="130" y="525" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" font-weight="500" fill="#085041">3. Sort nakladka</text>
    <text x="130" y="543" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#0F6E56">15 s / KLT</text>
    <line x1="130" y1="556" x2="130" y2="572" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>

    <rect x="58" y="572" width="144" height="50" rx="7" fill="#E1F5EE" stroke="#085041" stroke-width="1.5"/>
    <text x="130" y="591" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" font-weight="500" fill="#085041">Dopravnik</text>
    <text x="130" y="609" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#0F6E56">0 s odvoz</text>
    <line x1="130" y1="622" x2="130" y2="638" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>

    <rect x="58" y="638" width="144" height="32" rx="16" fill="#085041"/>
    <text x="130" y="654" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" font-weight="500" fill="#FFFFFF">43 s + sort · 0 odvoz</text>

    <!-- Paleta vetva -->
    <rect x="478" y="420" width="144" height="22" rx="5" fill="#744210"/>
    <text x="550" y="431" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" font-weight="500" fill="#FCD34D">Paleta vetva</text>

    <rect x="478" y="440" width="144" height="50" rx="7" fill="#FAEEDA" stroke="#EF9F27" stroke-width="0.5"/>
    <text x="550" y="459" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" font-weight="500" fill="#633806">2. Ulozenie do regalu</text>
    <text x="550" y="477" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#854F0B">15 s / zaznam</text>
    <line x1="550" y1="490" x2="550" y2="506" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>

    <rect x="478" y="506" width="144" height="50" rx="7" fill="#FCE8E8" stroke="#F09595" stroke-width="0.5"/>
    <text x="550" y="525" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" font-weight="500" fill="#9B2C2C">3. Zozbieranie</text>
    <text x="550" y="543" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#A32D2D">180 s / zaznam</text>
    <line x1="550" y1="556" x2="550" y2="572" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>

    <rect x="478" y="572" width="144" height="50" rx="7" fill="#FAEEDA" stroke="#EF9F27" stroke-width="0.5"/>
    <text x="550" y="591" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" font-weight="500" fill="#633806">4. Skenovanie</text>
    <text x="550" y="609" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#854F0B">8 s / zaznam</text>
    <line x1="550" y1="622" x2="550" y2="638" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>

    <rect x="478" y="638" width="144" height="50" rx="7" fill="#FAEEDA" stroke="#744210" stroke-width="1.5"/>
    <text x="550" y="657" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" font-weight="500" fill="#633806">5. Odvoz palety</text>
    <text x="550" y="675" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" fill="#854F0B">300 s / paletu</text>
    <line x1="550" y1="688" x2="550" y2="704" stroke="#888" stroke-width="1" marker-end="url(#a2)"/>

    <rect x="478" y="704" width="144" height="32" rx="16" fill="#744210"/>
    <text x="550" y="720" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="11" font-weight="500" fill="#FFFFFF">223 s + odvoz pal.</text>

    <!-- Merge arrows -->
    <path d="M130 670 L130 762 L338 762" fill="none" stroke="#888" stroke-width="0.5" stroke-dasharray="3 3" opacity="0.4"/>
    <path d="M550 736 L550 762 L342 762" fill="none" stroke="#888" stroke-width="0.5" stroke-dasharray="3 3" opacity="0.4" marker-end="url(#a2)"/>

    <!-- Final result -->
    <rect x="200" y="772" width="280" height="34" rx="17" fill="#085041"/>
    <text x="340" y="789" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="13" font-weight="500" fill="#FFFFFF">Uspora 8 498 EUR · 29,8 %</text>

    </svg>
    """, unsafe_allow_html=True)


st.markdown('<p class="section-title">PREHĽAD OBJEMOV</p>', unsafe_allow_html=True)
k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
for col, label, val, sub in [
    (k1, "Záznamy celkom", f"{r['n_total']:,}", "SPO + DFR"),
    (k2, "KLT záznamy", f"{r['n_klt']:,}", f"{round(r['n_klt']/r['n_total']*100,1)}% z celku"),
    (k3, "KLT ks", f"{r['n_klts']:,}", "→ dopravník"),
    (k4, "Paleta záznamy", f"{r['n_pal']:,}", f"{round(r['n_pal']/r['n_total']*100,1)}% z celku"),
    (k5, "Palety starý", f"{r['n_pal_old']:,}", "fill 70%"),
    (k6, "Palety nový", f"{r['n_pal_new']:,}", f"−{r['n_pal_old']-r['n_pal_new']} paliet"),
    (k7, "Úspora / záznam", f"{round(r['sav']/r['n_total'],2):.2f} €", f"{round(r['sav']/r['n_total']*czk,1):.1f} Kč"),
]:
    col.markdown(f"""<div class="mini-kpi"><p class="ml">{label}</p><p class="mv">{val}</p>
    <p class="ms">{sub}</p></div>""", unsafe_allow_html=True)


# ── Rozpad výpočtu úspory ─────────────────────────────────────────────────────
st.markdown('<p class="section-title">ROZPAD VÝPOČTU ÚSPORY</p>', unsafe_allow_html=True)

col_proc, col_dop, col_cnt = st.columns(3)

# ── PROCES ──────────────────────────────────────────────────────────────────
with col_proc:
    t_old_s = r['n_total']*216 + r['n_pal_old']*300
    t_new_s = (r['n_klt']*20 + r['n_klt']*15 + r['n_klts']*15
               + r['n_pal']*216 + r['n_pal_new']*300)
    t_old_h = t_old_s / 3600; t_new_h = t_new_s / 3600

    st.markdown(f"""
    <div style="background:#fff5f5;border:1.5px solid #feb2b2;border-radius:10px;padding:1rem 1.2rem">
      <p style="font-size:11px;font-weight:700;color:#9b2c2c;text-transform:uppercase;letter-spacing:.5px;margin:0 0 10px">
        🔧 PROCES — mzdové náklady</p>

      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <tr style="border-bottom:1px solid #fed7d7">
          <td style="padding:4px 0;color:#555;font-weight:600">Krok</td>
          <td style="padding:4px 0;text-align:right;color:#9b2c2c;font-weight:600">Starý<br><span style="font-size:10px;font-weight:400">({r['n_total']:,} záz.)</span></td>
          <td style="padding:4px 0;text-align:right;color:#2b4c7e;font-weight:600">Nový KLT<br><span style="font-size:10px;font-weight:400">({r['n_klt']:,} záz.)</span></td>
          <td style="padding:4px 0;text-align:right;color:#744210;font-weight:600">Nový Paleta<br><span style="font-size:10px;font-weight:400">({r['n_pal']:,} záz.)</span></td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Naskladnenie</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c">{r['n_total']:,}×20s</td>
          <td style="padding:3px 0;text-align:right;color:#2b4c7e">{r['n_klt']:,}×20s</td>
          <td style="padding:3px 0;text-align:right;color:#744210">{r['n_pal']:,}×20s</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Uloženie do regálu</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c">{r['n_total']:,}×15s</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#744210">{r['n_pal']:,}×15s</td>
        </tr>
        <tr style="background:#fff0f0">
          <td style="padding:3px 0;color:#9b2c2c;font-weight:600">Zozbieranie ⚠️</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c;font-weight:600">{r['n_total']:,}×180s</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#744210;font-weight:600">{r['n_pal']:,}×180s</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#276749;font-weight:600">Pikovanie do BINu ✓</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#276749;font-weight:600">{r['n_klt']:,}×8s</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Skenovanie</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c">{r['n_total']:,}×8s</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#744210">{r['n_pal']:,}×8s</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#276749">Sort nakládka (15s/KLT) ✓</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#276749">{r['n_klts']:,}×15s</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
        </tr>
        <tr style="background:#fff8f0">
          <td style="padding:3px 0;color:#744210;font-weight:600">Odvoz palety</td>
          <td style="padding:3px 0;text-align:right;color:#744210;font-weight:600">{r['n_pal_old']:,}×300s</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#744210;font-weight:600">{r['n_pal_new']:,}×300s</td>
        </tr>
        <tr style="border-top:1px solid #fed7d7">
          <td style="padding:3px 0;color:#333">Čas/záz. (ops)</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c;font-weight:600">223s + odvoz</td>
          <td style="padding:3px 0;text-align:right;color:#2b4c7e;font-weight:600">43s + sort</td>
          <td style="padding:3px 0;text-align:right;color:#744210;font-weight:600">223s + odvoz</td>
        </tr>
        <tr style="border-top:1.5px solid #feb2b2">
          <td style="padding:5px 0;color:#333;font-weight:600">Čas celkom</td>
          <td style="padding:5px 0;text-align:right;color:#9b2c2c;font-weight:600">{t_old_h:.1f} hod</td>
          <td colspan="2" style="padding:5px 0;text-align:right;color:#276749;font-weight:600">{t_new_h:.1f} hod (KLT+Pal)</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Priame ({rate:.0f} €/hod)</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c">{r['c_dir_old']:,.0f} €</td>
          <td colspan="2" style="padding:3px 0;text-align:right;color:#276749">{r['c_dir_new']:,.0f} €</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Opportunity cost</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c">{r['c_oc_old']:,.0f} €</td>
          <td colspan="2" style="padding:3px 0;text-align:right;color:#276749">{r['c_oc_new']:,.0f} €</td>
        </tr>
        <tr style="border-top:1.5px solid #feb2b2">
          <td style="padding:5px 0;font-weight:700;color:#333">Proces spolu</td>
          <td style="padding:5px 0;text-align:right;font-weight:700;color:#9b2c2c">{r['c_mzd_old']:,.0f} €</td>
          <td colspan="2" style="padding:5px 0;text-align:right;font-weight:700;color:#276749">{r['c_mzd_new']:,.0f} €</td>
        </tr>
      </table>
      <div style="background:#9b2c2c;border-radius:6px;padding:6px 10px;margin-top:10px;text-align:center">
        <span style="color:white;font-weight:700;font-size:14px">Úspora proces: {r['sav_mzd']:,.0f} €
        &nbsp;·&nbsp; {round(r['sav_mzd']*czk):,.0f} Kč</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── DOPRAVA ─────────────────────────────────────────────────────────────────
with col_dop:
    n_pal_old_bez = round(r['n_pal_old'] / FILL_FACTOR)  # bez fill korekcie
    st.markdown(f"""
    <div style="background:#fffbeb;border:1.5px solid #fbd38d;border-radius:10px;padding:1rem 1.2rem">
      <p style="font-size:11px;font-weight:700;color:#744210;text-transform:uppercase;letter-spacing:.5px;margin:0 0 10px">
        🚛 DOPRAVA — náklady na palety</p>

      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <tr style="border-bottom:1px solid #fbd38d">
          <td style="padding:4px 0;color:#555">Parameter</td>
          <td style="padding:4px 0;text-align:right;color:#555">Starý</td>
          <td style="padding:4px 0;text-align:right;color:#555">Nový</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Kapacita palety</td>
          <td style="padding:3px 0;text-align:right;color:#333">{PAL_M3_OLD:.3f} m³<br><span style="font-size:10px;color:#888">(fill 70%)</span></td>
          <td style="padding:3px 0;text-align:right;color:#276749">{PAL_M3_NEW:.2f} m³<br><span style="font-size:10px;color:#888">(KLT = 100%)</span></td>
        </tr>
        <tr style="background:#fffde7">
          <td style="padding:3px 0;color:#744210;font-weight:600">Počet paliet</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c;font-weight:600">{r['n_pal_old']:,}</td>
          <td style="padding:3px 0;text-align:right;color:#276749;font-weight:600">{r['n_pal_new']:,}</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#555;font-size:11px">&nbsp;&nbsp;bez fill korekcie</td>
          <td style="padding:3px 0;text-align:right;color:#888;font-size:11px">{n_pal_old_bez:,}</td>
          <td style="padding:3px 0;text-align:right;color:#888;font-size:11px">—</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#555;font-size:11px">&nbsp;&nbsp;fill korekcia</td>
          <td style="padding:3px 0;text-align:right;color:#9b2c2c;font-size:11px">+{r['n_pal_old']-n_pal_old_bez:,} pal.</td>
          <td style="padding:3px 0;text-align:right;color:#888;font-size:11px">—</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Ušetrené palety</td>
          <td colspan="2" style="padding:3px 0;text-align:right;color:#276749;font-weight:600">−{r['n_pal_old']-r['n_pal_new']:,} paliet</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Cena / paleta</td>
          <td colspan="2" style="padding:3px 0;text-align:right;color:#333">{price_czk:.0f} Kč = {price_czk/czk:.4f} €</td>
        </tr>
        <tr style="border-top:1.5px solid #fbd38d">
          <td style="padding:5px 0;font-weight:700;color:#333">Doprava spolu</td>
          <td style="padding:5px 0;text-align:right;font-weight:700;color:#9b2c2c">{r['c_pal_old']:,.0f} €</td>
          <td style="padding:5px 0;text-align:right;font-weight:700;color:#276749">{r['c_pal_new']:,.0f} €</td>
        </tr>
      </table>
      <div style="background:#744210;border-radius:6px;padding:6px 10px;margin-top:10px;text-align:center">
        <span style="color:white;font-weight:700;font-size:14px">Úspora doprava: {r['sav_pal']:,.0f} €
        &nbsp;·&nbsp; {round(r['sav_pal']*czk):,.0f} Kč</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── POČTY ───────────────────────────────────────────────────────────────────
with col_cnt:
    st.markdown(f"""
    <div style="background:#f0fff4;border:1.5px solid #9ae6b4;border-radius:10px;padding:1rem 1.2rem">
      <p style="font-size:11px;font-weight:700;color:#276749;text-transform:uppercase;letter-spacing:.5px;margin:0 0 10px">
        📦 POČTY — záznamy a objem</p>

      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <tr style="border-bottom:1px solid #9ae6b4">
          <td style="padding:4px 0;color:#555">Ukazovateľ</td>
          <td style="padding:4px 0;text-align:right;color:#555">Starý</td>
          <td style="padding:4px 0;text-align:right;color:#555">Nový</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Záznamy celkom</td>
          <td colspan="2" style="padding:3px 0;text-align:right;color:#333;font-weight:600">{r['n_total']:,}</td>
        </tr>
        <tr style="background:#f0fff4">
          <td style="padding:3px 0;color:#276749;font-weight:600">→ KLT záznamy</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#276749;font-weight:600">{r['n_klt']:,}</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#555;font-size:11px">&nbsp;&nbsp;KLT kusov</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#276749;font-size:11px">{r['n_klts']:,} KLT</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#555;font-size:11px">&nbsp;&nbsp;KLT záz. (%)</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#276749;font-size:11px">{round(r['n_klt']/r['n_total']*100,1)}%</td>
        </tr>
        <tr style="background:#f0fff4">
          <td style="padding:3px 0;color:#744210;font-weight:600">→ Paleta záznamy</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#744210;font-weight:600">{r['n_pal']:,}</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#555;font-size:11px">&nbsp;&nbsp;Paleta záz. (%)</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#744210;font-size:11px">{round(r['n_pal']/r['n_total']*100,1)}%</td>
        </tr>
        <tr style="border-top:1px solid #9ae6b4">
          <td style="padding:4px 0;color:#333">Palety starý</td>
          <td style="padding:4px 0;text-align:right;color:#9b2c2c;font-weight:600">{r['n_pal_old']:,}</td>
          <td style="padding:4px 0;text-align:right;color:#888">—</td>
        </tr>
        <tr>
          <td style="padding:3px 0;color:#333">Palety nový</td>
          <td style="padding:3px 0;text-align:right;color:#888">—</td>
          <td style="padding:3px 0;text-align:right;color:#276749;font-weight:600">{r['n_pal_new']:,}</td>
        </tr>
        <tr style="border-top:1.5px solid #9ae6b4">
          <td style="padding:5px 0;font-weight:700;color:#333">Rozdiel paliet</td>
          <td colspan="2" style="padding:5px 0;text-align:right;font-weight:700;color:#276749">−{r['n_pal_old']-r['n_pal_new']:,} paliet</td>
        </tr>
      </table>
      <div style="background:#276749;border-radius:6px;padding:6px 10px;margin-top:10px;text-align:center">
        <span style="color:white;font-weight:700;font-size:14px">ÚSPORA SPOLU: {r['sav']:,.0f} €
        &nbsp;·&nbsp; {r['sav_czk']:,.0f} Kč</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── Monthly ────────────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">MESAČNÝ PREHĽAD</p>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📊 Grafy", "📋 Tabuľka"])

with tab1:
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("**Mesačná úspora — Proces vs Doprava (€)**")
        chart_sav = mdf[['Mesiac','Úspora proces (€)','Úspora doprava (€)']].set_index('Mesiac')
        st.bar_chart(chart_sav, color=['#2E75B6','#E67E22'], height=280)
    with col_g2:
        st.markdown("**Mesačné celkové náklady: starý vs nový (€)**")
        chart_costs = mdf[['Mesiac','Nákl. starý (€)','Nákl. nový (€)']].set_index('Mesiac')
        st.bar_chart(chart_costs, color=['#C0392B','#1E5631'], height=280)

with tab2:
    # Header groups
    hdr_html = """
    <div style="overflow-x:auto;border-radius:8px;border:1px solid #e2e8f0;margin-top:4px">
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead>
        <tr>
          <th rowspan="2" style="padding:7px 10px;background:#2d3748;color:#fff;font-weight:600;border-right:1px solid #4a5568">Mesiac</th>
          <th rowspan="2" style="padding:7px 10px;background:#2d3748;color:#fff;font-weight:600;border-right:1px solid #4a5568;white-space:nowrap">Záznamy</th>
          <th colspan="3" style="padding:7px 10px;background:#2b4c7e;color:#fff;font-weight:600;text-align:center;border-right:1px solid #4a5568">KLT</th>
          <th colspan="3" style="padding:7px 10px;background:#744210;color:#fff;font-weight:600;text-align:center;border-right:1px solid #4a5568">Palety</th>
          <th colspan="2" style="padding:7px 10px;background:#9b2c2c;color:#fff;font-weight:600;text-align:center;border-right:1px solid #4a5568">Náklady starý</th>
          <th colspan="2" style="padding:7px 10px;background:#276749;color:#fff;font-weight:600;text-align:center;border-right:1px solid #4a5568">Náklady nový</th>
          <th colspan="3" style="padding:7px 10px;background:#1E5631;color:#fff;font-weight:600;text-align:center">Úspora</th>
        </tr>
        <tr>
          <th style="padding:5px 8px;background:#3a6186;color:#fff;font-weight:500;white-space:nowrap">záznamy</th>
          <th style="padding:5px 8px;background:#3a6186;color:#fff;font-weight:500;white-space:nowrap">KLT ks</th>
          <th style="padding:5px 8px;background:#3a6186;color:#fff;font-weight:500;white-space:nowrap;border-right:1px solid #4a5568">záz. %</th>
          <th style="padding:5px 8px;background:#975a16;color:#fff;font-weight:500;white-space:nowrap">starý</th>
          <th style="padding:5px 8px;background:#975a16;color:#fff;font-weight:500;white-space:nowrap">nový</th>
          <th style="padding:5px 8px;background:#975a16;color:#fff;font-weight:500;white-space:nowrap;border-right:1px solid #4a5568">rozdiel</th>
          <th style="padding:5px 8px;background:#c53030;color:#fff;font-weight:500;white-space:nowrap">mzdové</th>
          <th style="padding:5px 8px;background:#c53030;color:#fff;font-weight:500;white-space:nowrap;border-right:1px solid #4a5568">doprava</th>
          <th style="padding:5px 8px;background:#2f855a;color:#fff;font-weight:500;white-space:nowrap">mzdové</th>
          <th style="padding:5px 8px;background:#2f855a;color:#fff;font-weight:500;white-space:nowrap;border-right:1px solid #4a5568">doprava</th>
          <th style="padding:5px 8px;background:#276749;color:#fff;font-weight:500;white-space:nowrap">proces €</th>
          <th style="padding:5px 8px;background:#276749;color:#fff;font-weight:500;white-space:nowrap">doprava €</th>
          <th style="padding:5px 8px;background:#1E5631;color:#fff;font-weight:700;white-space:nowrap">SPOLU €</th>
        </tr>
      </thead>
      <tbody>"""

    rows_html = ""
    totals = {k: 0 for k in ['Záznamy','KLT záz.','Palety starý','Palety nový',
                               'up_proc','up_dop','up_tot']}
    max_sav = mdf['Úspora (€)'].max()
    min_sav = mdf['Úspora (€)'].min()

    for _, row in mdf.iterrows():
        is_partial = row['Mesiac'] in ('2025-09','2026-05')
        is_best    = row['Úspora (€)'] == max_sav
        is_worst   = row['Úspora (€)'] == min_sav
        bg = "#fffde7" if is_partial else ("#f0fff4" if is_best else ("#fff5f5" if is_worst else "#ffffff"))

        n_klt_pct  = round(row['KLT záz.']/row['Záznamy']*100,0) if row['Záznamy']>0 else 0
        pal_diff   = row['Palety starý'] - row['Palety nový']

        # back-calculate mzdové and doprava costs per month from stored values
        sav_proc   = row['Úspora proces (€)']
        sav_dop    = row['Úspora doprava (€)']
        nákl_st_mzd = row['Nákl. starý (€)'] - row['Pal. nákl. starý (€)'] if 'Pal. nákl. starý (€)' in mdf.columns else row['Nákl. starý (€)'] - row['Palety starý'] * (price_czk/czk)
        nákl_st_dop = row['Palety starý'] * (price_czk/czk)
        nákl_nv_mzd = row['Nákl. nový (€)'] - row['Pal. nákl. nový (€)'] if 'Pal. nákl. nový (€)' in mdf.columns else row['Nákl. nový (€)'] - row['Palety nový'] * (price_czk/czk)
        nákl_nv_dop = row['Palety nový'] * (price_czk/czk)

        part_note = " *" if is_partial else ""
        cells = f"""
          <td style="padding:6px 8px;color:#2d3748;font-weight:{'700' if is_partial else '400'};border-right:1px solid #e2e8f0;white-space:nowrap">{row['Mesiac']}{part_note}</td>
          <td style="padding:6px 8px;color:#2d3748;text-align:right;border-right:1px solid #e2e8f0">{row['Záznamy']:,}</td>
          <td style="padding:6px 8px;color:#2b4c7e;text-align:right">{row['KLT záz.']:,}</td>
          <td style="padding:6px 8px;color:#2b4c7e;text-align:right">{row['KLT ks']:,}</td>
          <td style="padding:6px 8px;color:#2b4c7e;text-align:right;border-right:1px solid #e2e8f0">{n_klt_pct:.0f}%</td>
          <td style="padding:6px 8px;color:#9b2c2c;text-align:right">{row['Palety starý']:,}</td>
          <td style="padding:6px 8px;color:#276749;text-align:right">{row['Palety nový']:,}</td>
          <td style="padding:6px 8px;color:#744210;text-align:right;font-weight:600;border-right:1px solid #e2e8f0">−{pal_diff:,}</td>
          <td style="padding:6px 8px;color:#9b2c2c;text-align:right">{nákl_st_mzd:,.0f} €</td>
          <td style="padding:6px 8px;color:#9b2c2c;text-align:right;border-right:1px solid #e2e8f0">{nákl_st_dop:,.0f} €</td>
          <td style="padding:6px 8px;color:#276749;text-align:right">{nákl_nv_mzd:,.0f} €</td>
          <td style="padding:6px 8px;color:#276749;text-align:right;border-right:1px solid #e2e8f0">{nákl_nv_dop:,.0f} €</td>
          <td style="padding:6px 8px;color:#276749;text-align:right">{sav_proc:,.0f} €</td>
          <td style="padding:6px 8px;color:#744210;text-align:right">{sav_dop:,.0f} €</td>
          <td style="padding:6px 8px;color:#1E5631;text-align:right;font-weight:700">{row['Úspora (€)']:,.0f} €</td>"""

        rows_html += f'<tr style="background:{bg}">{cells}</tr>'

        totals['Záznamy']      += row['Záznamy']
        totals['KLT záz.']     += row['KLT záz.']
        totals['Palety starý'] += row['Palety starý']
        totals['Palety nový']  += row['Palety nový']
        totals['up_proc']      += sav_proc
        totals['up_dop']       += sav_dop
        totals['up_tot']       += row['Úspora (€)']

    # Totals row
    tot_pal_diff = totals['Palety starý'] - totals['Palety nový']
    rows_html += f"""<tr style="background:#1E5631">
      <td style="padding:7px 8px;color:#fff;font-weight:700;border-right:1px solid #2f855a">SPOLU</td>
      <td style="padding:7px 8px;color:#fff;font-weight:700;text-align:right;border-right:1px solid #2f855a">{totals['Záznamy']:,}</td>
      <td style="padding:7px 8px;color:#9ae6b4;text-align:right;font-weight:600">{totals['KLT záz.']:,}</td>
      <td style="padding:7px 8px;color:#9ae6b4;text-align:right">—</td>
      <td style="padding:7px 8px;color:#9ae6b4;text-align:right;border-right:1px solid #2f855a">—</td>
      <td style="padding:7px 8px;color:#fbd38d;text-align:right;font-weight:600">{totals['Palety starý']:,}</td>
      <td style="padding:7px 8px;color:#9ae6b4;text-align:right;font-weight:600">{totals['Palety nový']:,}</td>
      <td style="padding:7px 8px;color:#fbd38d;text-align:right;font-weight:700;border-right:1px solid #2f855a">−{tot_pal_diff:,}</td>
      <td colspan="2" style="padding:7px 8px;color:#fbd38d;text-align:right;border-right:1px solid #2f855a">—</td>
      <td colspan="2" style="padding:7px 8px;color:#9ae6b4;text-align:right;border-right:1px solid #2f855a">—</td>
      <td style="padding:7px 8px;color:#fff;text-align:right;font-weight:600">{totals['up_proc']:,.0f} €</td>
      <td style="padding:7px 8px;color:#fbd38d;text-align:right;font-weight:600">{totals['up_dop']:,.0f} €</td>
      <td style="padding:7px 8px;color:#fff;text-align:right;font-weight:700;font-size:13px">{totals['up_tot']:,.0f} €</td>
    </tr>"""

    st.markdown(hdr_html + rows_html + "</tbody></table></div>", unsafe_allow_html=True)
    st.caption("* Neúplné mesiace (sep 2025, máj 2026)  ·  Zelená = najväčšia úspora  ·  Ružová = najmenšia")

# ── Sensitivity ────────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">CITLIVOSŤ PRAHU</p>', unsafe_allow_html=True)
with st.expander(f"Zobraziť porovnanie prahov (aktuálny: {thresh} ks)", expanded=False):
    rows=[]
    for t_val in [5,10,15,20,25,30,40,50,75,100]:
        rv = compute(df_raw, t_val, rate, czk, price_czk)
        rows.append({'Prah (ks)':t_val,'KLT záz.':rv['n_klt'],
            'KLT záz. (%)':f"{rv['n_klt']/rv['n_total']*100:.1f}%",
            'KLT ks':rv['n_klts'],'Palety nový':rv['n_pal_new'],
            'Nákl. nový (€)':rv['c_tot_new'],'Úspora (€)':rv['sav'],
            'Úspora (Kč)':rv['sav_czk'],'Úspora (%)':f"{rv['sav_pct']}%"})
    sdf=pd.DataFrame(rows)
    def hl_curr(row):
        return ['background-color:#DDEEFF;font-weight:bold']*len(row) if row['Prah (ks)']==thresh else ['']*len(row)
    s_cols = list(sdf.columns)
    s_header = "".join(f'<th style="padding:7px 10px;background:#2d3748;color:#fff;font-size:12px;font-weight:600;white-space:nowrap">{c}</th>' for c in s_cols)
    s_rows = ""
    for _, row in sdf.iterrows():
        is_curr = row['Prah (ks)'] == thresh
        bg = "#dbeafe" if is_curr else ("#f7fafc" if int(row['Prah (ks)']) % 2 == 0 else "#ffffff")
        fw_row = "700" if is_curr else "400"
        cells = ""
        for col in s_cols:
            val = row[col]
            if col == 'Nákl. nový (€)': val = f"{val:,.2f} €"
            elif col == 'Úspora (€)': val = f"{val:,.2f} €"
            elif col == 'Úspora (Kč)': val = f"{val:,.0f} Kč"
            elif col == 'KLT ks': val = f"{val:,}"
            fc = "#1e40af" if is_curr else ("#276749" if col in ('Úspora (€)','Úspora (Kč)','Úspora (%)') else "#2d3748")
            cells += f'<td style="padding:6px 10px;color:{fc};font-weight:{fw_row};font-size:12px;border-bottom:1px solid #e2e8f0">{val}</td>'
        s_rows += f'<tr style="background:{bg}">{cells}</tr>'
    st.markdown(f"""
    <div style="overflow-x:auto;border-radius:8px;border:1px solid #e2e8f0">
    <table style="width:100%;border-collapse:collapse">
      <thead><tr>{s_header}</tr></thead>
      <tbody>{s_rows}</tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)

# ── Export ─────────────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">EXPORT</p>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
c1.download_button("⬇️ Mesačný rozpad (CSV)", mdf.to_csv(index=False).encode('utf-8-sig'),
    f"KLT_mesacny_rozpad_prah{thresh}ks.csv", "text/csv", use_container_width=True)
c2.download_button("⬇️ Citlivosť prahu (CSV)", sdf.to_csv(index=False).encode('utf-8-sig') if 'sdf' in dir() else b'',
    "KLT_citlivost.csv", "text/csv", use_container_width=True)

st.markdown("---")
st.caption(f"Spracovanie DFR cez AS · SPO+DFR · Paleta: 24 KLT={PAL_M3_NEW:.2f}m³ · Starý fill 70% · {czk} Kč/€ · {datetime.now().strftime('%d.%m.%Y')}")
