import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import date

SEASON = "2025/26"
st.set_page_config(page_title="ACAC Basketball Player Impact Ratings", page_icon="🏀", layout="wide")
import os

import requests

def get_last_update_from_github(repo_owner, repo_name, branch="main"):
    """
    Fetches the latest commit date (UTC) from the specified GitHub repo & branch.
    """
    try:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{branch}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        commit_date = data["commit"]["committer"]["date"]
        # Convert from ISO (e.g., 2025-10-20T19:03:00Z) → Oct 20, 2025
        from datetime import datetime
        dt = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%b %d, %Y")
    except Exception as e:
        return "N/A"

# 🔧 Replace with your actual repo info
# Example: repo = "vivekpatel-acac/ACAC-Impact-Ratings"
repo_owner = "vivekpatel25"   # GitHub username or org
repo_name = "acac-war"  # repository name

last_update = get_last_update_from_github(repo_owner, repo_name)

# ---------- HEADER ----------
st.markdown(f"""
<div style="background: linear-gradient(90deg, #002244, #0078D7);
            padding: 1.6rem 2rem; border-radius: 8px; color: white;">
  <h1 style="margin-bottom:0;">🏀 ACAC Player Impact Ratings — {SEASON}</h1>
  <p style="margin-top:0.4rem; font-size:1rem; opacity:0.9;">
     Last updated on • <b>{last_update}</b>
  </p>
</div>
""", unsafe_allow_html=True)

# ---------- INTRO ----------
st.markdown("""
### 📊 What this shows
This leaderboard estimates each player's **overall impact** on their team's performance in the current ACAC season.

_This “Impact Index” blends box score and playing time similar to ESPN’s WAR analytics._
---
""")

# ---------- LOAD ----------
@st.cache_data
def load_board(gender):
    try:
        df = pd.read_csv(f"data/leaderboard_{gender}_2025.csv")
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error loading leaderboard for {gender}: {e}")
        return pd.DataFrame()

# ---------- SORT SCRIPT ----------
SORT_SCRIPT = """
<script>
let sortDirections = {};
function sortTable(n) {
  const table = event.target.closest("table");
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const currentDir = sortDirections[n] || "desc";
  const newDir = currentDir === "asc" ? "desc" : "asc";
  sortDirections[n] = newDir;

  rows.sort((a, b) => {
    const aText = a.cells[n].innerText.trim();
    const bText = b.cells[n].innerText.trim();
    const aNum = parseFloat(aText);
    const bNum = parseFloat(bText);
    if (!isNaN(aNum) && !isNaN(bNum)) {
      return newDir === "asc" ? aNum - bNum : bNum - aNum;
    }
    return newDir === "asc"
      ? aText.localeCompare(bText)
      : bText.localeCompare(aText);
  });
  rows.forEach(r => tbody.appendChild(r));
}
</script>
"""

# ---------- INLINE TABLE RENDER ----------
def render_table(df):
    # Detect dark or light mode
    dark = st.get_option("theme.base") == "dark"
    if dark:
        border_color, text_color, header_bg, row_hover, table_bg = (
            "#fff", "#fff", "#222", "rgba(255,255,255,0.1)", "#111"
        )
    else:
        border_color, text_color, header_bg, row_hover, table_bg = (
            "#000", "#000", "#f2f2f2", "rgba(0,0,0,0.05)", "#fff"
        )

    # Normalize numeric columns for coloring
    for col in ["Offense", "Defense", "Overall"]:
        if col in df.columns and df[col].notna().any():
            vmin, vmax = df[col].min(), df[col].max()
            rng = vmax - vmin if vmax != vmin else 1
            df[f"_{col}_norm"] = (df[col] - vmin) / rng
        else:
            df[f"_{col}_norm"] = 0.0

    html = f"""
    <div style="overflow-x:auto; margin:0; padding:0;">
      <table style="min-width:600px; width:100%; border-collapse:collapse; font-size:16px;
                    color:{text_color}; background-color:{table_bg};
                    border:2px solid {border_color}; border-radius:6px;">
        <thead><tr style="background:{header_bg}; color:{text_color};">
    """
    headers = ["Player", "Team", "G", "Offense", "Defense", "Overall"]
    for i, col in enumerate(headers):
        cursor = "pointer" if col in ["G", "Offense", "Defense", "Overall"] else "default"
        html += (
            f"<th onclick='sortTable({i})' style='border:1px solid {border_color}; "
            f"white-space:nowrap; cursor:{cursor}; padding:8px 10px;'>{col} ⬍</th>"
            if cursor == "pointer"
            else f"<th style='border:1px solid {border_color}; white-space:nowrap; padding:8px 10px;'>{col}</th>"
        )
    html += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        html += f"<tr onmouseover=\"this.style.background='{row_hover}'\" onmouseout=\"this.style.background='transparent'\">"
        for c in headers:
            bg = "transparent"
            if c == "Offense":
                intensity = row.get("_Offense_norm", 0)
                bg = f"rgba(255,0,0,{0.15 + 0.75*intensity})"
            elif c == "Defense":
                intensity = row.get("_Defense_norm", 0)
                bg = f"rgba(0,255,0,{0.15 + 0.75*intensity})"
            elif c == "Overall":
                intensity = row.get("_Overall_norm", 0)
                bg = f"rgba(128,128,128,{0.15 + 0.75*intensity})"

            weight = "bold" if c == "Overall" else "normal"
            html += (
                f"<td style='border:1px solid {border_color}; text-align:center; "
                f"white-space:nowrap; padding:8px 10px; font-weight:{weight}; "
                f"background-color:{bg};'>{row.get(c, '')}</td>"
            )
        html += "</tr>"
    html += "</tbody></table></div>"
    return html + SORT_SCRIPT

# ---------- MAIN ----------

tabs = st.tabs(["👨 Men", "👩 Women"])
for tab, gender in zip(tabs, ["men", "women"]):
    with tab:
        df = load_board(gender)
        if df.empty:
            st.info(f"No leaderboard yet for {gender}.")
            continue

        # rename & clean
        col_map = {}
        for c in df.columns:
            lc = c.lower()
            if "player" in lc:
                col_map[c] = "Player"
            elif "team" in lc:
                col_map[c] = "Team"
            elif "game" in lc and "id" not in lc:
                col_map[c] = "G"
            elif "off" in lc:
                col_map[c] = "Offense"
            elif "def" in lc:
                col_map[c] = "Defense"
            elif "overall" in lc or "total" in lc:
                col_map[c] = "Overall"

        df = df.rename(columns=col_map)
        keep = [c for c in ["Player", "Team", "G", "Offense", "Defense", "Overall"] if c in df.columns]
        df = df[keep].copy()

        for c in ["Offense", "Defense", "Overall"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").round(1)
        if "Overall" in df.columns:
            df = df.sort_values("Overall", ascending=False)

        st.subheader(f"📈 ACAC {gender.capitalize()} Leaderboard")
        st.caption("Click **Games**, **Offense**, **Defense**, or **Overall** to sort.")
        # Auto height (no blank space, mobile responsive)
        components.html(render_table(df), height=len(df) * 38, scrolling=False)

# ---------- FOOTER ----------
st.markdown("""
<div style="margin-top:2rem; text-align:center; color:gray; font-size:0.9rem;">
<hr>
© 2025 ACAC Analytics • Designed by Vivek Patel
</div>
""", unsafe_allow_html=True)
