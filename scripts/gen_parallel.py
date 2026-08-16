#!/usr/bin/env python3
"""并行生成多个漫画格：多 Key 负载均衡 + 失败自动换 Key 重试。

用法:
  python3 gen_parallel.py \
    --task '{"prompt":"...","out":"p1_1.png","image":"ref/trump_ref.jpg"}' \
    --task '{"prompt":"...","out":"p1_2.png"}' \
    --concurrency 2 --max-retries 3

说明:
  - 每个任务为一行 JSON: {prompt, out, image?, ratio?, size?}
  - 默认并发 2（两个 Key 各跑一路）；Key 从 ~/.config/agnes/key 与 key-backup 轮换
  - 任务失败自动换下一个 Key 重试，直至 max-retries 次或全部 Key 用完
  - 退出码: 全部成功=0, 有失败=1
"""
import argparse, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGNES = os.path.join(SCRIPT_DIR, "agnes_gen.py")
KEY_FILES = [
    os.path.expanduser("~/.config/agnes/key"),
    os.path.expanduser("~/.config/agnes/key-backup"),
]


def load_keys():
    keys = []
    for p in KEY_FILES:
        try:
            with open(p) as f:
                k = f.read().strip()
            if k:
                keys.append(k)
        except OSError:
            continue
    if not keys:
        sys.exit("错误：未找到任何 Agnes API Key（~/.config/agnes/key）")
    return keys


def run_one(task, key):
    env = dict(os.environ)
    env["AGNES_API_KEY"] = key
    cmd = [sys.executable, AGNES, "image",
           "--prompt", task["prompt"],
           "--ratio", task.get("ratio", "4:3"),
           "--size", task.get("size", "2K"),
           "--out", task["out"]]
    if task.get("image"):
        cmd += ["--image", task["image"]]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def main():
    ap = argparse.ArgumentParser(description="并行生成漫画格（多 Key 轮换 + 重试）")
    ap.add_argument("--task", action="append", required=True,
                    help="任务 JSON，如 '{\"prompt\":\"...\",\"out\":\"p1.png\"}'，可重复传")
    ap.add_argument("--concurrency", type=int, default=2,
                    help="并行数（默认 2，按 Key 数量）")
    ap.add_argument("--max-retries", type=int, default=3,
                    help="单个任务最大尝试次数（默认 3）")
    args = ap.parse_args()

    keys = load_keys()
    tasks = [json.loads(t) for t in args.task]
    print(f"任务数 {len(tasks)}，并发 {args.concurrency}，Key 数 {len(keys)}")

    # 初始 Key 轮询分配，尽量打散负载
    init_key = {i: keys[i % len(keys)] for i in range(len(tasks))}

    def worker(idx):
        task = tasks[idx]
        tried = set()
        for attempt in range(args.max_retries):
            key = init_key[idx]
            # 失败后换下一个 Key；同一 Key 不重复试
            candidates = [keys[i % len(keys)] for i in range(idx, idx + len(keys))]
            nxt = next((k for k in candidates if k not in tried), None)
            if nxt is None:
                break
            tried.add(nxt)
            print(f"[{idx+1}/{len(tasks)}] 第 {attempt+1} 次尝试 (Key#{keys.index(nxt)+1}): {task['out']}", flush=True)
            ok, log = run_one(task, nxt)
            if ok:
                return (idx, True, task["out"], log)
        return (idx, False, task["out"], "")

    results = [None] * len(tasks)
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(worker, i): i for i in range(len(tasks))}
        for fut in as_completed(futs):
            idx, ok, out, log = fut.result()
            results[idx] = ok
            if ok:
                print(f"[{idx+1}/{len(tasks)}] 完成: {out}", flush=True)
            else:
                print(f"[{idx+1}/{len(tasks)}] 失败: {out}\n{log}", flush=True)

    ok_n = sum(1 for r in results if r)
    print(f"\n完成 {ok_n}/{len(tasks)}")
    sys.exit(0 if ok_n == len(tasks) else 1)


if __name__ == "__main__":
    main()
