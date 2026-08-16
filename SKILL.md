---
name: hotspot-comic
description: 每日热点长漫画。检索当天有争议的新闻热点（默认：国内热点+国际科技热点+重要国家领导人事件，6-10 期），用 Agnes AI 生成黑白讽刺风格的多格漫画，拼接为纵向条漫，按日期归档，并生成一份微信兼容版 HTML 日报。用户说"今天的漫画/热点漫画/画个热点"时使用。
arguments:
  - name: date
    description: 制作日期（YYYY-MM-DD）；默认当天
    required: false
---

# 每日热点长漫画 (hotspot-comic)

把当天有争议的新闻热点，做成一张黑白讽刺风格的**纵向条漫**：顶部标题条 + 每格一张黑白漫画 + 格子下方台词条（台词由脚本排版，不依赖图片模型生成文字）。

## 工作流程

### 1. 检索当天热点
- 用新闻/网页搜索工具检索当天的争议性热点（`newssearch_search`、`websearch_search`，或 Google News RSS 兜底——见下方"RSS 兜底方案"）。
- **默认选题标准（用户可调整）**：
  - 国内热点事件：社会、民生、教育、商业、科技等领域有争议的国内事件。
  - 国际科技热点事件：AI、芯片、社交媒体、数据隐私、航天等科技领域的国际争议。
  - 其他领域的国际事件**除非是重要国家领导人**（总统/总理级），否则不选（娱乐八卦、普通名人、体育等一律排除）。
  - 总数 **6-10 期**。
- 优先选择：有明确对立双方、有戏剧冲突、讨论度高的事件。避免纯娱乐/纯技术/无争议内容。
- 一次检索多批热点（国内各搜一轮、国际科技各搜一轮），从中选出 6-10 个最适合作画的热点，逐期制作。每期开头向用户说明本期选题理由。
- 如果用户已指定热点或指定选题范围，跳过/按用户标准检索，直接用。
- 每期热点尽量分布在不同领域，避免一天内主题扎堆。

#### RSS 兜底方案（MCP 搜索不可用时）
当 `newssearch_search`/`websearch_search` 报 unknown tool 或失败时，改用 Google News RSS（纯 curl，无依赖）：
```
# 国内热点（中文）
curl -sL "https://news.google.com/rss/search?q=<URL编码关键词>&hl=zh-CN&gl=CN&ceid=CN:zh-Hans&when=3d"
# 国际/英文热点
curl -sL "https://news.google.com/rss/search?q=<URL编码关键词>&hl=en-US&gl=US&ceid=US:en&when=3d"
```
- 关键词示例：`%22controversy%22+OR+%22backlash%22`、`热点+争议+引发讨论`、`AI+controversy` 等。
- 用 python 正则解析 `<item>` 里的 `<title>`/`<pubDate>`/`<source>`。
- 若选题信息不足（只有标题无细节），优先换信息充分的选题，或补充检索该事件细节。

### 2. 设计分镜脚本（3-6 格）
按"起因 → 冲突 → 反转/结局"设计叙事。**格数由热点复杂度决定**，一般 4-6 格。
为每格写：
- `caption`：台词或旁白（一句，20 字以内，中文，讽刺或点睛）
- `prompt`：英文画面描述，**必须包含统一的黑白讽刺漫画风格前缀**（见下方风格规范）

### 3. 准备人物肖像（涉及真实人物时必须）
如果热点涉及**真实人物**（政客、名人、企业高管等），不能只靠文字描述生成形象——文生图画出的"特朗普/马斯克"往往只是"一个西装男"，不可辨识。必须：
1. **检索该人物的肖像照片**：先用 `imgsearch_search` 搜 "姓名 portrait / official portrait / face close-up"；若搜不到（空结果），用 Wikipedia 兜底——`curl "https://en.wikipedia.org/api/rest_v1/page/summary/<姓名>"` 解析返回的 `thumbnail.source` 或 `originalimage.source`。
2. **下载到工作目录** `ref/<人名>.jpg`（用 curl，存本地）。**下载后必须压缩到宽 ≤600px**（大图转 Data URI 可达 10MB，导致请求缓慢/失败）：
   ```
   python3 -c "from PIL import Image; im=Image.open('ref/<人名>.jpg').convert('RGB'); im=im.resize((600,round(im.height*600/im.width)),Image.LANCZOS); im.save('ref/<人名>.jpg',quality=88)"
   ```
   已有人名的直接复用，不重复下载。
3. 该人物出现的每个格子都用图生图，并在 prompt 开头写：`keep this exact man's face and distinctive hairstyle, ...`。
4. 已建立肖像库（命中直接复用，不重复下载）：`ref/trump_ref.jpg`（特朗普）、`ref/vance_ref.jpg`（万斯）、`ref/crenshaw_ref.jpg`（克伦肖）、`ref/owens_ref.jpg`（欧文斯）、`ref/kangana_ref.jpg`（康加娜）、`ref/sheeran_ref.jpg`（艾德·希兰）、`ref/maher_ref.jpg`（比尔·马厄）、`ref/aoc_ref.jpg`（AOC）、`ref/albanese_ref.jpg`（阿尔巴尼斯）、`ref/mullin_ref.jpg`（穆林）、`ref/hichilema_ref.jpg`（希奇莱马）、`ref/hankgreen_ref.jpg`（汉克·格林）、`ref/anderson_ref.jpg`（吉莲·安德森）、`ref/dong_ref.jpg`（董明珠）、`ref/leejm_ref.jpg`（李在明）、`ref/putin_ref.jpg`（普京）、`ref/takaichi_ref.jpg`（高市早苗）。

### 4. 逐格生成黑白漫画
每格调用 `agnes_gen.py image`。**涉及真实人物的格子必须传 `--image <肖像路径>`**：
```
python3 "<技能目录>/scripts/agnes_gen.py" image \
  --prompt "<风格前缀> keep this exact man's face and distinctive hairstyle, <本格画面描述>" \
  --image ref/trump_ref.jpg --ratio 4:3 --size 2K --out panel_1.png
```
不涉及真实人物的格子直接文生图（不带 `--image`）：
```
python3 "<技能目录>/scripts/agnes_gen.py" image \
  --prompt "<风格前缀> <本格画面描述>" \
  --ratio 4:3 --size 2K --out panel_2.png
```
- 统一 `--ratio 4:3`（横格，符合条漫阅读习惯）。
- 每格 prompt 都用**相同的风格前缀**保证整体画风一致。
- 如果某格画面崩坏（乱、缺人、出戏），重新生成该格，最多重试 1 次。
- 同一人物跨多格出现时，全部用同一张肖像参考，保证形象一致。

#### 4.1 并行生成（默认方式，提速一倍）
同一期或同一天的多格互相独立，**默认用 `gen_parallel.py` 并行生成**（2 个 Key 各跑一路，失败自动换 Key 重试），避免逐格排队：
```
python3 "<技能目录>/scripts/gen_parallel.py" \
  --task '{"prompt":"<风格前缀> <画面1>","out":"panel_1.png"}' \
  --task '{"prompt":"<风格前缀> keep this exact man's face, <画面2>","out":"panel_2.png","image":"ref/trump_ref.jpg"}' \
  --task '{"prompt":"<风格前缀> <画面3>","out":"panel_3.png"}' \
  --concurrency 2 --max-retries 3
```
- Key 自动从 `~/.config/agnes/key` 与 `~/.config/agnes/key-backup` 轮换；某格失败（如 502/503/限流）自动换下一个 Key 重试，直至 `--max-retries` 次。
- 并行数 `--concurrency` 默认 2（两个 Key）；实测双 Key 并发未被限流。
- 一次可提交 4 格（一期）或 8 格（两期），脚本打印进度；全部成功退出码 0。

### 5. 拼接为纵向条漫
```
python3 "<技能目录>/scripts/comic_stitch.py" \
  --title "<一句话标题>" \
  --subtitle "<YYYY-MM-DD>" \
  --panels panel_1.png panel_2.png ... \
  --captions "<格1台词>" "<格2台词>" ... \
  --width 1024 --out "<归档目录>/hotspot_comic_YYYYMMDD_<主题关键词>.png"
```

### 5.1 按日期归档（每天必做）
- 每个自然日一个归档目录：`hotspot_comics/YYYY-MM-DD/`（在用户工作目录下，如 `/Users/kenneth/agent/hotspot_comics/`）。
- 开始制作当天之前先 `mkdir -p hotspot_comics/YYYY-MM-DD`。
- 当天全部成品（6-10 期）完成后，统一归档到该目录；中间格子临时文件（panel_*.png）不保留。
- 成品命名含日期+主题：`hotspot_comic_YYYYMMDD_<主题>.png`。

### 5.2 生成 HTML 日报（每天必做，微信兼容版）
当天全部漫画完成后，生成一份**微信兼容版** HTML 日报并归档到当天目录：`hotspot_comics/YYYY-MM-DD/hotspot_comic_daily_YYYYMMDD_wechat.html`（图片用**相对路径**引用 `hotspot_comic_YYYYMMDD_<主题>.png`）。不再生成常规版。
- 用于直接复制到微信公众号编辑器，**必须遵守以下兼容限制**（微信编辑器会剥离/错乱这些语法）：
  - 页头用**纯色背景** `#333333`，不用 `linear-gradient`/`background-image`。
  - 布局用 **block 流式布局**，不用 `flex`/`grid`/浮动。
  - 图片 `style="width:100%; max-width:100%;"`（不要 `max-height`、`box-shadow`、圆角依赖）。
  - 目录用**纯文本清单**，不用 `<a href="#...">` 锚点跳转。
  - 不用 `box-shadow`、`position`、`letter-spacing` 依赖。
  - **不加顶部"发布前必读"提示块**，**不加尾部 copyright/页脚**——正文从标题栏开始，最后一条漫画结束即收尾。
- 正文结构：标题栏（日期 ｜ 选题范围 ｜ 共 N 期）→ 目录（按"国内热点/国际科技热点/国家领导人"分组）→ 每期一个区块（《标题》+ 领域标签 + 一句摘要 + 居中漫画图 + "热点概述"文字块）。无页脚。
- 每期"热点概述"写 2-4 句客观概括（事件 + 对立观点 + 折射的问题），与漫画标题呼应。

### 6. 展示结果
- 用 Read 工具查看最终 PNG，确认：标题正确、格子顺序正确、台词与画面匹配、无截断。
- 向用户展示最终图片路径，并附一段简短的"本期漫评"（1-3 句，点出讽刺或争议点）。

## 黑白讽刺漫画风格前缀（必用）

> black-and-white editorial cartoon, bold ink lines, high contrast shading, exaggerated caricature expressions, minimal grayscale tones, no color, newspaper comic style, clean background

画面描述示例（附加在风格前缀后）：
- 一群西装革履的人围着一枚巨大硬币争吵
- 一名程序员头顶冒着热气盯着屏幕
- 一个小人物站在巨大的字母"AI"下面

## 注意事项
- **台词不在图片里生成**：图片模型生成的中文文字常乱码。台词全部由 `comic_stitch.py` 排版到格子下方的台词条。因此每格 prompt 中不要要求画面出现文字。
- **真实人物必须用肖像图生图**：只有文生图时人物只是"一个西装男"，不可辨识。一定要检索肖像 → `--image` 图生图。涉及该人物的每格都要带肖像。
- **内容策略违规**：如果 Agnes 返回 `content_policy_violation`（如体重嘲讽、暴力画面、针对人身的指控、与违禁品/敏感物的关联），不要硬刚——改写该格 prompt，把直白的攻击性元素换成隐喻。实测有效改写案例：体重嘲讽→"屏幕上的愤怒气泡/网络骂战"；指控/法庭对抗→"访谈爆料/拳击台邀约"；"转发视频传播"→"手机上的问号气泡"；"委员会问责"→"普通办公会议"；草药/食用关联→"抽象叶子符号+植物海报"；司法意象（盲眼女神+倾斜天平）→"芯片vs羽毛的天平"。
- 敏感话题处理：保留讽刺，不渲染极端血腥/色情/暴力细节；涉及具体人物时用肖像参考图做讽刺漫画（新闻评论用途），避免肖像侵权。
- 生成耗时：每格约 10-30 秒；单期 4 格并行约 1-2 分钟；一天 6-10 期全流程约 30 分钟。途中网络偶发 502/503/连接重置时，并行脚本会自动换 Key 重试，无需手工干预。
- 成品统一命名：`hotspot_comic_YYYYMMDD_<主题>.png`，归档于 `hotspot_comics/YYYY-MM-DD/`。
- **微信兼容版 HTML 自查清单**（生成后逐项核对）：无 `linear-gradient`/渐变背景；无 `flex`/`grid`/float；无 `box-shadow`；无 `max-height`；目录无锚点链接；图片用相对路径且 `width:100%`；无顶部提示块、无尾部 copyright/页脚。满足全部才可交付。
- API Key 不写入任何文件代码逻辑之外：脚本运行时从 `~/.config/agnes/key`（或 `key-backup`）读取，无需手工 export。

## 依赖
- `agnes_gen.py`：图片生成（见同目录）。
- `comic_stitch.py`：条漫拼接。
- `gen_parallel.py`：并行生成调度（多 Key 轮换 + 失败重试）。
- Pillow（`python3 -m pip install --user --break-system-packages Pillow`）。
