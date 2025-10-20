import streamlit as st
import pandas as pd
from datetime import date

SEASON = 2025

st.set_page_config(page_title="ACAC Player Impact Ratings", page_icon="🏀", layout="wide")

# ---------- HEADER ----------
st.markdown(f"""
<div style="background: linear-gradient(90deg, #002244, #0078D7);
            padding: 1.6rem 2rem; border-radius: 8px; color: white;">
  <h1 style="margin-bottom:0;">🏀 ACAC Player Impact Ratings — {SEASON}</h1>
  <p style="margin-top:0.4rem; font-size:1rem; opacity:0.9;">
     Updated automatically • <b>{date.today():%b %d, %Y}</b>
  </p>
</div>
""", unsafe_allow_html=True)

# ---------- OVERVIEW ----------
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

# ---------- LOAD DATA ----------
@st.cache_data
def load_board(gender):
    try:
        df = pd.read_csv(f"data/leaderboard_{gender}_{SEASON}.csv")
        df.columns = df.columns.str.strip()  # remove stray spaces
        return df
    except Exception as e:
        st.error(f"Error loading leaderboard for {gender}: {e}")
        return pd.DataFrame()

# ---------- STYLING ----------
st.markdown("""
<style>
/* Background auto-adjust */
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
tbody td:last-child {
    background: linear-gradient(180deg, #eaeaea, #d6d6d6);
    font-weight: 700;
}
@media (prefers-color-scheme: dark) {
    tbody td:last-child {
        background: linear-gradient(180deg, #2a2a2a, #1e1e1e);
    }
}

/* Ensure page scroll, not inner div */
[data-testid="stDataFrame"] div[data-testid="stVerticalBlock"] {
    overflow: visible !important;
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

# ---------- TABS ----------
tabs = st.tabs(["👨 Men", "👩 Women"])

for tab, gender in zip(tabs, ["men", "women"]):
    with tab:
        df = load_board(gender)
        if df.empty:
            st.info(f"No leaderboard yet for **{gender}** division.")
            continue

        # Detect possible column names
        col_map = {}
        for col in df.columns:
            lc = col.lower()
            if "player" in lc:
                col_map[col] = "Player"
            elif "team" in lc:
                col_map[col] = "Team"
            elif "game" in lc and "id" not in lc:
                col_map[col] = "G"
            elif "off" in lc:
                col_map[col] = "Offense"
            elif "def" in lc:
                col_map[col] = "Defense"
            elif "overall" in lc or "total" in lc:
                col_map[col] = "Overall"

        df = df.rename(columns=col_map)

        # Keep only relevant columns that exist
        keep = [c for c in ["Player", "Team", "G", "Offense", "Defense", "Overall"] if c in df.columns]
        df = df[keep].copy()

        # Add ranking
        df.index = range(1, len(df) + 1)
        df.index.name = "#"

        # Clean values
        if "G" in df.columns:
            df["G"] = df["G"].astype(int)
        for c in ("Offense", "Defense", "Overall"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").round(1)

        # Default sort by Overall descending if available
        if "Overall" in df.columns:
            df = df.sort_values("Overall", ascending=False)

        st.subheader(f"📈 ACAC {gender.capitalize()} Leaderboard")
        st.caption("Player / Team fixed • Click **Games**, **Offense**, **Defense**, or **Overall** to sort")

        # Sortable + static columns
        st.data_editor(
            df,
            use_container_width=True,
            hide_index=False,
            disabled=True,  # disables cell editing
            column_order=[c for c in ["Player", "Team", "G", "Offense", "Defense", "Overall"] if c in df.columns],
            key=f"{gender}_editor"
        )

# ---------- FOOTER ----------
st.markdown("""
<div class="footer">
<hr>
© 2025 ACAC Analytics • Designed by Vivek Patel
</div>
""", unsafe_allow_html=True)