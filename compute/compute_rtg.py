import pandas as pd
from pathlib import Path

SEASON = 2025
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def load_all(folder):
    files = list(folder.glob("*.csv"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)

def process_gender(gender):
    box_path = DATA_DIR / "boxscores" / gender
    team_path = DATA_DIR / "teamstats" / gender
    out_file = DATA_DIR / f"leaderboard_{gender}_{SEASON}.csv"

    box = load_all(box_path)
    teams = load_all(team_path)
    if box.empty or teams.empty:
        print(f"⚠️ No data found for {gender}")
        return

    records = []

    for gid in teams["game_id"].unique():
        game_rows = teams[teams["game_id"] == gid]
        if len(game_rows) != 2:
            continue  # need both teams

        for _, trow in game_rows.iterrows():
            team = trow["team_name"]
            opp = trow["opp_team_name"]

            team_pts = trow["PTS"]
            opp_pts = game_rows.loc[game_rows["team_name"] == opp, "PTS"].values[0]
            diff = team_pts - opp_pts

            players = box[(box["game_id"] == gid) & (box["team_name"] == team)]
            if players.empty:
                continue

            total_min = players["MIN"].sum()
            for _, prow in players.iterrows():
                share = prow["MIN"] / total_min if total_min else 0
                off = round(team_pts * share)
                deff = round(opp_pts * share)
                net = round(diff * share)
                records.append({
                    "player_name": prow["player_name"],
                    "team_name": team,
                    "games": 1,
                    "minutes": prow["MIN"],
                    "offense": off,
                    "defense": -deff,   # defense is negative by ESPN logic
                    "overall": net
                })

    df = pd.DataFrame(records)
    df = df.groupby(["player_name", "team_name"], as_index=False).agg({
        "games": "sum",
        "minutes": "sum",
        "offense": "sum",
        "defense": "sum",
        "overall": "sum"
    }).sort_values("overall", ascending=False)

    df["offense"] = df["offense"].astype(int)
    df["defense"] = df["defense"].astype(int)
    df["overall"] = df["overall"].astype(int)

    df.to_csv(out_file, index=False)
    print(f"✅ Saved {len(df)} players → {out_file}")

def main():
    for gender in ["men", "women"]:
        process_gender(gender)

if __name__ == "__main__":
    main()
