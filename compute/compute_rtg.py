import pandas as pd
import numpy as np
from pathlib import Path
import re
import unicodedata

# ---------------- CONFIG ----------------
SEASON = 2025
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BOX_DIR = DATA_DIR / "boxscores"          # expects subfolders men/, women/
TEAM_DIR = DATA_DIR / "teamstats"         # expects subfolders men/, women/
OUT_TMPL = DATA_DIR / "leaderboard_{gender}_{season}.csv"

# Per-game blend (minutes vs. stats)
W_MINUTE = 0.30
W_STATS  = 0.70

# Offense construction: give points the lion's share
OFF_POINTS_W   = 0.80   # weight on PTS inside off_raw
OFF_SUPPORT_W  = 0.20   # weight on creation/2nd-chance (AST/OREB)

# Display scale so numbers feel like "WAR-ish" bands
SCALE = 10.0
ROUND_DEC = 1
# ----------------------------------------


def _read_csv_any_encoding(path: Path) -> pd.DataFrame:
    """Robust CSV reader for BOM/latin1/NBSP issues."""
    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, engine="python")
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, engine="python")


def _normalize_name(s: str) -> str:
    if pd.isna(s):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _load_all(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.csv"))
    dfs = []
    for f in files:
        df = _read_csv_any_encoding(f)
        df["__source_file"] = f.name
        dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def _coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        else:
            df[c] = 0.0
    return df


def _positive_share(series: pd.Series) -> pd.Series:
    """Return each value divided by the sum of positive values in its group."""
    pos = series.clip(lower=0)
    s = pos.sum()
    if s <= 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return pos / s


def process_gender(gender: str):
    box_path  = BOX_DIR  / gender
    team_path = TEAM_DIR / gender
    out_path  = OUT_TMPL.with_name(OUT_TMPL.name.format(gender=gender, season=SEASON))

    # ---- Load ----
    boxes = _load_all(box_path)
    teams = _load_all(team_path)

    if boxes.empty or teams.empty:
        pd.DataFrame(columns=["player_name","team_name","games","Offense","Defense","Total"]).to_csv(out_path, index=False)
        print(f"[{gender}] No data found. Wrote empty file: {out_path}")
        return

    # ---- Clean/standardize ----
    boxes.columns = [c.strip() for c in boxes.columns]
    teams.columns = [c.strip() for c in teams.columns]

    for c in ("game_id","team_name","player_name"):
        if c in boxes.columns:
            boxes[c] = boxes[c].map(_normalize_name)
    for c in ("game_id","team_name","opp_team_name"):
        if c in teams.columns:
            teams[c] = teams[c].map(_normalize_name)

    # Player numeric
    box_num = ["MIN","FGM","FGA","3PM","3PA","FTM","FTA","OREB","DREB","REB","AST","STL","BLK","TO","PF","PTS"]
    _coerce_numeric(boxes, box_num)

    # Team minutes present? else fallback/rename/default to 40
    if "team_min" not in teams.columns:
        rename_key = None
        for k in ("team minutes","minutes","MIN","min","gmin","GMIN"):
            if k in teams.columns:
                rename_key = k
                break
        if rename_key:
            teams = teams.rename(columns={rename_key: "team_min"})
        else:
            teams["team_min"] = 40.0
    _coerce_numeric(teams, ["team_min"])

    # ---- Merge team minutes into player rows ----
    key = ["game_id","team_name"]
    for k in key:
        if k not in boxes.columns or k not in teams.columns:
            raise SystemExit(f"[{gender}] Missing merge key '{k}' in box/team files.")
    merged = boxes.merge(teams[key + ["team_min"]], on=key, how="left", validate="m:1")
    merged["team_min"] = merged["team_min"].replace(0, np.nan).fillna(40.0)
    merged["min_share"] = (merged["MIN"] / merged["team_min"]).clip(lower=0)

    # ---- Offensive raw (points-heavy) ----
    # Volume & efficiency dampers
    merged["actions"] = merged["FGA"] + 0.44*merged["FTA"] + merged["AST"]
    merged["vol_factor"] = np.minimum(1.0, merged["actions"] / 8.0)   # full credit at ~8 actions
    ts_den = 2.0 * (merged["FGA"] + 0.44*merged["FTA"])
    merged["ts_pct"] = np.where(ts_den > 0, merged["PTS"] / ts_den, 0.0)
    merged["ts_scale"] = np.clip(np.where(ts_den > 0, merged["ts_pct"] / 0.55, 1.0), 0.6, 1.4)

    support = 0.7*merged["AST"] + 0.7*merged["OREB"]
    misses  = (merged["FGA"] - merged["FGM"]) + 0.5*(merged["FTA"] - merged["FTM"]) + merged["TO"]

    merged["off_raw"] = (
        OFF_POINTS_W  * merged["PTS"]
        + OFF_SUPPORT_W * support
        - misses
    ) * merged["vol_factor"] * merged["ts_scale"]

    # ---- Defensive raw ----
    merged["def_raw"] = merged["STL"] + 0.7*merged["BLK"] + 0.3*merged["DREB"] - 0.25*merged["PF"]

    # ---- Within-game positive shares ----
    merged["off_share"] = merged.groupby(key, group_keys=False)["off_raw"].apply(_positive_share)
    merged["def_share"] = merged.groupby(key, group_keys=False)["def_raw"].apply(_positive_share)

    # ---- Per-game blended scores ----
    merged["Off_game"] = W_MINUTE * merged["min_share"] + W_STATS * merged["off_share"]
    merged["Def_game"] = W_MINUTE * merged["min_share"] + W_STATS * merged["def_share"]
    merged["Total_game"] = merged["Off_game"] + merged["Def_game"]

    # ---- Aggregate season ----
    grp_cols = ["player_name","team_name"]
    agg = (merged
           .groupby(grp_cols, as_index=False)
           .agg(games=("game_id","nunique"),
                Offense=("Off_game","sum"),
                Defense=("Def_game","sum"),
                Total=("Total_game","sum")))

    # Scale for readability and round
SCALE = 4.0  # ↓ was 10, smaller for realistic range
for c in ("Offense","Defense","Total"):
    agg[c] = (agg[c] * SCALE).round(ROUND_DEC)
    # Sort and save
    agg = agg.sort_values("Total", ascending=False).reset_index(drop=True)
    agg.to_csv(out_path, index=False)
    print(f"[{gender}] Wrote {len(agg)} rows -> {out_path}")


def main():
    for g in ("men","women"):
        process_gender(g)

if __name__ == "__main__":
    main()