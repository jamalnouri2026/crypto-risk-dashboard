import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# تنظیمات اصلی داشبورد
st.set_page_config(page_title="Crypto Analysis Pro", layout="wide")
st.title("🚀 دشبورد تحلیل حرفه‌ای (نسخه اصلاح شده و بدون خطا)")

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

    # --- مدیریت پارامترها و حافظه موقت ---
    query_params = st.query_params
    
    if 'temp_params' not in st.session_state:
        st.session_state.temp_params = {}

    st.sidebar.header("⚙️ تنظیمات پورتفولیو")
    
    # دکمه ثبت با کلید اختصاصی
    if st.sidebar.button("💾 ثبت تغییرات در لینک", type="primary", key="save_btn_main"):
        st.query_params.update(st.session_state.temp_params)
        st.sidebar.success("لینک آپدیت شد!")

    # اسلایدر با کلید اختصاصی برای رفع ارور Duplicate ID
    conf_level = st.sidebar.slider(
        "سطح اطمینان VaR/CVaR (%)", 
        90.0, 99.0, 95.0, 0.5, 
        key="conf_level_slider"
    ) / 100
    
    portfolios_series = {}
    portfolios_returns = {}

    for i in range(1, 6):
        with st.sidebar.expander(f"💼 تنظیمات سبد شماره {i}", expanded=(i==1)):
            temp_weights = {}
            sum_alts = 0.0
            
            for coin in alt_coins:
                coin_name = coin.replace('-USD', '')
                param_key = f"p{i}_{coin_name}"
                
                # مقادیر پیش‌فرض
                default_val = 0.0
                if i == 1:
                    defaults = {'BTC': 72.95, 'ETH': 10.7, 'XRP': 3.3, 'BNB': 3.19, 'SOL': 1.86, 'DOGE': 0.71}
                    default_val = defaults.get(coin_name, 0.0)
                
                # خواندن مقدار اولیه
                saved_val = float(query_params.get(param_key, default_val))
                
                val = st.number_input(
                    f"{coin_name} (%)", 0.0, 100.0, saved_val, 
                    key=f"input_{param_key}_v2"
                )
                
                st.session_state.temp_params[param_key] = val
                temp_weights[coin] = val / 100
                sum_alts += val
            
            usdt_pct = max(0, 100.0 - sum_alts)
            temp_weights['USDT-USD'] = usdt_pct / 100
            st.info(f"نقدینگی (USDT): {usdt_pct:.2f}%")

            w_series = pd.Series(temp_weights)
            p_val = (norm_df[all_coins] * w_series).sum(axis=1)
            portfolios_series[f"سبد {i}"] = p_val
            portfolios_returns[f"سبد {i}"] = p_val.pct_change().dropna()

    portfolios_series["توتال بازار"] = market_total_series
    portfolios_returns["توتال بازار"] = market_daily_ret

    # --- ۱. جدول بازده و نوسان سالانه ---
    st.write("### 💎 ۱. تحلیل بازده و نوسان سالانه (Risk vs Reward)")
    risk_reward_data = []
    days_in_year = 365
    for name, rets in portfolios_returns.items():
        ann_return = (1 + rets.mean())**days_in_year - 1
        ann_std = rets.std() * np.sqrt(days_in_year)
        risk_reward_data.append({
            "نام سبد": name, 
            "Annualized Return": ann_return, 
            "Annualized Std Dev (Risk)": ann_std, 
            "Sharpe Ratio": ann_return / ann_std if ann_std != 0 else 0
        })
    
    st.table(pd.DataFrame(risk_reward_data).style.format({
        "Annualized Return": "{:.2%}", "Annualized Std Dev (Risk)": "{:.2%}", "Sharpe Ratio": "{:.2f}"
    }))

    # --- ۲. نمودار Scatter ---
    st.write("### 📍 ۲. نقشه جایگاه سبدها (Risk-Reward Map)")
    fig_scatter = go.Figure()
    for row in risk_reward_data:
        color = 'white' if row['نام سبد'] == "توتال بازار" else None
        fig_scatter.add_trace(go.Scatter(
            x=[row['Annualized Std Dev (Risk)']], 
            y=[row['Annualized Return']], 
            mode='markers+text', 
            name=row['نام سبد'], 
            text=[row['نام سبد']], 
            textposition="top center", 
            marker=dict(size=12, color=color)
        ))
    fig_scatter.update_layout(height=450, template="plotly_dark", xaxis_title="ریسک سالانه", yaxis_title="بازدهی سالانه")
    st.plotly_chart(fig_scatter, use_container_width=True)

    # --- ۳. جدول پیش‌بینی ریسک (VaR & CVaR) ---
    st.divider()
    st.write(f"### 🛡️ ۳. جدول پیش‌بینی ریسک")
    risk_full_data = []
    t_year = np.sqrt(365)
    for name, rets in portfolios_returns.items():
        v1 = np.percentile(rets, (1 - conf_level) * 100)
        risk_full_data.append({
            "نام سبد": name, 
            "VaR (روز)": f"{v1*100:.2f}%", 
            "VaR (سال)": f"{(v1*t_year)*100:.2f}%"
        })
    st.table(pd.DataFrame(risk_full_data))

    # --- ۴. نمودار رشد سرمایه (اصلاح شده) ---
    st.write("### 📈 ۴. مقایسه رشد سرمایه (Log Scale)")
    fig_log = go.Figure()
    for name, series in portfolios_series.items():
        line = dict(width=3, dash='dot', color='white') if name == "توتال بازار" else dict(width=2)
        fig_log.add_trace(go.Scatter(x=series.index, y=series, name=name, line=line))
    
    fig_log.update_layout(
        yaxis_type="log", 
        height=550, 
        template="plotly_dark", 
        xaxis_title="تاریخ", 
        yaxis_title="ارزش سبد (پایه ۱)",
        hovermode="x unified"
    )
    st.plotly_chart(fig_log, use_container_width=True)

except Exception as e:
    st.error(f"خطا در محاسبات یا رسم نمودار: {e}")