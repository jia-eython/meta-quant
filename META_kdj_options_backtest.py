# -*- coding: utf-8 -*-
"""
META 超短线期权代理回测：KDJ(9,3,3) 金叉/死叉 + 严格止损
=========================================================
用法：
  python 量化/META_kdj_options_backtest.py

说明：
- 数据：quant-backtest 数据层（Webull 沙盒）拉取 META 日线，默认 2020-01-01 ~ 2025-12-31
- 信号：金叉(K上穿D)->做多(买call代理)；死叉(K下穿D)->做空(买put代理)
- 止损：持仓期价格反向超过 stop 比例即强平
- 对比：只做多版本、买入持有基准

⚠️ 代理说明（重要）：
本脚本用「标的股票价格」模拟期权方向（金叉做多≈买call，死叉做空≈买put），
未建模 权利金/隐含波动率/时间价值衰减/合约杠杆。结果反映的是 KDJ 信号的方向质量，
真实期权会额外受 IV Crush 与权利金成本影响，尤其「买put」通常比卖空更亏（权利金白耗）。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import os

# 可配置：quant-backtest 数据层目录（本机缺省路径 → 用环境变量覆盖）
SKILL_DIR = os.environ.get("QUANT_BACKTEST_DIR", r"")
if not os.path.isdir(SKILL_DIR):
    raise SystemExit("找不到 quant-backtest 数据层目录。请设置环境变量 QUANT_BACKTEST_DIR 指向 skills/quant-backtest/scripts")
sys.path.insert(0, SKILL_DIR)
from data_source import load_daily  # noqa: E402


def kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3):
    low_n = df["low"].rolling(n).min()
    high_n = df["high"].rolling(n).max()
    denom = (high_n - low_n).replace(0, np.nan)
    rsv = ((df["close"] - low_n) / denom * 100).fillna(50.0)
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def signals(df: pd.DataFrame):
    k, d, _ = kdj(df)
    kp, dp = k.shift(1), d.shift(1)
    golden = (kp.notna() & dp.notna() & (kp <= dp) & (k > d)).to_numpy(bool)
    death = (kp.notna() & dp.notna() & (kp >= dp) & (k < d)).to_numpy(bool)
    return golden, death


def backtest(df: pd.DataFrame, stop: float, allow_short: bool):
    close = df["close"].to_numpy(float)
    golden, death = signals(df)
    n = len(df)
    pos = np.zeros(n, dtype=int)
    cur, entry = 0, None
    trades: list[tuple] = []

    for i in range(n):
        c = close[i]
        if cur == 0:
            if golden[i]:
                cur, entry = 1, c
            elif allow_short and death[i]:
                cur, entry = -1, c
        elif cur == 1:
            if death[i] or c <= entry * (1 - stop):
                trades.append((entry, c, (c / entry - 1) > 0))
                cur = 0
        elif cur == -1:
            if golden[i] or c >= entry * (1 + stop):
                trades.append((entry, c, (entry / c - 1) > 0))
                cur = 0
        pos[i] = cur

    ret = np.zeros(n)
    ret[1:] = pos[:-1] * (close[1:] / close[:-1] - 1)
    eq = 100000.0 * np.cumprod(1 + ret)
    total = eq[-1] / 100000.0 - 1
    years = n / 252.0
    annual = (pow(1 + total, 1 / years) - 1) * 100 if years > 0 and total > -1 else 0.0
    peak = np.maximum.accumulate(eq)
    mdd = float(((peak - eq) / peak).max() * 100)
    sr = pd.Series(ret)
    sharpe = float(sr.mean() / sr.std() * math.sqrt(252)) if sr.std() > 0 else None
    won = sum(1 for t in trades if t[2])
    closed = len(trades)
    return {
        "stop_loss_pct": round(stop * 100, 0),
        "total_return_pct": round(total * 100, 2),
        "annual_return_pct": round(annual, 2),
        "max_drawdown_pct": round(mdd, 2),
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
        "trades": closed,
        "won": won,
        "win_rate_pct": round(won / closed * 100, 1) if closed else None,
    }, eq


def main():
    market, symbol = "us", "META"
    start, end = "2020-01-01", "2025-12-31"
    df, src = load_daily(market, symbol, start, end, us_source="auto")
    bh = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100

    print("=" * 72)
    print(f"  {symbol}  {df.index.min().date()} ~ {df.index.max().date()}  "
          f"bars={len(df)}  数据源={src}")
    print(f"  买入持有基准: {bh:.2f}%")
    print("=" * 72)

    for label, allow_short in [("金叉做多 / 死叉做空(买call+买put)", True),
                               ("只做多(仅买call)", False)]:
        print(f"\n【{label}】")
        for stop in (0.03, 0.05, 0.08, 0.10):
            rep, _ = backtest(df, stop, allow_short)
            print("  ", json.dumps(rep, ensure_ascii=False))

    print("\n⚠️ 以上为标的股价格的方向性代理；真实期权还含权利金/IV/时间价值衰减，结论仅供信号方向参考。")


if __name__ == "__main__":
    main()
