#!/usr/bin/env python3
"""
agnes_gen.py — Agnes AI 图像 / 视频生成 CLI
文档参考: https://www.agnes-ai.com/zh-Hans/docs/overview
API 网关: https://apihub.agnes-ai.com/v1  (OpenAI 兼容, Bearer Token 认证)

用法:
  生成图片 (文生图):   python3 agnes_gen.py image  --prompt "..." [--size 2K] [--ratio 16:9] [--out out.png]
  编辑图片 (图生图):   python3 agnes_gen.py image  --prompt "..." --image URL_或本地路径 [--size 2K] [--out out.png]
  多图合成:            python3 agnes_gen.py image  --prompt "..." --image URL1 URL2 [--out out.png]
  生成视频 (文生视频): python3 agnes_gen.py video  --prompt "..." [--duration 5] [--fps 24] [--out out.mp4]
  图生视频:            python3 agnes_gen.py video  --prompt "..." --image URL_或本地路径 [--duration 5] [--out out.mp4]
  关键帧动画:          python3 agnes_gen.py video  --prompt "..." --keyframes URL1 URL2 [--duration 5] [--out out.mp4]

  提示: --image / --keyframes 支持公网 URL、Data URI，或本地图片文件路径(自动转 Data URI)。

环境变量:
  AGNES_API_KEY  必填。API 密钥。
  AGNES_BASE_URL 可选。默认 https://apihub.agnes-ai.com/v1
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"
IMAGE_MODEL = "agnes-image-2.1-flash"   # 文生图/图生图/多图合成
VIDEO_MODEL = "agnes-video-v2.0"        # 文生视频/图生视频/关键帧动画
DEFAULT_SIZE_TIER = "2K"
DEFAULT_RATIO = "1:1"


def die(msg: str):
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(1)


def get_api_key() -> str:
    """优先取环境变量 AGNES_API_KEY，否则读取 ~/.config/agnes/key 文件。"""
    key = os.environ.get("AGNES_API_KEY", "").strip()
    if key:
        return key
    for p in (os.path.expanduser("~/.config/agnes/key"), os.path.expanduser("~/.config/agnes/key-backup")):
        try:
            with open(p) as f:
                key = f.read().strip()
            if key:
                return key
        except OSError:
            continue
    die("未找到 API 密钥：请设置 AGNES_API_KEY 环境变量，或在 ~/.config/agnes/key 中写入密钥")
    return ""


def api_request(method: str, url: str, payload: dict | None = None, timeout: int = 360):
    """发送带 Bearer Token 的 JSON 请求, 返回解析后的 dict。"""
    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        die(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        die(f"网络错误: {e}")


def resolve_video_query_url(base: str) -> str:
    """由 base url (…/v1) 推导视频结果查询地址 …/agnesapi?video_id=…"""
    return base.rstrip("/").removesuffix("/v1") + "/agnesapi"


def to_data_uri(src: str) -> str:
    """把输入统一为可用的图片引用: 已是 http(s)/data: 则原样返回; 本地文件路径则转 Data URI。"""
    if src.startswith("http://") or src.startswith("https://") or src.startswith("data:"):
        return src
    if not os.path.isfile(src):
        die(f"本地图片不存在: {src}")
    mime = "image/png"
    low = src.lower()
    if low.endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    elif low.endswith(".gif"):
        mime = "image/gif"
    elif low.endswith(".webp"):
        mime = "image/webp"
    with open(src, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    print(f"[本地图片] {src} → Data URI ({len(b64)//1024}KB base64)", file=sys.stderr)
    return f"data:{mime};base64,{b64}"


# ---------------------------------------------------------------- 图像 ----
def gen_image(args) -> str:
    """POST /v1/images/generations, 返回保存到本地的文件路径。"""
    extra_body: dict = {}
    if args.image:
        extra_body["image"] = [to_data_uri(img) for img in args.image]  # 图生图/多图合成
    if not args.base64:
        extra_body["response_format"] = "url"

    payload = {
        "model": IMAGE_MODEL,
        "prompt": args.prompt,
        "size": args.size,           # 1K/2K/3K/4K 或 1024x768 等
        "ratio": args.ratio,         # 1:1, 3:4, 4:3, 16:9, 9:16, 2:3, 3:2, 21:9
        "extra_body": extra_body,
    }
    print(f"[图片] 模型={IMAGE_MODEL} size={args.size} ratio={args.ratio} 提示词: {args.prompt}", file=sys.stderr)
    resp = api_request("POST", os.environ.get("AGNES_BASE_URL", DEFAULT_BASE_URL).rstrip("/") + "/images/generations", payload)

    item = resp["data"][0]
    if args.base64 and item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
        path = args.out or "agnes_image.png"
        with open(path, "wb") as f:
            f.write(raw)
        print(f"[图片] 已保存 Base64 到: {path}")
        return path

    url = item.get("url")
    if not url:
        die("响应中没有图片 url 字段")
    if args.out:
        download_binary(url, args.out)
        print(f"[图片] 已下载到: {args.out}")
        return args.out
    print(f"[图片] 生成完成: {url}")
    return url


def download_binary(url: str, path: str):
    """下载生成的媒体文件。

    生成的图片/视频 URL 是公开的云存储地址, 无需 Bearer 鉴权;
    带上 Authorization 头反而可能触发 CDN 的 401 校验, 因此不带。
    """
    with urllib.request.urlopen(url, timeout=360) as resp, open(path, "wb") as f:
        f.write(resp.read())


# ---------------------------------------------------------------- 视频 ----
def gen_video(args) -> str:
    """POST /v1/videos 创建异步任务, 轮询查询结果, 返回视频 URL (或下载到本地)。"""
    base = os.environ.get("AGNES_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    query_base = resolve_video_query_url(base)

    # 帧数换算: num_frames 需满足 8n+1 且 <= 441
    fps = args.fps
    num_frames = args.frames or (args.duration * fps)
    num_frames = max(1, min(441, num_frames))
    num_frames = ((num_frames - 1) // 8) * 8 + 1  # 归一化到 8n+1

    payload: dict = {
        "model": VIDEO_MODEL,
        "prompt": args.prompt,
        "num_frames": num_frames,
        "frame_rate": fps,
    }
    if args.image:
        payload["image"] = to_data_uri(args.image[0])            # 图生视频
    if args.keyframes:
        payload["extra_body"] = {"image": [to_data_uri(k) for k in args.keyframes], "mode": "keyframes"}  # 关键帧
    if args.negative_prompt:
        payload["negative_prompt"] = args.negative_prompt

    print(f"[视频] 模型={VIDEO_MODEL} {num_frames}帧@{fps}fps ≈ {num_frames/fps:.1f}s 提示词: {args.prompt}", file=sys.stderr)
    resp = api_request("POST", base + "/videos", payload)

    video_id = resp.get("video_id") or resp.get("id") or resp.get("task_id")
    if not video_id:
        die(f"创建任务失败, 响应缺少 video_id: {resp}")
    status = resp.get("status", "queued")
    print(f"[视频] 任务已创建 video_id={video_id} status={status}", file=sys.stderr)
    if args.no_wait:
        print(f"[视频] (no-wait) 稍后手动查询: {query_base}?video_id={video_id}")
        return f"{query_base}?video_id={video_id}"

    # 轮询结果
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        time.sleep(args.interval)
        result = api_request("GET", f"{query_base}?video_id={video_id}", timeout=30)
        st = result.get("status")
        prog = result.get("progress", 0)
        print(f"[视频] status={st} progress={prog}%", file=sys.stderr)
        if st == "completed":
            # 真实 API 把 url 放在顶层, 文档示例放在 metadata.url, 两处都兼容
            url = result.get("url") or (result.get("metadata") or {}).get("url")
            if not url:
                die(f"任务完成但没有视频 url: {result}")
            if args.out:
                download_binary(url, args.out)
                print(f"[视频] 已下载到: {args.out}")
                return args.out
            print(f"[视频] 生成完成: {url}")
            return url
        if st == "failed":
            die(f"视频生成失败: {result.get('error') or result}")

    die(f"轮询超时 (>{args.timeout}s)。可用 video_id={video_id} 手动查询。")
    return ""  # 不可达


# ----------------------------------------------------------------- main ----
def main():
    parser = argparse.ArgumentParser(description="Agnes AI 图像/视频生成 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # image
    p_img = sub.add_parser("image", help="生成/编辑图片")
    p_img.add_argument("--prompt", required=True, help="提示词(文生图)或编辑指令(图生图)")
    p_img.add_argument("--size", default=DEFAULT_SIZE_TIER, help="尺寸档位 1K/2K/3K/4K, 或精确尺寸如 1024x768 (默认 2K)")
    p_img.add_argument("--ratio", default=DEFAULT_RATIO, help="比例: 1:1,3:4,4:3,16:9,9:16,2:3,3:2,21:9 (默认 1:1)")
    p_img.add_argument("--image", nargs="+", help="参考图 URL/DataURI (图生图/多图合成)")
    p_img.add_argument("--base64", action="store_true", help="以 Base64 输出并保存到文件")
    p_img.add_argument("--out", help="输出文件路径 (默认打印 URL)")
    p_img.set_defaults(func=gen_image)

    # video
    p_vid = sub.add_parser("video", help="生成视频 (异步)")
    p_vid.add_argument("--prompt", required=True, help="视频内容提示词")
    p_vid.add_argument("--image", nargs="+", help="图生视频: 起始图 URL (取第一张)")
    p_vid.add_argument("--keyframes", nargs="+", help="关键帧动画: 关键帧图 URL 列表")
    p_vid.add_argument("--duration", type=int, default=5, help="目标时长(秒), 默认 5s")
    p_vid.add_argument("--fps", type=int, default=24, help="帧率, 默认 24")
    p_vid.add_argument("--frames", type=int, help="直接指定帧数(8n+1, <=441); 默认按 duration*fps")
    p_vid.add_argument("--negative-prompt", help="负面提示词")
    p_vid.add_argument("--no-wait", action="store_true", help="只创建任务不轮询")
    p_vid.add_argument("--interval", type=float, default=5.0, help="轮询间隔秒数, 默认 5s")
    p_vid.add_argument("--timeout", type=int, default=600, help="轮询超时秒数, 默认 600s")
    p_vid.add_argument("--out", help="下载视频到本地路径")
    p_vid.set_defaults(func=gen_video)

    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n[中断] 已取消。", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()