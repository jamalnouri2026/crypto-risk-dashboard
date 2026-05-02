import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# تنظیمات اصلی داشبورد
st.set_page_config(page_title="Crypto Master Analysis Dashboard", layout="wide")
st.title("🚀 داشبورد جامع تحلیل استراتژی و مدیریت ریسک")

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
    
    # محاسبه توتال بازار (Benchmark)
    market_total_series = norm_df[alt_coins].mean(axis=1)
    market_daily_ret = market_total_series.pct_change().dropna()

    # --- سایدبار تنظیمات ---
    st.sidebar.header("⚙️ تنظیمات پورتفولیو")
    conf_level = st.sidebar.slider(
        "سطح اطمینان VaR/CVaR (%)", 90.0, 99.0, 95.0, 0.5,
        help="این عدد نشان‌دهنده دقت آماری است. مثلاً ۹۵٪ یعنی ما ۹۵٪ مطمئن هستیم که ضرر روزانه از حد مشخص شده فراتر نمی‌رود."
    ) / 100
    
    portfolios_series = {}
    portfolios_returns = {}

    for i in range(1, 6):
        with st.sidebar.expander(f"💼 تنظیمات سبد شماره {i}", expanded=(i==1)):
            temp_weights = {}
            sum_alts = 0.0
            for coin in alt_coins:
                coin_name = coin.replace('-USD', '')
                default_val = 0.0
                if i == 1:
                    defaults = {'BTC': 72.95, 'ETH': 10.7, 'XRP': 3.3, 'BNB': 3.19, 'SOL': 1.86, 'DOGE': 0.71, 'ADA': 0.0}
                    default_val = defaults.get(coin_name, 0.0)
                
                val = st.number_input(f"{coin_name} (%)", 0.0, 100.0, default_val, key=f"p{i}_{coin}", help=f"درصد اختصاص یافته به {coin_name}")
                temp_weights[coin] = val / 100
                sum_alts += val
            
            usdt_pct = 100.0 - sum_alts
            temp_weights['USDT-USD'] = max(0, usdt_pct) / 100
            if usdt_pct < 0: 
                st.error(f"بیش از ۱۰۰٪!")
            else: 
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

    with st.expander("❓ راهنمای شاخص‌های بازده و نوسان"):
        st.markdown("""
        * **Annualized Return:** میانگین سود انتظاری سبد در یک سال بر اساس عملکرد گذشته.
        * **Annualized Std Dev:** میزان نوسان (ریسک) سالانه. عدد بالاتر یعنی نوسانات قیمتی شدیدتر.
        * **Sharpe Ratio:** نسبت بازدهی به ریسک. هر چه بالاتر باشد، یعنی سبد به نسبت خطری که دارد، سود بهتری می‌دهد.
        """)

    # --- ۲. نمودار Scatter Risk vs Reward ---
    st.write("### 📍 ۲. نقشه جایگاه سبدها (Risk-Reward Map)")
    fig_scatter = go.Figure()
    for row in risk_reward_data:
        color = 'white' if row['نام سبد'] == "توتال بازار" else None
        symbol = 'star' if row['نام سبد'] == "توتال بازار" else 'circle'
        fig_scatter.add_trace(go.Scatter(
            x=[row['Annualized Std Dev (Risk)']], y=[row['Annualized Return']],
            mode='markers+text', name=row['نام سبد'], text=[row['نام سبد']],
            textposition="top center", marker=dict(size=15, symbol=symbol, color=color)
        ))
    fig_scatter.update_layout(xaxis_title="ریسک (نوسان سالانه)", yaxis_title="بازدهی سالانه", template="plotly", height=500)
    st.plotly_chart(fig_scatter, use_container_width=True)

    with st.expander("❓ راهنمای نمودار Risk-Reward"):
        st.write("این نمودار نشان می‌دهد هر سبد کجای مرز ریسک و پاداش قرار دارد. هدف، قرار گرفتن در قسمت بالا و سمت چپ نمودار است (سود زیاد، ریسک کم).")

    # --- ۳. جدول جامع پیش‌بینی ریسک (VaR & CVaR) ---
    st.divider()
    st.write(f"### 🛡️ ۳. جدول پیش‌بینی ریسک (VaR & CVaR) - سطح اطمینان {conf_level*100:.1f}%")
    risk_full_data = []
    t_week, t_month, t_year = np.sqrt(7), np.sqrt(30), np.sqrt(365)
    critical_risk_flag = False

    for name, rets in portfolios_returns.items():
        v1 = np.percentile(rets, (1 - conf_level) * 100)
        c1 = rets[rets <= v1].mean()
        if np.isnan(c1): c1 = 0
        if any(v <= -1.0 for v in [v1*t_year, c1*t_year]): critical_risk_flag = True

        risk_full_data.append({
            "نام سبد": name,
            "VaR (روز)": f"{v1*100:.2f}%", "CVaR (روز)": f"{c1*100:.2f}%",
            "VaR (هفته)": f"{(v1*t_week)*100:.2f}%", "CVaR (هفته)": f"{(c1*t_week)*100:.2f}%",
            "VaR (ماه)": f"{(v1*t_month)*100:.2f}%", "CVaR (ماه)": f"{(c1*t_month)*100:.2f}%",
            "VaR (سال)": f"{(v1*t_year)*100:.2f}%", "CVaR (سال)": f"{(c1*t_year)*100:.2f}%"
        })
    st.table(pd.DataFrame(risk_full_data))

    if critical_risk_flag:
        st.warning("⚠️ **هشدار ریسک بحرانی:** برخی مقادیر از ۱۰۰-٪ فراتر رفته‌اند. این یعنی بر اساس نوسانات فعلی، پتانسیل نابودی کامل سرمایه در آن بازه زمانی وجود دارد.")

    with st.expander("❓ راهنمای مفاهیم VaR و CVaR"):
        st.markdown("""
        * **VaR (Value at Risk):** بیشترین ضرر احتمالی در یک بازه زمانی. مثلاً VaR روزانه -3% یعنی با اطمینان بالا، ضرر فردا از 3% بیشتر نمی‌شود.
        * **CVaR (Conditional VaR):** میانگین ضرر در سناریوهای بحرانی (اگر بازار سقوط کند، عمق ضرر چقدر خواهد بود).
        """)

    # --- ۴. جدول بیشترین ریزش‌های تاریخی (Max Drawdown) ---
    st.write("### 📉 ۴. جدول بیشترین ریزش‌های تاریخی (Max Drawdown)")
    def get_max_dd(series, days):
        sub = series if days == 0 else series.tail(days)
        dd = (sub - sub.cummax()) / sub.cummax()
        return dd.min()

    dd_data = []
    for name, p_series in portfolios_series.items():
        dd_data.append({
            "نام سبد": name,
            "بیشترین ریزش ۱ روزه": f"{portfolios_returns[name].min()*100:.2f}%",
            "Max DD (۱ هفته)": f"{get_max_dd(p_series, 7)*100:.2f}%",
            "Max DD (۱ ماه)": f"{get_max_dd(p_series, 30)*100:.2f}%",
            "Max DD (۱ سال)": f"{get_max_dd(p_series, 365)*100:.2f}%",
            "Max DD (کل دوره)": f"{get_max_dd(p_series, 0)*100:.2f}%"
        })
    st.table(pd.DataFrame(dd_data))

    with st.expander("❓ راهنمای تحلیل درآودان"):
        st.write("درآودان نشان‌دهنده افت قیمت از بالاترین قله ثبت شده است. این شاخص بدترین تجربه ضرر واقعی را در گذشته نشان می‌دهد.")

    # --- ۵. نمودار رشد سرمایه (Log Scale) ---
    st.write("### 📈 ۵. نمودار مقایسه رشد سرمایه (Logarithmic Scale)")
    fig_log = go.Figure()
    for name, series in portfolios_series.items():
        line = dict(width=3, dash='dot', color='white') if name == "توتال بازار" else dict(width=2)
        fig_log.add_trace(go.Scatter(x=series.index, y=series, name=name, line=line))
    fig_log.update_layout(template="plotly", height=600, yaxis_type="log", hovermode="x unified")
    st.plotly_chart(fig_log, use_container_width=True)

    with st.expander("❓ چرا از مقیاس لگاریتمی استفاده می‌کنیم؟"):
        st.write("در مقیاس لگاریتمی، فاصله‌ها بر اساس درصد تغییرات هستند. این کار باعث می‌شود رشد قیمت در اعداد پایین و بالا به یک اندازه قابل مقایسه باشد.")

except Exception as e:
    st.error(f"خطا در اجرای داشبورد: {e}")