import streamlit as st
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
from fetcher import MarketFetcher
from aggregator import MarketAggregator
from tracker import RealTimeTracker

# Page config
st.set_page_config(page_title="Prediction Market Aggregator", layout="wide", page_icon="📊")

# Initialize components in session state
if 'fetcher' not in st.session_state:
    st.session_state.fetcher = MarketFetcher()
if 'aggregator' not in st.session_state:
    st.session_state.aggregator = MarketAggregator()
if 'tracker' not in st.session_state:
    # Tracker gets its own Fetcher instance via factory to avoid event loop conflicts
    st.session_state.tracker = RealTimeTracker(MarketFetcher, st.session_state.aggregator)
    st.session_state.tracker.start_in_background()

st.title("📊 Prediction Market Aggregator")
st.markdown("Track and aggregate probabilities from **Polymarket**, **Kalshi**, and **PredictIt**.")

# Sidebar for configuration
st.sidebar.header("Tracking Configuration")
st.sidebar.markdown("Set up real-time alerts for Discord.")
tracked_query = st.sidebar.text_input("Question to Track", placeholder="e.g., Trump wins 2024")
webhook_url = st.sidebar.text_input("Discord Webhook URL", type="password")
interval = st.sidebar.slider("Check Interval (seconds)", 60, 3600, 300)

if st.sidebar.button("Add Tracking Job"):
    if tracked_query and webhook_url:
        st.session_state.tracker.add_tracking_job(tracked_query, webhook_url, interval=interval)
        st.sidebar.success(f"Tracking started for: {tracked_query}")
    else:
        st.sidebar.error("Please provide both query and webhook URL.")

# Main search interface
st.markdown("### Search & Aggregate")
query = st.text_input("Enter keywords or a full sentence to aggregate market odds:", placeholder="e.g., Who will win the 2024 election?")

if query:
    with st.spinner(f"Searching for '{query}' across platforms..."):
        async def get_data():
            return await st.session_state.fetcher.fetch_all()

        # Streamlit 1.37+ uses a specific loop, we should ensure we're using asyncio correctly
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        all_markets = asyncio.run(get_data())
        matched = st.session_state.aggregator.aggregate_markets(query, all_markets)

        if matched:
            st.subheader(f"Results for: {query}")

            # Aggregate probabilities
            probs = st.session_state.aggregator.calculate_aggregate_probability(matched, outcome_name="Yes")

            col1, col2, col3 = st.columns(3)
            col1.metric("Accuracy Weighted 🎯", f"{probs.get('accuracy_weighted', 0):.2%}")
            col2.metric("Simple Average", f"{probs.get('simple_average', 0):.2%}")
            col3.metric("Liquidity Weighted 💰", f"{probs.get('liquidity_weighted', 0):.2%}")

            # Show individual markets
            st.markdown("---")
            st.markdown("### Individual Market Data")
            market_data = []
            for m in matched:
                yes_prob = 0
                found = False
                for o in m['outcomes']:
                    if o['name'] and "yes" in str(o['name']).lower():
                        yes_prob = o['probability']
                        found = True
                        break

                if not found and m['outcomes']:
                    yes_prob = m['outcomes'][0]['probability']

                market_data.append({
                    "Platform": m['platform'],
                    "Question": m['question'],
                    "Probability": f"{yes_prob:.2%}",
                    "URL": m['url']
                })

            df = pd.DataFrame(market_data)
            st.dataframe(df, width='stretch')

            # Visualization
            st.markdown("### Probability Distribution")
            fig, ax = plt.subplots(figsize=(10, 4))
            platforms = [m['platform'] for m in matched]
            probs_list = [float(m.replace('%', ''))/100 for m in df['Probability']]

            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
            ax.bar(range(len(platforms)), probs_list, color=colors[:len(platforms)])
            ax.set_xticks(range(len(platforms)))
            ax.set_xticklabels(platforms, rotation=45, ha='right')
            ax.set_ylabel('Probability')
            ax.set_ylim(0, 1)
            ax.axhline(y=probs.get('accuracy_weighted', 0), color='r', linestyle='--', label='Accuracy Weighted Avg')
            ax.legend()
            st.pyplot(fig)

        else:
            st.warning("No matching markets found. Try different keywords.")
else:
    st.info("Enter a query above to see aggregated probabilities from Polymarket, Kalshi, and PredictIt.")

# Show active tracking jobs
if st.session_state.tracker.tracking_jobs:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Active Tracking Jobs")
    for q in list(st.session_state.tracker.tracking_jobs.keys()):
        col1_side, col2_side = st.sidebar.columns([4, 1])
        col1_side.write(f"• {q}")
        if col2_side.button("🗑️", key=f"del_{q}"):
            st.session_state.tracker.remove_tracking_job(q)
            st.rerun()
