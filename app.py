import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv, set_key
import plotly.express as px
import requests

import database
import agents

load_dotenv()

st.set_page_config(
    page_title="ScoutPulse — Autonomous Price Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

database.init_db()

def run_scheduled_hunt():
    try:
        agents.run_full_watchlist_check()
    except Exception as e:
        print("Background hunt error:", e)

@st.cache_resource
def init_background_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scheduled_hunt, 'interval', hours=12, id='watchlist_hunt_job', replace_existing=True)
    scheduler.start()
    return scheduler

try:
    init_background_scheduler()
except Exception as e:
    print("Scheduler note:", e)

with st.sidebar:
    st.title("ScoutPulse")
    st.caption("Autonomous Price Intelligence")
    st.markdown("---")
    st.subheader("Add Product")
    with st.form("add_product_form", clear_on_submit=True):
        item_name = st.text_input("Product Name", placeholder="e.g. Sony WH-1000XM5")
        target_price = st.number_input("Target Budget (₹)", min_value=1.0, value=15000.0, step=500.0)
        if st.form_submit_button("Add to Watchlist", use_container_width=True):
            if item_name.strip():
                database.add_item(item_name.strip(), target_price)
                st.success("Added product!")
                time.sleep(0.3)
                st.rerun()
            else:
                st.error("Enter product name.")

    st.markdown("---")
    with st.expander("API & Settings"):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        gk = os.getenv("GEMINI_API_KEY", "")
        tk = os.getenv("TAVILY_API_KEY", "")
        tt = os.getenv("TELEGRAM_BOT_TOKEN", "")
        tc = os.getenv("TELEGRAM_CHAT_ID", "")
        with st.form("api_form"):
            ng = st.text_input("GEMINI_API_KEY", value=gk if not gk.startswith("your_") else "", type="password")
            nt = st.text_input("TAVILY_API_KEY", value=tk if not tk.startswith("your_") else "", type="password")
            ntt = st.text_input("TELEGRAM_BOT_TOKEN", value=tt if not tt.startswith("your_") else "", type="password")
            ntc = st.text_input("TELEGRAM_CHAT_ID", value=tc if not tc.startswith("your_") else "")
            if st.form_submit_button("Save", use_container_width=True):
                if not os.path.exists(env_path):
                    with open(env_path, "w") as f: f.write("")
                if ng: set_key(env_path, "GEMINI_API_KEY", ng)
                if nt: set_key(env_path, "TAVILY_API_KEY", nt)
                if ntt: set_key(env_path, "TELEGRAM_BOT_TOKEN", ntt)
                if ntc: set_key(env_path, "TELEGRAM_CHAT_ID", ntc)
                st.success("Saved!")
                time.sleep(0.5)
                st.rerun()

    st.markdown("---")
    if st.button("Send Test Telegram Alert", use_container_width=True):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or token.startswith("your_") or not chat or chat.startswith("your_"):
            st.error("Configure Telegram in sidebar.")
        else:
            try:
                r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": "Test alert from ScoutPulse."}, timeout=10)
                if r.status_code == 200:
                    st.success("Test sent!")
                else:
                    st.error(f"Error: {r.text}")
            except Exception as e:
                st.error(f"Error: {e}")

st.title("ScoutPulse")
st.caption("Autonomous Price Intelligence & Multi-Agent Deal Auditor")
st.markdown("---")

items = database.get_all_items()
watched_count = len(items)
deals_count = sum(1 for i in items if i["status"] == "Deal Found")
savings = sum((i["target_price_inr"] - i["effective_price_inr"]) for i in items if i["status"] == "Deal Found" and 0 < i["effective_price_inr"] < i["target_price_inr"])
effs = [i["effective_price_inr"] for i in items if i["effective_price_inr"] > 0]
lowest = f"₹{min(effs):,.2f}" if effs else "₹0.00"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Trackers", watched_count)
c2.metric("Targets Met", deals_count)
c3.metric("Max Potential Savings", f"₹{savings:,.0f}")
c4.metric("Lowest Deal Found", lowest)

st.markdown("---")

if st.button("Run Price Hunt", type="primary"):
    if not items:
        st.warning("Watchlist is empty.")
    else:
        with st.status("Running Multi-Agent Intelligence Pipeline...", expanded=True) as status:
            res = agents.run_full_watchlist_check()
            st.session_state["execution_results"] = res
            status.update(label="Hunt Completed Successfully", state="complete", expanded=False)
        st.rerun()

if "execution_results" not in st.session_state or st.session_state["execution_results"] is None:
    st.session_state["execution_results"] = []

t1, t2, t3 = st.tabs(["Watchlist & Deals", "Price Analytics", "Agent Execution Logs"])

with t1:
    st.subheader("Tracked Products & Live Deals")
    if not items:
        st.info("No active trackers in your watchlist. Add a product using the sidebar.")
    else:
        for item in items:
            with st.container():
                col_i, col_s, col_a1, col_a2 = st.columns([3, 1, 1, 1])
                with col_i:
                    st.markdown(f"**{item['item_name']}** (ID: #{item['id']})")
                    st.markdown(f"Target Budget: ₹{item['target_price_inr']:,.2f} | Base: ₹{item['current_price_inr']:,.2f} | **Effective: ₹{item['effective_price_inr']:,.2f}**")
                    if item["coupon_notes"]:
                        st.caption(f"Offers: {item['coupon_notes']}")
                    if item["buy_link"]:
                        st.markdown(f"[View Deal Listing]({item['buy_link']})")
                with col_s:
                    st.markdown(f"**Status:**\n`{item['status']}`")
                with col_a1:
                    if st.button("Re-check", key=f"rew_{item['id']}", use_container_width=True):
                        database.reset_item_status(item["id"])
                        st.rerun()
                with col_a2:
                    if st.button("Remove", key=f"del_{item['id']}", type="secondary", use_container_width=True):
                        database.delete_item(item["id"])
                        st.rerun()
                st.divider()

with t2:
    st.subheader("Historical Price Intelligence")
    if not items:
        st.info("No data available.")
    else:
        opts = {f"{i['id']} - {i['item_name']}": i['id'] for i in items}
        sel_label = st.selectbox("Select Product", options=list(opts.keys()), key="sel_hist")
        sel_id = opts[sel_label]
        sel_item = next((i for i in items if i['id'] == sel_id), None)
        hist = database.get_price_history(sel_id)
        if not hist:
            st.info("No price history records found yet. Run a price hunt.")
        else:
            df = pd.DataFrame(hist)
            df["checked_at"] = pd.to_datetime(df["checked_at"])
            df = df.sort_values("checked_at")
            fig = px.area(df, x="checked_at", y="price_inr", title=f"Price Trajectory — {sel_item['item_name']}", template="plotly_dark")
            fig.update_traces(line_color="#10B981", fillcolor="rgba(16, 185, 129, 0.1)")
            if sel_item and sel_item["target_price_inr"] > 0:
                fig.add_hline(y=sel_item["target_price_inr"], line_dash="dash", line_color="#F59E0B", annotation_text="Target Budget")
            fig.update_layout(plot_bgcolor="#111827", paper_bgcolor="#111827", font_family="Inter")
            st.plotly_chart(fig, use_container_width=True)

with t3:
    st.subheader("Multi-Agent Pipeline Execution Timeline")
    if not st.session_state["execution_results"]:
        st.info("No execution trace logs available. Run a Price Hunt.")
    else:
        for res in st.session_state["execution_results"]:
            st.markdown(f"**Product:** `{res.get('item_name')}`")
            for log in res.get("agent_logs", []):
                st.text(log)
            st.divider()
