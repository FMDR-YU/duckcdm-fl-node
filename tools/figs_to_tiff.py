# -*- coding: utf-8 -*-
"""Export the manuscript figures as TIFF (LZW, 300 dpi, RGB) for the BMC submission.

    python tools/figs_to_tiff.py [--out Manuscript/v2/BMC_MIDM/figures]
"""
import argparse
import os

from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGS = [('Fig1', 'Figures/v2/node/Fig1_node_architecture.png'),
        ('Fig2', 'Figures/v2/atlas/Fig_atlas_virtual_sites.png'),
        ('Fig3', 'Figures/v2/cross_cohort/Fig3_routes_cohorts.png'),
        ('Fig4', 'Figures/v2/cross_cohort/Fig4_exposure_vs_size_cohorts.png'),
        ('Fig5', 'Figures/v2/cross_cohort/Fig6_canary_cohorts.png')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, 'Manuscript', 'v2', 'BMC_MIDM', 'figures'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for name, rel in FIGS:
        src = os.path.join(BASE, rel)
        im = Image.open(src)
        if im.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', im.size, (255, 255, 255))
            bg.paste(im.convert('RGBA'), mask=im.convert('RGBA').split()[-1])
            im = bg
        else:
            im = im.convert('RGB')
        dst = os.path.join(a.out, f'{name}.tif')
        # BMC: at most 170 mm wide and at least 300 dpi at that width; the dpi tag is set so that the stored width is 170 mm
        dpi = max(300.0, im.size[0] / (170.0 / 25.4))
        im.save(dst, format='TIFF', compression='tiff_lzw', dpi=(dpi, dpi))
        w_mm = im.size[0] / dpi * 25.4
        print(f'{name}: {im.size[0]}x{im.size[1]} px, {w_mm:.0f} mm wide at {dpi:.0f} dpi -> {os.path.relpath(dst, BASE)} ({os.path.getsize(dst) / 2**20:.1f} MB)')


if __name__ == '__main__':
    main()
