#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字形线 · A 线①「字体演变」生成器（v2 · 2026-10-03 改为模板驱动）

⚠️⚠️ 版式**不在本脚本里**。唯一权威文件：
     02-商品/03-字形线/版式/模板-朝代-v9.html       （std 1920×1080）
     02-商品/03-字形线/版式/模板-朝代-v9-mac.html   （Mac 1920×1248）
   本脚本只做两件事：① 按朝代配置组装数据 ② 替换模板槽位。
   改版式 → 改模板；改内容 → 改下面 ERAS。

三联图（屏幕自左向右）：碑刻宋 | 毛笔 | 古文字
  展卷自右向左读 → 古文字 → 毛笔 → 碑刻宋（今文）

用法：
  python3 gen-evolution.py                 # 出全部配置齐全的期
  python3 gen-evolution.py shang zhou      # 只出指定期
  python3 gen-evolution.py --sync-mac      # 改了 std 模板后同步 Mac 模板（6 处差异）

输出：02-商品/05-承接站/样张/evolution-{slug}-{std,mac}.html
截图：shoot-evolution.sh（内部按 2× 渲染再缩，见 作品范式.md §九）
"""
import pathlib
import re
import sys

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '02-商品/05-承接站/样张'
TPL_DIR = ROOT / '02-商品/03-字形线/版式'
A = ROOT / '02-商品/02-素材'
F = A / '字体'
SEAL = A / '底纹/seal.png'

TPL = {'std': TPL_DIR / '模板-朝代-v9.html',
       'mac': TPL_DIR / '模板-朝代-v9-mac.html'}
SLOTS = ('tag', 'title', 'triple', 'quote', 'brand', 'era')
# ⚠️ EDITIONS 里的 `quote_cols` 一律按**阅读顺序**填写（第一句在前，如商＝['天命玄鸟','降而生商']）。
#    生成器输出时会 reversed() 再写入 DOM —— 因为 `.quote` 是 flex row（DOM 序＝屏幕自左向右），
#    而竖排题跋是**右起**（第一句贴最右）。直接按阅读顺序输出会把两列写反。
# 底纹是 <img> 的属性值，不能塞注释标记（属性里的注释会被当字面文本）→ 单独用正则换
# ⚠️⚠️ 正则**必须限定在 </style> 之后的正文**里跑：
#    模板头部的大注释里写了底纹 <img> 的示例（带真实文件名），无条件全文件替换会
#    **先命中注释里的那一处**，正文里的真底纹层原封不动 → 所有期次都退化成模板默认底纹。
#    2026-10-04 实测症状：周的凤凰被换成商的玄鸟（商因默认值恰好就是玄鸟，毫无察觉）。
TEX_RE = re.compile(r'(<img class="texture" src=")[^"]*(")')
SLOT_RE = {k: re.compile(r'<!--S:%s-->(.*?)<!--E:%s-->' % (k, k), re.S) for k in SLOTS}

# Mac 模板 = std 模板改这 6 处（与 B 线同一套办法，防止两份 CSS 各改各的漂移）
MAC_DELTAS = [
    ('html,body{width:1920px;height:1080px', 'html,body{width:1920px;height:1248px'),
    ('.stage{position:relative;width:1920px;height:1080px',
     '.stage{position:relative;width:1920px;height:1248px'),
    ('.title-box{position:absolute;left:960px;top:262px',
     '.title-box{position:absolute;left:960px;top:343px'),
    ('.triple{position:absolute;left:960px;top:371px',
     '.triple{position:absolute;left:960px;top:455px'),
    ('.colophon{position:absolute;left:210px;bottom:140px',
     '.colophon{position:absolute;left:210px;bottom:130px'),
    ('.brand-block{position:absolute;left:960px;bottom:140px',
     '.brand-block{position:absolute;left:960px;bottom:130px'),
    ('.era{position:absolute;left:960px;top:746px', '.era{position:absolute;left:960px;top:830px'),
]
MAC_HEAD = """朝代线（A 线「字体演变」）版式模板 v9 · Mac 版（1920×1248，截图 2× 得 3840×2496）

  ⚠️ 本文件由 模板-朝代-v9.html 自动同步生成（gen-evolution.py --sync-mac），
     **只差下列 6 处**；改版式请改 std 版后重跑同步，不要手改本文件。
       画幅 1080 → 1248｜画心标题 262 → 343｜三联字区 371 → 455｜字下行 746 → 830
       落款两区 距底 140 → 130（左下角 + 正下中）"""

# ── 各期配置 ───────────────────────────────────────────────
# ancient.kind: 'img'（手绘 SVG，仅商周有）或 'font'（字体渲染）
# ancient = None → **两格版**：只有「今文·碑刻宋 | 今文·毛笔」，不留古文字格。
#   2026-10-04 用户定：14 朝做两格、商周保持三格（古文字 SVG 仅商周有），
#   这样 16 朝壁纸可齐。两格版 `.triple` 仍是 flex 居中，自动对称，不需改坐标。
# texture = None → 该期尚无自有底纹（A 线铁律：每期须有自己底纹才允许上架）→
#   生成时把模板里的 .texture 底纹层整条删掉，输出「无底纹样张」。
# tex_pos = 底纹在**成品里**的垂直取景（CSS object-position，默认不写＝center 50%）。
#   ⭐ 商周专用（2026-10-05 用户定：商周「切回原版，只做原版大小的稍微下移」）。
#     底纹图 1536×1024 用 object-fit:cover 铺进 1920×1080 ⇒ 上下各被裁 100px、可见源图
#     y∈[80,944]；object-position 只挪**可见窗口**、不改图本身（mask 渐隐跟着元素不动）。
#     Y 从 50% 往 0% 走＝底纹内容**下移**，极限 50%→0% ＝下移 100px（成品坐标）。
# tag   = 左上角系列标文案 ⭐ 2026-10-05 用户定：一律「上 下 五 千 年 · 朝代名」，
#         与模板母版口径一致（不要再写成「字 体 演 变 · X」）
# brand = 正下中品牌行（中文产品一律「第七境™」）
# 14 朝「一字一格」格子下的两行标注（用户 2026-10-04 要求把字体写上）。
#   母版语义：cap 写**类别**、sub 写**字体**（商＝「今文 · 碑刻宋」/「思源宋体」）。
#   14 朝只有一种字体，故 cap 一律「今文 · 宋体」、sub 一律「思源宋体」。
CELL_CAP, CELL_SUB = '今文 · 宋体', '思源宋体'
# 「一字一格」里若某一格改用毛笔，标注跟着换（sub 用该期的 brush_sub）：
BRUSH_CAP = '今文 · 毛笔'
# ⭐ char_fonts：逐格指定字体（2026-10-05 用户定，三皇五帝首用）。
#   字符串或列表，长度须与 char 相同；'s' = 今文宋体（.song-char），'b' = 毛笔（.brush-char）。
#   不写＝全宋体。
#   ⭐ 分配规则（用户 2026-10-05）：**一字宋、一字毛，逐字交替（ABAB…）**——
#       2 字 → 'sb'      4 字 → 'sbsb'      5 字 → 'sbsbs'
#       （首个字一律宋体；觉醒年代 4 字不参与，保持全宋体）
#   ⇒ 这样多字朝代也有「两体对比」，主标题「字形演变·三千年」就不必改了。
# 单字朝代补「朝」凑成两格（用户 2026-10-04 定）；商周不受影响（仍是「今文宋｜毛笔｜古文字」三格）
ERAS = {
    'shang': dict(
        name='商', layer='商', texture=A / '底纹/xuanniao-raw.png',
        tex_pos='center 0%',   # 原版图 + 下移 100px（极限）⇒ 玄鸟质心落到成品 38%
                               # （未下移是 28.9%，七朝档位 37.5%–50.6%）
        char='商', hint='右 起 展 卷 · 自 卜 辞 至 今 文',
        tag='上 下 五 千 年 · 商', brand='第七境™',
        ancient=dict(kind='img', src=A / '古文字/jiaguwen-shang.svg',
                     cap='甲骨文', sub='约前十三世纪 · 契刻', size=246),
        brush_sub='马善政楷书',
        quote_src='《诗经·商颂》', quote_cols=['天命玄鸟', '降而生商'],
        en='SHANG DYNASTY', years='c. 1600 – 1046 BC',
    ),
    'zhou': dict(
        name='周', layer='周', texture=A / '底纹/phoenix-full.png',
        tex_pos='center 35%',  # 原版图（09-29 老脚本平铺云版）+ 下移 30px
                               # （未下移质心已在 45.2%，只做「稍微」对齐 ⇒ 48%）
        char='周', hint='右 起 展 卷 · 自 吉 金 至 今 文',
        tag='上 下 五 千 年 · 周', brand='第七境™',
        ancient=dict(kind='img', src=A / '古文字/jinwen-zhou-31_E60B.svg',
                     cap='金文', sub='西周 · 青铜器铭文', size=274),
        brush_sub='马善政楷书',
        quote_src='《诗经·大雅·卷阿》', quote_cols=['凤凰鸣矣', '于彼高冈'],
        en='ZHOU DYNASTY', years='1046 – 256 BC',
    ),
    # ── 以下 14 期为「一字一格」版（无古文字格、暂无自有底纹）──────────
    #   字面有几个字就给几格、一格一个字（2026-10-04 用户定）；字体统一思源宋体 Black，
    #   不再做碑刻宋/毛笔两体对比。单字朝代补「朝」凑成两个字（夏→夏朝…清→清朝）
    #   ⇒ 只剩 三国(2)、三皇五帝/五代十国/觉醒年代(4)、两晋南北朝(5) 是多字。
    #   题跋＝线上朝代页同一份金句（11-运营/朝代页流水线/eras.py 的 verse/src），站内外一致。
    'sanhuang': dict(
        name='三皇五帝', texture=A / '底纹/longma-full.png', char='三皇五帝',
        char_fonts='sbsb',      # 三(宋) 皇(毛) 五(宋) 帝(毛)
        hint='一 字 一 格 · 宋 体 ｜ 毛 笔', tag='上 下 五 千 年 · 三皇五帝', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='《周易·贲卦》', quote_cols=['观乎人文', '以化成天下'],
        en='LEGENDARY ERA', years='c. 2700 BC and earlier',
    ),
    'xia': dict(
        name='夏', texture=A / '底纹/linggui-full.png', char='夏',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 夏', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='《尚书·洪范》', quote_cols=['天乃锡禹', '洪范九畴'],
        en='XIA DYNASTY', years='c. 2070 – 1600 BC',
    ),
    'qin': dict(
        name='秦', texture=A / '底纹/heilong-full.png', char='秦',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 秦', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='杜牧《阿房宫赋》', quote_cols=['六王毕', '四海一'],
        en='QIN DYNASTY', years='221 – 206 BC',
    ),
    'han': dict(
        name='汉', texture=A / '底纹/baihu-full.png', char='汉',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 汉', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='《汉书·陈汤传》', quote_cols=['明犯强汉者', '虽远必诛'],
        en='HAN DYNASTY', years='202 BC – AD 220',
    ),
    'sanguo': dict(
        name='三国', texture=A / '底纹/luoshen-full.png', char='三国',
        char_fonts='sb',        # 三(宋) 国(毛)
        hint='一 字 一 格 · 宋 体 ｜ 毛 笔', tag='上 下 五 千 年 · 三国', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='杨慎《临江仙》', quote_cols=['青山依旧在', '几度夕阳红'],
        en='THREE KINGDOMS', years='AD 220 – 280',
    ),
    'jin': dict(
        name='两晋南北朝', texture=A / '底纹/baie-full.png', char='两晋南北朝',
        char_fonts='sbsbs',     # 两(宋) 晋(毛) 南(宋) 北(毛) 朝(宋)
        hint='一 字 一 格 · 宋 体 ｜ 毛 笔', tag='上 下 五 千 年 · 两晋南北朝', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='王羲之《兰亭集序》', quote_cols=['仰观宇宙', '俯察品类'],
        en='JIN DYNASTY', years='AD 265 – 589',
    ),
    'sui': dict(
        name='隋', texture=A / '底纹/longge-full.png',
        # 原位减云底纹（龙舸）；几何修正（zoom 0.98 / 上移 76px）已做进底纹本身，
        # 所以这里**不设 tex_pos**（取景＝默认居中）——见 底纹-朝代/README.md §十二
        char='隋',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 隋', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='皮日休《汴河怀古》', quote_cols=['隋亡为此河', '千里赖通波'],
        en='SUI DYNASTY', years='AD 581 – 618',
    ),
    'tang': dict(
        name='唐', texture=A / '底纹/gongshi-full.png',
        tex_pos='center 5%',    # 原位减云底纹（贡狮）；下移 90px ⇒ 狮顶落到成品 y≈40
                               # （换算 Y=50−D/2，D=成品下移 px，上限 100，同 §九）
        char='唐',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 唐', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='王维《早朝大明宫》', quote_cols=['九天阊阖', '万国衣冠'],
        en='TANG DYNASTY', years='AD 618 – 907',
    ),
    'wudai': dict(
        name='五代十国', texture=A / '底纹/mojie-full.png', char='五代十国',
        char_fonts='sbsb',      # 五(宋) 代(毛) 十(宋) 国(毛)
        hint='一 字 一 格 · 宋 体 ｜ 毛 笔', tag='上 下 五 千 年 · 五代十国', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='李煜《虞美人》', quote_cols=['春花秋月', '往事知多少'],
        en='FIVE DYNASTIES', years='AD 907 – 960',
    ),
    'song': dict(
        name='宋', texture=A / '底纹/ruihe-full.png',
        tex_pos='center 9%',    # 原位减云底纹（瑞鹤）；下移 81px ⇒ 鹤头落到成品 y≈40
        char='宋',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 宋', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='张载·横渠四句', quote_cols=['为天地立心', '为生民立命'],
        en='SONG DYNASTY', years='AD 960 – 1279',
    ),
    'yuan': dict(
        name='元', texture=A / '底纹/feixue-full.png',   # 原位减云（六月飞雪）
        # 金句「不分好歹／错勘贤愚」出自《窦娥冤》【滚绣球】，是**反祥瑞**（骂天地不公）
        # ⇒ 不配正面瑞兽，改配**六月飞雪**（窦娥三桩誓愿之一），同源同篇、雪＝清白证冤。
        # 2026-10-09 用户拍板。底纹合成见 gen-texture-full.py 的 'feixue'（含 shift=225）。
        char='元',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 元', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='关汉卿《窦娥冤》', quote_cols=['不分好歹', '错勘贤愚'],
        en='YUAN DYNASTY', years='AD 1271 – 1368',
    ),
    'ming': dict(
        name='明', texture=A / '底纹/qilin-full.png',
        tex_pos='center 13%',   # 原位减云底纹（麒麟）；下移 75px ⇒ 麟角落到成品 y≈40
        char='明',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 明', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='王守仁《传习录》', quote_cols=['心外无物', '心外无理'],
        en='MING DYNASTY', years='AD 1368 – 1644',
    ),
    'qing': dict(
        name='清', texture=A / '底纹/luduan-full.png',
        # ⭐ 2026-10-09 用户：原「风雷行龙」的**龙朝向反了**（龙头朝右外侧飞出），
        #   在「镜像」与「换瑞兽」之间选了**换瑞兽 ⇒ 甪端**（清代宫廷瑞兽，
        #   「明君在位、明达方外幽远之事则奉书而至」↔ 金句「不拘一格降人才」的求贤之意）。
        #   原底纹 fenglong-full.png / -raw.png **保留存档不删**（见 §十二 实录）。
        #   甪端主体天然落在净空内（bbox y189–571）⇒ 不设 tex_pos、不需几何步。
        char='清',        # 单字朝代＝同一字两种字体（碑刻宋｜毛笔），不加「朝」
        hint='一 字 二 体 · 碑 刻 与 毛 笔', tag='上 下 五 千 年 · 清', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        quote_src='龚自珍《己亥杂诗》', quote_cols=['我劝天公', '不拘一格'],
        en='QING DYNASTY', years='AD 1644 – 1912',
    ),
    'juexing': dict(
        name='觉醒年代', texture=A / '底纹/qianzi-full.png',   # 原位减云（铅字／字模托盘）
        # ⭐ 2026-10-09 用户拍板：**铅字／报刊肌理**。觉醒年代＝字形演变的近代转折
        #   （碑刻→毛笔→**铅字**），比「萤火／微光」更紧扣主题、也避开瑞兽体系。
        #   ⚠️ 构图只能走「局部主体 + 大留白」：中间是「觉醒年代」4 个方块大字，
        #      满幅方格肌理（第一版做法）会与它正面打架。
        #   底纹合成见 gen-texture-full.py 的 'qianzi'（k=0.45 + zoom0.97/shift159）。
        char='觉醒年代',
        hint='一 字 一 格 · 今 文 宋 体', tag='上 下 五 千 年 · 觉醒年代', brand='第七境™',
        ancient=None, brush_sub='马善政楷书',
        # qsize：该页题跋字号（默认 54）。本页第一列 10 字，54px 时＝1026px 会戳出画外，
        #   降到 48px → 912px，底边 y974，仍在母版 9 字列（底 985）的范围内。
        #   2026-10-04 用户：三列太碎，「折成两行就行」。
        # 2026-10-04 用户三改：三列太碎→两列；随后「第一列不要太长，这几个字去第二列」
        #   ⇒ 定稿 `愿中国青年`(6) / `都摆脱冷气只是向上走`(10)。第二列 10 字需 qsize=48。
        quote_src='鲁迅《热风》', quote_cols=['有一分热', '发一分光'],
        en='THE AWAKENING', years='AD 1840 – 1949',
    ),
}


def vcol(text, fs=None):
    """竖排一列（自上而下逐字）。fs＝该列字号，覆盖模板 .vc span 的 54px。

    ⚠️ 必须内联在 <span> 上：`.vc span{font-size:54px}` 是显式声明，
       写在 .vc 容器上的 font-size 会被它盖掉（继承 < 显式）。
    """
    st = f' style="font-size:{fs}px"' if fs else ''
    return '<div class="vc">' + ''.join(f'<span{st}>{c}</span>' for c in text) + '</div>'


def vsrc(text):
    """出处竖排，书名号旋转 90°"""
    out = []
    for c in text:
        out.append('<span class="rot">《</span>' if c == '《'
                   else '<span class="rot">》</span>' if c == '》'
                   else f'<span>{c}</span>')
    return ''.join(out)


def sync_mac():
    s = TPL['std'].read_text(encoding='utf-8')
    for a, b in MAC_DELTAS:
        if s.count(a) != 1:
            raise SystemExit(f'同步失败：std 模板里找不到唯一锚点 {a!r}')
        s = s.replace(a, b)
    old = '朝代线（A 线「字体演变」）版式模板 v9 · 唯一权威文件'
    if old not in s:
        raise SystemExit('同步失败：std 模板头部标题已改，请同步更新 MAC_HEAD')
    TPL['mac'].write_text(s.replace(old, MAC_HEAD, 1), encoding='utf-8')
    print(f'  ✓ 已同步 → {TPL["mac"].name}（6 处差异）')


def build(slug, spec):
    e = ERAS[slug]
    an = e.get('ancient')          # None = 两格版（今文·碑刻宋 | 今文·毛笔）

    # ⚠️ 多字朝代（三皇五帝/两晋南北朝/五代十国/觉醒年代/三国）同排写出，必须做两件事：
    #    ① `white-space:nowrap` —— .cell 只有 290px 宽，不写会直接换行；
    #    ② 按字数缩字号 —— 目标整幅宽 ≈300px（略宽于 cell，但仍在格子间距内），
    #       否则四/五个 262px 的字会横贯画面并压到隔壁格上。单字保持母版 262px 不变。
    #    2026-10-04 用户要求：多字朝代写全名，字小一点。
    _n = len(e['char'])
    _gs = f' style="font-size:{max(48, round(300 / _n))}px;white-space:nowrap"' if _n > 1 else ''
    song_cell = f"""    <div class="cell">
      <div class="song-char"{_gs}>{e['char']}</div>
      <div class="cap">今文 · 碑刻宋</div>
      <div class="sub">思源宋体</div>
    </div>"""
    brush_cell = f"""    <div class="cell">
      <div class="brush-char"{_gs}>{e['char']}</div>
      <div class="cinnabar-dot"></div>
      <div class="cap">今文 · 毛笔</div>
      <div class="sub">{e['brush_sub']}</div>
    </div>"""

    if an is None:
        # ── 「一字一格」版：字面有几个字就给几格，一格一个字 ──
        # 2026-10-04 用户定：不再做「碑刻宋 vs 毛笔」两体对比，字体统一用现代的
        # 思源宋体 Black。`.triple` 是 `left:960px + translateX(-50%)` 的 flex 居中盒，
        # 格子数变化后自动对称回画面正中，**不需要改任何坐标**。
        #    ≤3 字：保持母版尺寸 cell 290 / 字 262 / 分隔线 200
        #    ≥4 字：按可用宽缩放。可用宽上限 1100px —— 算上空口再宽就会压到右上角那列
        #           竖排题跋。可用宽 = 格子总宽 + gap 总数 + 分隔线总数，
        #           其中 gap 由模板写死 40px（在 .triple 上，槽位替换不到它）。
        _cs = e['char']
        _n = len(_cs)
        if _n == 1:
            # ── 单字朝代：**同一个字两种字体**（2026-10-04 用户终稿）──
            #   「单字朝代做两种字体的单字，不要朝字」——即回到碑刻宋｜毛笔两体，
            #   与母版商周的前两格**完全同规格**（cell 290 / 字 262 / 分隔线 200 /
            #   朱砂点落第二格）。之前「补『朝』凑两格」的做法作废。
            triple = f"""{song_cell}

    <div class="divider"></div>

{brush_cell}"""
        else:
            if _n <= 3:
                _fs, _cw, _dh = 262, 290, 200
                _cstyle = f'font-size:{_fs}px'
                _dmb = 48                    # 母版分隔线距格底
            else:
                # ⚠️ 可用宽上限 980px（2026-10-04 由 1100 收紧）：
                #    觉醒年代题跋折成 3 列后，题跋块左缘推到 x≈1486（2 列时是 x≈1548），
                #    1100 宽的画心右缘会压到那列出处上。980 → 右缘 1450，留 36px 呼吸。
                # ⚠️ 竖向重心：字号缩小后必须把行盒锁回母版高度 262px。`.triple` 是
                #    `align-items:flex-end` 底对齐盒 → 小字更靠上（用户 2026-10-04 指出
                #    「南北朝偏高」）。line-height:262px 用对称半行距把墨迹中心拉回母版位置，
                #    同时格子总高回到母版 334px，整条画心的上下边界也就与母版重合。
                _tw = 980
                _frame = 40 * (2 * _n - 2) + (_n - 1)
                _cw = (_tw - _frame) // _n
                _fs = _cw
                _dh = round(_fs * 0.76)      # 分隔线高度跟着字走（母版 200/262 ≈ .76）
                _cstyle = f'font-size:{_fs}px;line-height:262px'
                # 分隔线：保持「线心」的母版绝对位置（母版线心距格底 200/2+48 = 148px）
                _dmb = 148 - _dh // 2
            _mid = _n // 2                   # 朱砂点睛落在画心正中那一格
            # 朱砂点：母版关系是「点右缘≈墨迹右缘、点顶在墨迹顶上 17px 处」（right 26 / top 2）。
            # 字号缩了以后墨迹往格子中心收，若仍用 26/2 会飘到字外或悬在行上方
            # → 按墨迹实际位置反算（墨迹宽高按 0.9 / 0.86 em 估）。≤3 字走模板默认值，不动。
            _dot_r = max(4, (_cw - round(_fs * 0.9)) // 2 - 2) if _n > 3 else 26
            _dot_t = 2 + (262 - _fs) // 2 if _n > 3 else 2
            _fm = e.get('char_fonts')        # None = 全宋体；否则逐格 's' / 'b'
            if _fm is not None:
                assert len(_fm) == _n, f'{slug}: char_fonts 长度({len(_fm)}) ≠ 字数({_n})'
            _cells = []
            for _i, _c in enumerate(_cs):
                _dot = (f'<div class="cinnabar-dot" style="right:{_dot_r}px;top:{_dot_t}px"></div>\n      '
                        if _i == _mid else '')
                # 该格用毛笔 → 换 class（.brush-char）与标注；字号/行高沿用同一套 _cstyle
                _isb = bool(_fm) and _fm[_i] == 'b'
                _cls = 'brush-char' if _isb else 'song-char'
                _cap = BRUSH_CAP if _isb else CELL_CAP
                _sub = e['brush_sub'] if _isb else CELL_SUB
                _cells.append(
                    f'    <div class="cell" style="width:{_cw}px">\n'
                    f'      {_dot}<div class="{_cls}" style="{_cstyle}">{_c}</div>\n'
                    f'      <div class="cap" style="white-space:nowrap">{_cap}</div>'
                    f'<div class="sub" style="white-space:nowrap">{_sub}</div>\n'
                    f'    </div>')
            triple = (f'\n\n    <div class="divider" style="height:{_dh}px;'
                      f'margin-bottom:{_dmb}px"></div>\n\n').join(_cells)
    else:
        # ⚠️ 古文字尺寸是**每期不同**的（商 246 / 周 274），必须内联写上去：
        #    模板里的 .oracle-glyph / .oracle-font 只是兜底默认值，内联 style 优先级更高。
        #    2026-10-04 之前的写法把尺寸算出来了却没落到 HTML 上 → 周的金文被按 246 渲染
        #    （比母版小 11%、笔画显细），与母版比对时只有「金文格」一格差。
        if an['kind'] == 'img':
            sz = f' style="width:{an["size"]}px;height:{an["size"]}px"'
            ancient = (f'<div class="oracle-box"><img class="oracle-glyph" '
                       f'src="file://{an["src"]}"{sz}></div>')
        elif an.get('family'):
            # 直接用一个已在页面加载的字体族（如明·宋体字走 webfont 'Noto Serif SC'）
            ancient = (f'<div class="oracle-box"><div class="oracle-font" '
                       f'style="font-family:\'{an["family"]}\',serif;font-weight:400;'
                       f'font-size:{an["size"]}px">'
                       f'{an.get("char", e["char"])}</div></div>')
        else:
            if not pathlib.Path(an['font']).exists():
                print(f'  ✗ {slug}: 缺古文字字体 {pathlib.Path(an["font"]).name}（跳过）')
                return None
            ancient = (f'<div class="oracle-box"><div class="oracle-font" '
                       f'style="font-size:{an["size"]}px">'
                       f'{an.get("char", e["char"])}</div></div>')
        triple = f"""
{song_cell}

    <div class="divider"></div>

{brush_cell}

    <div class="divider"></div>

    <div class="cell">
      {ancient}
      <div class="cap">{an['cap']}</div>
      <div class="sub">{an['sub']}</div>
    </div>"""

    # 品牌行：拉丁用 .brand-en（Georgia 大写）／中文用 .brand-cn（毛笔体）
    core = e['brand'][:-1] if e['brand'].endswith('™') else e['brand']
    cls = 'brand-en' if core[:1].isascii() and core[:1].isalpha() else 'brand-cn'
    tm = '<span class="tm">™</span>' if e['brand'].endswith('™') else ''
    brand = f'<div class="{cls}">{core}{tm}</div>'

    # 题跋折列：竖排一列最多 9 字（54px × line-height 1.9 ≈ 102.6px/字 → 923px，
    # 自 y62 起算底到 985，正好不越画外）。超长就从中对半折成两列。
    # 2026-10-04 用户指出「觉醒年代第一列太长，折行早一点」——原 10 字列＝1026px 会戳出画外。
    MAX_COL = 9
    qfs = e.get('qsize')          # 指定了该页字号就**不折列**（靠缩字号解决超长）
    cols = []
    for c in e['quote_cols']:
        if qfs is None and len(c) > MAX_COL:
            h = (len(c) + 1) // 2
            print(f'    ↳ 题跋折列：{c} → {c[:h]} / {c[h:]}')
            cols += [c[:h], c[h:]]
        else:
            cols.append(c)

    # 页内微调：**只在 14 朝样张里注入一段页内 CSS**，模板文件与商周母版逐字节不动
    #   （动模板＝主题模版变更，且会让已完成的商周正式成品与宣传片终态对齐失效）。
    #
    # ① 落款位置（2026-10-04 三轮，最终＝**不动**）
    #    - 一轮：用户「落款高一点」→ 落款 +40，但只抬落款会让它与上方年代行只剩 7px
    #      （实测年代墨迹底 y809 / 落款墨迹顶 y817）⇒ 必须**与年代行同幅平移**。
    #    - 二轮：用户「印章和品牌名靠上了」→ 整组 +20。
    #    - 三轮：**用户澄清原话指的是「金句出处」，不是落款** → 落款回到母版、不再注入。
    #      现在 14 朝落款与商周**完全一致**（品牌名墨迹 y857–896）。
    #
    # ② 金句出处抬高（用户 2026-10-04：「落款高一点我说的是金句的出处」）
    #    模板 `.vc-src{align-self:flex-end}` 是把出处**吊在金句盒底部**（底边再低 12px）。
    #    母版商周题跋只有 4 字列（盒高 410），出处看着还在上部；14 朝题跋长（7–10 字列），
    #    盒底被顶到 y970+，出处就跟着掉到画面下缘（觉醒年代实测 y770–986）。
    #    ⇒ 改 `flex-start`：出处**贴题跋起点**（y62 起），与金句同起点。
    #      ⚠️ 这与母版商周的落位不同（母版＝底部），16 朝要统一须改模板走执行申请单。
    brand_extra = ''   # 出处＝母版做法（模板 flex-end，附在金句末尾），不再注入偏移

    vals = {
        'tag': e['tag'],
        'title': (f'<div class="triple-title">字 形 演 变 · 三 千 年</div>\n'
                  f'    <div class="triple-hint">{e["hint"]}</div>'),
        'triple': triple,
        # ⚠️ 金句列必须**逆序**写入 DOM —— `.quote` 是 flex row（按 DOM 顺序自左向右排），
        #    而中文竖排题跋是**右起**（第一句贴最右，如商「天命玄鸟」在右、"降而生商"在左）。
        #    所以 EDITIONS 里的 quote_cols 按**阅读顺序**（第一句在前）填写，
        #    这里 reversed() 落到 DOM 上才得到右起版式。
        #    2026-10-04 用户实测指出：曾按阅读顺序直接输出 → 最右列成了第二句（顺序反了）。
        'quote': '<div class="vc src">' + vsrc(e['quote_src']) + '</div>\n    ' + \
                 '\n    '.join(vcol(c, qfs) for c in reversed(cols)),
        'brand': brand_extra + brand + '\n    <div class="brand-url">www.theseventhrealm.com</div>',
        'era': f'<div class="en">{e["en"]}</div><div class="years">{e["years"]}</div>',
    }
    html = TPL[spec].read_text(encoding='utf-8')
    # 只在 </style> 之后的正文里换底纹 —— 头部注释里有同名标签的示例文本，全文件替换会先命中它
    head, sep, body = html.partition('</style>')
    if not sep:
        raise SystemExit('模板缺少 </style> —— 无法定位正文')
    if e.get('texture'):
        # tex_pos：只挪底纹的可见窗口（object-position），图本身与 mask 渐隐都不动
        _extra = f' style="object-position:{e["tex_pos"]}"' if e.get('tex_pos') else ''
        body, n = TEX_RE.subn(lambda m: m.group(1) + 'file://' + str(e['texture']) + m.group(2) + _extra,
                              body, count=1)
    else:
        # 该期尚无自有底纹 → 把底纹层整条删掉（不留下空 src，避免出碎图占位）
        body, n = re.subn(r'[ \t]*<img class="texture"[^>]*>\n?', '', body, count=1)
    if n != 1:
        raise SystemExit('正文里未找到 .texture 底纹层 —— 模板可能被改坏')
    html = head + sep + body
    for k, v in vals.items():
        html, n = SLOT_RE[k].subn(lambda m, v=v: v, html, count=1)
        if n != 1:
            raise SystemExit(f'模板槽位 {k} 替换失败（命中 {n} 次）—— 模板可能被改坏')
    out = OUT / f'evolution-{slug}-{spec}.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    print(f'  ✓ {out.name}')
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--sync-mac' in args:
        sync_mac()
        sys.exit(0)
    want = [a for a in args if not a.startswith('-')] or list(ERAS)
    for s in want:
        if s not in ERAS:
            print('未知期', s); continue
        print(f'[{ERAS[s]["name"]}]')
        for spec in ('std', 'mac'):
            build(s, spec)
