"""Site-side data loader for the FLARE XGBoost job.

Each virtual site reads only its own folder: <folder>/<client_id>/train.parquet and valid.parquet
(feature columns + y), written by make_sites.py. The validation file is used for monitoring only;
the reported performance comes from the common validation set, scored outside the federation.
"""
import os

import pandas as pd
import xgboost as xgb
from nvflare.app_opt.xgboost.data_loader import XGBDataLoader


class ParquetSiteLoader(XGBDataLoader):
    def __init__(self, folder: str):
        self.folder = folder

    def _matrix(self, name: str) -> xgb.DMatrix:
        df = pd.read_parquet(os.path.join(self.folder, self.client_id, f"{name}.parquet"))
        y = df["y"].to_numpy()
        return xgb.DMatrix(df.drop(columns=["y"]), label=y, data_split_mode=self.data_split_mode)

    def load_data(self):
        return self._matrix("train"), self._matrix("valid")
