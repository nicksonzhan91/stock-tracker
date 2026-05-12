"""
push_github.py — 將 latest.json 推送到 GitHub Pages
"""
import subprocess
import sys
import os

REPO = os.path.join(os.path.dirname(__file__), "..")
REPO = os.path.abspath(REPO)


def git(args: list) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", REPO] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def main():
    # 暫存 latest.json
    code, out = git(["add", "data/latest.json"])
    if code != 0:
        print(f"[GitHub] git add 失敗: {out}")
        return

    # 確認是否有變更
    code, diff = git(["diff", "--cached", "--name-only"])
    if not diff.strip():
        print("[GitHub] latest.json 無變動，略過 push")
        return

    # commit
    code, out = git(["commit", "-m", "data: update latest.json"])
    if code != 0:
        print(f"[GitHub] commit 失敗: {out}")
        return
    print(f"[GitHub] commit: {out}")

    # push
    code, out = git(["push", "origin", "main"])
    if code == 0:
        print("[GitHub] Push 成功 ✅")
    else:
        print(f"[GitHub] push 失敗: {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
