import pandas as pd, numpy as np, re, unicodedata
from pathlib import Path

# ---------- CONFIG ----------
SEASON = 2025
FT_WEIGHT = 0.44
MIN_POSSESSIONS_FOR_PLAYER = 300

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# ----------------------------


# --- Basic helpers ---
def slugify(s):
    if pd.isna(s):
        s = ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return s.strip("-")

def poss(fga, tov, fta, orb):
    """Estimate team possessions"""
    return fga + tov + FT_WEIGHT * fta - orb

def normalize_name(n):
    return re.sub(r"\s+", " ", str(n)).strip()


# --- Player name / jersey cleaning ---
def clean_player_name_and_jersey(name):
    """
    Extract jersey number (if present) and clean player name.
    Examples:
        '05 - Brandon Gillis' → ('Brandon Gillis', 5)
        '#11 Romarie Johnson' → ('Romarie Johnson', 11)
        'Brandon Gillis' → ('Brandon Gillis', None)
    """
    name = str(name).strip()
    jersey = None
    match = re.match(r"^#?(\d+)\s*[-–:]?\s*(.*)", name)
    if match:
        jersey = match.group(1).lstrip("0")
        name = match.group(2).strip()
    return name, jersey


def preprocess_boxscores(df):
    """Clean player names and auto-extract jersey numbers"""
    df[["player_name", "jersey_from_name"]] = df["player_name"].apply(
        lambda n: pd.Series(clean_player_name_and_jersey(n))
    )
    if "jersey" in df.columns:
        df["jersey"] = df["jersey"].fillna(df["jersey_from_name"])
    else:
        df["jersey"] = df["jersey_from_name"]
    df.drop(columns=["jersey_from_name"], inplace=True)
    df["player_name"] = df["player_name"].map(normalize_name)
    return df


# --- Load all boxscores for one gender ---
def load_boxscores(folder: Path):
    rows = []
    for p in sorted(folder.glob("*.csv")):
        try:
            df = pd.read_csv(p, encoding="utf-8-sig", engine="python")
        except UnicodeDecodeError:
            df = pd.read_csv(p, encoding="latin1", engine="python")
        df["__source_file"] = p.name
        df = preprocess_boxscores(df)
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    allbx = pd.concat(rows, ignore_index=True)

    # Normalize column names and handle MIN variations
    allbx.columns = [c.strip() for c in allbx.columns]
    rename_map = {"MIN": "minutes", "Min": "minutes", "min": "minutes"}
    allbx.rename(columns=rename_map, inplace=True)

    # Ensure expected columns exist
    for col in ["team_id", "opp_team_id", "team_name", "opp_team_name"]:
        if col not in allbx.columns:
            allbx[col] = ""

    for c in ["player_name","team_name","opp_team_name","team_id","opp_team_id","game_id","pos","class","jersey"]:
        if c in allbx.columns:
            allbx[c] = allbx[c].astype(str).fillna("").map(normalize_name)

    # Fallback IDs if missing
    allbx["team_id"] = np.where(allbx["team_id"].eq(""), allbx["team_name"], allbx["team_id"])
    allbx["opp_team_id"] = np.where(allbx["opp_team_id"].eq(""), allbx["opp_team_name"], allbx["opp_team_id"])

    # Numeric columns
    num_cols = [
        "minutes","team_pts_for","team_fga","team_fta","team_tov","team_orb",
        "team_pts_against","opp_fga","opp_fta","opp_tov","opp_orb"
    ]
    for c in num_cols:
        if c not in allbx.columns:
            allbx[c] = 0.0
        else:
            allbx[c] = pd.to_numeric(allbx[c], errors="coerce").fillna(0.0)

    print(f"Loaded {len(allbx)} rows from {folder}")
    return allbx.drop_duplicates()


# --- Core rating computation ---
def process_gender(gender):
    boxdir = DATA_DIR / "boxscores" / gender
    roster_path = DATA_DIR / f"roster_{gender}_25-26.csv"
    out_file = DATA_DIR / f"leaderboard_{gender}_{SEASON}.csv"

    box = load_boxscores(boxdir)
    if box.empty:
        print(f"No {gender} boxscores found.")
        return

    roster = pd.read_csv(roster_path) if roster_path.exists() else pd.DataFrame(
        columns=["player_id","player_name","team_id","team_name","pos","class","jersey","season"]
    )

    # player_id
    pid = box.apply(
        lambda r: f"{slugify(r['team_id'])}_{SEASON}_{slugify(r['player_name'])}"
                  + (f"_{slugify(r['jersey'])}" if str(r.get('jersey','')).strip() else ""),
        axis=1
    )
    box = box.assign(player_id=pid)

    # team-game possessions
    team_game = (
        box.groupby(["game_id","team_id","team_name","opp_team_id","opp_team_name"], as_index=False)
        .agg(
            pts_for=("team_pts_for","first"),
            fga=("team_fga","first"),
            fta=("team_fta","first"),
            tov=("team_tov","first"),
            orb=("team_orb","first"),
            pts_against=("team_pts_against","first"),
            ofga=("opp_fga","first"),
            ofta=("opp_fta","first"),
            otov=("opp_tov","first"),
            oorb=("opp_orb","first"),
        )
    )
    team_game["poss_for"] = poss(team_game.fga, team_game.tov, team_game.fta, team_game.orb)
    team_game["poss_opp"] = poss(team_game.ofga, team_game.otov, team_game.ofta, team_game.oorb)

    # minutes share
    team_minutes = box.groupby(["game_id","team_id"])["minutes"].transform("sum").replace(0, np.nan)
    box["min_share"] = (box["minutes"] / team_minutes).fillna(0)

    # merge totals
    m = box.merge(
        team_game[["game_id","team_id","pts_for","pts_against","poss_for","poss_opp"]],
        on=["game_id","team_id"], how="left", validate="m:1"
    )

    # apportion team results
    m["pts_for_on"] = m["pts_for"] * m["min_share"]
    m["pts_against_on"] = m["pts_against"] * m["min_share"]
    m["poss_for_on"] = m["poss_for"] * m["min_share"]
    m["poss_against_on"] = m["poss_opp"] * m["min_share"]

    # aggregate per player
    g = (
        m.groupby(["player_id","team_id"], as_index=False)
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

    # --- safe merge with roster ---
    expected_cols = ["player_id","player_name","team_id","team_name","pos","class","jersey"]
    for col in expected_cols:
        if col not in roster.columns:
            roster[col] = ""

    out = (
        g.merge(roster[expected_cols], on=["player_id","team_id"], how="left")
         .fillna({"team_name": g["team_id"]})
         .assign(season=SEASON)
         .sort_values("tRtg", ascending=False)
    )

    cols = [
        "player_id","player_name","team_name","pos","class",
        "poss_for","OffRtg_on","DefRtg_on","tRtg","season"
    ]
    out[cols].to_csv(out_file, index=False)
    print(f"Wrote {out_file} with {len(out)} players.")


def main():
    for gender in ["men","women"]:
        process_gender(gender)

if __name__ == "__main__":
    main()
