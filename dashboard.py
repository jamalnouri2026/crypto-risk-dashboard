import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# تنظیمات اصلی داشبورد
st.set_page_config(page_title="Crypto Analysis Pro", layout="wide")
st.title("🚀 دشبورد جامع تحلیل و مدیریت ریسک")

# لیست کوین‌ها
alt_coins = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'XRP-USD', 'DOGE-USD', 'ADA-USD']
all_coins = alt_coins + ['USDT-USD']

@st.cache_data
def load_data():
    df = yf.download(all_coins, start='2023-01-01')['Close']
    return df

try:
    data = load_data()
    norm_df = data / data.iloc[0]
    daily_returns = data.pct_change().dropna()
    
    market_total_series = norm_df[alt_coins].mean(axis=1)
    market_daily_ret = market_total_series.pct_change().dropna()

    # --- مدیریت پارامترها و دکمه ذخیره ---
    if 'temp_params' not in st.session_state:
        st.session_state.temp_params = {}

    st.sidebar.header("🕹️ منوی کنترل")
    save_trigger = st.sidebar.button("🔴 ثبت نهایی در لینک (Share)", type="primary", use_container_width=True, key="final_save_btn_v3")
    
    if save_trigger:
        st.query_params.update(st.session_state.temp_params)
        st.sidebar.success("لینک با موفقیت آپدیت شد!")

    st.sidebar.divider()
    conf_level = st.sidebar.slider("سطح اطمینان ریسک (%)", 90.0, 99.0, 95.0, 0.5, key="risk_level_slider_v3") / 100
    
    portfolios_series = {}
    portfolios_returns = {}

    for i in range(1, 6):
        with st.sidebar.expander(f"💼 تنظیمات سبد {i}", expanded=(i==1)):
            temp_weights = {}
            sum_alts = 0.0
            for coin in alt_coins:
                coin_name = coin.replace('-USD', '')
                param_key = f"p{i}_{coin_name}"
                default_val = 0.0
                if i == 1:
                    defaults = {'BTC': 72.95, 'ETH': 10.7, 'XRP': 3.3, 'BNB': 3.19, 'SOL': 1.86, 'DOGE': 0.71}
                    default_val = defaults.get(coin_name, 0.0)
                
                saved_val = float(st.query_params.get(param_key, default_val))
                val = st.number_input(f"{coin_name} (%)", 0.0, 100.0, saved_val, key=f"inp_{param_key}_{i}_v3")
                
                st.session_state.temp_params[param_key] = val
                temp_weights[coin] = val / 100
                sum_alts += val
            
            usdt_pct = max(0, 100.0 - sum_alts)
            temp_weights['USDT-USD'] = usdt_pct / 100
            st.info(f"نقدینگی: {usdt_pct:.2f}%")
            
            w_series = pd.Series(temp_weights)
            p_val = (norm_df[all_coins] * w_series).sum(axis=1)
            portfolios_series[f"سبد {i}"] = p_val
            portfolios_returns[f"سبد {i}"] = p_val.pct_change().dropna()

    portfolios_series["توتال بازار"] = market_total_series
    portfolios_returns["توتال بازار"] = market_daily_ret

    # --- ۱. جدول بازده و نوسان سالانه ---
    st.write("### 💎 ۱. تحلیل بازده و نوسان سالانه (Risk vs Reward)")
    rr_data = []
    days_year = 365
    for name, rets in portfolios_returns.items():
        ann_ret = (1 + rets.mean())**days_year - 1
        ann_std = rets.std() * np.sqrt(days_year)
        rr_data.append({"نام سبد": name, "Annualized Return": ann_ret, "Annualized Std Dev (Risk)": ann_std, "Sharpe Ratio": ann_ret/ann_std if ann_std != 0 else 0})
    st.table(pd.DataFrame(rr_data).style.format({"Annualized Return": "{:.2%}", "Annualized Std Dev (Risk)": "{:.2%}", "Sharpe Ratio": "{:.2f}"}))

    with st.expander("❓ راهنمای شاخص‌های بازده و نوسان"):
        st.markdown("""
        * **Annualized Return:** سود سالانه انتظاری سبد بر اساس داده‌های تاریخی.
        * **Annualized Std Dev (Risk):** نوسان‌پذیری یا انحراف معیار سالانه؛ هرچه بیشتر باشد، ریسک سبد بالاتر است.
        * **Sharpe Ratio:** نسبت سود به ریسک؛ اعداد بالاتر از ۱ نشان‌دهنده کیفیت بالای استراتژی هستند.
        """)

    # --- ۲. نقشه ریسک و ریوارد ---
    st.write("### 📍 ۲. نقشه ریسک و ریوارد (Risk-Reward Map)")
    fig_scat = go.Figure()
    for row in rr_data:
        color = 'white' if row['نام سبد'] == "توتال بازار" else None
        symbol = 'star' if row['نام سبد'] == "توتال بازار" else 'circle'
        fig_scat.add_trace(go.Scatter(x=[row['Annualized Std Dev (Risk)']], y=[row['Annualized Return']], mode='markers+text', name=row['نام سبد'], text=[row['نام سبد']], textposition="top center", marker=dict(size=12, color=color, symbol=symbol)))
    fig_scat.update_layout(height=450, template="plotly_dark", xaxis_title="ریسک (Standard Deviation)", yaxis_title="بازدهی (Annual Return)")
    st.plotly_chart(fig_scat, use_container_width=True)

    # --- ۳. جدول جامع پیش‌بینی ریسک (VaR & CVaR) ---
    st.divider()
    st.write(f"### 🛡️ ۳. جدول پیش‌بینی ریسک (سطح اطمینان {conf_level*100:.1f}%)")
    risk_rows = []
    t_week, t_month, t_year = np.sqrt(7), np.sqrt(30), np.sqrt(365)
    crit_flag = False

    for name, rets in portfolios_returns.items():
        v1 = np.percentile(rets, (1 - conf_level) * 100)
        c1 = rets[rets <= v1].mean()
        if np.isnan(c1): c1 = 0
        if any(v <= -1.0 for v in [v1*t_year, c1*t_year]): crit_flag = True
        
        risk_rows.append({
            "نام سبد": name,
            "VaR (روز)": f"{v1*100:.2f}%", "CVaR (روز)": f"{c1*100:.2f}%",
            "VaR (ماه)": f"{(v1*t_month)*100:.2f}%", "CVaR (ماه)": f"{(c1*t_month)*100:.2f}%",
            "VaR (سال)": f"{(v1*t_year)*100:.2f}%", "CVaR (سال)": f"{(c1*t_year)*100:.2f}%"
        })
    st.table(pd.DataFrame(risk_rows))

    if crit_flag:
        st.warning("⚠️ **هشدار ریسک بحرانی:** مقادیر زیر ۱۰۰-٪ نشان‌دهنده احتمال صفر شدن سرمایه در بازه زمانی مربوطه است.")

    with st.expander("❓ راهنمای مفاهیم VaR و CVaR"):
        st.markdown("""
        * **VaR (Value at Risk):** بیشترین ضرر احتمالی در یک بازه زمانی با احتمال مشخص.
        * **CVaR (Conditional VaR):** میانگین ضرر در صورتی که بازار وارد یک وضعیت بحرانی (خارج از VaR) شود.
        """)

    # --- ۴. بیشترین ریزش‌های تاریخی (Max Drawdown) ---
    st.write("### 📉 ۴. بیشترین ریزش‌های تاریخی (Max Drawdown)")
    def get_dd(series, days):
        sub = series.tail(days) if days > 0 else series
        return ((sub - sub.cummax()) / sub.cummax()).min()

    dd_rows = []
    for name, p_ser in portfolios_series.items():
        dd_rows.append({
            "نام سبد": name,
            "بیشترین ریزش ۱ روز": f"{portfolios_returns[name].min()*100:.2f}%",
            "Max DD (ماه)": f"{get_dd(p_ser, 30)*100:.2f}%",
            "Max DD (کل دوره)": f"{get_dd(p_ser, 0)*100:.2f}%"
        })
    st.table(pd.DataFrame(dd_rows))

    with st.expander("❓ راهنمای تحلیل درآودان (Drawdown)"):
        st.write("این جدول بدترین ریزش‌های تجربه شده سبد از «قله تا دره» را نشان می‌دهد و نمایانگر ریسک واقعی است.")

    # --- ۵. نمودار رشد سرمایه ---
    st.write("### 📈 ۵. مقایسه رشد سرمایه (Log Scale)")
    fig_l = go.Figure()
    for name, ser in portfolios_series.items():
        line = dict(width=3, dash='dot', color='white') if name == "توتال بازار" else dict(width=2)
        fig_l.add_trace(go.Scatter(x=ser.index, y=ser, name=name, line=line))
    fig_l.update_layout(yaxis_type="log", height=500, template="plotly_dark", hovermode="x unified", xaxis_title="Time", yaxis_title="Portfolio Value (Normalized)")
    st.plotly_chart(fig_l, use_container_width=True)

    with st.expander("❓ چرا از مقیاس لگاریتمی استفاده می‌کنیم؟"):
        st.write("در مقیاس لگاریتمی، رشد ۱۰ درصدی در قیمت ۱۰۰ دلار و ۱۰۰۰۰ دلار به یک اندازه دیده می‌شود که برای تحلیل درازمدت دارایی‌های پرنوسان مثل کریپتو ضروری است.")

except Exception as e:
    st.error(f"خطا در اجرا: {e}")