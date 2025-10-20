import streamlit as st
import pandas as pd
from datetime import date

SEASON = 2025

st.set_page_config(
    page_title="ACAC Player Impact Ratings",
    page_icon="🏀",
    layout="wide",
)

# ---------- Gradient Header ----------
st.markdown(f"""
<div style="
    background: linear-gradient(90deg, #002244, #0078D7);
    padding: 1.6rem 2rem;
    border-radius: 8px;
    color: white;
">
  <h1 style="margin-bottom:0;">🏀 ACAC Player Impact Ratings — {SEASON}</h1>
  <p style="margin-top:0.4rem; font-size:1rem; opacity:0.9;">
     Updated automatically • <b>{date.today():%b %d, %Y}</b>
  </p>
</div>
""", unsafe_allow_html=True)

# ---------- Overview ----------
st.markdown("""
### 📊 What this shows
This leaderboard estimates each player's **overall impact** on their team's performance in the current ACAC season.

**Weights**
- 🎯 **30 %** — Team minute share (on-court value)  
- 📊 **70 %** — Individual box-score impact  

**Ratings**
- 🔴 **Offense:** Scoring & creation impact  
- 🟩 **Defense:** Stops & rebounding impact  
- ⚫ **Overall:** Combined impact (Off + Def)

_Not a WAR metric — this “Impact Index” blends box score and playing time similar to ESPN’s analytics._
---
""")

# ---------- Data Loader ----------
@st.cache_data
def load_board(gender):
    try:
        return pd.read_csv(f"data/leaderboard_{gender}_{SEASON}.csv")
    except Exception:
        return pd.DataFrame()

# ---------- Styling ----------
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg);
    color: var(--fg);
}
@media (prefers-color-scheme: dark) {
    :root { --bg:#0e1117; --fg:#fafafa; }
}
@media (prefers-color-scheme: light) {
    :root { --bg:#f9f9f9; --fg:#111; }
}

/* Table tweaks */
[data-testid="stDataFrame"] div[data-testid="stVerticalBlock"] {
    overflow: visible !important;
}
thead tr th div {
    justify-content: center !important;
    white-space: nowrap !important;
}
tbody td {
    text-align: center !important;
    white-space: nowrap !important;
}
tr:nth-child(even) {
    background-color: rgba(200,200,200,0.04);
}

/* Highlight last column (Overall) */
tbody td:last-child {
    background: linear-gradient(180deg, #cfcfcf, #bfbfbf);
    font-weight: 700;
}
@media (prefers-color-scheme: dark) {
    tbody td:last-child {
        background: linear-gradient(180deg, #2a2a2a, #1e1e1e);
    }
}

/* Footer */
.footer {
    margin-top: 3rem;
    text-align: center;
    color: gray;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# ---------- Tabs ----------
tabs = st.tabs(["👨 Men", "👩 Women"])

for tab, gender in zip(tabs, ["men", "women"]):
    with tab:
        df = load_board(gender)
        if df.empty:
            st.info(
                f"No leaderboard yet for **{gender}**. "
                f"Run `python compute/compute_rtg.py` to generate "
                f"`data/leaderboard_{gender}_{SEASON}.csv`."
            )
            continue

        # Rename and prepare
        df = df.rename(columns={
            "player_name": "Player",
            "team_name": "Team",
            "games": "G",
            "Off": "Offense",
            "Def": "Defense",
            "Overall": "Overall"
        })
        cols = ["Player", "Team", "G", "Offense", "Defense", "Overall"]
        df = df[cols].copy()

        # Add rank starting at 1
        df.index = range(1, len(df) + 1)
        df.index.name = "#"

        # Round numeric columns
        df["G"] = df["G"].astype(int)
        for c in ("Offense", "Defense", "Overall"):
            df[c] = df[c].round(1)

        st.subheader(f"📈 ACAC {gender.capitalize()} Leaderboard")
        st.caption("Player / Team columns fixed • Sort by **Games**, **Offense**, **Defense**, or **Overall**")

        # Split static vs sortable columns
        static_cols = ["#", "Player", "Team"]
        sortable_cols = ["G", "Offense", "Defense", "Overall"]

        # Streamlit dataframe allows sorting by column headers
        st.dataframe(
            df.style.format({
                "Offense": "{:.1f}",
                "Defense": "{:.1f}",
                "Overall": "{:.1f}"
            }),
            use_container_width=True,
            hide_index=False
        )

# ---------- Footer ----------
st.markdown("""
<div class="footer">
<hr>
© 2025 ACAC Analytics • Designed by Vivek Patel
</div>
""", unsafe_allow_html=True)