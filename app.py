import streamlit as st
import pandas as pd
from datetime import date

SEASON = 2025

st.set_page_config(
    page_title="ACAC Player Impact Ratings",
    page_icon="🏀",
    layout="wide",
)

# ---------- Gradient Banner ----------
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
- 🔴 **Offense:** Scoring + creation impact  
- 🟩 **Defense:** Stops + rebounding impact  
- ⚫ **Overall:** Sum of offensive + defensive value  

_Not a pure WAR model — more a possession-based “Impact Index” inspired by ESPN analytics._
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
/* Dark/light adaptive background */
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

/* Table look */
.stTable tr td, .stTable tr th {
    text-align:center !important;
    font-weight:600 !important;
    padding:0.4rem 0.6rem !important;
}
.stTable th {
    font-weight:700 !important;
    background:#e6e6e6;
}
@media (prefers-color-scheme: dark) {
    .stTable th { background:#222; }
}

/* Full page scroll */
[data-testid="stDataFrame"], [data-testid="stHorizontalBlock"] {
    overflow:visible !important;
}

/* Footer */
.footer {
    margin-top:3rem;
    text-align:center;
    color:gray;
    font-size:0.9rem;
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

        # Rename + format
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
        df["G"] = df["G"].astype(int)
        for c in ("Offense", "Defense", "Overall"):
            df[c] = df[c].round(1)

        st.subheader(f"📈 ACAC {gender.capitalize()} Leaderboard")
        st.caption("Player / Team columns fixed • Sort by **Games**, **Offense**, **Defense**, or **Overall**")

        # Show static table (no inner scroll)
        st.table(df.style.format({
            "Offense": "{:.1f}",
            "Defense": "{:.1f}",
            "Overall": "{:.1f}"
        }))

# ---------- Footer ----------
st.markdown("""
<div class="footer">
<hr>
© 2025 ACAC Analytics • Designed by Vivek Patel
</div>
""", unsafe_allow_html=True)