import pandas as pd, numpy as np, re, unicodedata
from pathlib import Path

# ---------- CONFIG ----------
SEASON = 2025
FT_WEIGHT = 0.44
MIN_POSSESSIONS_FOR_PLAYER = 1  # lowered for single-game data
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
# ----------------------------

def slugify(s):
    if pd.isna(s): s = ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return s.strip("-")

def normalize_name(n):
    return re.sub(r"\s+", " ", str(n)).strip().upper()

def poss(fga, tov, fta, orb):
    return fga + tov + FT_WEIGHT * fta - orb

def clean_player_name_and_jersey(name):
    name = str(name).strip()
    jersey = None
    match = re.match(r"^#?(\d+)\s*[-–:]?\s*(.*)", name)
    if match:
        jersey = match.group(1).lstrip("0")
        name = match.group(2).strip()
    return name, jersey

def preprocess_boxscores(df, source_name):
    df[["player_name", "jersey_from_name"]] = df["player_name"].apply(
        lambda n: pd.Series(clean_player_name_and_jersey(n))
    )
    df["jersey"] = df.get("jersey", df["jersey_from_name"])
    df.drop(columns=["jersey_from_name"], inplace=True)
    df["player_name"] = df["player_name"].map(lambda x: x.strip().title())
    if "game_id" not in df.columns:
        df["game_id"] = Path(source_name).stem
    df["game_id"] = df["game_id"].str.replace("v", "-").str.replace("_", "-").str.upper()
    df["team_name"] = df["team_name"].map(normalize_name)
    return df

def load_boxscores(folder: Path):
    print(f"\n🔍 Loading boxscores from: {folder}")
    rows = []
    for p in sorted(folder.glob("*.csv")):
        print(f"📂 {p.name}")
        try:
            df = pd.read_csv(p, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(p, encoding="cp1252")
        rename_map = {"MIN": "minutes"}
        df.rename(columns=rename_map, inplace=True)
        if "player_name" not in df.columns:
            continue
        df = preprocess_boxscores(df, p.name)
        rows.append(df)
    if not rows: return pd.DataFrame()
    allbx = pd.concat(rows, ignore_index=True)
    print(f"✅ Loaded {len(allbx)} player rows.")
    return allbx

def load_teamstats(folder: Path):
    print(f"\n📊 Loading teamstats from: {folder}")
    rows = []
    for p in sorted(folder.glob("*.csv")):
        try:
            df = pd.read_csv(p)
            df["game_id"] = df["game_id"].astype(str).str.replace("v", "-").str.replace("_", "-").str.upper()
            df["team_name"] = df["team_name"].map(normalize_name)
            df["opp_team_name"] = df["opp_team_name"].map(normalize_name)
            rows.append(df)
        except Exception as e:
            print(f"⚠️ Could not read {p.name}: {e}")
    if not rows: return pd.DataFrame()
    ts = pd.concat(rows, ignore_index=True)
    pts_col = next((c for c in ts.columns if c.strip().upper() in ["PTS", "POINTS", "SCORE"]), None)
    ts["pts_for"] = ts[pts_col]
    ts["poss_for"] = poss(ts["FGA"], ts["TOV"], ts["FTA"], ts["OREB"])
    print(f"✅ Loaded {len(ts)} teamstat rows.")
    return ts

def process_gender(gender):
    boxdir = DATA_DIR / "boxscores" / gender
    teamdir = DATA_DIR / "teamstats" / gender
    out_file = DATA_DIR / f"leaderboard_{gender}_{SEASON}.csv"

    box = load_boxscores(boxdir)
    teams = load_teamstats(teamdir)
    if box.empty or teams.empty:
        print(f"⚠️ Missing data for {gender}")
        return

    merged = box.merge(teams, on=["game_id","team_name"], how="left")
    print(f"🔗 Merged player-boxscore with teamstats → {merged.shape[0]} rows")

    merged["minutes"] = pd.to_numeric(merged.get("minutes", 0), errors="coerce").fillna(0)
    team_minutes = merged.groupby(["game_id","team_name"])["minutes"].transform("sum").replace(0, np.nan)
    merged["min_share"] = merged["minutes"] / team_minutes

    merged["pts_for_on"] = merged["pts_for"] * merged["min_share"]
    merged["poss_for_on"] = merged["poss_for"] * merged["min_share"]

    opp = teams.rename(columns={
        "team_name": "opp_team_name",
        "opp_team_name": "team_name",
        "pts_for": "pts_against",
        "poss_for": "poss_opp"
    })[["game_id","team_name","pts_against","poss_opp"]]
    merged = merged.merge(opp, on=["game_id","team_name"], how="left")
    merged["pts_against_on"] = merged["pts_against"] * merged["min_share"]
    merged["poss_against_on"] = merged["poss_opp"] * merged["min_share"]

    g = (
        merged.groupby(["player_name","team_name"], as_index=False)
        .agg(
            pts_for=("pts_for_on","sum"),
            pts_against=("pts_against_on","sum"),
            poss_for=("poss_for_on","sum"),
            poss_against=("poss_against_on","sum"),
        )
    )

    g["OffRtg_on"] = 100 * g["pts_for"] / g["poss_for"].clip(lower=1)
    g["DefRtg_on"] = 100 * g["pts_against"] / g["poss_against"].clip(lower=1)
    g["tRtg"] = g["OffRtg_on"] + g["DefRtg_on"].abs()
    g = g[g["poss_for"] >= MIN_POSSESSIONS_FOR_PLAYER]

    print(f"✅ Computed {len(g)} player ratings for {gender}")
    g.to_csv(out_file, index=False)
    print(f"💾 Saved: {out_file}")

def main():
    for gender in ["men","women"]:
        process_gender(gender)

if __name__ == "__main__":
    main()