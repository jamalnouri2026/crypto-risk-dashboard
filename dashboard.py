"""
Crypto Analysis Pro — داشبورد جامع تحلیل و مدیریت ریسک
سیستم ذخیره‌سازی ترکیبی: localStorage (رفرش‌پایدار) + URL (اشتراک‌گذاری)
"""

import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import json
import os

st.set_page_config(
    page_title="Crypto Analysis Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Vazirmatn', sans-serif; direction: rtl; }
    .main-header {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 2rem;
        text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }
    .main-header h1 { color: #f0e6ff; font-size: 2rem; margin: 0 0 0.3rem; font-weight: 700; }
    .main-header p  { color: #a78bfa; margin: 0; font-size: 0.9rem; }
    .metric-card {
        background: #1e1b2e; border: 1px solid #3d3a5c; border-radius: 12px;
        padding: 1.2rem 1.5rem; text-align: center;
    }
    .metric-label { font-size: 0.78rem; color: #a78bfa; font-weight: 600; letter-spacing: 0.05em; }
    .metric-value { font-size: 1.6rem; font-weight: 700; color: #e9d5ff; margin: 0.3rem 0 0; }
    .metric-sub   { font-size: 0.75rem; color: #6b7280; margin-top: 0.2rem; }
    .risk-banner {
        background: linear-gradient(90deg, #7f1d1d, #991b1b);
        border-right: 4px solid #ef4444; border-radius: 10px;
        padding: 0.9rem 1.2rem; color: #fecaca; font-size: 0.88rem; margin: 1rem 0;
    }
    [data-testid="stSidebar"] { background-color: #0d0b1a; }
    hr { border-color: #2d2b45; margin: 1.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ─── ثابت‌ها ─────────────────────────────────────────────────────────────────
ALT_COINS  = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'XRP-USD', 'DOGE-USD', 'ADA-USD']
ALL_COINS  = ALT_COINS + ['USDT-USD']
COIN_NAMES = {c: c.replace('-USD', '') for c in ALT_COINS}
DAYS_YEAR  = 365

DEFAULT_WEIGHTS_P1 = {
    'BTC': 72.95, 'ETH': 10.7, 'XRP': 3.3,
    'BNB': 3.19,  'SOL': 1.86, 'DOGE': 0.71, 'ADA': 0.0
}

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Vazirmatn, sans-serif", color="#d1d5db"),
    margin=dict(t=30, b=40, l=10, r=10),
    legend=dict(bgcolor="rgba(20,17,40,0.8)", bordercolor="#3d3a5c", borderwidth=1),
)

# ─── Bridge HTML برای localStorage ───────────────────────────────────────────
# این فایل باید کنار crypto_dashboard.py باشه
BRIDGE_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "localstorage_bridge.html")
with open(BRIDGE_HTML_PATH, "r", encoding="utf-8") as _f:
    BRIDGE_HTML = _f.read()

# ─── توابع Persistence ───────────────────────────────────────────────────────
def get_url_params() -> dict:
    result = {}
    for i in range(1, 6):
        for coin in ALT_COINS:
            key = f"p{i}_{COIN_NAMES[coin]}"
            if key in st.query_params:
                try:
                    result[key] = float(st.query_params[key])
                except (ValueError, TypeError):
                    pass
    return result

def build_defaults() -> dict:
    d = {}
    for i in range(1, 6):
        for coin in ALT_COINS:
            key = f"p{i}_{COIN_NAMES[coin]}"
            d[key] = DEFAULT_WEIGHTS_P1.get(COIN_NAMES[coin], 0.0) if i == 1 else 0.0
    return d

# ─── بارگذاری bridge (localStorage) ─────────────────────────────────────────
# اولین بار که صفحه لود می‌شه، bridge مقادیر localStorage رو برمی‌گردونه
if 'ls_loaded' not in st.session_state:
    st.session_state.ls_loaded = False
    st.session_state.ls_data   = None

ls_value = components.html(BRIDGE_HTML, height=0)

if ls_value is not None and not st.session_state.ls_loaded:
    st.session_state.ls_data   = ls_value
    st.session_state.ls_loaded = True

# ادغام منابع: URL > localStorage > default
url_params = get_url_params()
defaults   = build_defaults()
merged     = {**defaults}

# ls_data ممکنه object خاص Streamlit باشه — تبدیل ایمن به dict معمولی
ls_raw = st.session_state.ls_data
if ls_raw:
    try:
        ls_dict = dict(ls_raw) if not isinstance(ls_raw, dict) else ls_raw
        merged.update({k: float(v) for k, v in ls_dict.items() if k in defaults})
    except Exception:
        pass  # اگه تبدیل شکست خورد، از مقادیر default استفاده می‌کنیم

merged.update(url_params)  # URL همیشه برنده است

if 'current_weights' not in st.session_state:
    st.session_state.current_weights = merged.copy()

# ─── توابع تحلیل ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="📥 در حال بارگذاری داده‌های بازار...")
def load_market_data(start='2023-01-01'):
    df = yf.download(ALL_COINS, start=start, progress=False)['Close']
    df.dropna(how='all', inplace=True)
    return df

def build_portfolio(norm_df, weights):
    cols = [c for c in weights if c in norm_df.columns]
    w = pd.Series({c: weights[c] for c in cols})
    return (norm_df[cols] * w).sum(axis=1)

def annualized_stats(rets):
    ann_ret = (1 + rets.mean()) ** DAYS_YEAR - 1
    ann_std = rets.std() * np.sqrt(DAYS_YEAR)
    return {"return": ann_ret, "std": ann_std, "sharpe": ann_ret/ann_std if ann_std > 0 else 0.0}

def var_cvar(rets, conf):
    v = np.percentile(rets, (1-conf)*100)
    tail = rets[rets <= v]
    return v, float(np.nan_to_num(tail.mean() if not tail.empty else v))

def max_dd(ser, tail=0):
    s = ser.tail(tail) if tail > 0 else ser
    return float(((s - s.cummax()) / s.cummax()).min())

def pct(v, d=2): return f"{v*100:.{d}f}%"

# ─── هدر ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>📊 داشبورد جامع تحلیل و مدیریت ریسک رمزارز</h1>
  <p>تحلیل سبدهای سرمایه‌گذاری · VaR · CVaR · Max Drawdown · Risk-Reward Map</p>
</div>
""", unsafe_allow_html=True)

# ─── بارگذاری داده ───────────────────────────────────────────────────────────
try:
    raw = load_market_data()
except Exception as e:
    st.error(f"❌ خطا: {e}")
    st.stop()

norm_df    = raw / raw.iloc[0]
daily_ret  = raw.pct_change().dropna()
market_ser = norm_df[ALT_COINS].mean(axis=1)
market_ret = market_ser.pct_change().dropna()

# ─── سایدبار ─────────────────────────────────────────────────────────────────
sb = st.sidebar
sb.markdown("## 🕹️ منوی کنترل")

c1, c2 = sb.columns(2)
save_url  = c1.button("🔗 شیر URL", use_container_width=True, type="primary",
                      help="لینک قابل اشتراک‌گذاری با دیگران می‌سازه")
clear_btn = c2.button("🗑️ پاک‌سازی", use_container_width=True,
                      help="همه تنظیمات رو به پیش‌فرض برمی‌گردونه")

if save_url:
    active = {k: str(v) for k, v in st.session_state.current_weights.items() if v > 0}
    st.query_params.update(active)
    sb.success("✅ URL آپدیت شد — آن را کپی کنید!")

if clear_btn:
    st.query_params.clear()
    st.session_state.ls_data   = None
    st.session_state.ls_loaded = False
    st.session_state.current_weights = defaults.copy()
    components.html("<script>window.parent.postMessage({type:'CLEAR_STORAGE'},'*');</script>", height=0)
    st.rerun()

sb.markdown("""
<div style="font-size:0.75rem;color:#6b7280;margin-top:4px;line-height:1.6">
💾 تنظیمات <b style="color:#a78bfa">خودکار</b> روی این مرورگر ذخیره می‌شن<br>
🔗 برای اشتراک‌گذاری از دکمه «شیر URL» استفاده کن
</div>
""", unsafe_allow_html=True)

sb.divider()
conf_level = sb.slider("سطح اطمینان ریسک (%)", 90.0, 99.0, 95.0, 0.5) / 100

# ─── ساخت سبدها ──────────────────────────────────────────────────────────────
port_series  = {}
port_returns = {}
new_weights  = {}

for i in range(1, 6):
    with sb.expander(f"💼 سبد {i}", expanded=(i == 1)):
        wt, total = {}, 0.0
        for coin in ALT_COINS:
            name = COIN_NAMES[coin]
            key  = f"p{i}_{name}"
            val  = st.number_input(f"{name} (%)", 0.0, 100.0,
                                   float(merged.get(key, 0.0)), 0.01,
                                   key=f"inp_{key}_{i}")
            wt[coin] = val / 100
            total += val
            new_weights[key] = val

        usdt_pct = max(0.0, 100.0 - total)
        wt['USDT-USD'] = usdt_pct / 100
        sb.caption(f"💵 نقدینگی (USDT): {usdt_pct:.2f}%")

        lbl = f"سبد {i}"
        pv  = build_portfolio(norm_df, wt)
        port_series[lbl]  = pv
        port_returns[lbl] = pv.pct_change().dropna()

# ─── ذخیره خودکار در localStorage هنگام تغییر ───────────────────────────────
if new_weights != st.session_state.current_weights:
    st.session_state.current_weights = new_weights.copy()
    js_payload = json.dumps(new_weights)
    components.html(f"""
    <script>
      window.parent.postMessage({{type:'SAVE_TO_STORAGE', payload:{js_payload}}}, '*');
    </script>
    """, height=0)

port_series["توتال بازار"]  = market_ser
port_returns["توتال بازار"] = market_ret

# ─── متریک‌ها ─────────────────────────────────────────────────────────────────
st.subheader("📋 خلاصه سبد اول")
s1  = annualized_stats(port_returns["سبد 1"])
v1, cv1 = var_cvar(port_returns["سبد 1"], conf_level)
for col, (lbl, val, sub) in zip(st.columns(4), [
    ("بازده سالانه", pct(s1["return"]), "Annualized Return"),
    ("نوسان سالانه", pct(s1["std"]),    "Annual Std Dev"),
    ("نسبت شارپ",   f"{s1['sharpe']:.2f}", "Sharpe Ratio"),
    (f"VaR ({conf_level*100:.0f}%)", pct(v1), "Daily Value at Risk"),
]):
    col.markdown(f"""<div class="metric-card">
      <div class="metric-label">{lbl}</div>
      <div class="metric-value">{val}</div>
      <div class="metric-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ─── جداول تحلیل ─────────────────────────────────────────────────────────────
st.subheader("💎 ۱. بازده و نوسان سالانه")
rr = []
for n, r in port_returns.items():
    s = annualized_stats(r)
    rr.append({"نام سبد": n, "بازده سالانه": pct(s["return"]),
               "نوسان سالانه": pct(s["std"]), "شارپ": f"{s['sharpe']:.2f}"})
st.dataframe(pd.DataFrame(rr).set_index("نام سبد"), use_container_width=True)

st.subheader("📍 ۲. نقشه ریسک-ریوارد")
fig_sc = go.Figure()
for row in rr:
    is_m = row["نام سبد"] == "توتال بازار"
    fig_sc.add_trace(go.Scatter(
        x=[float(row["نوسان سالانه"].rstrip('%'))/100],
        y=[float(row["بازده سالانه"].rstrip('%'))/100],
        mode='markers+text', name=row["نام سبد"],
        text=[row["نام سبد"]], textposition="top center",
        marker=dict(size=16 if is_m else 12,
                    symbol='star' if is_m else 'circle',
                    line=dict(width=1.5, color='white') if is_m else dict(width=0))))
fig_sc.update_layout(**PLOTLY_LAYOUT, height=400, xaxis_title="ریسک",
    yaxis_title="بازدهی", xaxis=dict(tickformat=".0%"), yaxis=dict(tickformat=".0%"))
st.plotly_chart(fig_sc, use_container_width=True)

st.divider()
st.subheader(f"🛡️ ۳. VaR/CVaR  (اطمینان {conf_level*100:.1f}%)")
tw, tm, ty = np.sqrt(7), np.sqrt(30), np.sqrt(DAYS_YEAR)
risk_rows, crit = [], False
for n, r in port_returns.items():
    v, cv = var_cvar(r, conf_level)
    if any(x <= -1 for x in [v*ty, cv*ty]): crit = True
    risk_rows.append({"نام سبد": n,
        "VaR روز": pct(v), "CVaR روز": pct(cv),
        "VaR هفته": pct(v*tw), "CVaR هفته": pct(cv*tw),
        "VaR ماه": pct(v*tm), "CVaR ماه": pct(cv*tm),
        "VaR سال": pct(v*ty), "CVaR سال": pct(cv*ty)})
st.dataframe(pd.DataFrame(risk_rows).set_index("نام سبد"), use_container_width=True)
if crit:
    st.markdown('<div class="risk-banner">⚠️ <b>هشدار بحرانی:</b> احتمال از دست رفتن کامل سرمایه.</div>', unsafe_allow_html=True)

st.subheader("📉 ۴. Max Drawdown")
dd_rows = []
for n, s in port_series.items():
    dd_rows.append({"نام سبد": n,
        "بدترین روز": pct(port_returns[n].min()),
        "Max DD ماه": pct(max_dd(s, 30)),
        "Max DD ۶ ماه": pct(max_dd(s, 180)),
        "Max DD کل": pct(max_dd(s))})
st.dataframe(pd.DataFrame(dd_rows).set_index("نام سبد"), use_container_width=True)

st.subheader("📈 ۵. رشد سرمایه (لگاریتمی)")
fig_l = go.Figure()
clrs = ['#a78bfa', '#34d399', '#f59e0b', '#f87171', '#60a5fa']
for idx, (n, s) in enumerate(port_series.items()):
    im = n == "توتال بازار"
    fig_l.add_trace(go.Scatter(x=s.index, y=s.values, name=n, mode='lines',
        line=dict(width=2.5 if im else 1.8, dash='dot' if im else 'solid',
                  color='white' if im else clrs[idx % len(clrs)])))
fig_l.update_layout(**PLOTLY_LAYOUT, height=500, yaxis_type="log",
    xaxis_title="تاریخ", yaxis_title="ارزش (لگ)", hovermode="x unified")
st.plotly_chart(fig_l, use_container_width=True)

st.divider()
st.subheader("🔗 ۶. ماتریس همبستگی")
corr = daily_ret[ALT_COINS].corr()
lbls = [COIN_NAMES[c] for c in ALT_COINS]
fig_h = go.Figure(go.Heatmap(z=corr.values, x=lbls, y=lbls,
    colorscale="RdBu_r", zmid=0, zmin=-1, zmax=1,
    text=[[f"{v:.2f}" for v in row] for row in corr.values],
    texttemplate="%{text}", textfont=dict(size=11)))
fig_h.update_layout(**PLOTLY_LAYOUT, height=400)
st.plotly_chart(fig_h, use_container_width=True)

st.divider()
st.caption(f"📅 آخرین داده: {raw.index[-1].date()}  •  Yahoo Finance  •  ⚠️ صرفاً آموزشی")