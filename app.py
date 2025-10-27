import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import requests
from datetime import datetime

SEASON = "2025/26"
st.set_page_config(page_title="ACAC Basketball Player Impact Ratings", page_icon="🏀", layout="wide")

# ---------- FETCH LAST UPDATE ----------
def get_last_update_from_github(repo_owner, repo_name, branch="main"):
    try:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{branch}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        dt = datetime.strptime(data["commit"]["committer"]["date"], "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%b %d, %Y")
    except Exception:
        return "N/A"

repo_owner = "vivekpatel25"
repo_name = "acac-war"
last_update = get_last_update_from_github(repo_owner, repo_name)

# ---------- HEADER ----------
st.markdown(f"""
<div style="background:linear-gradient(90deg,#002244,#0078D7);
            padding:1.6rem 2rem;border-radius:8px;color:white;">
  <h1 style="margin-bottom:0;">🏀 ACAC Basketball Player Impact Ratings — {SEASON}</h1>
  <p style="margin-top:0.4rem;font-size:1rem;opacity:0.9;">
     Last updated on • <b>{last_update}</b>
  </p>
</div>
""", unsafe_allow_html=True)

# ---------- INTRO ----------
st.markdown("""
<h3 style="display:flex;align-items:center;">
  📊&nbsp;About These Ratings
</h3>
<p style="font-size:1.05rem; color:#444; margin-top:-0.2rem;">
  Each player’s <b>Overall Impact</b> blends offensive creation, defensive activity, and playing time contribution.
</p>
<hr style="margin-top:0.8rem; margin-bottom:1.2rem; border: none; border-top: 1px solid #ddd;">
""", unsafe_allow_html=True)

# ---------- LOAD LEADERBOARDS ----------
@st.cache_data
def load_board(gender):
    try:
        df = pd.read_csv(f"data/leaderboard_{gender}_2025.csv")
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error loading {gender} data: {e}")
        return pd.DataFrame()

# ---------- SORT SCRIPT ----------
SORT_SCRIPT = """
<script>
let sortDirections = {};
function sortTable(n) {
  const table = event.target.closest("table");
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr")).filter(r => !r.classList.contains("divider"));
  const divider = tbody.querySelector(".divider");
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

  // keep divider fixed after sorting
  tbody.innerHTML = "";
  rows.forEach((r, i) => {
    tbody.appendChild(r);
    if (i === 19 && divider) tbody.appendChild(divider);
  });
}
</script>
"""

# ---------- TABLE RENDERER ----------
def render_table(df):
    dark = st.get_option("theme.base") == "dark"
    if dark:
        border_color, text_color, header_bg, row_hover, table_bg = (
            "#fff", "#fff", "#222", "rgba(255,255,255,0.1)", "#111"
        )
    else:
        border_color, text_color, header_bg, row_hover, table_bg = (
            "#000", "#000", "#f2f2f2", "rgba(0,0,0,0.05)", "#fff"
        )

    for col in ["Offense", "Defense", "Overall"]:
        if col in df.columns and df[col].notna().any():
            vmin, vmax = df[col].min(), df[col].max()
            rng = vmax - vmin if vmax != vmin else 1
            df[f"_{col}_norm"] = (df[col] - vmin) / rng
        else:
            df[f"_{col}_norm"] = 0.0

    headers = ["Player", "Team", "Games", "Offense", "Defense", "Overall"]
    html = f"""
    <div style="overflow-x:auto;margin:0;padding:0;">
      <table style="width:100%;border-collapse:collapse;font-size:16px;
                    color:{text_color};background-color:{table_bg};
                    border:2px solid {border_color};border-radius:6px;">
        <thead><tr style="background:{header_bg};color:{text_color};">
    """
    for i, col in enumerate(headers):
        cursor = "pointer" if col in ["Games", "Offense", "Defense", "Overall"] else "default"
        html += (
            f"<th onclick='sortTable({i})' style='border:1px solid {border_color};white-space:nowrap;"
            f"cursor:{cursor};padding:8px 10px;'>{col} ⬍</th>"
            if cursor == "pointer"
            else f"<th style='border:1px solid {border_color};white-space:nowrap;padding:8px 10px;'>{col}</th>"
        )
    html += "</tr></thead><tbody>"

    for idx, row in df.iterrows():
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
                f"<td style='border:1px solid {border_color};text-align:center;white-space:nowrap;"
                f"padding:8px 10px;font-weight:{weight};background-color:{bg};'>"
                f"{row.get(c,'')}</td>"
            )
        html += "</tr>"
        if idx == 19:  # ---- Top-20 divider ----
            html += f"<tr class='divider'><td colspan='{len(headers)}' style='border-top:4px solid {border_color};'></td></tr>"

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

        df = df.rename(columns=str.strip)
        df = df.rename(columns={
            next((c for c in df.columns if "player" in c.lower()), "Player"): "Player",
            next((c for c in df.columns if "team" in c.lower()), "Team"): "Team",
            next((c for c in df.columns if "game" in c.lower()), "Games"): "Games",
            next((c for c in df.columns if "off" in c.lower()), "Offense"): "Offense",
            next((c for c in df.columns if "def" in c.lower()), "Defense"): "Defense",
            next((c for c in df.columns if "overall" in c.lower() or "total" in c.lower()), "Overall"): "Overall",
        })

        keep = [c for c in ["Player","Team","Games","Offense","Defense","Overall"] if c in df.columns]
        df = df[keep].copy()
        for c in ["Offense","Defense","Overall"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").round(1)
        if "Overall" in df.columns:
            df = df.sort_values("Overall", ascending=False).reset_index(drop=True)

        st.subheader(f"📈 ACAC {gender.capitalize()} Leaderboard — Full Table")
        st.caption("Click **Games**, **Offense**, **Defense**, or **Overall** to sort.")

        # --- Note box (auto adapts to theme) ---
        dark_mode = st.get_option("theme.base") == "dark"
        note_bg = "#1e1e1e" if dark_mode else "#f0f4ff"
        note_text = "#e0e0e0" if dark_mode else "#000"
        note_border = "#3399ff" if dark_mode else "#0066cc"

        st.markdown(f"""
        <div style="background-color:{note_bg};border-left:6px solid {note_border};
            padding:10px 15px;border-radius:6px;margin-bottom:1rem;
            color:{note_text};font-size:0.95rem;">
        <b>🟦 Note:</b> The <b>Top 20 players</b> are displayed above the dark horizontal line.
        </div>
        """, unsafe_allow_html=True)
        components.html(render_table(df), height=len(df)*38 + 120, scrolling=False)

# ---------- FOOTER ----------
st.markdown("""
<div style="margin-top:2rem;text-align:center;color:gray;font-size:0.9rem;">
<hr>
© 2025 ACAC Basketball Ratings • Designed by Vivek Patel
</div>
""", unsafe_allow_html=True)