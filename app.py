import streamlit as st
import pandas as pd
import math
from datetime import datetime

st.set_page_config(
    page_title="KLT Plánovanie prepravy",
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

    t_old = n_total*216 + n_pal_old*300
    t_new = n_klt*20 + n_klt*15 + n_klts*15 + n_pal*216 + n_pal_new*300

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
        monthly.append({'Mesiac':month,'Záznamy':len(grp),'KLT záz.':len(mk),'Pal. záz.':len(mp),
            'Palety starý':npa_,'Palety nový':npo_,
            'Nákl. starý (€)':ct_o,'Nákl. nový (€)':ct_n,'Úspora (€)':us,'Úspora (Kč)':round(us*czk,2),
            'Úspora proces (€)':round(cm_o-cm_n,2),'Úspora doprava (€)':round(cp_o-cp_n,2)})

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
    thresh    = st.slider("Prah KLT / Paleta (ks)", 1, 100, 20)
    price_czk = st.number_input("Cena za paletu (Kč)", value=561.0, step=10.0)
    rate      = st.number_input("Sadzba práce (€/hod)", value=15.0, step=0.5)
    czk       = st.number_input("Kurz EUR/CZK", value=24.29, step=0.01)

    st.markdown("---")
    st.markdown("### 📂 Nahrať súbor")
    uploaded = st.file_uploader("Zošit2.xlsx", type=['xlsx'])

    st.markdown("---")
    st.caption(f"Paleta: {KLT_PER_PAL} KLT = {PAL_M3_NEW:.2f} m³  \nStarý fill: 70 % → {PAL_M3_OLD:.3f} m³  \nFiltre: SPO + DFR")

# ── Load data ──────────────────────────────────────────────────────────────────
df_raw = None
if uploaded:
    try:
        df = pd.read_excel(uploaded, header=None)
        df.columns = df.iloc[0]; df = df.iloc[1:].reset_index(drop=True)
        df_raw = df[(df['Geosize']=='SPO') & (df['Typ distribuce']=='DFR')].copy()
        if len(df_raw) == 0:
            st.error("Súbor neobsahuje záznamy SPO + DFR.")
            df_raw = None
    except Exception as e:
        st.error(f"Chyba: {e}"); df_raw = None

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 📦 KLT Plánovanie prepravy")

if df_raw is None:
    st.info("👈 Nahrajte súbor **Zošit2.xlsx** v ľavom paneli.")
    st.markdown("---")
    st.markdown("**Čo uvidíte po nahraní súboru:**")
    cols = st.columns(3)
    for col, (icon, title, desc) in zip(cols, [
        ("💰", "Celková úspora", "Veľká zelená karta s úsporou v € aj Kč — okamžite vidno koľko sa ušetrí"),
        ("📊", "Rozpad nákladov", "Proces vs Doprava — kde presne úspora vzniká"),
        ("📅", "Mesačný prehľad", "Tabuľka a grafy po mesiacoch + citlivosť prahu"),
    ]):
        col.markdown(f"### {icon} {title}\n{desc}")
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
        <p class="clabel">🟢 Nový proces  (prah {thresh} ks)</p>
        <p class="cval">{r['c_tot_new']:,.0f} €</p>
        <p class="csub">{r['c_tot_new']*czk:,.0f} Kč</p>
        <hr style="border-color:#5DCAA5;margin:10px 0">
        <p class="cdetail">Mzdové: {r['c_mzd_new']:,.0f} €</p>
        <p class="cdetail">Palety ({r['n_pal_new']} ks): {r['c_pal_new']:,.0f} €</p>
    </div>
    """, unsafe_allow_html=True)

# ── Mini KPIs ──────────────────────────────────────────────────────────────────
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
    disp = mdf[['Mesiac','Záznamy','KLT záz.','Pal. záz.','Palety starý','Palety nový',
                'Nákl. starý (€)','Nákl. nový (€)','Úspora (€)','Úspora (Kč)']].copy()
    def hl(row):
        if row['Mesiac'] in('2025-09','2026-05'):
            return ['background-color:#fffbe6']*len(row)
        return ['']*len(row)
    st.dataframe(
        disp.style.apply(hl, axis=1)
            .format({'Nákl. starý (€)':'{:,.2f} €','Nákl. nový (€)':'{:,.2f} €',
                     'Úspora (€)':'{:,.2f} €','Úspora (Kč)':'{:,.0f} Kč'})
            .highlight_max(subset=['Úspora (€)'], color='#d4edda')
            .highlight_min(subset=['Úspora (€)'], color='#f8d7da'),
        use_container_width=True, hide_index=True
    )

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
    st.dataframe(
        sdf.style.apply(hl_curr,axis=1)
            .format({'Nákl. nový (€)':'{:,.2f} €','Úspora (€)':'{:,.2f} €',
                     'Úspora (Kč)':'{:,.0f} Kč','KLT ks':'{:,}'}),
        use_container_width=True, hide_index=True
    )

# ── Export ─────────────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">EXPORT</p>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
c1.download_button("⬇️ Mesačný rozpad (CSV)", mdf.to_csv(index=False).encode('utf-8-sig'),
    f"KLT_mesacny_rozpad_prah{thresh}ks.csv", "text/csv", use_container_width=True)
c2.download_button("⬇️ Citlivosť prahu (CSV)", sdf.to_csv(index=False).encode('utf-8-sig') if 'sdf' in dir() else b'',
    "KLT_citlivost.csv", "text/csv", use_container_width=True)

st.markdown("---")
st.caption(f"KLT Plánovanie prepravy · SPO+DFR · Paleta: 24 KLT={PAL_M3_NEW:.2f}m³ · Starý fill 70% · {czk} Kč/€ · {datetime.now().strftime('%d.%m.%Y')}")
