# -*- coding: utf-8 -*-
import json, sys, collections
sys.path.insert(0, '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/bjx')
from sources import *

SRC = collections.OrderedDict([
    ("S1_gutenberg", S1_GUTENBERG),
    ("S2_sohu",      S2_SOHU),
    ("S3_meipian",   S3_MEIPIAN),
    ("S4_zhonghua",  S4_ZHONGHUA),
    ("S5_rsonglab",  S5_RSONGLAB),
    ("S6_wyxin",     S6_WYXIN),
    ("S7_ahedu",     S7_AHEDU),
])

for k, v in SRC.items():
    print(k, len(v))

FULL = 568
print("--- length check (expect 568 for complete sources) ---")

# --- automatic S1 vs S3 character pair report (index-aligned) ---
z1, z3 = S1_GUTENBERG, S3_MEIPIAN
pairs = collections.OrderedDict()
for i, (a, b) in enumerate(zip(z1, z3)):
    if a != b:
        pairs.setdefault((a, b), []).append(i)
print("\n--- S1(Gutenberg trad) vs S3(meipian simp): differing chars ---")
for (a, b), idx in pairs.items():
    print(f"{a} -> {b}   n={len(idx)}  idx={idx[:8]}")
print("total differing positions:", sum(len(v) for v in pairs.values()))
