# -*- coding: utf-8 -*-
"""Pinyin + origin-era data for the 504 百家姓 surnames.

PINYIN source : S2 (搜狐/「诗评万象」《百家姓》全文附拼音, tone marks stripped,
                upper-cased) cross-checked against S7 (安徽教育资源网 拼音版) and
                S4 (中华书局本注释中的注音). Polyphone decisions recorded in
                POLYPHONE_NOTES below.
ORIGIN source : the per-surname origin accounts in S4 (中华书局《蒙学经典·百家姓》,
                one note per surname, all 504) and S2 (origin list #1-444). Only
                the ERA FACT is recorded here; no source wording is reproduced.
ERA CODE      : key into ERA_TABLE below (approx_year = midpoint of the era).
"""

# ---------- pinyin : "surname PINYIN" (504 lines, text order) ----------
PINYIN_RAW = """
赵 ZHAO
钱 QIAN
孙 SUN
李 LI
周 ZHOU
吴 WU
郑 ZHENG
王 WANG
冯 FENG
陈 CHEN
褚 CHU
卫 WEI
蒋 JIANG
沈 SHEN
韩 HAN
杨 YANG
朱 ZHU
秦 QIN
尤 YOU
许 XU
何 HE
吕 LV
施 SHI
张 ZHANG
孔 KONG
曹 CAO
严 YAN
华 HUA
金 JIN
魏 WEI
陶 TAO
姜 JIANG
戚 QI
谢 XIE
邹 ZOU
喻 YU
柏 BAI
水 SHUI
窦 DOU
章 ZHANG
云 YUN
苏 SU
潘 PAN
葛 GE
奚 XI
范 FAN
彭 PENG
郎 LANG
鲁 LU
韦 WEI
昌 CHANG
马 MA
苗 MIAO
凤 FENG
花 HUA
方 FANG
俞 YU
任 REN
袁 YUAN
柳 LIU
酆 FENG
鲍 BAO
史 SHI
唐 TANG
费 FEI
廉 LIAN
岑 CEN
薛 XUE
雷 LEI
贺 HE
倪 NI
汤 TANG
滕 TENG
殷 YIN
罗 LUO
毕 BI
郝 HAO
邬 WU
安 AN
常 CHANG
乐 YUE
于 YU
时 SHI
傅 FU
皮 PI
卞 BIAN
齐 QI
康 KANG
伍 WU
余 YU
元 YUAN
卜 BU
顾 GU
孟 MENG
平 PING
黄 HUANG
和 HE
穆 MU
萧 XIAO
尹 YIN
姚 YAO
邵 SHAO
湛 ZHAN
汪 WANG
祁 QI
毛 MAO
禹 YU
狄 DI
米 MI
贝 BEI
明 MING
臧 ZANG
计 JI
伏 FU
成 CHENG
戴 DAI
谈 TAN
宋 SONG
茅 MAO
庞 PANG
熊 XIONG
纪 JI
舒 SHU
屈 QU
项 XIANG
祝 ZHU
董 DONG
梁 LIANG
杜 DU
阮 RUAN
蓝 LAN
闵 MIN
席 XI
季 JI
麻 MA
强 QIANG
贾 JIA
路 LU
娄 LOU
危 WEI
江 JIANG
童 TONG
颜 YAN
郭 GUO
梅 MEI
盛 SHENG
林 LIN
刁 DIAO
钟 ZHONG
徐 XU
邱 QIU
骆 LUO
高 GAO
夏 XIA
蔡 CAI
田 TIAN
樊 FAN
胡 HU
凌 LING
霍 HUO
虞 YU
万 WAN
支 ZHI
柯 KE
昝 ZAN
管 GUAN
卢 LU
莫 MO
经 JING
房 FANG
裘 QIU
缪 MIAO
干 GAN
解 XIE
应 YING
宗 ZONG
丁 DING
宣 XUAN
贲 FEI
邓 DENG
郁 YU
单 SHAN
杭 HANG
洪 HONG
包 BAO
诸 ZHU
左 ZUO
石 SHI
崔 CUI
吉 JI
钮 NIU
龚 GONG
程 CHENG
嵇 JI
邢 XING
滑 HUA
裴 PEI
陆 LU
荣 RONG
翁 WENG
荀 XUN
羊 YANG
於 YU
惠 HUI
甄 ZHEN
曲 QU
家 JIA
封 FENG
芮 RUI
羿 YI
储 CHU
靳 JIN
汲 JI
邴 BING
糜 MI
松 SONG
井 JING
段 DUAN
富 FU
巫 WU
乌 WU
焦 JIAO
巴 BA
弓 GONG
牧 MU
隗 KUI
山 SHAN
谷 GU
车 CHE
侯 HOU
宓 FU
蓬 PENG
全 QUAN
郗 XI
班 BAN
仰 YANG
秋 QIU
仲 ZHONG
伊 YI
宫 GONG
宁 NING
仇 QIU
栾 LUAN
暴 BAO
甘 GAN
钭 TOU
厉 LI
戎 RONG
祖 ZU
武 WU
符 FU
刘 LIU
景 JING
詹 ZHAN
束 SHU
龙 LONG
叶 YE
幸 XING
司 SI
韶 SHAO
郜 GAO
黎 LI
蓟 JI
薄 BO
印 YIN
宿 SU
白 BAI
怀 HUAI
蒲 PU
邰 TAI
从 CONG
鄂 E
索 SUO
咸 XIAN
籍 JI
赖 LAI
卓 ZHUO
蔺 LIN
屠 TU
蒙 MENG
池 CHI
乔 QIAO
阴 YIN
郁 YU
胥 XU
能 NAI
苍 CANG
双 SHUANG
闻 WEN
莘 SHEN
党 DANG
翟 ZHAI
谭 TAN
贡 GONG
劳 LAO
逄 PANG
姬 JI
申 SHEN
扶 FU
堵 DU
冉 RAN
宰 ZAI
郦 LI
雍 YONG
郤 XI
璩 QU
桑 SANG
桂 GUI
濮 PU
牛 NIU
寿 SHOU
通 TONG
边 BIAN
扈 HU
燕 YAN
冀 JI
郏 JIA
浦 PU
尚 SHANG
农 NONG
温 WEN
别 BIE
庄 ZHUANG
晏 YAN
柴 CHAI
瞿 QU
阎 YAN
充 CHONG
慕 MU
连 LIAN
茹 RU
习 XI
宦 HUAN
艾 AI
鱼 YU
容 RONG
向 XIANG
古 GU
易 YI
慎 SHEN
戈 GE
廖 LIAO
庾 YU
终 ZHONG
暨 JI
居 JU
衡 HENG
步 BU
都 DU
耿 GENG
满 MAN
弘 HONG
匡 KUANG
国 GUO
文 WEN
寇 KOU
广 GUANG
禄 LU
阙 QUE
东 DONG
欧 OU
殳 SHU
沃 WO
利 LI
蔚 WEI
越 YUE
夔 KUI
隆 LONG
师 SHI
巩 GONG
厍 SHE
聂 NIE
晁 CHAO
勾 GOU
敖 AO
融 RONG
冷 LENG
訾 ZI
辛 XIN
阚 KAN
那 NA
简 JIAN
饶 RAO
空 KONG
曾 ZENG
毋 WU
沙 SHA
乜 NIE
养 YANG
鞠 JU
须 XU
丰 FENG
巢 CHAO
关 GUAN
蒯 KUAI
相 XIANG
查 ZHA
后 HOU
荆 JING
红 HONG
游 YOU
竺 ZHU
权 QUAN
逯 LU
盖 GE
益 YI
桓 HUAN
公 GONG
万俟 MO QI
司马 SI MA
上官 SHANG GUAN
欧阳 OU YANG
夏侯 XIA HOU
诸葛 ZHU GE
闻人 WEN REN
东方 DONG FANG
赫连 HE LIAN
皇甫 HUANG FU
尉迟 YU CHI
公羊 GONG YANG
澹台 TAN TAI
公冶 GONG YE
宗政 ZONG ZHENG
濮阳 PU YANG
淳于 CHUN YU
单于 CHAN YU
太叔 TAI SHU
申屠 SHEN TU
公孙 GONG SUN
仲孙 ZHONG SUN
轩辕 XUAN YUAN
令狐 LING HU
钟离 ZHONG LI
宇文 YU WEN
长孙 ZHANG SUN
慕容 MU RONG
鲜于 XIAN YU
闾丘 LV QIU
司徒 SI TU
司空 SI KONG
亓官 QI GUAN
司寇 SI KOU
仉 ZHANG
督 DU
子车 ZI CHE
颛孙 ZHUAN SUN
端木 DUAN MU
巫马 WU MA
公西 GONG XI
漆雕 QI DIAO
乐正 YUE ZHENG
壤驷 RANG SI
公良 GONG LIANG
拓跋 TUO BA
夹谷 JIA GU
宰父 ZAI FU
谷梁 GU LIANG
晋 JIN
楚 CHU
闫 YAN
法 FA
汝 RU
鄢 YAN
涂 TU
钦 QIN
段干 DUAN GAN
百里 BAI LI
东郭 DONG GUO
南门 NAN MEN
呼延 HU YAN
归 GUI
海 HAI
羊舌 YANG SHE
微生 WEI SHENG
岳 YUE
帅 SHUAI
缑 GOU
亢 KANG
况 KUANG
后 HOU
有 YOU
琴 QIN
梁丘 LIANG QIU
左丘 ZUO QIU
东门 DONG MEN
西门 XI MEN
商 SHANG
牟 MOU
佘 SHE
佴 NAI
伯 BO
赏 SHANG
南宫 NAN GONG
墨 MO
哈 HA
谯 QIAO
笪 DA
年 NIAN
爱 AI
阳 YANG
佟 TONG
第五 DI WU
言 YAN
福 FU
"""

# ---------- origin era : "surname CODE CONF" (504 lines, text order) ----------
ORIGIN_RAW = """
赵 ZX h
钱 ZX h
孙 CQ h
李 SM m
周 CQ h
吴 SM m
郑 ZX h
王 CQ m
冯 ZX h
陈 ZX h
褚 CQ h
卫 ZX h
蒋 ZX h
沈 ZX h
韩 CQ h
杨 ZX h
朱 ZX m
秦 ZX h
尤 WD h
许 ZX h
何 ZG m
吕 XA h
施 SM h
张 LT m
孔 SH h
曹 ZX h
严 CQ h
华 CQ h
金 LT m
魏 CQ h
陶 LT m
姜 LT m
戚 CQ h
谢 ZX h
邹 ZX h
喻 LJ h
柏 CQ h
水 XA h
窦 XA h
章 CQ h
云 CQ h
苏 ZX h
潘 ZX h
葛 XA h
奚 XA h
范 CQ h
彭 LT m
郎 CQ h
鲁 ZX h
韦 XA h
昌 LT m
马 ZG h
苗 CQ h
凤 LT m
花 TA h
方 ZX h
俞 LT m
任 LT m
袁 CQ h
柳 CQ h
酆 ZX h
鲍 CQ h
史 ZX h
唐 LT m
费 XA h
廉 LT m
岑 ZX h
薛 XA h
雷 LT m
贺 CQ h
倪 CQ h
汤 SH h
滕 ZX h
殷 SH h
罗 CQ h
毕 ZX h
郝 SH h
邬 LT m
安 LT m
常 LT m
乐 CQ h
于 ZX h
时 CQ h
傅 SH h
皮 ZX h
卞 CQ h
齐 ZX h
康 ZX h
伍 CQ h
余 CQ h
元 SH h
卜 LT l
顾 XA h
孟 CQ h
平 ZG h
黄 ZX m
和 LT m
穆 CQ h
萧 CQ h
尹 LT m
姚 LT m
邵 ZX h
湛 XA h
汪 CQ h
祁 CQ h
毛 ZX h
禹 CQ h
狄 ZX h
米 TA h
贝 ZX h
明 CQ h
臧 CQ h
计 ZX h
伏 NB h
成 ZX h
戴 CQ h
谈 CQ h
宋 ZG h
茅 ZX h
庞 ZX h
熊 LT m
纪 ZX h
舒 ZX h
屈 CQ h
项 CQ h
祝 ZX h
董 LT m
梁 CQ h
杜 ZX m
阮 SH h
蓝 CQ h
闵 CQ h
席 QN h
季 CQ h
麻 CQ h
强 CQ h
贾 ZX h
路 LT m
娄 ZX h
危 LT m
江 ZX h
童 LT m
颜 CQ h
郭 ZX h
梅 SH h
盛 ZX h
林 SH h
刁 ZX h
钟 CQ h
徐 XA h
邱 ZX h
骆 ZX h
高 ZX h
夏 CQ h
蔡 ZX h
田 CQ m
樊 ZX h
胡 CQ m
凌 ZX h
霍 ZX h
虞 ZX h
万 ZX h
支 HA h
柯 CQ h
昝 CQ h
管 ZX h
卢 CQ h
莫 LT m
经 CQ h
房 LT m
裘 CQ h
缪 CQ h
干 CQ h
解 ZX h
应 ZX h
宗 ZX l
丁 ZX h
宣 ZX h
贲 CQ h
邓 SH h
郁 CQ h
单 ZX h
杭 XA h
洪 LT m
包 CQ h
诸 HA h
左 ZX h
石 ZX h
崔 CQ h
吉 ZX h
钮 LJ l
龚 LT m
程 LT m
嵇 XA h
邢 ZX h
滑 ZX h
裴 ZX h
陆 ZG m
荣 ZX h
翁 ZX m
荀 ZX h
羊 CQ h
於 LT m
惠 CQ h
甄 LT m
曲 ZX l
家 ZG l
封 XA h
芮 ZX h
羿 XA h
储 ZX l
靳 ZG h
汲 CQ h
邴 CQ h
糜 XA h
松 QN h
井 CQ h
段 CQ h
富 CQ h
巫 LT m
乌 LT m
焦 ZX h
巴 ZX h
弓 CQ h
牧 LT m
隗 SH h
山 ZX l
谷 ZX h
车 CQ h
侯 ZX l
宓 LT m
蓬 ZX h
全 ZX h
郗 ZX h
班 CQ h
仰 ZG h
秋 CQ h
仲 LT m
伊 LT m
宫 ZX h
宁 CQ h
仇 SH h
栾 CQ h
暴 SH h
甘 XA h
钭 ZG h
厉 CQ h
戎 CQ h
祖 SH h
武 XA h
符 CQ h
刘 XA h
景 CQ h
詹 ZX h
束 ZG h
龙 LT m
叶 CQ h
幸 UN l
司 LT m
韶 LT m
郜 ZX h
黎 LT m
蓟 ZX h
薄 SH h
印 CQ h
宿 ZX h
白 LT m
怀 ZX h
蒲 XA h
邰 LT m
从 ZX h
鄂 CQ h
索 SH h
咸 LT m
籍 CQ h
赖 ZX h
卓 CQ h
蔺 ZG h
屠 LT m
蒙 XA h
池 ZG h
乔 LT m
阴 CQ h
郁 CQ h
胥 CQ h
能 ZX h
苍 LT m
双 XA h
闻 CQ h
莘 XA h
党 XA h
翟 LT m
谭 ZX h
贡 CQ h
劳 HX h
逄 SH h
姬 LT m
申 ZX h
扶 XA h
堵 CQ h
冉 LT m
宰 CQ h
郦 XA h
雍 ZX h
郤 CQ h
璩 UN l
桑 LT m
桂 QN h
濮 LT m
牛 ZX h
寿 CQ h
通 CQ h
边 SH h
扈 XA h
燕 SH h
冀 ZX h
郏 ZX h
浦 CQ h
尚 XA h
农 ZX h
温 ZX h
别 ZX l
庄 CQ h
晏 LT m
柴 CQ h
瞿 SH h
阎 ZX h
充 ZX h
慕 NB h
连 LT m
茹 NB h
习 SH h
宦 ZG h
艾 XA h
鱼 CQ h
容 LT m
向 CQ h
古 ZX h
易 CQ h
慎 CQ h
戈 XA h
廖 SH h
庾 LT m
终 LT m
暨 SH h
居 CQ h
衡 SH h
步 CQ h
都 CQ h
耿 SH h
满 ZX h
弘 CQ h
匡 CQ h
国 XA h
文 ZX h
寇 ZX h
广 LT m
禄 SH h
阙 CQ h
东 LT m
欧 CQ h
殳 LT m
沃 SH h
利 LT m
蔚 NB l
越 XA h
夔 ZX h
隆 CQ h
师 LT m
巩 ZX h
厍 NB l
聂 CQ h
晁 CQ h
勾 LT m
敖 LT m
融 LT m
冷 LT m
訾 LT m
辛 XA h
阚 CQ h
那 SH h
简 CQ h
饶 ZG h
空 SH h
曾 XA h
毋 ZG h
沙 LT m
乜 CQ h
养 CQ h
鞠 LT m
须 LT m
丰 ZX h
巢 LT m
关 XA h
蒯 SH h
相 XA h
查 CQ h
后 LT m
荆 ZX h
红 ZX h
游 CQ h
竺 SH h
权 SH h
逯 ZG h
盖 ZG h
益 LT m
桓 LT m
公 CQ h
万俟 NB h
司马 ZX m
上官 CQ h
欧阳 ZG h
夏侯 ZG h
诸葛 XA h
闻人 CQ h
东方 LT m
赫连 LJ h
皇甫 CQ h
尉迟 NB h
公羊 CQ h
澹台 CQ h
公冶 CQ h
宗政 HX h
濮阳 CQ h
淳于 ZX h
单于 HX h
太叔 CQ h
申屠 ZX h
公孙 LT m
仲孙 CQ h
轩辕 LT m
令狐 CQ h
钟离 CQ h
宇文 NB h
长孙 NB h
慕容 SG h
鲜于 ZX h
闾丘 CQ h
司徒 LT m
司空 ZX h
亓官 ZX h
司寇 ZX h
仉 CQ h
督 CQ h
子车 CQ h
颛孙 CQ h
端木 CQ h
巫马 ZX h
公西 CQ h
漆雕 CQ h
乐正 ZX h
壤驷 ZX h
公良 CQ h
拓跋 NB h
夹谷 SO l
宰父 ZX h
谷梁 CQ h
晋 ZX h
楚 ZX h
闫 ZX h
法 ZG h
汝 CQ h
鄢 CQ h
涂 XA h
钦 HA h
段干 ZG l
百里 CQ h
东郭 ZX h
南门 SH h
呼延 HA h
归 ZX l
海 CQ h
羊舌 CQ h
微生 ZX h
岳 LT m
帅 LJ h
缑 ZX h
亢 ZX h
况 SG h
后 LT m
有 LT m
琴 CQ h
梁丘 CQ h
左丘 CQ h
东门 CQ h
西门 CQ h
商 LT m
牟 CQ h
佘 UN l
佴 UN l
伯 LT m
赏 CQ h
南宫 CQ h
墨 SH h
哈 UN l
谯 ZX h
笪 UN l
年 ZX h
爱 TA h
阳 ZX h
佟 SH h
第五 HX h
言 CQ h
福 CQ h
"""

# ---------- era reference table ----------
# code : (中文 label, 英文 label for the wallpaper line, approx_year)
ERA_TABLE = {
    "LT": ("上古传说", "LEGENDARY ERA",     -2600),
    "XA": ("夏",       "XIA DYNASTY",       -1800),
    "SH": ("商",       "SHANG DYNASTY",     -1300),
    "SM": ("商末周初", "LATE SHANG / EARLY ZHOU", -1050),
    "ZX": ("西周",     "WESTERN ZHOU",      -950),
    "CQ": ("春秋",     "SPRING AND AUTUMN", -600),
    "ZG": ("战国",     "WARRING STATES",    -350),
    "QN": ("秦",       "QIN DYNASTY",       -215),
    "HX": ("西汉",     "WESTERN HAN",       -150),
    "HA": ("汉",       "HAN DYNASTY",       -50),
    "HD": ("东汉",     "EASTERN HAN",        100),
    "SG": ("三国",     "THREE KINGDOMS",     240),
    "LJ": ("两晋",     "JIN DYNASTY",        320),
    "NB": ("南北朝",   "NORTHERN & SOUTHERN", 480),
    "SU": ("隋",       "SUI DYNASTY",        610),
    "TA": ("唐",       "TANG DYNASTY",       750),
    "WD": ("五代十国", "FIVE DYNASTIES",     930),
    "BS": ("北宋",     "NORTHERN SONG",     1050),
    "SO": ("宋",       "SONG / JIN DYNASTY", 1120),
    "NS": ("南宋",     "SOUTHERN SONG",     1200),
    "YU": ("元",       "YUAN DYNASTY",      1300),
    "MI": ("明",       "MING DYNASTY",      1500),
    "QG": ("清",       "QING DYNASTY",      1750),
    "XD": ("近现代",   "MODERN ERA",        1900),
    "UN": ("不详",     None,                 None),
}

# surnames whose origin account in the sources offers several conflicting
# lineages, or where the era had to be inferred from a person's floruit
MULTI_ORIGIN = {"王","李","吴","何","胡","田","陆","翁","黄","杜","程","仲","伊",
                "侯","山","宗","钮","储","曲","家","别"}

# polyphones / readings that a reviewer must confirm before printing
POLYPHONE_NOTES = {
 "万俟": ("MO QI",   "姓氏专读 Mòqí，绝不读 WAN SI"),
 "单":   ("SHAN",    "姓氏读 Shàn，不读 dān"),
 "单于": ("CHAN YU", "读 Chányú，不读 SHAN YU / DAN YU"),
 "解":   ("XIE",     "姓氏读 Xiè，不读 jiě"),
 "仇":   ("QIU",     "姓氏读 Qiú，不读 chóu"),
 "尉迟": ("YU CHI",  "读 Yùchí，不读 WEI CHI"),
 "长孙": ("ZHANG SUN","读 Zhǎngsūn，不读 CHANG SUN"),
 "乐":   ("YUE",     "姓氏读 Yuè，不读 lè"),
 "乐正": ("YUE ZHENG","读 Yuèzhèng"),
 "查":   ("ZHA",     "姓氏读 Zhā，不读 chá"),
 "曾":   ("ZENG",    "姓氏读 Zēng，不读 céng"),
 "缪":   ("MIAO",    "姓氏读 Miào，不读 móu/mù"),
 "盖":   ("GE",      "姓氏读 Gě，不读 gài"),
 "燕":   ("YAN",     "姓氏读 Yān"),
 "华":   ("HUA",     "姓氏读 Huà，不读 huá（作姓读去声）"),
 "任":   ("REN",     "姓氏读 Rén，不读 rèn"),
 "能":   ("NAI",     "姓氏读 Nài，不读 néng"),
 "郗":   ("XI",      "姓氏读 Xī（又读 Chī）"),
 "阚":   ("KAN",     "姓氏读 Kàn"),
 "乜":   ("NIE",     "姓氏读 Niè，不读 miē"),
 "相":   ("XIANG",   "姓氏读 Xiàng"),
 "缑":   ("GOU",     "读 Gōu"),
 "隗":   ("KUI",     "姓氏 Kuí / Wěi 两读并存；S2、S7 均以 Kuí 为主，S4 以 Wěi 为主 —— 需确认"),
 "宓":   ("FU",      "姓氏 Fú / Mì 两读并存；S2、S4 以 Fú 为主 —— 需确认"),
 "贲":   ("FEI",     "姓氏 Féi / Bēn 两读并存；S2、S4、S7 均以 Féi 为主 —— 需确认"),
 "柏":   ("BAI",     "姓氏 Bǎi / Bó 两读并存；S2 标 Bǎi(Bó) —— 需确认"),
 "那":   ("NA",      "姓氏 Nā / Nuó 两读并存；S2 标 Nā(Nuó)，S4 以 Nuó 为主 —— 需确认"),
 "蔚":   ("WEI",     "姓氏 Wèi / Yù 两读并存；S2、S7 标 Wèi，S4 注 Yù —— 需确认"),
 "亢":   ("KANG",    "姓氏读 Kàng；S2 表内误标 Kòng（应为 Kàng）"),
 "佴":   ("NAI",     "姓氏 Nài / Mì 两读并存；S4 以 Nài 为主"),
 "翟":   ("ZHAI",    "姓氏 Zhái / Dí 两读并存；S4 以 Zhái 为主"),
 "莘":   ("SHEN",    "姓氏读 Shēn"),
 "吕":   ("LV",      "ü 的转写需拍板：LV（大陆常见）/ LU / LYU（护照标准）；闾丘同"),
 "闾丘": ("LV QIU",  "ü 的转写需拍板：LV / LU / LYU"),
 "郤":   ("XI",      "姓氏读 Xì（中华書局本作 郤；S2 作 却 并注 Xì）"),
 "谯":   ("QIAO",    "读 Qiáo"),
 "句/勾": ("GOU",    "勾姓读 Gōu"),
}
