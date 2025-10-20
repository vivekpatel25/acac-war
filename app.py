import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
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

# ---------- INTRO ----------
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

# ---------- LOAD ----------
@st.cache_data
def load_board(gender):
    try:
        df = pd.read_csv(f"data/leaderboard_{gender}_{SEASON}.csv")
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error loading leaderboard for {gender}: {e}")
        return pd.DataFrame()

# ---------- STYLES ----------
st.markdown("""
<style>
/* Fix Streamlit dark theme issues */
[data-theme="light"] table {
  color: #000 !important;
  background-color: #fff !important;
  border: 2px solid #000 !important;
}
[data-theme="dark"] table {
  color: #fff !important;
  background-color: #111 !important;
  border: 2px solid #fff !important;
}
[data-theme="light"] th {
  background-color: #f2f2f2 !important;
  color: #000 !important;
  border: 1px solid #000 !important;
}
[data-theme="dark"] th {
  background-color: #222 !important;
  color: #fff !important;
  border: 1px solid #fff !important;
}
[data-theme="light"] td, [data-theme="dark"] td {
  border: 1px solid currentColor !important;
  white-space: nowrap !important;
  padding: 8px 10px !important;
  text-align: center !important;
}
[data-theme="light"] tbody tr:hover td {
  background-color: rgba(0,0,0,0.05) !important;
}
[data-theme="dark"] tbody tr:hover td {
  background-color: rgba(255,255,255,0.1) !important;
}
th {
  font-weight: 600 !important;
  cursor: pointer !important;
}
tbody td:last-child {
  font-weight: bold !important;
}
table {
  width: 100% !important;
  border-collapse: collapse !important;
  margin: 0 !important;
}
</style>
""", unsafe_allow_html=True)

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

# ---------- RENDER TABLE ----------
def render_table(df):
    html = "<table><thead><tr>"
    headers = ["#", "Player", "Team", "G", "Offense", "Defense", "Overall"]
    for i, col in enumerate(headers):
        if col in ["G", "Offense", "Defense", "Overall"]:
            html += f"<th onclick='sortTable({i})'>{col} ⬍</th>"
        else:
            html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"
    for idx, row in df.iterrows():
        html += "<tr>"
        html += f"<td>{idx}</td>"
        html += "".join([
            f"<td>{row.get(c, '')}</td>"
            for c in ["Player", "Team", "G", "Offense", "Defense", "Overall"]
        ])
        html += "</tr>"
    html += "</tbody></table>"
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
        df.index = range(1, len(df) + 1)

        for c in ["Offense", "Defense", "Overall"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").round(1)
        if "Overall" in df.columns:
            df = df.sort_values("Overall", ascending=False)

        st.subheader(f"📈 ACAC {gender.capitalize()} Leaderboard")
        st.caption("Click **Games**, **Offense**, **Defense**, or **Overall** to sort.")
        components.html(render_table(df), height=len(df)*43 + 150, scrolling=False)

# ---------- FOOTER ----------
st.markdown("""
<div style="margin-top:2rem; text-align:center; color:gray; font-size:0.9rem;">
<hr>
© 2025 ACAC Analytics • Designed by Vivek Patel
</div>
""", unsafe_allow_html=True)
