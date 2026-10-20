"""T0 driver (host side): isolated federated topology for the XGBoost export study.

    python t0.py all     --dataset synpuf --scenario B1 --seed 42 --config plain
    python t0.py prepare|up|submit|check|down  [same options]

prepare  provision FLARE startup kits (server1, site-1..3, admin) with the image, and let each site allow-list
         its own data-loader class (`fl_data.ParquetSiteLoader`) in local/resources.json
up       start the aggregator and the three sites (compose.yml): aggregator without data, sites on separate
         internal networks, each site seeing only its own data folder
submit   run the job from the admin container (no data mounted) and wait for it
check    isolation checks with docker exec, then compare the model the sites hold with the simulator's
down     stop and remove the containers and networks

Needs Docker running (start Docker Desktop from your own terminal), the image snuh-fl-flare:0.1, and the site
files from make_sites.py. Writes aggregates only to analysis/federated/out/t0/. The kits (with keys) and the
FLARE workspace stay in data/federated/t0/.
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FED = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(FED))
DOCKER = next(p for p in (r"C:\Program Files\Docker\Docker\resources\bin\docker.exe", "docker")
              if p == "docker" or os.path.exists(p))
IMAGE = "snuh-fl-flare:0.1"
WS = os.path.join(ROOT, "data", "federated", "t0")
KITS = os.path.join(WS, "workspace", "snuh_t0", "prod_00")
OUT = os.path.join(FED, "out", "t0")
LOADER_CLASS = "fl_data.ParquetSiteLoader"
fwd = lambda p: p.replace("\\", "/")  # noqa: E731


def run(cmd, env=None, log=None, check=True):
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if log:
        with open(log, "w", encoding="utf-8") as f:
            f.write(r.stdout + r.stderr)
    if check and r.returncode:
        print(r.stdout[-2500:], r.stderr[-3500:])
        sys.exit(f"command failed ({r.returncode}): {' '.join(str(c) for c in cmd[:6])} ...")
    return r


def site_dir(a):
    return os.path.join(ROOT, "data", "federated", a.dataset + (f"_{a.tag}" if a.tag else ""), f"{a.scenario}_s{a.seed}")


def compose(a, *args, log=None, check=True):
    env = dict(os.environ, T0_KITS=fwd(KITS), T0_DATA=fwd(site_dir(a)), T0_ANALYSIS=fwd(os.path.join(ROOT, "analysis")),
               T0_OUT=fwd(OUT))
    return run([DOCKER, "compose", "-f", os.path.join(HERE, "compose.yml"), *args], env=env, log=log, check=check)


def prepare(a):
    for k in (1, 2, 3):
        if not os.path.exists(os.path.join(site_dir(a), f"site-{k}", "train.parquet")):
            sys.exit(f"missing site files in {site_dir(a)} -- run make_sites.py first")
    shutil.rmtree(os.path.join(WS, "workspace"), ignore_errors=True)       # old kits hold old keys
    os.makedirs(WS, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    run([DOCKER, "run", "--rm", "--network", "none", "-v", f"{WS}:/ws", "-v", f"{HERE}:/t0:ro", IMAGE,
         "nvflare", "provision", "-p", "/t0/project.yml", "-w", "/ws/workspace", "--force"],
        log=os.path.join(OUT, "t0_provision.log"))
    for k in (1, 2, 3):                                                   # each site approves its own loader class
        loc = os.path.join(KITS, f"site-{k}", "local")
        with open(os.path.join(loc, "resources.json.default"), encoding="utf-8") as f:
            res = json.load(f)
        res["class_allow_list"] = sorted(set(res["class_allow_list"]) | {LOADER_CLASS})
        with open(os.path.join(loc, "resources.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
    print(f"kits ready: {KITS}")


def up(a):
    os.makedirs(OUT, exist_ok=True)
    compose(a, "up", "-d", "server1", "site-1", "site-2", "site-3", log=os.path.join(OUT, "t0_up.log"))
    time.sleep(20)
    print(run([DOCKER, "ps", "--filter", "name=t0-", "--format", "{{.Names}} {{.Status}}"]).stdout.strip())


def submit(a):
    with open(os.path.join(site_dir(a), "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    pos = man["pooled"]["events_train"]
    neg = man["pooled"]["n_train"] - pos
    t = time.time()
    r = compose(a, "run", "--rm", "-T", "admin", "python", "t0/submit_job.py", "--config", a.config, "--seed", str(a.seed),
                "--pos", str(pos), "--neg", str(neg), log=os.path.join(OUT, "t0_submit.log"), check=False)
    tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
    print("\n".join(tail))
    print(f"job finished in {time.time() - t:.0f} s, exit {r.returncode}")
    if r.returncode:
        sys.exit("submit failed -- see out/t0/t0_submit.log and `docker logs t0-server1`")


def dx(container, *cmd):
    r = subprocess.run([DOCKER, "exec", container, *cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() + (("\n" + r.stderr.strip()) if r.returncode and r.stderr.strip() else "")


def probe(container, host, port):
    code = ("import socket,errno\ns=socket.socket(); s.settimeout(3)\n"
            f"try: s.connect(({host!r},{port})); print('connected')\n"
            "except socket.gaierror: print('unresolved')\n"
            "except socket.timeout: print('timeout')\n"
            "except OSError as e: print(errno.errorcode.get(e.errno, str(e.errno)))\n")
    return dx(container, "python", "-c", code)


def check(a):
    res = {"dataset": a.dataset, "scenario": a.scenario, "seed": a.seed, "config": a.config}
    mounts = lambda c: sorted(m for m in dx(c, "sh", "-c", "grep -E ' /(fl|data|work|out)' /proc/mounts | cut -d' ' -f2").split())  # noqa: E731
    res["server_mounts"] = mounts("t0-server1")
    res["server_has_data_dir"] = "No such file" not in dx("t0-server1", "sh", "-c", "ls /data 2>&1")
    res["server_data_files"] = int(dx("t0-server1", "sh", "-c",
                                      "find / \\( -path /proc -o -path '*/site-packages' \\) -prune -o \\( -name '*.parquet' "
                                      "-o -name 'matrix_*' \\) -print 2>/dev/null | wc -l") or -1)
    res["server_ip_forward"] = dx("t0-server1", "cat", "/proc/sys/net/ipv4/ip_forward")
    for k in (1, 2, 3):
        c = f"t0-site-{k}"
        res[f"site{k}_data_dirs"] = dx(c, "ls", "/data").split()
        res[f"site{k}_data_files"] = sorted(dx(c, "ls", f"/data/site-{k}").split())
        res[f"site{k}_networks"] = sorted(run([DOCKER, "inspect", "-f", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}", c]).stdout.split())
        res[f"site{k}_reaches_server"] = probe(c, "server1", 8002)
        other = (k % 3) + 1
        ip = run([DOCKER, "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}",
                  f"t0-site-{other}"]).stdout.split()[0]
        res[f"site{k}_to_site{other}_by_name"] = probe(c, f"t0-site-{other}", 8002)
        res[f"site{k}_to_site{other}_by_ip"] = probe(c, ip, 8002)
        res[f"site{k}_to_internet"] = probe(c, "1.1.1.1", 443)
    res["server_networks"] = sorted(run([DOCKER, "inspect", "-f", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}",
                                         "t0-server1"]).stdout.split())
    # bytes that crossed each container's network interface since start (received / sent): the traffic of the whole
    # job, including registration and heartbeats -- what leaves a site during training
    stats = run([DOCKER, "stats", "--no-stream", "--format", "{{.Name}}|{{.NetIO}}", "t0-server1", "t0-site-1", "t0-site-2",
                 "t0-site-3"]).stdout.strip().splitlines()
    res["net_io_received_sent"] = {s.split("|")[0]: s.split("|")[1] for s in stats if "|" in s}
    res["isolation_ok"] = bool(
        not res["server_has_data_dir"] and res["server_data_files"] == 0
        and all(res[f"site{k}_data_dirs"] == [f"site-{k}"] and res[f"site{k}_reaches_server"] == "connected"
                and res[f"site{k}_to_site{(k % 3) + 1}_by_name"] == "unresolved"
                and res[f"site{k}_to_site{(k % 3) + 1}_by_ip"] not in ("connected", "ECONNREFUSED")
                and res[f"site{k}_to_internet"] != "connected" for k in (1, 2, 3)))

    models = sorted(glob.glob(os.path.join(glob.escape(KITS), "site-*", "**", "model.json"), recursive=True), key=os.path.getmtime)
    res["model_files"] = len(models)
    if models:
        sha = [hashlib.sha256(open(m, "rb").read()).hexdigest() for m in models[-3:]]
        res["site_models_identical_bytes"] = len(set(sha)) == 1
        sys.path.insert(0, os.path.join(os.path.dirname(FED), "snuh_pilot"))
        sys.path.insert(0, FED)
        if a.tag:
            os.environ["PILOT_TAG"] = a.tag
        import numpy as np
        import pilot_lib as pl
        import xgboost as xgb
        X, y, split, aux, meta = pl.load_matrix(a.dataset)
        val = np.where(split == "val")[0]
        dval = xgb.DMatrix(X.iloc[val])
        b = xgb.Booster()
        b.load_model(models[-1])
        p_t0 = b.predict(dval)
        res["t0_val_auroc"] = pl.auc(y[val], p_t0)
        sim = pl.fed_model_path(a.dataset, a.scenario, a.seed, f"xgb_{a.config}")
        if os.path.exists(sim):
            bs = xgb.Booster()
            bs.load_model(sim)
            p_sim = bs.predict(dval)
            res["simulator_val_auroc"] = pl.auc(y[val], p_sim)
            res["max_abs_pred_diff_vs_simulator"] = float(np.abs(p_t0 - p_sim).max())
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "t0_check.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=1))
    print("isolation_ok:", res["isolation_ok"])


def down(a):
    compose(a, "down", "-v", "--remove-orphans", check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["all", "prepare", "up", "submit", "check", "down"])
    ap.add_argument("--dataset", default="synpuf")
    ap.add_argument("--tag", default="")
    ap.add_argument("--scenario", choices=["B1", "B2"], default="B1")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--config", choices=["plain", "krcp", "leaky", "regularized"], default="plain")
    a = ap.parse_args()
    if a.action == "all":
        prepare(a)
        try:
            up(a)
            submit(a)
            check(a)
        finally:
            down(a)
    else:
        {"prepare": prepare, "up": up, "submit": submit, "check": check, "down": down}[a.action](a)


if __name__ == "__main__":
    main()
