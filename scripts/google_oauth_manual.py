# -*- coding: utf-8 -*-
"""ブラウザ操作だけで Google のリフレッシュトークンを取り直す（PCへのインストール不要）。

  python scripts/google_oauth_manual.py url
      → 認可URLを表示。ユーザーがブラウザで開き、Google広告と Merchant Center の
        権限を持つアカウントでログイン・同意する。最後に localhost へ転送されて
        「接続できません」と表示されるが、そのページのアドレスバーのURL
        （?code=... を含む）をコピーしてもらう。
  python scripts/google_oauth_manual.py exchange "<コピーしたURL>"
      → 認可コードをリフレッシュトークンに交換して表示する。

client_id / client_secret は通常どおり Lambda 環境変数から自動取得される。
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ads_manager.config import load_google_config  # noqa: E402

SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/content",
]
REDIRECT_URI = "http://localhost:8765/"


def auth_url() -> str:
    cfg = load_google_config()
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def exchange(redirected_url: str) -> dict:
    cfg = load_google_config()
    qs = parse_qs(urlparse(redirected_url.strip()).query)
    if "code" not in qs:
        raise SystemExit("URL に code= が含まれていません。転送後のアドレスバー全体を貼ってください")
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": qs["code"][0],
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=30)
    body = resp.json()
    if "refresh_token" not in body:
        raise SystemExit(f"交換に失敗: {body.get('error')} {body.get('error_description')}")
    return body


def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] == "url":
        print(auth_url())
        return 0
    if len(argv) >= 2 and argv[0] == "exchange":
        body = exchange(argv[1])
        out = Path(__file__).resolve().parent.parent / "reports" / "google_refresh_token.txt"
        out.parent.mkdir(exist_ok=True)
        out.write_text(body["refresh_token"], encoding="utf-8")
        print(f"リフレッシュトークンを保存: {out}（スコープ: {body.get('scope')}）")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
