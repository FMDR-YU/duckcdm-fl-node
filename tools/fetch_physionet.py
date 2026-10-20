#!/usr/bin/env python3
"""Download a PhysioNet project with checksum verification.

PhysioNet's own instructions use GNU wget, which is not installed here; the
`wget` in PowerShell is an alias for Invoke-WebRequest and does not accept those
options. This uses the standard library only.

Credentialed projects (MIMIC-IV-ED among them) need a PhysioNet account with
CITI "Data or Specimens Only Research" training and a signed DUA. The password
is read with getpass at run time: it is never taken from the command line, so it
does not reach shell history, the process list, or this repository.

    python tools/fetch_physionet.py                      # mimic-iv-ed 2.2 -> data/mimic-iv-ed/full-2.2
    python tools/fetch_physionet.py --project mimic-iv-ed-demo --dest data/mimic-iv-ed/demo-2.2
    python tools/fetch_physionet.py --verify-only        # re-check what is already on disk

Files already present with the right SHA-256 are skipped, so an interrupted run
can simply be repeated.
"""
import argparse
import base64
import getpass
import hashlib
import os
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = "https://physionet.org/files"
# PhysioNet's file server offers Basic auth only to wget-style clients: with the
# default "Python-urllib" (or a browser) User-Agent a credentialed project answers
# 403 before any login, even with a valid password. Checked 2026-10-06: a
# "Wget/..." agent gets the normal 401 challenge. PhysioNet's own download
# instructions use wget, so present the same client type.
USER_AGENT = "Wget/1.21.4 (fetch_physionet.py)"


def _opener(user, password):
    req = urllib.request.Request
    token = base64.b64encode(f"{user}:{password}".encode()).decode()

    def fetch(url, out=None, label=""):
        r = req(url, headers={"User-Agent": USER_AGENT})
        if user:
            r.add_header("Authorization", "Basic " + token)
        with urllib.request.urlopen(r) as resp:
            if out is None:
                return resp.read()
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            h = hashlib.sha256()
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "wb") as fh:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    fh.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if sys.stdout.isatty():
                        pct = f"{100 * done / total:5.1f}%" if total else "     "
                        print(f"\r  {label:<44} {done/1e6:7.1f} MB {pct}",
                              end="", flush=True)
            print(f"\r  {label:<44} {done/1e6:7.1f} MB  done ")
            return h.hexdigest()

    return fetch


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", default="mimic-iv-ed")
    p.add_argument("--version", default="2.2")
    p.add_argument("--dest", default=None)
    p.add_argument("--user", default=None, help="PhysioNet username (password is prompted)")
    p.add_argument("--verify-only", action="store_true")
    a = p.parse_args()

    dest = a.dest or os.path.join(BASE, "data", a.project, "full-" + a.version)
    dest = dest if os.path.isabs(dest) else os.path.join(BASE, dest)
    base_url = f"{ROOT}/{a.project}/{a.version}"

    sums_path = os.path.join(dest, "SHA256SUMS.txt")

    if a.verify_only:
        if not os.path.exists(sums_path):
            sys.exit(f"no SHA256SUMS.txt in {dest}; nothing to verify")
        user = password = ""
        text = open(sums_path, "rb").read()
    else:
        # An open project needs no credentials; try anonymously first.
        user, password = "", ""
        try:
            text = _opener("", "")(f"{base_url}/SHA256SUMS.txt")
            print(f"{a.project} {a.version}: open access, no credentials needed")
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                raise
            print(f"{a.project} {a.version} is credentialed; PhysioNet login required.")
            user = a.user or input("  PhysioNet username: ").strip()
            password = getpass.getpass("  PhysioNet password (not echoed): ")
            try:
                text = _opener(user, password)(f"{base_url}/SHA256SUMS.txt")
            except urllib.error.HTTPError as e2:
                if e2.code == 401:
                    sys.exit("  HTTP 401: username or password not accepted. Re-run and retype the password.")
                sys.exit(
                    f"  HTTP {e2.code}: logged in but no access. Check that the account is "
                    f"credentialed, the required training is approved, and the DUA for "
                    f"{a.project} is signed at https://physionet.org/content/{a.project}/{a.version}/"
                )

    want = {}
    for line in text.decode().splitlines():
        line = line.strip()
        if line:
            digest, _, name = line.partition(" ")
            want[name.strip()] = digest

    print(f"{len(want)} files -> {dest}")
    fetch = _opener(user, password)
    ok = skipped = failed = 0
    for name, digest in sorted(want.items()):
        out = os.path.join(dest, name.replace("/", os.sep))
        if os.path.exists(out) and sha256(out) == digest:
            skipped += 1
            continue
        if a.verify_only:
            print(f"  MISSING/BAD  {name}")
            failed += 1
            continue
        got = fetch(f"{base_url}/{name}", out, label=name)
        if got == digest:
            ok += 1
        else:
            print(f"    CHECKSUM MISMATCH for {name} - deleting")
            os.remove(out)
            failed += 1

    if not a.verify_only and not os.path.exists(sums_path):
        os.makedirs(dest, exist_ok=True)
        open(sums_path, "wb").write(text)

    print(f"\ndownloaded {ok}, already correct {skipped}, failed {failed}")
    if failed:
        sys.exit("re-run to retry the failed files")


if __name__ == "__main__":
    main()
