#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from pathlib import Path

SEASON = 2025
DATA_DIR = Path(__file__).resolve().parent / "data"

st.set_page_config(page_title=f"ACAC Player Net Points — Season {SEASON}",
                   layout="wide",
                   page_icon="🏀")

st.title(f"ACAC Player Net Points — Season {SEASON}")

tabs = st.tabs(["Men", "Women"])
genders = ["men","women"]

def read_csv_robust(p: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig","utf-8","latin1"):
        try:
            df = pd.read_csv(p, encoding=enc)
            break
        except Exception:
            df = None
    if df is None:
        return pd.DataFrame()
    # de-NBSP and tidy strings
    df = df.applymap(lambda x: str(x).replace("\xa0"," ").strip() if isinstance(x,str) else x)
    return df

for tab, gender in zip(tabs, genders):
    with tab:
        path = DATA_DIR / f"leaderboard_{gender}_{SEASON}.csv"
        if not path.exists():
            st.info(f"No leaderboard yet. Run `python compute/compute_rtg.py` to generate:\n\n`{path}`")
            continue

        df = read_csv_robust(path)

        # enforce columns order if present
        cols = [c for c in ["player_name","team_name","games","Off","Def","Overall"] if c in df.columns]
        df = df[cols].copy()

        # cast numbers to int (no decimals) if present
        for c in ["games","Off","Def","Overall"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

        # rename headers nicely
        nice = {
            "player_name":"Player",
            "team_name":"Team",
            "games":"G",
            "Off":"Offense",
            "Def":"Defense",
            "Overall":"Overall"
        }
        df = df.rename(columns=nice)

        if df.empty or df.shape[0] == 0:
            st.info("Leaderboard is empty.")
        else:
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
