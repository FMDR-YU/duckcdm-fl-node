# -*- coding: utf-8 -*-
"""eICU-CRD -> the pilot's analysis matrix (one row per person, first-24-hour ICU features, hospital mortality).

Used by analysis/snuh_pilot/00_build_matrix.py --dataset eicu. It returns the feature matrix only: no patient, stay or
hospital-system ids, no dates. The full release is credentialed (PhysioNet DUA), so the user runs it; the open demo
(data/eicu/demo-2.0.1, ODbL) is what Claude may run and test on.

Unit and task
-------------
One row per person: the earliest ICU stay of each `uniquepid` (a later stay of the same person would put one person into
training, validation, a site and the membership-inference sets at once). Only stays with APACHE IV first-day variables
(apacheApsVar and apachePredVar) are kept, so that the predictors are the same for every row. Outcome: hospital
discharge status "Expired". Prediction time: the end of the first ICU day.

Features: age, sex, collapsed ethnicity, admission height and weight and BMI, hours from hospital to ICU admission,
unit type, ICU and hospital admission source, admission-diagnosis group, the 24 first-day APACHE physiology variables
(missing code -1 becomes missing), total Glasgow coma score, and history flags (elective surgery, thrombolytics, readmission,
AIDS, hepatic failure, lymphoma, metastatic cancer, leukemia, immunosuppression, cirrhosis, diabetes). Not used: the
APACHE predicted mortality (apachePatientResult), diedinhospital, SAPS-3 fields and anything charted after day 1.
The hospital id is kept as a non-feature column (`hospital_id`) so that real hospitals can serve as sites later.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

APS = ["intubated", "vent", "dialysis", "eyes", "motor", "verbal", "meds", "urine", "wbc", "temperature", "respiratoryrate",
       "sodium", "heartrate", "meanbp", "ph", "hematocrit", "creatinine", "albumin", "pao2", "pco2", "bun", "glucose",
       "bilirubin", "fio2"]
HISTORY = ["electivesurgery", "thrombolytics", "readmit", "aids", "hepaticfailure", "lymphoma", "metastaticcancer", "leukemia",
           "immunosuppression", "cirrhosis", "diabetes"]
CONTINUOUS = ["age", "height", "weight", "bmi", "hours_hospital_to_icu"] + [c for c in APS if c not in ("intubated", "vent", "dialysis")] + ["gcs_total"]
CATEGORICAL = ["gender", "ethnicity_group", "unit_type", "unit_source", "hospital_source", "dx_group", "intubated", "vent", "dialysis"] + HISTORY
FEATURES = CONTINUOUS + CATEGORICAL
SUBGROUPS = ["sg_sex", "sg_age65", "sg_unit", "sg_ethnicity"]

UNIT_TYPE = {"med-surg icu": 1, "micu": 2, "cardiac icu": 3, "sicu": 4, "ccu-cticu": 5, "neuro icu": 6, "csicu": 7, "cticu": 8}
UNIT_GROUP = {1: "med-surg", 2: "medical-cardiac", 3: "medical-cardiac", 5: "medical-cardiac", 4: "surgical", 7: "surgical",
              8: "surgical", 6: "neuro"}
ETHNICITY = {"caucasian": 1, "african american": 2, "hispanic": 3, "asian": 4, "native american": 5}
ETHNICITY_LABEL = {0: "other", 1: "white", 2: "black", 3: "hispanic", 4: "other", 5: "other"}
# keyword rules for the APACHE admission diagnosis text (first match wins); the strings are diagnosis categories, not free text
DX_RULES = [("sepsis", 1), ("cardiac arrest", 2), ("arrest", 2), ("cabg", 3), ("valve", 3), ("chf", 4), ("infarction", 5),
            ("pneumonia", 6), ("copd", 6), ("asthma", 6), ("respiratory", 6), ("gi bleed", 7), ("bleed", 7), ("diabetic", 8),
            ("dka", 8), ("stroke", 9), ("intracranial", 9), ("hemorrhage", 9), ("neuro", 9), ("trauma", 10), ("renal", 11),
            ("overdose", 12), ("drug", 12)]


def _contains_code(s: pd.Series, rules: list[tuple[str, int]], default: int = 0) -> pd.Series:
    low = s.fillna("").astype(str).str.lower()
    out = pd.Series(default, index=s.index, dtype=int)
    done = pd.Series(False, index=s.index)
    for key, code in rules:
        hit = low.str.contains(key, regex=False) & ~done
        out = out.mask(hit, code)
        done |= hit
    return out


def _source_code(s: pd.Series) -> pd.Series:
    rules = [("emergency", 1), ("operating", 2), ("recovery", 2), ("pacu", 2), ("floor", 3), ("direct", 4), ("other hospital", 5),
             ("other icu", 6), ("icu", 6), ("step", 7), ("sdu", 7), ("observation", 8), ("chest pain", 8)]
    return _contains_code(s, rules)


def _parse_age(s: pd.Series) -> pd.Series:
    t = s.astype(str).str.strip()
    t = t.mask(t.str.startswith(">"), "90")
    return pd.to_numeric(t, errors="coerce")


HOSPITAL_RULES = ("top3", "spread3", "all")
MIN_HOSPITAL_ROWS = 2000      # a hospital qualifies as a site when it has at least this many analysis rows (full release: 14 hospitals)


def pick_hospitals(hospital_id, rule: str, min_rows: int = MIN_HOSPITAL_ROWS) -> list[int]:
    """Pre-specified choice of real hospitals as sites (docs/EICU_REAL_SITES_PLAN.md).
    top3    the three hospitals with most analysis rows (sizes alike)
    spread3 among hospitals with >= min_rows rows, the largest, the median-ranked and the smallest (sizes apart)
    all     every hospital with >= min_rows rows (the full release has 14 such hospitals; stage 2 of the plan)
    Ties are broken by hospital id (ascending). Returns hospital ids ordered by size, largest first."""
    sizes = pd.Series(hospital_id).value_counts()
    sizes = sizes[sizes.index >= 0]
    order = sorted(sizes.index, key=lambda h: (-int(sizes[h]), int(h)))
    ok = [h for h in order if sizes[h] >= min_rows]
    if rule == "top3":
        chosen = order[:3]
    elif rule == "spread3":
        if len(ok) < 3:
            raise ValueError(f"spread3 needs at least three hospitals with >= {min_rows} rows, found {len(ok)}")
        chosen = [ok[0], ok[(len(ok) - 1) // 2], ok[-1]]
    elif rule == "all":
        chosen = ok
    else:
        raise ValueError(f"unknown hospital rule {rule!r}; one of {HOSPITAL_RULES}")
    if len(set(chosen)) < 3 or len(set(chosen)) != len(chosen):
        raise ValueError("the rule did not yield at least three distinct hospitals")
    return [int(h) for h in chosen]


def build(eicu_dir: str, n_sample: int | None = None, seed: int = 42, hospitals: str | list[int] | None = None,
          min_hospital_rows: int = MIN_HOSPITAL_ROWS):
    """-> (matrix with features + y + split + stratum + subgroup columns + hospital_id, feature names, subgroup names, info).
    hospitals: None = every person (virtual sites are drawn later by pilot_lib.scenarios); a rule name ('top3', 'spread3') or a
    list of three hospital ids = keep only those hospitals' people, add a `site` column (0..2, largest hospital first) and split
    train / validation inside each hospital, so the real hospitals are the fixed sites (B1 = B2 = site)."""
    from sklearn.model_selection import train_test_split

    def read(name, cols=None):
        return pd.read_csv(os.path.join(eicu_dir, name + ".csv.gz"), usecols=cols, low_memory=False)

    pat = read("patient", ["patientunitstayid", "patienthealthsystemstayid", "uniquepid", "gender", "age", "ethnicity", "hospitalid",
                           "apacheadmissiondx", "admissionheight", "admissionweight", "hospitaladmitoffset", "hospitaladmitsource",
                           "hospitaldischargeyear", "hospitaldischargestatus", "unittype", "unitadmitsource", "unitvisitnumber"])
    aps = read("apacheApsVar", ["patientunitstayid"] + APS).drop_duplicates("patientunitstayid")
    pred = read("apachePredVar", ["patientunitstayid"] + HISTORY).drop_duplicates("patientunitstayid")
    n_stays = len(pat)

    pat = pat.sort_values(["uniquepid", "hospitaldischargeyear", "patienthealthsystemstayid", "unitvisitnumber", "patientunitstayid"])
    first = pat.drop_duplicates("uniquepid", keep="first")
    n_people = len(first)
    first = first.merge(aps, on="patientunitstayid", how="inner").merge(pred, on="patientunitstayid", how="inner")
    status = first["hospitaldischargestatus"].astype(str).str.strip().str.lower()
    first = first[status.isin(["alive", "expired"])].reset_index(drop=True)
    y = (first["hospitaldischargestatus"].astype(str).str.strip().str.lower() == "expired").astype(int)

    df = pd.DataFrame(index=first.index)
    df["age"] = _parse_age(first["age"])
    df["height"] = pd.to_numeric(first["admissionheight"], errors="coerce").where(lambda v: (v > 100) & (v < 230))
    df["weight"] = pd.to_numeric(first["admissionweight"], errors="coerce").where(lambda v: (v > 25) & (v < 350))
    df["bmi"] = df["weight"] / (df["height"] / 100.0) ** 2
    df["bmi"] = df["bmi"].where((df["bmi"] > 10) & (df["bmi"] < 80))
    df["hours_hospital_to_icu"] = (-pd.to_numeric(first["hospitaladmitoffset"], errors="coerce") / 60.0).clip(lower=0)
    g = first["gender"].astype(str).str.strip().str.lower()
    df["gender"] = np.where(g == "male", 1.0, np.where(g == "female", 0.0, np.nan))
    eth = first["ethnicity"].fillna("").astype(str).str.strip().str.lower()
    df["ethnicity_group"] = eth.map(ETHNICITY).fillna(0).astype(int)
    df["unit_type"] = first["unittype"].fillna("").astype(str).str.strip().str.lower().map(UNIT_TYPE).fillna(0).astype(int)
    df["unit_source"] = _source_code(first["unitadmitsource"])
    df["hospital_source"] = _source_code(first["hospitaladmitsource"])
    df["dx_group"] = _contains_code(first["apacheadmissiondx"], DX_RULES)
    for c in APS:
        v = pd.to_numeric(first[c], errors="coerce")
        df[c] = v.mask(v < 0)                                  # -1 is the missing code of the APACHE tables
    gcs = df[["eyes", "motor", "verbal"]]
    df["gcs_total"] = gcs.sum(axis=1).where(gcs.notna().all(axis=1))
    for c in HISTORY:
        v = pd.to_numeric(first[c], errors="coerce")
        df[c] = v.where(v.isin([0, 1]))

    info = {"unit": "first ICU stay per person with APACHE IV first-day variables", "n_stays_in_release": int(n_stays),
            "n_people": int(n_people), "n_rows": int(len(df))}
    if n_sample and n_sample < len(df):
        idx = np.arange(len(df))
        keep, _ = train_test_split(idx, train_size=n_sample, stratify=y, random_state=seed)
        keep = np.sort(keep)
        df, y, first = df.iloc[keep].reset_index(drop=True), y.iloc[keep].reset_index(drop=True), first.iloc[keep].reset_index(drop=True)
        info["sampled"] = int(n_sample)

    hosp = pd.to_numeric(first["hospitalid"], errors="coerce").fillna(-1).astype(int).to_numpy()
    site = None
    if hospitals is not None:
        if n_sample:
            raise ValueError("hospitals and n_sample cannot be combined")
        chosen = pick_hospitals(hosp, hospitals, min_hospital_rows) if isinstance(hospitals, str) else [int(h) for h in hospitals]
        keep = np.isin(hosp, chosen)
        df, y, first, hosp = df[keep].reset_index(drop=True), y[keep].reset_index(drop=True), first[keep].reset_index(drop=True), hosp[keep]
        site = np.array([chosen.index(h) for h in hosp], dtype=int)
        info["hospital_rule"] = hospitals if isinstance(hospitals, str) else "explicit"
        info["site_rows"] = [int((site == k).sum()) for k in range(len(chosen))]   # counts only; hospital ids are not written out
        info["n_rows_in_sites"] = int(len(df))

    out = df[FEATURES].astype(float).copy()
    out["y"] = y.to_numpy(int)
    out["split"] = "val"
    if site is None:
        tr, _ = train_test_split(np.arange(len(out)), test_size=0.3, stratify=out["y"], random_state=seed)
        out.loc[tr, "split"] = "train"
    else:                                   # 70/30 inside each hospital, so every site keeps its own outcome mix
        for k in range(int(site.max()) + 1):
            rows = np.where(site == k)[0]
            strat = out["y"].to_numpy()[rows]
            tr_k, _ = train_test_split(rows, test_size=0.3, stratify=strat if strat.min() != strat.max() else None, random_state=seed + k)
            out.loc[tr_k, "split"] = "train"
        out["site"] = site
    out["stratum"] = out["unit_type"].astype(int).map(UNIT_GROUP).fillna("other").to_numpy()
    out["sg_sex"] = np.where(df["gender"].to_numpy() == 1, "male", np.where(df["gender"].to_numpy() == 0, "female", "NA"))
    out["sg_age65"] = np.where(out["age"] >= 65, ">=65", np.where(out["age"].isna(), "NA", "<65"))
    out["sg_unit"] = out["stratum"]
    out["sg_ethnicity"] = df["ethnicity_group"].map(ETHNICITY_LABEL).to_numpy()
    out["hospital_id"] = hosp
    return out, list(FEATURES), list(SUBGROUPS), info
