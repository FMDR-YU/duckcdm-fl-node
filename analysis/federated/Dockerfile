# Federated XGBoost arm (NVIDIA FLARE 2.9.0, histogram-based horizontal).
# The Windows xgboost wheel is built without the federated communicator (USE_FEDERATED False),
# so this arm runs in a Linux container on the same laptop. xgboost is pinned to 3.2.0: FLARE 2.9.0 requires
# <3.4, and from 3.3 the DataSplitMode enum lives in xgboost._typing, which FLARE's serializer does not whitelist.
#   docker build -t snuh-fl-flare:0.1 analysis/federated
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-fl.txt /tmp/requirements-fl.txt
RUN pip install -r /tmp/requirements-fl.txt

WORKDIR /work/analysis/federated
