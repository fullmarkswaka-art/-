# -*- coding: utf-8 -*-
"""Merchant API (v1) で Merchant Center に属性補完データを流し込む。

Merchant Center 本体のフィード（gsfeed.xml の定期取得）には brand / custom_label が
無いため、API 用の「補助データソース」を作り、商品ごとに brand / custom_label_0 /
custom_label_1 / product_type だけを productInputs として登録する。補助データソースの
値は本体フィードとマージされ、本体フィードの再取得で消えない。

必要権限: OAuth スコープ https://www.googleapis.com/auth/content と、
GCP プロジェクトの Merchant Center への開発者登録（developerRegistration:registerGcp 済み）。
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

import requests

from .config import load_google_config

MERCHANT_ID = "5642612701"
BASE = "https://merchantapi.googleapis.com"
SUPPLEMENT_NAME = "属性補完（brand/outlet/series）API補助データ"
TOKEN_OVERRIDE = Path(__file__).resolve().parent.parent / "reports" / "google_refresh_token.txt"


class MerchantApiError(RuntimeError):
    pass


class MerchantClient:
    def __init__(self, merchant_id: str = MERCHANT_ID):
        cfg = load_google_config()
        # Lambda 側のトークンが content スコープ無しの間は、取り直したトークンを優先する
        refresh_token = cfg.refresh_token
        if TOKEN_OVERRIDE.exists():
            refresh_token = TOKEN_OVERRIDE.read_text(encoding="utf-8").strip()
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": cfg.client_id, "client_secret": cfg.client_secret,
            "refresh_token": refresh_token, "grant_type": "refresh_token"}, timeout=30)
        body = resp.json()
        if "access_token" not in body:
            raise MerchantApiError(f"アクセストークン取得に失敗: {body.get('error_description')}")
        self.headers = {"Authorization": f"Bearer {body['access_token']}"}
        self.merchant_id = merchant_id
        self.account = f"accounts/{merchant_id}"

    def _req(self, method: str, path: str, **kw) -> dict:
        resp = requests.request(method, f"{BASE}/{path}", headers=self.headers,
                                timeout=60, **kw)
        try:
            body = resp.json()
        except ValueError:
            raise MerchantApiError(f"{method} {path}: HTTP {resp.status_code}")
        if resp.status_code >= 400:
            err = body.get("error", {})
            raise MerchantApiError(
                f"{method} {path}: {err.get('code')} {err.get('message')}")
        return body

    # ---- データソース ----
    def list_data_sources(self) -> list[dict]:
        return self._req("GET", f"datasources/v1/{self.account}/dataSources").get("dataSources", [])

    def primary_data_source(self) -> dict:
        """gsfeed.xml を取得しているプライマリ（ショッピング広告向け）を返す。

        AUTOFEED（サイト自動クロール・無料リスティング用）もプライマリとして
        存在するため、feedLabel/contentLanguage を持つファイル取得型を優先する。
        """
        cands = [ds for ds in self.list_data_sources() if "primaryProductDataSource" in ds]
        for ds in cands:
            uri = ds.get("fileInput", {}).get("fetchSettings", {}).get("fetchUri", "")
            if "gsfeed" in uri:
                return ds
        for ds in cands:
            if ds["primaryProductDataSource"].get("feedLabel"):
                return ds
        raise MerchantApiError("プライマリの商品データソースが見つかりません")

    def ensure_supplemental(self, apply: bool) -> dict:
        """API 用の補助データソースを（無ければ）作り、プライマリのルールに連結する。"""
        primary = self.primary_data_source()
        pp = primary["primaryProductDataSource"]
        sup = next((d for d in self.list_data_sources()
                    if d.get("displayName") == SUPPLEMENT_NAME), None)
        plan = {"primary": {"name": primary["name"], "displayName": primary.get("displayName"),
                            "feedLabel": pp.get("feedLabel"),
                            "contentLanguage": pp.get("contentLanguage"),
                            "defaultRule": pp.get("defaultRule")},
                "supplemental": sup, "apply": apply}
        if not apply:
            return plan
        if sup is None:
            body = {"displayName": SUPPLEMENT_NAME,
                    "supplementalProductDataSource": {
                        "feedLabel": pp.get("feedLabel"),
                        "contentLanguage": pp.get("contentLanguage")}}
            try:
                sup = self._req("POST", f"datasources/v1/{self.account}/dataSources", json=body)
            except MerchantApiError as e:
                if "Unexpected field" not in str(e):
                    raise
                # 一部アカウントでは feedLabel/contentLanguage を受け付けないため無指定で作る
                body["supplementalProductDataSource"] = {}
                sup = self._req("POST", f"datasources/v1/{self.account}/dataSources", json=body)
            plan["supplemental"] = sup
            plan["created"] = True
        rule = pp.get("defaultRule") or {"takeFromDataSources": [{"self": True}]}
        linked = [r.get("supplementalDataSourceName") for r in rule.get("takeFromDataSources", [])]
        if sup["name"] not in linked:
            rule["takeFromDataSources"].append({"supplementalDataSourceName": sup["name"]})
            updated = self._req(
                "PATCH", f"datasources/v1/{primary['name']}",
                params={"updateMask": "primaryProductDataSource.defaultRule"},
                json={"primaryProductDataSource": {"defaultRule": rule}})
            plan["linked"] = updated["primaryProductDataSource"].get("defaultRule")
        return plan

    # ---- 商品属性の登録 ----
    def upsert_attributes(self, csv_path: Path, apply: bool, limit: int | None = None) -> dict:
        sup = next((d for d in self.list_data_sources()
                    if d.get("displayName") == SUPPLEMENT_NAME), None)
        if sup is None and apply:
            raise MerchantApiError("補助データソースが未作成です（ensure_supplemental を先に）")
        # 補助データソースに feedLabel/contentLanguage が無い場合はプライマリに合わせる
        pp = self.primary_data_source()["primaryProductDataSource"]
        fl = (sup or {}).get("supplementalProductDataSource", {}).get("feedLabel") or pp.get("feedLabel")
        lang = (sup or {}).get("supplementalProductDataSource", {}).get("contentLanguage") or pp.get("contentLanguage")
        rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
        if limit:
            rows = rows[:limit]
        result = {"data_source": sup["name"] if sup else None, "rows": len(rows), "apply": apply,
                  "ok": 0, "errors": []}
        if not apply:
            result["sample"] = rows[:3]
            return result
        for r in rows:
            attrs = {"customLabel0": r["custom_label_0"]}
            if r.get("brand"):
                attrs["brand"] = r["brand"]
            if r.get("custom_label_1"):
                attrs["customLabel1"] = r["custom_label_1"]
            if r.get("product_type"):
                attrs["productTypes"] = [r["product_type"]]
            body = {"offerId": r["id"], "contentLanguage": lang, "feedLabel": fl,
                    "productAttributes": attrs}
            for attempt in range(3):
                try:
                    self._req("POST", f"products/v1/{self.account}/productInputs:insert",
                              params={"dataSource": sup["name"]}, json=body)
                    result["ok"] += 1
                    break
                except MerchantApiError as e:
                    if attempt == 2:
                        result["errors"].append({"id": r["id"], "error": str(e)[:200]})
                    else:
                        time.sleep(2 ** attempt)
        return result

    def get_product(self, offer_id: str) -> dict:
        sup = next((d for d in self.list_data_sources()
                    if d.get("displayName") == SUPPLEMENT_NAME), None)
        pp = self.primary_data_source()["primaryProductDataSource"]
        lang = pp.get("contentLanguage", "ja")
        fl = pp.get("feedLabel", "JP")
        return self._req("GET", f"products/v1/{self.account}/products/{lang}~{fl}~{offer_id}")
