# -*- coding: utf-8 -*-
"""Figure 1 of the ACI paper: one institutional node (OMOP CDM DuckDB file + duckcdm + FLARE client + export gate), three
such nodes under a federated-learning server, and what crosses the institutional boundary. Schematic only, no data.
Black and white, outlines only (document rule). Boxes carry names only; arrows carry a number that the key below explains.
Output Figures/v2/node/Fig1_node_architecture.{png,pdf}.

    python fig_node_architecture.py [--out DIR]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figures as F  # noqa: E402
import pilot_lib as L  # noqa: E402

NODE_W, NODE_H = 6.0, 5.6
KEY = [
    ('1', 'cohort and feature matrix read from the file by duckcdm (circe-compiled cohort, SQL features)'),
    ('2', 'gradient histograms up, global trees down (NVIDIA FLARE 2.9, histogram-based XGBoost 3.2); no patient rows leave'),
    ('3', 'the same cohort definition JSON (institutional ATLAS, circe 1.11.1) is compiled at every node: code goes to the data'),
    ('4', 'ATLAS 3.0 in a browser on the same host, served by duckcdm (WebAPI, Achilles)'),
    ('5', 'trained model enters the export gate: utility, leakage and reproducibility gates plus the canary / LiRA audit'),
    ('6', 'leaves the institution only if every gate passes: the model and its audit record (aggregates only, cells of 11 or more)'),
]


def box(ax, x, y, w, h, text, fs=6.6, lw=0.8, ls='-', weight='normal'):
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=lw, ls=ls, ec='k'))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha='center', va='center', fontsize=fs, fontweight=weight, linespacing=1.25)


def arrow(ax, x0, y0, x1, y1, lw=0.8, ls='-', style='-|>'):
    ax.annotate('', xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle=style, lw=lw, ls=ls, color='k', shrinkA=0, shrinkB=0, mutation_scale=7))


def tag(ax, x, y, n):
    """Small circled number next to an arrow, white-backed so it never sits on a line."""
    ax.text(x, y, n, ha='center', va='center', fontsize=5.8,
            bbox=dict(boxstyle='circle,pad=0.25', fc='white', ec='k', lw=0.6))


def draw_node(ax, x, y, label, tags=True):
    W, H = NODE_W, NODE_H
    box(ax, x, y, W, H, '', lw=1.1)
    ax.text(x + 0.15, y + H - 0.12, label, ha='left', va='top', fontsize=7, fontweight='bold')
    g = 0.55
    cw = 2.45
    dw = W - g - cw - 0.55
    xd = x + g + cw + 0.3
    box(ax, x + g, y + 3.75, W - g - 0.25, 0.95, 'FLARE client', fs=6.6)
    box(ax, x + g, y + 2.15, cw, 1.2, 'OMOP CDM v5.3\none DuckDB file', fs=6.2)
    box(ax, xd, y + 2.15, dw, 1.2, 'duckcdm\n(pure Python)', fs=6.2)
    box(ax, x + g, y + 0.3, cw, 1.2, 'export gate', fs=6.6, lw=1.0)
    box(ax, xd, y + 0.3, dw, 1.2, 'ATLAS 3.0', fs=6.2, ls='--')
    arrow(ax, x + g + cw, y + 2.75, xd, y + 2.75, lw=0.7)                      # file -> duckcdm
    arrow(ax, x + g + cw / 2, y + 3.35, x + g + cw / 2, y + 3.75, lw=0.7)      # file -> client
    arrow(ax, xd + dw / 2, y + 2.15, xd + dw / 2, y + 1.5, lw=0.7, style='<|-|>')   # duckcdm <-> ATLAS
    xg = x + g / 2
    ax.plot([x + g, xg, xg], [y + 4.22, y + 4.22, y + 0.9], lw=0.7, color='k')
    arrow(ax, xg, y + 0.9, x + g, y + 0.9, lw=0.7)                            # model -> gate
    if tags:
        tag(ax, x + g + cw / 2 + 0.45, y + 3.55, '1')
        tag(ax, xd + dw / 2 + 0.45, y + 1.82, '4')
        tag(ax, xg, y + 2.6, '5')
    return {'client_top': (x + g + (W - g - 0.25) / 2, y + 4.7), 'gate_bottom': (x + g + cw / 2, y + 0.3), 'top': y + H,
            'duckcdm_top': (xd + dw / 2, y + 3.35)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(L.BASE, 'Figures', 'v2', 'node'))
    a = ap.parse_args()
    plt = F.style()
    fig, ax = plt.subplots(figsize=(9.0, 7.0))
    ax.set_xlim(0, 20.4)
    ax.set_ylim(-2.9, 13.6)
    ax.set_aspect('equal')
    ax.axis('off')

    xs = [0.3, 7.2, 14.1]
    y0 = 3.2
    anchors = [draw_node(ax, x, y0, f'institution {k + 1}') for k, x in enumerate(xs)]

    # FL server, top centre; a bus collects the three clients
    sx, sy, sw, sh = 5.0, 11.6, 6.4, 1.5
    box(ax, sx, sy, sw, sh, 'FL server', fs=6.8, lw=1.1)
    busy = 10.4
    for p in anchors:
        cx = p['client_top'][0]
        arrow(ax, cx, p['top'], cx, busy, lw=0.8, style='<|-|>')
    ax.plot([anchors[0]['client_top'][0], anchors[-1]['client_top'][0]], [busy, busy], lw=0.8, color='k')
    arrow(ax, sx + sw / 2, busy, sx + sw / 2, sy, lw=0.8, style='<|-|>')
    tag(ax, sx + sw / 2 + 0.45, (busy + sy) / 2, '2')

    # cohort definition JSON, top right, dashed, straight down into node 3's duckcdm
    jx, jy, jw, jh = 13.4, 11.6, 6.7, 1.5
    box(ax, jx, jy, jw, jh, 'cohort definition JSON', fs=6.8, ls='--')
    d = anchors[-1]['duckcdm_top']
    ax.plot([d[0], d[0]], [jy, y0 + NODE_H + 0.01], lw=0.7, color='k', ls='--')
    arrow(ax, d[0], y0 + NODE_H + 0.02, d[0], y0 + NODE_H, lw=0.7, ls='--')
    tag(ax, d[0] + 0.45, (jy + busy) / 2, '3')

    # released artefacts: collected from the three gates below the nodes
    gy = 2.2
    for p in anchors:
        gx, gyy = p['gate_bottom']
        ax.plot([gx, gx], [gyy, gy], lw=0.8, color='k')
    ax.plot([anchors[0]['gate_bottom'][0], anchors[-1]['gate_bottom'][0]], [gy, gy], lw=0.8, color='k')
    rx, ry, rw, rh = 6.2, 0.3, 8.0, 1.1
    arrow(ax, rx + rw / 2, gy, rx + rw / 2, ry + rh, lw=0.8)
    tag(ax, rx + rw / 2 + 0.45, (gy + ry + rh) / 2, '6')
    box(ax, rx, ry, rw, rh, 'released model + audit record', fs=6.8, lw=1.0)

    # key
    ax.plot([0.3, 20.1], [-0.2, -0.2], lw=0.5, color='k')
    for i, (n, text) in enumerate(KEY):
        yk = -0.6 - 0.42 * i
        tag(ax, 0.55, yk, n)
        ax.text(1.0, yk, text, ha='left', va='center', fontsize=6)
    F.save(fig, a.out, 'Fig1_node_architecture')


if __name__ == '__main__':
    main()
