import pandas as pd, numpy as np, re, unicodedata
from pathlib import Path

SEASON = 2025
FT_WEIGHT = 0.44
WINS_PER_NETPOINT = 2.7
REPLACEMENT_PERCENTILE = 10           # 10th percentile
MIN_POSSESSIONS_FOR_PLAYER = 300      # eligibility filter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BOX_DIR = DATA_DIR / "boxscores"
ROSTER_PATH = DATA_DIR / f"roster_{SEASON}.csv"
OUT_LEADERBOARD = Path(__file__).resolve().parent.parent / "site" / f"leaderboard_{SEASON}.csv"

def slugify(s):
    if pd.isna(s): s = ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return s.strip("-")

def poss(fga, tov, fta, orb):
    return fga + tov + FT_WEIGHT*fta - orb

def normalize_name(n):  # keep case but collapse spaces
    return re.sub(r"\s+", " ", str(n)).strip()

def load_boxscores():
    rows = []
    for p in sorted(BOX_DIR.glob("*.csv")):
        df = pd.read_csv(p)
        df["__source_file"] = p.name
        rows.append(df)
    if not rows:
        raise SystemExit("No boxscore files found in data/boxscores/")
    allbx = pd.concat(rows, ignore_index=True)

    # normalize basic fields
    for c in ["player_name","team_name","opp_team_name","team_id","opp_team_id","game_id","pos","class","jersey"]:
        if c in allbx.columns:
            allbx[c] = allbx[c].astype(str).fillna("").map(normalize_name)
    allbx["team_id"] = allbx["team_id"].where(allbx["team_id"]!="", allbx["team_name"])
    allbx["opp_team_id"] = allbx["opp_team_id"].where(allbx["opp_team_id"]!="", allbx["opp_team_name"])

    # numeric types
    num_cols = ["minutes","team_pts_for","team_fga","team_fta","team_tov","team_orb",
                "team_pts_against","opp_fga","opp_fta","opp_tov","opp_orb"]
    for c in num_cols:
        allbx[c] = pd.to_numeric(allbx[c], errors="coerce").fillna(0.0)

    # drop duplicate player-game-team rows if any
    allbx = allbx.drop_duplicates(subset=["game_id","team_id","player_name","minutes",
                                          "team_pts_for","team_pts_against","team_fga","team_fta","team_tov","team_orb",
                                          "opp_fga","opp_fta","opp_tov","opp_orb"])
    return allbx

def ensure_roster(box):
    # Build or update roster_2025.csv
    if ROSTER_PATH.exists():
        roster = pd.read_csv(ROSTER_PATH)
    else:
        roster = pd.DataFrame(columns=["player_id","player_name","team_id","team_name","pos","class","jersey","season"])

    # create player_id
    pid = (box.apply(lambda r: f"{slugify(r['team_id'])}_{SEASON}_{slugify(r['player_name'])}" + (f"_{slugify(r['jersey'])}" if str(r.get('jersey','')).strip() else ""), axis=1))
    box = box.assign(player_id=pid)

    core = (box[["player_id","player_name","team_id","team_name","pos","class","jersey"]]
               .drop_duplicates("player_id")
               .assign(season=SEASON))

    new_players = core[~core["player_id"].isin(roster["player_id"])]
    if len(new_players):
        roster = pd.concat([roster, new_players], ignore_index=True)
        roster.to_csv(ROSTER_PATH, index=False)

    return box, roster

def compute_league_baseline(team_games):
    lg_pts = team_games["pts_for"].sum()
    lg_poss = team_games["poss_for"].sum()
    return 100 * lg_pts / max(1, lg_poss)

def main():
    box = load_boxscores()
    box, roster = ensure_roster(box)

    # possessions per team-game (single copy per team per game)
    team_game = (box.groupby(["game_id","team_id","team_name","opp_team_id","opp_team_name"], as_index=False)
                    .agg(pts_for=("team_pts_for","first"),
                         fga=("team_fga","first"),
                         fta=("team_fta","first"),
                         tov=("team_tov","first"),
                         orb=("team_orb","first"),
                         pts_against=("team_pts_against","first"),
                         ofga=("opp_fga","first"),
                         ofta=("opp_fta","first"),
                         otov=("opp_tov","first"),
                         oorb=("opp_orb","first")))

    team_game["poss_for"] = poss(team_game.fga, team_game.tov, team_game.fta, team_game.orb)
    team_game["poss_opp"] = poss(team_game.ofga, team_game.otov, team_game.ofta, team_game.oorb)

    offrtg_league = compute_league_baseline(team_game)

    # minutes shares per team-game
    team_minutes = box.groupby(["game_id","team_id"])["minutes"].transform("sum").replace(0, np.nan)
    box["min_share"] = (box["minutes"] / team_minutes).fillna(0)

    # merge team-game totals back to player rows
    m = box.merge(team_game[["game_id","team_id","pts_for","pts_against","poss_for","poss_opp"]],
                  on=["game_id","team_id"], how="left", validate="m:1")

    # apportion team results to players by minute share
    m["pts_for_on"] = m["pts_for"] * m["min_share"]
    m["pts_against_on"] = m["pts_against"] * m["min_share"]
    m["poss_for_on"] = m["poss_for"] * m["min_share"]
    m["poss_against_on"] = m["poss_opp"] * m["min_share"]

    # aggregate season-to-date per player
    g = (m.groupby(["player_id","team_id"], as_index=False)
           .agg(pts_for=("pts_for_on","sum"),
                pts_against=("pts_against_on","sum"),
                poss_for=("poss_for_on","sum"),
                poss_against=("poss_against_on","sum")))

    g["OffRtg_on"] = 100 * g["pts_for"] / g["poss_for"].clip(lower=1)
    g["DefRtg_on"] = 100 * g["pts_against"] / g["poss_against"].clip(lower=1)
    g["oNet"] = g["OffRtg_on"] - offrtg_league
    g["dNet"] = offrtg_league - g["DefRtg_on"]
    g["tNet"] = g["oNet"] + g["dNet"]

    # replacement levels from eligible players
    elig = g[g["poss_for"] >= MIN_POSSESSIONS_FOR_PLAYER]
    rep_o = np.percentile(elig["oNet"], REPLACEMENT_PERCENTILE) if len(elig) else 0.0
    rep_d = np.percentile(elig["dNet"], REPLACEMENT_PERCENTILE) if len(elig) else 0.0

    factor = g["poss_for"] / 100.0
    scale = 1.0 / WINS_PER_NETPOINT
    g["oWAR"] = (g["oNet"] - rep_o) * scale * factor
    g["dWAR"] = (g["dNet"] - rep_d) * scale * factor
    g["tWAR"] = g["oWAR"] + g["dWAR"]

    out = (g.merge(roster[["player_id","player_name","team_id","team_name","pos","class"]], on=["player_id","team_id"], how="left")
             .assign(season=SEASON)
             .sort_values("tWAR", ascending=False))

    cols = ["player_id","player_name","team_name","pos","class",
            "poss_for","OffRtg_on","DefRtg_on","oNet","dNet","tNet","oWAR","dWAR","tWAR","season"]
    out[cols].to_csv(OUT_LEADERBOARD, index=False)
    print(f"Wrote {OUT_LEADERBOARD} with {len(out)} players. League OffRtg baseline = {offrtg_league:.2f}")

if __name__ == "__main__":
    main()
