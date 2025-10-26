import pandas as pd
import numpy as np
import re, unicodedata
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================
SEASON = 2025
FT_WEIGHT = 0.44
W_MINUTE = 0.20
W_STATS  = 0.80
SCALE = 10.0

DATA_DIR  = Path(__file__).resolve().parent.parent / "data"
BOX_DIR   = DATA_DIR / "boxscores"
TEAM_DIR  = DATA_DIR / "teamstats"
OUT_TMPL  = DATA_DIR / "leaderboard_{gender}_{season}.csv"

# ============================================================
# HELPERS
# ============================================================

def read_csv_any_encoding(path: Path) -> pd.DataFrame:
    """Read CSV robustly handling weird encodings (utf-8-sig / latin1)."""
    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, engine="python")
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, engine="python")

def normalize_name(s):
    """Normalize text fields (strip accents, nbsp, extra spaces)."""
    if pd.isna(s):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def load_all(folder: Path) -> pd.DataFrame:
    """Load and combine all CSVs in a folder."""
    files = sorted(folder.glob("*.csv"))
    if not files:
        return pd.DataFrame()
    parts = []
    for f in files:
        df = read_csv_any_encoding(f)
        df["__file"] = f.name
        parts.append(df)
    df = pd.concat(parts, ignore_index=True)
    print(f"📂 Loaded {len(files)} files from {folder.name} ({len(df)} rows)")
    return df

def coerce_numeric(df: pd.DataFrame, cols: list[str]):
    """Force numeric conversion with 0 fill for missing cols."""
    for c in cols:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

def get_league_ts(team_df):
    """Compute league true-shooting percentage baseline."""
    pts = team_df["PTS"].sum()
    fga = team_df["FGA"].sum()
    fta = team_df["FTA"].sum()
    denom = 2 * (fga + FT_WEIGHT * fta)
    ts = pts / denom if denom > 0 else 0.5
    print(f"   ➤ League TS% = {ts:.3f}")
    return ts

# ============================================================
# CORE PROCESS
# ============================================================

def process_gender(gender: str):
    print(f"\n================= {gender.upper()} =================")

    box_path  = BOX_DIR / gender
    team_path = TEAM_DIR / gender
    out_path  = OUT_TMPL.with_name(OUT_TMPL.name.format(gender=gender, season=SEASON))

    boxes = load_all(box_path)
    teams = load_all(team_path)

    if boxes.empty or teams.empty:
        pd.DataFrame(columns=["player_name","team_name","G","Offense","Defense","Overall"]).to_csv(out_path, index=False)
        print(f"[{gender}] No data found → empty file written.")
        return

    # Clean column names and normalize ids
    boxes.columns = [c.strip() for c in boxes.columns]
    teams.columns = [c.strip() for c in teams.columns]

    for c in ("game_id","team_name","player_name"):
        if c in boxes.columns:
            boxes[c] = boxes[c].map(normalize_name)
    for c in ("game_id","team_name","opp_team_name"):
        if c in teams.columns:
            teams[c] = teams[c].map(normalize_name)

    # Numeric coercion
    box_cols  = ["MIN","FGM","FGA","3PM","3PA","FTM","FTA","OREB","DREB","REB","AST","STL","BLK","TO","PF","PTS"]
    team_cols = ["PTS","FGA","FTA","team_min"]
    coerce_numeric(boxes, box_cols)
    coerce_numeric(teams, team_cols)

    # Handle missing team_min
    if "team_min" not in teams.columns:
        teams["team_min"] = 40.0

    # League TS baseline
    league_ts = get_league_ts(teams)

    # Merge team minutes to each player record
    key = ["game_id","team_name"]
    merged = boxes.merge(teams[key + ["team_min"]], on=key, how="left", validate="m:1")
    merged["team_min"] = merged["team_min"].replace(0,np.nan).fillna(40.0)
    merged["min_share"] = (merged["MIN"]/merged["team_min"]).clip(lower=0)

    # ----------------------------------------------------
    # OFFENSIVE IMPACT
    # ----------------------------------------------------
    merged["plays"] = merged["FGA"] + FT_WEIGHT * merged["FTA"]
    merged["expected_pts"] = 2 * league_ts * merged["plays"]
    merged["off_raw"] = (merged["PTS"] - merged["expected_pts"]) \
                        + 0.7*merged["AST"] + 0.7*merged["OREB"] - merged["TO"]

    # ----------------------------------------------------
    # DEFENSIVE IMPACT
    # ----------------------------------------------------
    merged["def_raw"] = merged["STL"] + 0.7*merged["BLK"] + 0.3*merged["DREB"] - 0.25*merged["PF"]

    # ----------------------------------------------------
    # NORMALIZE WITHIN TEAM-GAME
    # ----------------------------------------------------
    def normalize_within(group):
        pos_sum = group[group > 0].sum()
        return group / pos_sum if pos_sum > 0 else 0

    merged["off_share"] = merged.groupby(key)["off_raw"].transform(normalize_within)
    merged["def_share"] = merged.groupby(key)["def_raw"].transform(normalize_within)

    # ----------------------------------------------------
    # COMBINE MINUTES SHARE + STAT SHARE
    # ----------------------------------------------------
    merged["Off_game"] = W_MINUTE*merged["min_share"] + W_STATS*merged["off_share"]
    merged["Def_game"] = W_MINUTE*merged["min_share"] + W_STATS*merged["def_share"]
    merged["Overall_game"] = merged["Off_game"] + merged["Def_game"]

    # ----------------------------------------------------
    # AGGREGATE SEASON TOTALS
    # ----------------------------------------------------
    agg = (
        merged.groupby(["player_name","team_name"], as_index=False)
        .agg(G=("game_id","nunique"),
             Offense=("Off_game","sum"),
             Defense=("Def_game","sum"),
             Overall=("Overall_game","sum"))
    )

    # Fill NaNs and scale
    for c in ("Offense","Defense","Overall"):
        agg[c] = (agg[c].fillna(0) * SCALE).round(1)

    # Sort & export
    agg = agg.sort_values("Overall", ascending=False).reset_index(drop=True)
    agg.to_csv(out_path, index=False)
    print(f"[{gender}] ✅ Saved {len(agg)} rows → {out_path}")

# ============================================================
# MAIN
# ============================================================

def main():
    for gender in ("men","women"):
        process_gender(gender)

if __name__ == "__main__":
    main()