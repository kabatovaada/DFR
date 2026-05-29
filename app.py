import streamlit as st
import pandas as pd
import openpyxl
import math
import io
import json
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KLT Plánovanie prepravy",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
.metric-card {
    background: #f0f4f8;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    border-left: 4px solid #185FA5;
}
.metric-card.green { border-left-color: #1E5631; background: #f0faf3; }
.metric-card.red   { border-left-color: #A32D2D; background: #fdf0f0; }
.metric-card.amber { border-left-color: #854F0B; background: #fdf7f0; }
.metric-label { font-size: 12px; color: #666; margin: 0; }
.metric-value { font-size: 22px; font-weight: 600; margin: 4px 0 0; }
.section-title {
    font-size: 13px; font-weight: 600; color: #1F3864;
    border-bottom: 2px solid #1F3864; padding-bottom: 4px;
    margin: 1.5rem 0 0.75rem;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
KLT_M3       = 0.05
KLT_PER_PAL  = 24
PAL_M3_NEW   = KLT_PER_PAL * KLT_M3        # 1.2 m³
FILL_FACTOR  = 0.70
PAL_M3_OLD   = PAL_M3_NEW * FILL_FACTOR     # 0.84 m³
RATE         = 15.0
CZK          = 24.29
VYKON_STD    = 70
VYKON_DIST   = 60
PRICE_PAL_CZK = 561.0
PRICE_PAL_EUR = round(PRICE_PAL_CZK / CZK, 4)

# ── Helpers ───────────────────────────────────────────────────────────────────
def dir_cost(t_s):  return (t_s / 3600) * RATE
def opp_cost(t_s):  return (t_s / 3600) * (VYKON_STD - VYKON_DIST) / VYKON_STD * RATE

def compute_all(df_raw, thresh):
    df = df_raw.copy()
    df['Počet ks']   = pd.to_numeric(df['Počet ks'],   errors='coerce').fillna(0)
    df['Objem [m3]'] = pd.to_numeric(df['Objem [m3]'], errors='coerce').fillna(0)
    df['preprava']   = df['Počet ks'].apply(lambda x: 'Paleta' if x >= thresh else 'KLT')
    df['month']      = pd.to_datetime(df['Date']).dt.strftime('%Y-%m')

    klt = df[df['preprava'] == 'KLT']
    pal = df[df['preprava'] == 'Paleta']
    n_total = len(df); n_klt = len(klt); n_pal = len(pal)

    old_grp = df.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index()
    old_grp['n_pal'] = old_grp['Objem [m3]'].apply(lambda v: math.ceil(v / PAL_M3_OLD))
    n_pal_old = int(old_grp['n_pal'].sum())

    kg = klt.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index() if n_klt > 0 else pd.DataFrame({'Objem [m3]': []})
    if len(kg) > 0: kg['nk'] = kg['Objem [m3]'].apply(lambda v: math.ceil(v / KLT_M3))
    n_klts = int(kg['nk'].sum()) if len(kg) > 0 else 0

    pg = pal.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index() if n_pal > 0 else pd.DataFrame({'Objem [m3]': []})
    if len(pg) > 0: pg['np'] = pg['Objem [m3]'].apply(lambda v: math.ceil(v / PAL_M3_NEW))
    n_pal_new = int(pg['np'].sum()) if len(pg) > 0 else 0

    t_old = n_total * 216 + n_pal_old * 300
    t_new = n_klt * 20 + n_klt * 15 + n_klts * 15 + n_pal * 216 + n_pal_new * 300

    c_mzd_old = dir_cost(t_old) + opp_cost(t_old)
    c_mzd_new = dir_cost(t_new) + opp_cost(t_new)
    c_pal_old = n_pal_old * PRICE_PAL_EUR
    c_pal_new = n_pal_new * PRICE_PAL_EUR
    c_tot_old = round(c_mzd_old + c_pal_old, 2)
    c_tot_new = round(c_mzd_new + c_pal_new, 2)
    sav       = round(c_tot_old - c_tot_new, 2)

    # Monthly
    monthly = []
    for month, grp in df.groupby('month'):
        mk = grp[grp['preprava']=='KLT']; mp = grp[grp['preprava']=='Paleta']
        og = grp.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index()
        og['np'] = og['Objem [m3]'].apply(lambda v: math.ceil(v / PAL_M3_OLD))
        kg_ = mk.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index() if len(mk) > 0 else pd.DataFrame({'Objem [m3]': []})
        if len(kg_) > 0: kg_['nk'] = kg_['Objem [m3]'].apply(lambda v: math.ceil(v / KLT_M3))
        pg_ = mp.groupby(['Date','TargetBranch'])['Objem [m3]'].sum().reset_index() if len(mp) > 0 else pd.DataFrame({'Objem [m3]': []})
        if len(pg_) > 0: pg_['np'] = pg_['Objem [m3]'].apply(lambda v: math.ceil(v / PAL_M3_NEW))
        nk_  = int(kg_['nk'].sum()) if len(kg_) > 0 else 0
        npo_ = int(pg_['np'].sum()) if len(pg_) > 0 else 0
        npa_ = int(og['np'].sum())
        tso  = len(grp)*216 + npa_*300
        tsn  = len(mk)*20 + len(mk)*15 + nk_*15 + len(mp)*216 + npo_*300
        cm_o = dir_cost(tso) + opp_cost(tso)
        cm_n = dir_cost(tsn) + opp_cost(tsn)
        cp_o = npa_ * PRICE_PAL_EUR; cp_n = npo_ * PRICE_PAL_EUR
        ct_o = round(cm_o + cp_o, 2); ct_n = round(cm_n + cp_n, 2)
        us   = round(ct_o - ct_n, 2)
        monthly.append({'Mesiac': month, 'Záznamy': len(grp),
            'KLT záznamy': len(mk), 'Paleta záznamy': len(mp),
            'KLT ks': nk_, 'Palety starý': npa_, 'Palety nový': npo_,
            'Nákl. starý (€)': ct_o, 'Nákl. nový (€)': ct_n, 'Úspora (€)': us,
            'Úspora (Kč)': round(us * CZK, 2),
            'Úspora proces (€)': round(cm_o - cm_n, 2),
            'Úspora doprava (€)': round(cp_o - cp_n, 2)})

    return {
        'n_total': n_total, 'n_klt': n_klt, 'n_pal': n_pal,
        'n_klts': n_klts, 'n_pal_old': n_pal_old, 'n_pal_new': n_pal_new,
        'c_mzd_old': round(c_mzd_old, 2), 'c_mzd_new': round(c_mzd_new, 2),
        'c_pal_old': round(c_pal_old, 2), 'c_pal_new': round(c_pal_new, 2),
        'c_tot_old': c_tot_old, 'c_tot_new': c_tot_new,
        'sav': sav, 'sav_czk': round(sav * CZK, 2),
        'sav_pct': round(sav / c_tot_old * 100, 1) if c_tot_old > 0 else 0,
        'sav_mzd': round(c_mzd_old - c_mzd_new, 2),
        'sav_pal': round(c_pal_old - c_pal_new, 2),
        'monthly': pd.DataFrame(monthly),
        'df': df,
    }

def load_file(uploaded):
    df = pd.read_excel(uploaded, header=None)
    df.columns = df.iloc[0]; df = df.iloc[1:].reset_index(drop=True)
    filtered = df[(df['Geosize'] == 'SPO') & (df['Typ distribuce'] == 'DFR')].copy()
    return filtered

def metric_card(label, value, sub=None, color='blue'):
    sub_html = f'<p style="font-size:11px;color:#888;margin:2px 0 0">{sub}</p>' if sub else ''
    st.markdown(f"""
    <div class="metric-card {color}">
        <p class="metric-label">{label}</p>
        <p class="metric-value">{value}</p>
        {sub_html}
    </div>""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Gaylord_container_KLT.jpg/320px-Gaylord_container_KLT.jpg", use_column_width=True)
    st.markdown("## 📦 KLT Plánovanie prepravy")
    st.markdown("---")

    st.markdown("### ⚙️ Parametre")
    thresh = st.slider("Prah KLT / Paleta (ks)", 1, 100, 20, 1,
                        help="Záznamy s menej kusmi → KLT, ostatné → Paleta")
    price_czk = st.number_input("Cena za paletu (Kč)", value=561.0, step=10.0, format="%.2f")
    rate_eur  = st.number_input("Sadzba práce (€/hod)", value=15.0, step=0.5, format="%.2f")
    czk_rate  = st.number_input("Kurz EUR/CZK", value=24.29, step=0.01, format="%.2f")

    # Update globals if changed
    PRICE_PAL_CZK = price_czk
    PRICE_PAL_EUR = round(price_czk / czk_rate, 4)
    RATE = rate_eur
    CZK  = czk_rate

    st.markdown("---")
    st.markdown("### 📂 Nahrať súbor")
    uploaded = st.file_uploader("Zošit2.xlsx (SPO+DFR dáta)", type=['xlsx'],
                                  help="Súbor musí obsahovať stĺpce: Geosize, Typ distribuce, Počet ks, Objem [m3]")
    st.markdown("---")
    st.markdown("**Filtre:** `Geosize = SPO` · `Typ distribuce = DFR`")
    st.markdown(f"**Paleta:** {KLT_PER_PAL} KLT = {PAL_M3_NEW:.2f} m³")
    st.markdown(f"**Starý fill:** 70 % → {PAL_M3_OLD:.3f} m³")

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("# 📦 KLT Plánovanie prepravy — Analýza a optimalizácia")
st.markdown(f"*Prah: **{thresh} ks** · Cena palety: **{price_czk:.0f} Kč** · Sadzba: **{rate_eur:.0f} €/hod** · Kurz: **{czk_rate} Kč/€***")

if uploaded is None:
    st.info("👈 Nahrajte súbor Zošit2.xlsx v ľavom paneli pre spustenie analýzy.")
    st.markdown("---")

    # Show process comparison even without data
    st.markdown('<p class="section-title">POROVNANIE PROCESOV</p>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔴 Súčasný proces** — všetko na paletu")
        steps_old = [
            ("Naskladnenie + štítok", "20 s / záznam", ""),
            ("Uloženie do regálu", "8 s / záznam", ""),
            ("Zozbieranie z portov", "**180 s / záznam**", "⚠️ 83 % celkového času"),
            ("Skenovanie + paleta", "8 s / záznam", ""),
            ("Odvoz palety", "300 s / paletu", "fill 70 %"),
        ]
        for krok, cas, pozn in steps_old:
            color = "#fdf0f0" if "Zozbieranie" in krok else "#f8f9fa"
            border = "#E24B4A" if "Zozbieranie" in krok else "#ddd"
            st.markdown(f"""<div style="background:{color};border-left:3px solid {border};
                padding:6px 10px;margin:3px 0;border-radius:4px;font-size:13px">
                <b>{krok}</b> — {cas} {f'<span style="color:#888;font-size:11px">{pozn}</span>' if pozn else ''}
                </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown("**🟢 Nový proces** — KLT + Paleta podľa prahu")
        steps_new = [
            ("Naskladnenie do AS", "20 s / záznam", "všetky záznamy", "#f0faf3", "#1E5631"),
            (f"Rozhodnutie: < {thresh} ks?", "—", "po naskladnení", "#fffbe6", "#854F0B"),
            ("KLT: Vypikovanie do BINu", "15 s / záznam", "+ 15 s / KLT sort", "#f0faf3", "#1E5631"),
            ("KLT: Dopravník", "0 s odvoz", "✅ eliminovaný odvoz", "#f0faf3", "#1E5631"),
            ("Paleta: súčasný proces", "216 s / záznam", "+ odvoz 300 s/pal", "#fdf7f0", "#854F0B"),
        ]
        for krok, cas, pozn, bg, bc in steps_new:
            st.markdown(f"""<div style="background:{bg};border-left:3px solid {bc};
                padding:6px 10px;margin:3px 0;border-radius:4px;font-size:13px">
                <b>{krok}</b> — {cas} <span style="color:#888;font-size:11px">{pozn}</span>
                </div>""", unsafe_allow_html=True)
    st.stop()

# ── Load and compute ──────────────────────────────────────────────────────────
try:
    df_raw = load_file(uploaded)
    if len(df_raw) == 0:
        st.error("Súbor neobsahuje záznamy s Geosize=SPO a Typ distribuce=DFR.")
        st.stop()
    res = compute_all(df_raw, thresh)
except Exception as e:
    st.error(f"Chyba pri načítaní súboru: {e}")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">KĽÚČOVÉ UKAZOVATELE</p>', unsafe_allow_html=True)
c1,c2,c3,c4,c5,c6 = st.columns(6)
with c1: metric_card("Záznamy celkom", f"{res['n_total']:,}", f"KLT: {res['n_klt']} · Pal: {res['n_pal']}")
with c2: metric_card("KLT ks", f"{res['n_klts']:,}", f"{res['n_klt']} záz. → dopravník", "blue")
with c3: metric_card("Palety (nový)", f"{res['n_pal_new']:,}", f"vs {res['n_pal_old']} starý (−{res['n_pal_old']-res['n_pal_new']})", "amber")
with c4: metric_card("Celkové náklady starý", f"{res['c_tot_old']:,.0f} €", f"{res['c_tot_old']*CZK:,.0f} Kč", "red")
with c5: metric_card("Celkové náklady nový", f"{res['c_tot_new']:,.0f} €", f"{res['c_tot_new']*CZK:,.0f} Kč", "blue")
with c6: metric_card("ÚSPORA", f"{res['sav']:,.0f} € ({res['sav_pct']}%)", f"{res['sav_czk']:,.0f} Kč", "green")

# ── Cost breakdown ─────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">ROZPAD NÁKLADOV A ÚSPOR</p>', unsafe_allow_html=True)
col_b, col_c = st.columns([2, 1])

with col_b:
    breakdown_data = {
        'Zložka': ['Proces — priame mzdové', 'Proces — opportunity cost', 'PROCES SPOLU', 'DOPRAVA — palety', 'CELKOVÉ NÁKLADY'],
        'Starý (€)': [round(res['c_mzd_old'] * (dir_cost(1) / (dir_cost(1) + opp_cost(1))), 2) if (dir_cost(1)+opp_cost(1))>0 else 0,
                      round(res['c_mzd_old'] * (opp_cost(1) / (dir_cost(1) + opp_cost(1))), 2) if (dir_cost(1)+opp_cost(1))>0 else 0,
                      res['c_mzd_old'], res['c_pal_old'], res['c_tot_old']],
        'Nový (€)':  [0, 0, res['c_mzd_new'], res['c_pal_new'], res['c_tot_new']],
        'Úspora (€)': [0, 0, res['sav_mzd'], res['sav_pal'], res['sav']],
        'Úspora (Kč)': [0, 0, round(res['sav_mzd']*CZK,2), round(res['sav_pal']*CZK,2), res['sav_czk']],
        '% z úspory': [0, 0, round(res['sav_mzd']/res['sav']*100,1) if res['sav']>0 else 0,
                       round(res['sav_pal']/res['sav']*100,1) if res['sav']>0 else 0, 100.0],
    }
    # Compute priame/OC properly
    t_old_total = res['n_total']*216 + res['n_pal_old']*300
    t_new_total = (res['n_klt']*20 + res['n_klt']*15 + res['n_klts']*15 +
                   res['n_pal']*216 + res['n_pal_new']*300)
    c_dir_old = dir_cost(t_old_total); c_oc_old = opp_cost(t_old_total)
    c_dir_new = dir_cost(t_new_total); c_oc_new = opp_cost(t_new_total)
    breakdown_data['Starý (€)'][0] = round(c_dir_old, 2)
    breakdown_data['Starý (€)'][1] = round(c_oc_old, 2)
    breakdown_data['Nový (€)'][0]  = round(c_dir_new, 2)
    breakdown_data['Nový (€)'][1]  = round(c_oc_new, 2)
    breakdown_data['Úspora (€)'][0] = round(c_dir_old - c_dir_new, 2)
    breakdown_data['Úspora (€)'][1] = round(c_oc_old - c_oc_new, 2)
    breakdown_data['Úspora (Kč)'][0] = round((c_dir_old-c_dir_new)*CZK, 2)
    breakdown_data['Úspora (Kč)'][1] = round((c_oc_old-c_oc_new)*CZK, 2)
    breakdown_data['% z úspory'][0]  = round((c_dir_old-c_dir_new)/res['sav']*100,1) if res['sav']>0 else 0
    breakdown_data['% z úspory'][1]  = round((c_oc_old-c_oc_new)/res['sav']*100,1) if res['sav']>0 else 0

    bdf = pd.DataFrame(breakdown_data)

    def style_breakdown(df):
        styles = []
        for i, row in df.iterrows():
            if 'CELKOVÉ' in str(row['Zložka']):
                styles.append(['background-color:#1F3864;color:white;font-weight:bold']*len(row))
            elif 'SPOLU' in str(row['Zložka']) or 'DOPRAVA' in str(row['Zložka']):
                styles.append(['background-color:#EBF3FB;font-weight:bold']*len(row))
            else:
                styles.append(['']*len(row))
        return pd.DataFrame(styles, index=df.index, columns=df.columns)

    st.dataframe(
        bdf.style
            .apply(style_breakdown, axis=None)
            .format({'Starý (€)': '{:,.2f} €', 'Nový (€)': '{:,.2f} €',
                     'Úspora (€)': '{:,.2f} €', 'Úspora (Kč)': '{:,.0f} Kč',
                     '% z úspory': '{:.1f} %'}),
        use_container_width=True, hide_index=True
    )

with col_c:
    st.markdown("**Podiel na celkovej úspore**")
    import json as _json
    pct_proc = round(res['sav_mzd']/res['sav']*100,1) if res['sav']>0 else 0
    pct_dop  = round(res['sav_pal']/res['sav']*100,1) if res['sav']>0 else 0
    for label, pct, color, eur_val in [
        ('Proces (mzdové)', pct_proc, '#2E75B6', res['sav_mzd']),
        ('Doprava (palety)', pct_dop, '#E67E22', res['sav_pal']),
    ]:
        st.markdown(f"""
        <div style="margin:8px 0">
            <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px">
                <span>{label}</span><span style="font-weight:600">{pct}%  ·  {eur_val:,.0f} €</span>
            </div>
            <div style="background:#eee;border-radius:4px;height:18px">
                <div style="background:{color};width:{pct}%;height:18px;border-radius:4px"></div>
            </div>
        </div>""", unsafe_allow_html=True)

# ── Monthly table ──────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">MESAČNÝ ROZPAD</p>', unsafe_allow_html=True)
mdf = res['monthly'].copy()
if len(mdf) > 0:
    mdf_display = mdf[['Mesiac','Záznamy','KLT záznamy','Paleta záznamy',
                        'Úspora proces (€)','Úspora doprava (€)','Úspora (€)','Úspora (Kč)',
                        'Nákl. starý (€)','Nákl. nový (€)']].copy()

    def highlight_partial(row):
        if row['Mesiac'] in ('2025-09','2026-05'):
            return ['background-color:#FFF9E6']*len(row)
        return ['']*len(row)

    st.dataframe(
        mdf_display.style
            .apply(highlight_partial, axis=1)
            .format({'Úspora proces (€)': '{:,.2f} €', 'Úspora doprava (€)': '{:,.2f} €',
                     'Úspora (€)': '{:,.2f} €', 'Úspora (Kč)': '{:,.0f} Kč',
                     'Nákl. starý (€)': '{:,.2f} €', 'Nákl. nový (€)': '{:,.2f} €'})
            .highlight_max(subset=['Úspora (€)'], color='#d4edda')
            .highlight_min(subset=['Úspora (€)'], color='#f8d7da'),
        use_container_width=True, hide_index=True
    )

    # Charts
    col_ch1, col_ch2 = st.columns(2)
    with col_ch1:
        st.markdown("**Mesačná úspora: proces vs doprava**")
        chart_data = mdf[['Mesiac','Úspora proces (€)','Úspora doprava (€)']].set_index('Mesiac')
        st.bar_chart(chart_data, color=['#2E75B6','#E67E22'])

    with col_ch2:
        st.markdown("**Mesačné celkové náklady**")
        chart_data2 = mdf[['Mesiac','Nákl. starý (€)','Nákl. nový (€)']].set_index('Mesiac')
        st.bar_chart(chart_data2, color=['#C0392B','#1E5631'])

# ── Sensitivity ───────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">CITLIVOSŤ PRAHU  (aktuálny prah: ' + str(thresh) + ' ks)</p>', unsafe_allow_html=True)
snap_thresholds = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100]
snap_rows = []
for t_val in snap_thresholds:
    r = compute_all(df_raw, t_val)
    snap_rows.append({
        'Prah (ks)': t_val,
        'KLT záz.': r['n_klt'],
        'KLT záz. (%)': f"{r['n_klt']/r['n_total']*100:.1f}%",
        'KLT ks': r['n_klts'],
        'Palety nový': r['n_pal_new'],
        'Nákl. nový (€)': r['c_tot_new'],
        'Úspora (€)': r['sav'],
        'Úspora (%)': f"{r['sav_pct']}%",
    })
snap_df = pd.DataFrame(snap_rows)

def highlight_current(row):
    if row['Prah (ks)'] == thresh:
        return ['background-color:#DDEEFF;font-weight:bold']*len(row)
    return ['']*len(row)

st.dataframe(
    snap_df.style
        .apply(highlight_current, axis=1)
        .format({'Nákl. nový (€)': '{:,.2f} €', 'Úspora (€)': '{:,.2f} €', 'KLT ks': '{:,}'}),
    use_container_width=True, hide_index=True
)

# ── Download ───────────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">EXPORT</p>', unsafe_allow_html=True)
col_d1, col_d2 = st.columns(2)

with col_d1:
    # CSV export of monthly breakdown
    csv = mdf.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        "⬇️  Stiahnuť mesačný rozpad (CSV)",
        data=csv,
        file_name=f"KLT_mesacny_rozpad_prah{thresh}ks.csv",
        mime="text/csv",
        use_container_width=True
    )

with col_d2:
    # CSV export of sensitivity
    csv2 = snap_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        "⬇️  Stiahnuť citlivosť prahu (CSV)",
        data=csv2,
        file_name=f"KLT_citlivost_prahu.csv",
        mime="text/csv",
        use_container_width=True
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(f"""
<div style="font-size:11px;color:#888;text-align:center">
KLT Plánovanie prepravy  ·  Filtre: Geosize=SPO · DFR  ·
Paleta: {KLT_PER_PAL} KLT = {PAL_M3_NEW:.2f}m³ (starý fill 70% = {PAL_M3_OLD:.3f}m³)  ·
Výkon: {VYKON_STD}→{VYKON_DIST} JBL/hod  ·
Kurz: {CZK} Kč/€  ·  {datetime.now().strftime('%d.%m.%Y')}
</div>
""", unsafe_allow_html=True)
