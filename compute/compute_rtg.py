import pandas as pd, numpy as np, re, unicodedata
from pathlib import Path

# ---------- CONFIG ----------
SEASON = 2025
FT_WEIGHT = 0.44
MIN_POSSESSIONS_FOR_PLAYER = 10
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
# ----------------------------

def slugify(s):
    if pd.isna(s): s = ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return s.strip("-")

def poss(fga, tov, fta, orb):
    return fga + tov + FT_WEIGHT * fta - orb

def normalize_name(n):
    return re.sub(r"\s+", " ", str(n)).strip()

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
    if "jersey" in df.columns:
        df["jersey"] = df["jersey"].fillna(df["jersey_from_name"])
    else:
        df["jersey"] = df["jersey_from_name"]
    df.drop(columns=["jersey_from_name"], inplace=True)
    df["player_name"] = df["player_name"].map(normalize_name)
    if "game_id" not in df.columns:
        df["game_id"] = Path(source_name).stem  # fallback: filename as game_id
    return df

def load_boxscores(folder: Path):
    print(f"\n🔍 Looking for boxscore files in: {folder}")
    if not folder.exists():
        print(f"❌ Folder missing: {folder}")
        return pd.DataFrame()

    rows = []
    for p in sorted(folder.glob("*.csv")):
        print(f"📂 Found file: {p.name}")
        try:
            try:
                df = pd.read_csv(p, encoding="utf-8-sig", engine="python")
            except UnicodeDecodeError:
                df = pd.read_csv(p, encoding="cp1252", engine="python")
        except Exception as e:
            print(f"⚠️ Failed to read {p.name}: {e}")
            continue

        print(f"✅ Read {len(df)} rows from {p.name}, columns: {list(df.columns)}")
        if "player_name" not in df.columns:
            print(f"⚠️ Skipping {p.name} — no 'player_name' column found.")
            continue

        rename_map = {"MIN": "minutes", "Min": "minutes", "min": "minutes"}
        df.rename(columns=rename_map, inplace=True)
        df = preprocess_boxscores(df, p.name)
        rows.append(df)

    if not rows:
        print("⚠️ No valid CSV files found.")
        return pd.DataFrame()

    allbx = pd.concat(rows, ignore_index=True)
    print(f"✅ Combined total {len(allbx)} rows across {len(rows)} files")

    for col in ["team_id","opp_team_id","team_name","opp_team_name"]:
        if col not in allbx.columns:
            allbx[col] = ""

    num_cols = ["minutes","team_pts_for","team_fga","team_fta","team_tov","team_orb",
                "team_pts_against","opp_fga","opp_fta","opp_tov","opp_orb"]
    for c in num_cols:
        if c not in allbx.columns:
            allbx[c] = 0
        else:
            allbx[c] = pd.to_numeric(allbx[c], errors="coerce").fillna(0.0)

    return allbx.drop_duplicates()

def process_gender(gender):
    boxdir = DATA_DIR / "boxscores" / gender
    roster_path = DATA_DIR / f"roster_{gender}_25-26.csv"
    out_file = DATA_DIR / f"leaderboard_{gender}_{SEASON}.csv"

    box = load_boxscores(boxdir)
    if box.empty:
        print(f"⚠️ No {gender} boxscores loaded — leaderboard will be empty.")
        return

    print(f"🏀 Proceeding with {len(box)} rows for {gender}")

    # Generate team-level dummy data if not present
    if "team_id" not in box.columns or box["team_id"].eq("").all():
        box["team_id"] = box["team_name"]

    team_game = (
        box.groupby(["game_id","team_id","team_name"], as_index=False)
        .agg(
            pts_for=("team_pts_for","sum"),
            fga=("team_fga","sum"),
            fta=("team_fta","sum"),
            tov=("team_tov","sum"),
            orb=("team_orb","sum"),
            pts_against=("team_pts_against","sum"),
            ofga=("opp_fga","sum"),
            ofta=("opp_fta","sum"),
            otov=("opp_tov","sum"),
            oorb=("opp_orb","sum"),
        )
    )
    team_game["poss_for"] = poss(team_game.fga, team_game.tov, team_game.fta, team_game.orb)
    team_game["poss_opp"] = poss(team_game.ofga, team_game.otov, team_game.ofta, team_game.oorb)

    team_minutes = box.groupby(["game_id","team_id"])["minutes"].transform("sum").replace(0, np.nan)
    box["min_share"] = (box["minutes"] / team_minutes).fillna(0)

    # ✅ Safe merge: drop duplicates first
    team_game = team_game.drop_duplicates(subset=["game_id","team_id"])
    m = box.merge(
        team_game[["game_id","team_id","pts_for","pts_against","poss_for","poss_opp"]],
        on=["game_id","team_id"], how="left"
    )

    m["pts_for_on"] = m["pts_for"] * m["min_share"]
    m["pts_against_on"] = m["pts_against"] * m["min_share"]
    m["poss_for_on"] = m["poss_for"] * m["min_share"]
    m["poss_against_on"] = m["poss_opp"] * m["min_share"]

    g = (
        m.groupby(["player_name","team_name"], as_index=False)
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