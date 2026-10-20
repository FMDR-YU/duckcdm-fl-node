# -*- coding: utf-8 -*-
"""MIMIC-IV-ED -> the pilot's analysis matrix (one row per person, triage-time features, hospital admission).

Used by analysis/snuh_pilot/00_build_matrix.py --dataset mimic_ed. Not a loader of rows for anyone to read: it returns
the feature matrix only (no subject, stay or admission ids, no dates) and is run on the full release by the user.

Unit and task
-------------
One row per person: that person's first ED stay in the release (later stays of the same person would put one person into
training, validation, a site and the membership-inference sets at once). Outcome: disposition == ADMITTED.

Features: the same triage-time set as safe-model-bundle/poc/src/mimic_ed_loader.py (vitals, pain, ESI acuity, arrival
mode and hour, prior-medication count, sex, collapsed race, triage-incomplete flag), but missing values are kept
(XGBoost reads them; the pilot's ensemble imputes inside the model on training rows only). Not used: diagnosis, pyxis,
vitalsign, outtime (coded after discharge or recorded during the stay) and the free-text chief complaint.
If MIMIC-IV hosp/patients.csv.gz is given, `age` (anchor_age; over 89 is grouped as 91) is added.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

VITALS = ["temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp"]
CONTINUOUS = VITALS + ["pain", "n_prior_meds", "arrival_hour"]
CATEGORICAL = ["acuity", "gender", "arrival_ambulance", "arrival_walkin", "race_group", "arrival_weekend",
               "triage_incomplete"]
FEATURES = CONTINUOUS + CATEGORICAL
SUBGROUPS = ["sg_sex", "sg_arrival", "sg_esi", "sg_race"]
RACE_GROUPS = {"WHITE": 1, "BLACK": 2, "HISPANIC": 3, "ASIAN": 4, "AMERICAN INDIAN": 5, "NATIVE HAWAIIAN": 5}
RACE_LABEL = {0: "other", 1: "white", 2: "black", 3: "hispanic", 4: "asian", 5: "other"}


def _race_group(s: pd.Series) -> pd.Series:
    up = s.fillna("").astype(str).str.upper()
    out = pd.Series(0, index=s.index, dtype=int)
    for prefix, code in RACE_GROUPS.items():
        out = out.mask(up.str.startswith(prefix) & (out == 0), code)
    return out


def build(ed_dir: str, patients_path: str | None = None, n_sample: int | None = None, seed: int = 42):
    """-> (matrix with features + y + split + stratum + subgroup columns, feature names, subgroup names, info dict)."""
    from sklearn.model_selection import train_test_split

    def read(name, cols):
        return pd.read_csv(os.path.join(ed_dir, name + ".csv.gz"), usecols=cols, low_memory=False)

    stays = read("edstays", ["subject_id", "stay_id", "intime", "gender", "race", "arrival_transport", "disposition"])
    triage = read("triage", ["stay_id"] + VITALS + ["pain", "acuity"])
    medrecon = read("medrecon", ["stay_id", "name"])
    n_stays = len(stays)

    stays["_t"] = pd.to_datetime(stays["intime"], errors="coerce")
    first = stays.sort_values(["subject_id", "_t", "stay_id"]).drop_duplicates("subject_id", keep="first").reset_index(drop=True)
    n_people = len(first)

    df = pd.DataFrame(index=first.index)
    df["arrival_hour"] = first["_t"].dt.hour.astype(float)
    df["arrival_weekend"] = (first["_t"].dt.dayofweek >= 5).astype(int)
    df["gender"] = (first["gender"].astype(str).str.upper().str.strip() == "M").astype(int)
    transport = first["arrival_transport"].astype(str).str.upper().str.strip()
    df["arrival_ambulance"] = transport.isin(["AMBULANCE", "HELICOPTER"]).astype(int)
    df["arrival_walkin"] = (transport == "WALK IN").astype(int)
    df["race_group"] = _race_group(first["race"])

    tri = triage.drop_duplicates("stay_id").set_index("stay_id")
    sid = first["stay_id"]
    for c in VITALS:
        df[c] = pd.to_numeric(tri[c].reindex(sid).to_numpy(), errors="coerce")
    pain = pd.to_numeric(tri["pain"].reindex(sid).to_numpy(), errors="coerce")      # free text in v2.x ("UA" ...)
    df["pain"] = np.where((pain < 0) | (pain > 10), np.nan, pain)
    df["acuity"] = pd.to_numeric(tri["acuity"].reindex(sid).to_numpy(), errors="coerce")
    df["triage_incomplete"] = df[VITALS].isna().any(axis=1).astype(int)
    df["n_prior_meds"] = sid.map(medrecon.groupby("stay_id")["name"].nunique()).fillna(0).astype(float)

    features = list(FEATURES)
    info = {"unit": "first ED stay per person", "n_stays_in_release": int(n_stays), "n_people": int(n_people),
            "uses_patients": False}
    age = None
    if patients_path and os.path.exists(patients_path):
        pat = pd.read_csv(patients_path, usecols=["subject_id", "anchor_age"])
        age = first["subject_id"].map(pat.drop_duplicates("subject_id").set_index("subject_id")["anchor_age"])
        df["age"] = age.astype(float).to_numpy()
        features.append("age")
        info["uses_patients"] = True

    df["y"] = (first["disposition"].astype(str).str.upper().str.strip() == "ADMITTED").astype(int).to_numpy()

    if n_sample and n_sample < len(df):
        df, _ = train_test_split(df, train_size=n_sample, stratify=df["y"], random_state=seed)
        df = df.reset_index(drop=True)
        info["sampled"] = int(n_sample)
    out = df[features].astype(float).copy()
    out["y"] = df["y"].to_numpy(int)
    tr, _ = train_test_split(np.arange(len(out)), test_size=0.3, stratify=out["y"], random_state=seed)
    out["split"] = "val"
    out.loc[tr, "split"] = "train"
    esi = out["acuity"]
    out["stratum"] = np.select([esi <= 2, esi == 3, esi >= 4], ["ESI1-2", "ESI3", "ESI4-5"], "NA")
    out["sg_sex"] = np.where(df["gender"].to_numpy() == 1, "male", "female")
    out["sg_arrival"] = np.select([df["arrival_ambulance"] == 1, df["arrival_walkin"] == 1], ["ambulance", "walk-in"], "other")
    out["sg_esi"] = out["stratum"]
    out["sg_race"] = df["race_group"].map(RACE_LABEL).to_numpy()
    subgroups = list(SUBGROUPS)
    if age is not None:
        out["sg_age65"] = np.where(out["age"] >= 65, ">=65", np.where(out["age"].isna(), "NA", "<65"))
        subgroups.append("sg_age65")
    return out, features, subgroups, info
