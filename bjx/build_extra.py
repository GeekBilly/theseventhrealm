# -*- coding: utf-8 -*-
"""Merge pinyin + origin-era into 百家姓-交叉验证.json"""
import json, sys, collections
sys.path.insert(0, '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/bjx')
from extra_data import PINYIN_RAW, ORIGIN_RAW, ERA_TABLE, MULTI_ORIGIN, POLYPHONE_NOTES

P = '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/百家姓-交叉验证.json'
d = json.load(open(P, encoding='utf-8'))
seq = d["sequence"]
names = [e["simplified"] for e in seq]
trads = [e["traditional"] for e in seq]

def parse(raw, ncol):
    out = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line: continue
        parts = line.split(None, ncol)   # surname, then value (may contain space)
        assert len(parts) == ncol + 1, line
        out.append(tuple(parts))
    return out

CONF = {"h": "high", "m": "medium", "l": "low"}
pin = parse(PINYIN_RAW, 1)
ori = [(nm, code, CONF[c]) for (nm, code, c) in parse(ORIGIN_RAW, 2)]
print("parsed pinyin:", len(pin), " origin:", len(ori))

# --- integrity: must line up 1:1 with the 504 sequence, in text order ---
assert [s for s, _ in pin] == names, [
    (i, a, b) for i, (a, b) in enumerate(zip([s for s, _ in pin], names)) if a != b][:10]
assert [s for s, _, _ in ori] == names, [
    (i, a, b) for i, (a, b) in enumerate(zip([s for s, _, _ in ori], names)) if a != b][:10]
print("alignment OK: pinyin & origin both match the 504-surname sequence in order")

# --- pinyin map (simplified + traditional keys so either script can be looked up) ---
pinyin_map = {}
for (s, py) in pin:
    pinyin_map[s] = py
for (s, py), t in zip(pin, trads):
    pinyin_map.setdefault(t, py)
# full-width safety: everything ASCII upper
for k, v in pinyin_map.items():
    assert v == v.upper() and v.replace(" ", "").isalpha(), (k, v)

# --- origin map ---
origin_map = {}
low_or_unknown = []
for i, (s, code, conf) in enumerate(ori):
    label, label_en, year = ERA_TABLE[code]
    order = i + 1
    # source attribution: S2's origin list covers entries #1-440 and #501-504 only
    in_s2 = (order <= 440) or (order >= 501)
    src = "S2+S4" if in_s2 else "S4"
    if code == "UN":
        conf = "unknown"
    elif s in MULTI_ORIGIN and conf == "h":
        conf = "medium"
    year_disp = None if year is None else (f"c. {abs(year)} BC" if year < 0 else f"c. AD {year}")
    origin_map[s] = {
        "era_label": label,
        "era_label_en": label_en,
        "approx_year": year,
        "year_display": year_disp,
        "source": src,
        "confidence": conf,
    }
    if conf in ("low", "unknown"):
        low_or_unknown.append((order, s, code, conf))

# traditional keys too (郁/后 collide harmlessly: same value)
for i, (s, code, conf) in enumerate(ori):
    t = trads[i]
    if t not in origin_map:
        origin_map[t] = dict(origin_map[s])

# duplicate graphs (后 x2, 郁 x2) share a key: a name counts as S2-covered if ANY
# of its occurrences lies inside S2's origin-list range
for _i, (_s, _c, _f) in enumerate(ori):
    _o = _i + 1
    if (_o <= 440) or (_o >= 501):
        origin_map[_s]["source"] = "S2+S4"
        origin_map[trads[_i]]["source"] = "S2+S4"

CANON = [origin_map[s] for s in names]   # stats over the 504 canonical surnames only

# --- uncertain list ---
origin_uncertain = []
for order, s, code, conf in low_or_unknown:
    label, _, year = ERA_TABLE[code]
    origin_uncertain.append({
        "order": order,
        "surname": s,
        "era_label": label,
        "approx_year": year,
        "confidence": conf,
        "reason": ("來源未給出可定位的起源時代，僅記最早見於文獻的時代 → approx_year 留 null"
                   if conf == "unknown" else
                   "來源敘述籠統（未指明朝代），或所據世系有多種互異說法 → approx_year 為暫定值，印前請確認"),
    })

# --- stats ---
conf_dist = collections.Counter(v["confidence"] for v in CANON)
era_dist = collections.Counter(v["era_label"] for v in CANON)
covered = sum(1 for v in CANON if v["approx_year"] is not None)

d["pinyin_map"] = pinyin_map
d["origin_map"] = origin_map
d["origin_uncertain"] = origin_uncertain
d["era_reference"] = {c: {"era_label": l, "era_label_en": e, "approx_year": y}
                      for c, (l, e, y) in ERA_TABLE.items()}
d["pinyin_notes"] = {
    "rule": "標準漢語拼音，去聲調符號，全大寫；多字姓用單個空格分隔。",
    "primary_source": "S2（搜狐《百家姓》全文附拼音）；以 S7（安徽教育資源網拼音版）與 S4（中華書局本注音）核對",
    "coverage": "504 / 504（全部單姓與複姓）",
    "polyphone_review": POLYPHONE_NOTES,
    "lu_umlaut_decision": "吕 → LV、闾丘 → LV QIU（本檔採用）。若版面要英文母語者易讀，可改 LU / LU QIU；若要護照式標準，可改 LYU / LYU QIU。三者皆非錯，需統一拍板。",
}
d["origin_coverage"] = {
    "S4_zhonghua": {
        "annotations": 504,
        "covered_surnames": "504 / 504（444 單姓 + 60 複姓，每姓一條起源注，無缺口）",
        "datable_era": "498 / 504（6 姓來源未給出可定位的時代）",
        "note": "S4 是目前唯一覆盖全部 504 姓的起源来源，含全部 60 个複姓。",
    },
    "S2_sohu": {
        "origin_entries": 444,
        "covered_order_slots": "第 1–440 位 + 第 501–504 位",
        "not_covered_order_slots": "第 441–500 位，共 60 個槽位（59 個不同姓氏，因『后』同時佔第 398 與第 480 位）",
        "not_covered_examples": "亓官、司寇、子車、拓跋、夾谷、谷梁、段干、東郭、南門、呼延、羊舌、微生、況、有、琴、梁丘、左丘、東門、西門、商、牟、佘、佴、伯、賞、墨、哈、譙、笪、年、愛、陽 等",
        "note": "S2 源流注的編號與《百家姓》原文順序一致（第 409–440 條正好對應万俟…司空），編到第 440 條後直接跳到尾四條（佟、第五、言、福），中間 60 個姓沒有源流注。",
    },
    "conclusion": "可以給全部 504 個姓都印年份 —— S4 覆蓋 100%。S2 只能覆蓋 444 位，缺口集中在複姓與尾段單姓。",
}

d["origin_method"] = {
    "rule": "取各姓來源敘述中『姓氏由來』所繫的朝代／時代；传说世系记为『上古传说』。",
    "granularity": "朝代級（粗粒度），approx_year 取該朝代中點，非具體年份。",
    "source": "S4（中華書局本，504 姓每姓一條起源注，覆蓋 100%）為主；S2（源流注，覆蓋 444 姓）為輔。僅取『時代』這一事實，未採用、未改寫、未複述兩者的任何成句表述。",
    "year_convention": "公元前為負數；approx_year 為該時代的粗略中點，用於版面標注，不宜作精確年代引用。",
    "confidence_scale": {
        "high": "來源明確指出朝代，且姓氏形成繫於可定年的國／人／事",
        "medium": "起源屬傳說時代（三皇五帝堯舜禹），或來源並列多種互異源流",
        "low": "來源敘述籠統、未指明朝代，年份為暫定值",
        "unknown": "來源僅稱『起源不詳』，approx_year 為 null",
    },
}

json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print("\npinyin_map:", len(pinyin_map), "entries (504 surnames + traditional aliases)")
print("origin_map:", len(origin_map), "entries (504 surnames + traditional aliases)")
print("origin with approx_year:", covered, "/ 504")
print("confidence distribution:", dict(conf_dist))
print("origin_uncertain:", len(origin_uncertain))
print("\nera distribution:")
for k, v in era_dist.most_common():
    print(f"  {k:6s} {v:3d}")
print("\nspot checks:")
for s in ["赵","欧阳","万俟","单","解","仇","尉迟","长孙","乐","查","曾","缪","盖","吕","闾丘"]:
    print(f"  {s:4s} {pinyin_map[s]:12s} {origin_map[s]['era_label']:6s} {origin_map[s]['year_display']}")
print("\nwrote", P)
