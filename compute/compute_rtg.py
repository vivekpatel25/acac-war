import pandas as pd, numpy as np, re, unicodedata
from pathlib import Path

SEASON = 2025
FT_WEIGHT = 0.44
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
MIN_POSSESSIONS_FOR_PLAYER = 1

def normalize_name(n):
    return re.sub(r"\s+", " ", str(n)).strip().upper()

def poss(fga, tov, fta, orb):
    return fga + tov + FT_WEIGHT * fta - orb

def clean_player_name(name):
    name = str(name).strip()
    return re.sub(r"\s+", " ", name).title()

def load_boxscores(folder):
    print(f"\n🔍 Loading boxscores from {folder}")
    all_files = sorted(folder.glob("*.csv"))
    if not all_files:
        print("❌ No files found.")
        return pd.DataFrame()
    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(f, encoding="cp1252")
        df.rename(columns={"MIN":"minutes"}, inplace=True)
        df["game_id"] = Path(f.name).stem.replace("v","-").replace("_","-").upper()
        df["team_name"] = df["team_name"].map(normalize_name)
        df["player_name"] = df["player_name"].map(clean_player_name)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    print(f"✅ Boxscores: {len(df)} rows, teams: {df.team_name.unique().tolist()}")
    return df

def load_teamstats(folder):
    print(f"\n📊 Loading teamstats from {folder}")
    frames = []
    for f in sorted(folder.glob("*.csv")):
        df = pd.read_csv(f)
        df["game_id"] = df["game_id"].astype(str).replace("v","-").replace("_","-").str.upper()
        df["team_name"] = df["team_name"].map(normalize_name)
        df["opp_team_name"] = df["opp_team_name"].map(normalize_name)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    pts_col = next((c for c in df.columns if c.upper() in ["PTS","POINTS","SCORE"]), None)
    df["pts_for"] = df[pts_col]
    df["poss_for"] = poss(df["FGA"], df["TOV"], df["FTA"], df["OREB"])
    print(f"✅ Teamstats: {len(df)} rows, teams: {df.team_name.unique().tolist()}")
    return df

def process_gender(g):
    boxdir = DATA_DIR / "boxscores" / g
    teamdir = DATA_DIR / "teamstats" / g
    outfile = DATA_DIR / f"leaderboard_{g}_{SEASON}.csv"

    box = load_boxscores(boxdir)
    team = load_teamstats(teamdir)
    if box.empty or team.empty:
        print("⚠️ Missing data, skip.")
        return

    print(f"\n🔗 Merging on keys: game_id + team_name")
    merged = box.merge(team, on=["game_id","team_name"], how="left")
    print(f"🔎 After merge: {merged.shape[0]} rows, matched: {merged['pts_for'].notna().sum()}")

    merged["minutes"] = pd.to_numeric(merged.get("minutes", 0), errors="coerce").fillna(0)
    team_minutes = merged.groupby(["game_id","team_name"])["minutes"].transform("sum").replace(0,np.nan)
    merged["min_share"] = merged["minutes"]/team_minutes

    merged["pts_for_on"] = merged["pts_for"] * merged["min_share"]
    merged["poss_for_on"] = merged["poss_for"] * merged["min_share"]

    opp = team.rename(columns={
        "team_name":"opp_team_name",
        "opp_team_name":"team_name",
        "pts_for":"pts_against",
        "poss_for":"poss_opp"
    })[["game_id","team_name","pts_against","poss_opp"]]
    merged = merged.merge(opp,on=["game_id","team_name"],how="left")
    merged["pts_against_on"] = merged["pts_against"]*merged["min_share"]
    merged["poss_against_on"] = merged["poss_opp"]*merged["min_share"]

    g = (
        merged.groupby(["player_name","team_name"],as_index=False)
        .agg(
            pts_for=("pts_for_on","sum"),
            pts_against=("pts_against_on","sum"),
            poss_for=("poss_for_on","sum"),
            poss_against=("poss_against_on","sum")
        )
    )
    g["OffRtg_on"] = 100*g["pts_for"]/g["poss_for"].clip(lower=1)
    g["DefRtg_on"] = 100*g["pts_against"]/g["poss_against"].clip(lower=1)
    g["tRtg"] = g["OffRtg_on"] + g["DefRtg_on"].abs()
    g = g[g["poss_for"]>=MIN_POSSESSIONS_FOR_PLAYER]

    print(f"✅ Computed {len(g)} player ratings for {g}")
    g.to_csv(outfile,index=False)
    print(f"💾 Saved: {outfile}")

def main():
    for g in ["men","women"]:
        process_gender(g)

if __name__=="__main__":
    main()
