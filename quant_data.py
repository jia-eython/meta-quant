# -*- coding: utf-8 -*-
"""
自包含数据层：用 Webull 沙盒拉取 META 日线 / M5 分钟线。
密钥从环境变量或本机 .env 读取（真实密钥勿提交到仓库）。
"""
from __future__ import annotations
import os, time
from pathlib import Path
import pandas as pd

SANDBOX_HOST = "api.sandbox.webull.com"

def load_env():
    for p in (Path(".env"), Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"):
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('\"').strip("'"))
            return

def _client():
    load_env()
    from webull.core.client import ApiClient
    from webull.data.data_client import DataClient
    from webull.core.common.api_type import DEFAULT as HTTP_API_TYPE
    key = os.environ.get("SANDBOX_APP_KEY", "").strip()
    sec = os.environ.get("SANDBOX_APP_SECRET", "").strip()
    if not key or not sec:
        raise SystemExit("缺少 Webull 沙盒密钥。请设置环境变量或本机 .env 填入 SANDBOX_APP_KEY / SANDBOX_APP_SECRET（真实值勿提交）。")
    c = ApiClient(key, sec, "us", timeout=60, auto_retry=True, max_retry_num=3)
    c._stream_logger_set = True; c._file_logger_set = True
    c.add_endpoint("us", SANDBOX_HOST, api_type=HTTP_API_TYPE)
    return DataClient(c)

def _parse(bars):
    df = pd.DataFrame(bars)
    df["dt"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    for col in ("open", "close", "high", "low", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["dt", "open", "close", "high", "low", "volume"]].dropna(subset=["open", "close", "high", "low"]).reset_index(drop=True)

def _fetch(client, symbol, timespan, start, end, page_bars=1200, max_pages=45):
    start_ts = pd.Timestamp(start).tz_localize("America/New_York").tz_localize(None)
    end_ts = pd.Timestamp(end).tz_localize("America/New_York").tz_localize(None)
    frames = []; end_ms = None
    for _ in range(max_pages):
        kw = dict(symbol=symbol, category="US_STOCK", timespan=timespan, count=str(page_bars))
        if end_ms is None:
            r = client.market_data.get_history_bar(**kw)
        else:
            r = client.market_data.get_history_bar(**kw, end_time=end_ms)
        if getattr(r, "status_code", 0) != 200:
            break
        data = r.json()
        b = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else None)
        if isinstance(b, dict):
            b = b.get("items")
        if not b:
            break
        df = _parse(b)
        frames.append(df)
        mn = df["dt"].min()
        if mn <= start_ts:
            break
        end_ms = int(mn.tz_localize("America/New_York").timestamp() * 1000) - 1
        time.sleep(0.4)
        if len(df) < page_bars:
            break
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).drop_duplicates("dt").sort_values("dt").reset_index(drop=True)
    out = out[(out["dt"] >= start_ts) & (out["dt"] <= end_ts)]
    return out.reset_index(drop=True)

def fetch_m5(symbol, start, end):
    return _fetch(_client(), symbol, "M5", start, end)

def load_daily(market, symbol, start, end, us_source=None):
    df = _fetch(_client(), symbol, "D", start, end)
    df = df.set_index("dt").sort_index()
    return df, "webull-sandbox"