import pandas as pd
import numpy as np
from pathlib import Path
import re, unicodedata

# ---------------- CONFIG ----------------
SEASON = 2025
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BOX_DIR  = DATA_DIR / "boxscores"
TEAM_DIR = DATA_DIR / "teamstats"
OUT_TMPL = DATA_DIR / "leaderboard_{gender}_{season}.csv"

W_MINUTE = 0.20   # weight for minutes share
W_STATS  = 0.80   # weight for box-score stats
FT_WEIGHT = 0.44  # for possessions calc
SCALE = 10.0      # presentation scale
# ----------------------------------------


def _read_csv_any_encoding(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, engine="python")
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, engine="python")


def _normalize_name(s: str) -> str:
    if pd.isna(s): return ""
    s = unicodedata.normalize("NFKD", str(s)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _load_all(folder: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(folder.glob("*.csv")):
        df = _read_csv_any_encoding(f)
        df["__file"] = f.name
        rows.append(df)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _coerce_numeric(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def get_league_ts(team_df):
    pts = team_df["PTS"].sum()
    fga = team_df["FGA"].sum()
    fta = team_df["FTA"].sum()
    denom = 2 * (fga + FT_WEIGHT * fta)
    return pts / denom if denom > 0 else 0.5


def process_gender(gender: str):
    box_path  = BOX_DIR  / gender
    team_path = TEAM_DIR / gender
    out_path  = OUT_TMPL.with_name(OUT_TMPL.name.format(gender=gender, season=SEASON))

    boxes = _load_all(box_path)
    teams = _load_all(team_path)

    if boxes.empty or teams.empty:
        pd.DataFrame(columns=["player_name","team_name","G","OffRtg","DefRtg","TotRtg"]).to_csv(out_path, index=False)
        print(f"[{gender}] No data found. Empty file written.")
        return

    boxes.columns = [c.strip() for c in boxes.columns]
    teams.columns = [c.strip() for c in teams.columns]

    for c in ("game_id","team_name","player_name"):
        if c in boxes.columns:
            boxes[c] = boxes[c].map(_normalize_name)
    for c in ("game_id","team_name","opp_team_name"):
        if c in teams.columns:
            teams[c] = teams[c].map(_normalize_name)

    # numeric conversions
    _coerce_numeric(boxes, ["MIN","FGM","FGA","3PM","3PA","FTM","FTA","OREB","DREB","REB","AST","STL","BLK","TO","PF","PTS"])
    _coerce_numeric(teams, ["PTS","FGA","FTA","team_min"])

    # fallback for team minutes
    if "team_min" not in teams.columns:
        teams["team_min"] = 40.0

    # league efficiency baseline
    league_ts = get_league_ts(teams)
    print(f"[{gender}] League TS% = {league_ts:.3f}")

    key = ["game_id","team_name"]
    merged = boxes.merge(teams[key + ["team_min"]], on=key, how="left", validate="m:1")
    merged["team_min"] = merged["team_min"].replace(0,np.nan).fillna(40.0)
    merged["min_share"] = (merged["MIN"]/merged["team_min"]).clip(lower=0)

    # --- OFFENSIVE RAW IMPACT (vs league) ---
    merged["plays"] = merged["FGA"] + FT_WEIGHT * merged["FTA"]
    merged["expected_pts"] = 2 * league_ts * merged["plays"]
    merged["off_raw"] = (merged["PTS"] - merged["expected_pts"]) \
                        + 0.7*merged["AST"] + 0.7*merged["OREB"] - merged["TO"]

    # --- DEFENSIVE RAW IMPACT ---
    merged["def_raw"] = merged["STL"] + 0.7*merged["BLK"] + 0.3*merged["DREB"] - 0.25*merged["PF"]

    # normalize within team-game
    def _normalize_within(g):
        pos_sum = g[g>0].sum()
        return g / pos_sum if pos_sum>0 else 0

    merged["off_share"] = merged.groupby(key)["off_raw"].transform(_normalize_within)
    merged["def_share"] = merged.groupby(key)["def_raw"].transform(_normalize_within)

    # combine minutes + stats
    merged["Off_game"] = W_MINUTE*merged["min_share"] + W_STATS*merged["off_share"]
    merged["Def_game"] = W_MINUTE*merged["min_share"] + W_STATS*merged["def_share"]
    merged["Tot_game"] = merged["Off_game"] + merged["Def_game"]

    # aggregate per player
    agg = (merged.groupby(["player_name","team_name"], as_index=False)
           .agg(G=("game_id","nunique"),
                OffRtg=("Off_game","sum"),
                DefRtg=("Def_game","sum"),
                TotRtg=("Tot_game","sum")))

    for c in ("OffRtg","DefRtg","TotRtg"):
        agg[c] = (agg[c]*SCALE).round(1)

    agg = agg.sort_values("TotRtg", ascending=False).reset_index(drop=True)
    agg.to_csv(out_path,index=False)
    print(f"[{gender}] Wrote {len(agg)} rows → {out_path}")


def main():
    for gender in ("men","women"):
        process_gender(gender)

if __name__ == "__main__":
    main()