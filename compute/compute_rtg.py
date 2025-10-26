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
# Weights: 20% minutes share, 80% player box stats
W_MINUTE = 0.20
W_STATS  = 0.80
# ----------------------------------------


def _read_csv_any_encoding(path: Path) -> pd.DataFrame:
    """
    Robust CSV reader that survives weird NBSP/latin1 encodings
    and BOM markers we saw in ACAC exports.
    """
    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, engine="python")
        except UnicodeDecodeError:
            continue
    # Last try, no encoding—let pandas guess
    return pd.read_csv(path, engine="python")


def _normalize_name(s: str) -> str:
    if pd.isna(s):
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _load_all(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.csv"))
    rows = []
    for f in files:
        df = _read_csv_any_encoding(f)
        df["__source_file"] = f.name
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        else:
            df[c] = 0.0
    return df


def process_gender(gender: str):
    box_path  = BOX_DIR  / gender
    team_path = TEAM_DIR / gender
    out_path  = OUT_TMPL.with_name(OUT_TMPL.name.format(gender=gender, season=SEASON))

    # ---- Load ----
    boxes = _load_all(box_path)
    teams = _load_all(team_path)

    if boxes.empty or teams.empty:
        # Write a header-only CSV so the app shows a clear message
        pd.DataFrame(columns=["player_name","team_name","G","Off","Def","Overall"]).to_csv(out_path, index=False)
        print(f"[{gender}] No data found. Wrote empty file: {out_path}")
        return

    # ---- Clean column names that may vary slightly ----
    boxes.columns = [c.strip() for c in boxes.columns]
    teams.columns = [c.strip() for c in teams.columns]

    # Normalize string id fields
    for c in ("game_id", "team_name", "player_name"):
        if c in boxes.columns:
            boxes[c] = boxes[c].map(_normalize_name)

    for c in ("game_id", "team_name", "opp_team_name"):
        if c in teams.columns:
            teams[c] = teams[c].map(_normalize_name)

    # Standardize expected numeric columns
    box_num = ["MIN","FGM","FGA","3PM","3PA","FTM","FTA","OREB","DREB","REB","AST","STL","BLK","TO","PF","PTS"]
    _coerce_numeric(boxes, box_num)

    # Team minutes column expected as "team_min"
    if "team_min" not in teams.columns:
        # Backstop: if not present, try MIN or GMIN variants; default 40
        fallback = None
        for k in ("team minutes","minutes","MIN","min","gmin","GMIN"):
            if k in teams.columns:
                fallback = k
                break
        if fallback:
            teams = teams.rename(columns={fallback: "team_min"})
        else:
            teams["team_min"] = 40.0  # safe default

    # Ensure numeric team stats
    _coerce_numeric(teams, ["team_min","FGM","FGA","3PM","3PA","FTM","FTA","OREB","DREB","TOV","PTS"])

    # ---- Merge team minutes into player rows (by game, team) ----
    key = ["game_id","team_name"]
    missing_keys = [k for k in key if k not in boxes.columns or k not in teams.columns]
    if missing_keys:
        raise SystemExit(f"Missing merge keys in data: {missing_keys}")

    merged = boxes.merge(
        teams[key + ["team_min"]],
        on=key, how="left", validate="m:1"
    )
    merged["team_min"] = merged["team_min"].replace(0, np.nan).fillna(40.0)
    merged["min_share"] = (merged["MIN"] / merged["team_min"]).clip(lower=0)

    # ---- Player box-score impact (per game) ----
    # Offense: reward scoring/AST/OREB; penalize misses, TO
    merged["off_raw"] = (
        merged["PTS"]
        + 0.7 * merged["AST"]
        + 0.7 * merged["OREB"]
        - (merged["FGA"] - merged["FGM"])
        - 0.5 * (merged["FTA"] - merged["FTM"])
        - merged["TO"]
    )

    # Defense: reward STL/BLK/DREB; slightly penalize PF
    merged["def_raw"] = (
        merged["STL"]
        + 0.7 * merged["BLK"]
        + 0.3 * merged["DREB"]
        - 0.25 * merged["PF"]
    )

    # ---- Normalize off/def within team-game to prevent minute spikes ----
    def _share(col):
        # share of positive total; negatives remain negative but scaled sensibly
        def _fn(g: pd.Series):
            pos_sum = g[g > 0].sum()
            if pos_sum <= 0:
                return pd.Series(np.zeros(len(g)), index=g.index)
            return g / pos_sum
        return _fn

    merged["off_share"] = merged.groupby(key)["off_raw"].transform(_share("off_raw"))
    merged["def_share"] = merged.groupby(key)["def_raw"].transform(_share("def_raw"))

    # ---- Combine minutes share (30%) + stats (70%) => per-game scores ----
    merged["Off_game"] = W_MINUTE * merged["min_share"] + W_STATS * merged["off_share"]
    merged["Def_game"] = W_MINUTE * merged["min_share"] + W_STATS * merged["def_share"]
    merged["Overall_game"] = merged["Off_game"] + merged["Def_game"]

    # ---- Aggregate season totals per player ----
    grp_cols = ["player_name","team_name"]
    agg = (merged
           .groupby(grp_cols, as_index=False)
           .agg(G=("game_id", "nunique"),
                Off=("Off_game", "sum"),
                Def=("Def_game", "sum"),
                Overall=("Overall_game","sum"))
           )

    # Scale up a bit so numbers are in a readable range.
    # (This is purely presentational; adjust if you prefer different magnitude.)
    SCALE = 10.0
    for c in ("Off","Def","Overall"):
        agg[c] = (agg[c] * SCALE).round(1)

    # Sort by Overall descending
    agg = agg.sort_values("Overall", ascending=False).reset_index(drop=True)

    # Save
    agg.to_csv(out_path, index=False)
    print(f"[{gender}] Wrote {len(agg)} rows -> {out_path}")


def main():
    for gender in ("men","women"):
        process_gender(gender)


if __name__ == "__main__":
    main()
