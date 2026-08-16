# hotspot-comic · 每日热点长漫画

把当天有争议的新闻热点，做成一张黑白讽刺风格的**纵向条漫**：顶部标题条 + 每格一张黑白漫画 + 格子下方台词条（台词由脚本排版，不依赖图片模型生成文字）。

## 功能特性

- **热点检索**：自动检索当天争议性热点（默认：国内热点 + 国际科技热点 + 重要国家领导人事件），总数 6-10 期；MCP 搜索不可用时自动切换 Google News RSS 兜底。
- **肖像库**：涉及真实人物（政客、名人、企业高管等）时检索官方肖像 → 图生图保证形象可辨识，内置 17+ 位人物肖像库可直接复用。
- **并行生成**：默认通过 `gen_parallel.py` 并行生成多格漫画（双 API Key 轮换 + 失败自动重试），单期 4 格约 1-2 分钟。
- **自动拼接**：`comic_stitch.py` 将各格漫画 + 台词条拼接为纵向条漫，台词由脚本排版（图片模型生成中文易乱码，因此不依赖图片内文字）。
- **按日期归档**：成品统一归档到 `hotspot_comics/YYYY-MM-DD/`，命名 `hotspot_comic_YYYYMMDD_<主题>.png`。
- **微信兼容版 HTML 日报**：生成符合微信公众号编辑器限制的 HTML（纯色背景、block 流式布局、相对路径图片、无锚点/阴影/页脚），可直接复制进公众号编辑器。

## 快速开始

```bash
# 安装依赖
python3 -m pip install --user --break-system-packages Pillow

# 准备 API Key（脚本自动读取，无需手工 export）
#   ~/.config/agnes/key          （主 Key）
#   ~/.config/agnes/key-backup   （备用 Key，并行生成时轮换）
```

## 工作流程（由 AI 按 SKILL.md 执行）

1. **检索当天热点** → 选出 6-10 个有对立双方、有戏剧冲突的争议事件（国内 / 国际科技 / 国家领导人）
2. **设计分镜脚本**（每期 4-6 格）→ 每格写台词（≤20 字中文）+ 英文画面描述（统一黑白讽刺风格前缀）
3. **准备人物肖像** → 涉及真实人物时检索官方肖像并压缩到宽 ≤600px 存入 `ref/`
4. **逐格生成** → `gen_parallel.py` 并行文生图/图生图（`--ratio 4:3 --size 2K`）
5. **拼接条漫** → `comic_stitch.py` 排版台词条 + 拼接 → 按日期归档
6. **生成微信版 HTML 日报** → 归档到当天目录

## 目录结构

```
hotspot-comic/
├── SKILL.md               # 技能定义（完整工作流 + 风格规范 + 注意事项）
├── scripts/
│   ├── agnes_gen.py       # Agnes 图片生成（文生图 / 图生图 / 参数控制）
│   ├── comic_stitch.py    # 条漫拼接（标题条 + 格子 + 台词条）
│   └── gen_parallel.py    # 并行生成调度（多 Key 轮换 + 失败重试）
└── README.md
```

## 产物归档

- 条漫成品：`hotspot_comics/YYYY-MM-DD/hotspot_comic_YYYYMMDD_<主题>.png`
- 微信日报：`hotspot_comics/YYYY-MM-DD/hotspot_comic_daily_YYYYMMDD_wechat.html`
- 中间临时文件（`panel_*.png`）不保留。

## 黑白讽刺风格前缀（每格 prompt 必用）

> black-and-white editorial cartoon, bold ink lines, high contrast shading, exaggerated caricature expressions, minimal grayscale tones, no color, newspaper comic style, clean background

## 注意事项

- **台词不进图片**：图片模型生成中文文字易乱码，台词全部由 `comic_stitch.py` 排版到格子下方。
- **真实人物必须用肖像图生图**：仅文生图时人物不可辨识，务必先检索肖像 → `--image` 图生图。
- **内容策略违规**：Agnes 返回 `content_policy_violation` 时改写 prompt，把直白攻击性元素换成隐喻（SKILL.md 有实测改写案例）。
- 生成耗时：每格约 10-30 秒；一天 6-10 期全流程约 30 分钟；网络偶发 502/503 时并行脚本自动换 Key 重试。