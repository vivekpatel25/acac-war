#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compute ACAC Net Points Leaderboards (Offense / Defense / Overall)

Model:
- For each team-game:
    diff = team_pts - opp_pts
    split offense/defense share of team differential by team scoring mix:
        split_off = PTS / (PTS + opp_pts)  (def share = 1 - split_off)
        off_share_game = diff * split_off
        def_share_game = diff * (1 - split_off)

- Player allocation per game:
    A) Team context via minutes share (40%):
        share = player_MIN / team_min
        mins_off  = 0.4 * share * off_share_game
        mins_def  = 0.4 * share * def_share_game

    B) Boxscore allocation (60%):
        Build non-negative box weights:
            off_box = PTS + 0.7*AST + 0.7*OREB - (FGA-FGM) - 0.5*(FTA-FTM) - TO
            def_box = STL + 0.7*BLK + 0.3*DREB - 0.25*PF
        If all weights <= 0 for a team-game, fall back to minutes weights.
        off_pts  = 0.6 * off_share_game * (off_box_i / sum_off_box_pos)
        def_pts  = 0.6 * def_share_game * (def_box_i / sum_def_box_pos)

    Player game Off  = mins_off + off_pts
    Player game Def  = mins_def + def_pts
    Player game Ovr  = Off + Def

- Season aggregate: sum across games for each player.

Output: data/leaderboard_{men|women}_2025.csv
Columns:
    player_name,team_name,games,Off,Def,Overall
Values rounded to integers (no decimals).
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import re, unicodedata
from pathlib import Path

SEASON = 2025
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
BOX_DIR = DATA_DIR / "boxscores"
TEAM_DIR = DATA_DIR / "teamstats"

# ------------------ helpers ------------------

def read_csv_robust(path: Path) -> pd.DataFrame:
    """
    Read CSV with robust encoding fallback and normalize NBSP.
    """
    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except Exception:
            df = None
    if df is None:
        raise RuntimeError(f"Failed to read CSV: {path}")
    # strip NBSP, trim whitespace in all string cells
    df = df.applymap(lambda x: str(x).replace("\xa0", " ").strip() if isinstance(x, str) else x)
    return df

def load_all(folder: Path, glob="*.csv") -> pd.DataFrame:
    files = sorted(folder.glob(glob))
    if not files:
        return pd.DataFrame()
    frames = []
    for f in files:
        frames.append(read_csv_robust(f))
    return pd.concat(frames, ignore_index=True)

def to_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
        else:
            out[c] = 0.0
    return out

def normalize_names(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].astype(str).str.replace("\xa0", " ", regex=False).str.replace(r"\s+", " ", regex=True).str.strip()
        else:
            out[c] = ""
    return out

# ------------------ core compute ------------------

def process_gender(gender: str):
    box_path  = BOX_DIR  / gender
    team_path = TEAM_DIR / gender
    out_path  = DATA_DIR  / f"leaderboard_{gender}_{SEASON}.csv"

    # --- load data
    box = load_all(box_path)
    team = load_all(team_path)

    if box.empty or team.empty:
        # write empty with header expected by app, then exit
        pd.DataFrame(columns=["player_name","team_name","games","Off","Def","Overall"]).to_csv(out_path, index=False)
        print(f"[{gender}] no data -> wrote empty leaderboard")
        return

    # --- rename columns for consistency (boxscore)
    # Expect at minimum: game_id, team_name, player_name, MIN, FGM, FGA, 3PM, 3PA, FTM, FTA, OREB, DREB, REB, AST, STL, BLK, TO, PF, PTS
    box = normalize_names(box, ["game_id","team_name","player_name"])
    # Allow "MIN" or "minutes"
    if "MIN" not in box.columns and "minutes" in box.columns:
        box = box.rename(columns={"minutes":"MIN"})
    # standardize types
    box = to_num(box, ["MIN","FGM","FGA","3PM","3PA","FTM","FTA","OREB","DREB","REB","AST","STL","BLK","TO","PF","PTS"])

    # --- teamstats columns
    # Expect: game_id, team_name, opp_team_name, team_min, FGM,FGA,3PM,3PA,FTM,FTA,OREB,DREB,TOV,PTS
    team = normalize_names(team, ["game_id","team_name","opp_team_name"])
    team = to_num(team, ["team_min","FGM","FGA","3PM","3PA","FTM","FTA","OREB","DREB","TOV","PTS"])

    # compute opponent PTS by self-merge
    opp_pts = team[["game_id","team_name","PTS"]].rename(columns={"team_name":"opp_team_name","PTS":"opp_pts"})
    team = team.merge(opp_pts, on=["game_id","opp_team_name"], how="left")
    team["opp_pts"] = team["opp_pts"].fillna(0.0)
    team["diff"] = team["PTS"] - team["opp_pts"]

    # if team_min missing/zero, compute from boxscore per team-game
    zero_min_mask = (team["team_min"] <= 0)
    if zero_min_mask.any():
        # sum minutes from box for each (game, team)
        tm = box.groupby(["game_id","team_name"], as_index=False)["MIN"].sum().rename(columns={"MIN":"team_min_from_box"})
        team = team.merge(tm, on=["game_id","team_name"], how="left")
        team.loc[zero_min_mask, "team_min"] = team.loc[zero_min_mask, "team_min_from_box"].fillna(0.0)
        team.drop(columns=["team_min_from_box"], inplace=True)

    # compute offense vs defense shares of differential
    # use scoring mix split: off_share = diff * (PTS/(PTS+opp_pts)), def_share = diff - off_share
    denom = (team["PTS"] + team["opp_pts"]).replace(0, np.nan)
    split_off = (team["PTS"] / denom).fillna(0.5)
    team["off_share"] = team["diff"] * split_off
    team["def_share"] = team["diff"] - team["off_share"]

    # merge team-game info into player rows
    keys = ["game_id","team_name"]
    m = box.merge(team[["game_id","team_name","team_min","diff","off_share","def_share"]], on=keys, how="left")

    # minutes share
    m["team_min"] = m["team_min"].replace(0, np.nan)
    m["min_share"] = (m["MIN"] / m["team_min"]).fillna(0)

    # --- Boxscore weights (non-negative)
    m["off_box"] = (m["PTS"]
                    + 0.7*m["AST"]
                    + 0.7*m["OREB"]
                    - (m["FGA"] - m["FGM"])
                    - 0.5*(m["FTA"] - m["FTM"])
                    - m["TO"])
    m["def_box"] = (m["STL"]
                    + 0.7*m["BLK"]
                    + 0.3*m["DREB"]
                    - 0.25*m["PF"])

    # clip negatives to zero for weight building
    m["off_w"] = m["off_box"].clip(lower=0)
    m["def_w"] = m["def_box"].clip(lower=0)

    # per team-game sums for normalization
    sums = (m.groupby(keys, as_index=False)
              .agg(off_sum=("off_w","sum"), def_sum=("def_w","sum"), min_sum=("min_share","sum")))
    m = m.merge(sums, on=keys, how="left")

    # avoid 0 divisors: fall back to minutes share weights if off_sum/def_sum are zero
    m["off_alpha"] = np.where(m["off_sum"] > 0, m["off_w"]/m["off_sum"], m["min_share"])
    m["def_alpha"] = np.where(m["def_sum"] > 0, m["def_w"]/m["def_sum"], m["min_share"])

    # minutes-sourced pieces (40%)
    m["mins_off"] = 0.4 * m["min_share"] * m["off_share"]
    m["mins_def"] = 0.4 * m["min_share"] * m["def_share"]

    # boxscore-sourced pieces (60%)
    m["box_off"] = 0.6 * m["off_share"] * m["off_alpha"]
    m["box_def"] = 0.6 * m["def_share"] * m["def_alpha"]

    m["Off"] = m["mins_off"] + m["box_off"]
    m["Def"] = m["mins_def"] + m["box_def"]
    m["Overall"] = m["Off"] + m["Def"]

    # games played
    m["game_flag"] = 1

    # aggregate season
    agg = (m.groupby(["player_name","team_name"], as_index=False)
             .agg(games=("game_flag","sum"),
                  Off=("Off","sum"),
                  Def=("Def","sum"),
                  Overall=("Overall","sum")))

    # round to integers (no decimals)
    for c in ["Off","Def","Overall"]:
        agg[c] = agg[c].round(0).astype(int)

    # sort by Overall desc
    agg = agg.sort_values("Overall", ascending=False)

    # write
    agg[["player_name","team_name","games","Off","Def","Overall"]].to_csv(out_path, index=False)
    print(f"[{gender}] wrote {out_path} with {len(agg)} players.")


def main():
    for gender in ("men","women"):
        process_gender(gender)

if __name__ == "__main__":
    main()
