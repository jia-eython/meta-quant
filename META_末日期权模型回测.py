# -*- coding: utf-8 -*-
"""
META 末日期权(当日到期平值call) 买入->止盈/止损卖出 模型回测
结论先行: 618 个交易日, 所有止盈/止损组合期望均<0, 胜率29%~47%, 说明买末日call按规则卖出仍是负期望。
模型: 真实META M5行权+Black-Scholes合成当日到期平值call; sigma=近30日已实现波动率; 进/出场各2% spread。
声明: 沙盒无META已到期期权(DELISTING=0)且META无每日0DTE, 故用合成价建模, 用于评估规则层期望。
"""
from __future__ import annotations
import sys, math, time
from datetime import datetime, time as dtime
import numpy as np, pandas as pd
from quant_data import fetch_m5  # noqa: E402  自包含数据层

def norm(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def bs(S,K,sigma,t):
    t=max(t,1e-9)
    if sigma<=0 or S<=0: return 0.0
    d1=(math.log(S/K)+0.5*sigma*sigma*t)/(sigma*math.sqrt(t))
    return S*norm(d1)-K*norm(d1-sigma*math.sqrt(t))

def main():
    start="2024-03-15"; end="2026-09-02"
    m5=fetch_m5(start,end)
    print("M5 bars:",len(m5)," range:",m5["dt"].min(),"~",m5["dt"].max())
    if m5.empty: return
    for c in ("open","close","high","low","volume"): m5[c]=pd.to_numeric(m5[c],errors="coerce")
    m5=m5.dropna(subset=["open","close","high","low"])
    m5["date"]=m5["dt"].dt.date
    daily_close=m5.groupby("date")["close"].last().sort_index()
    rv=(daily_close.pct_change().rolling(30).std()*math.sqrt(252)).shift(1); rv_d=rv.to_dict()
    groups={d:g.sort_values("dt").reset_index(drop=True) for d,g in m5.groupby("date")}
    def tleft(dt):
        pc=datetime.combine(dt.date(),dtime(16,0)); secs=(pc-dt.to_pydatetime()).total_seconds()
        return max(secs/(6.5*3600),1e-6)/252.0
    def simulate(tp,sl,spread=0.02):
        res=[]
        for d,g in groups.items():
            s0=float(g["open"].iloc[0]);
            if s0<=0: continue
            K=round(s0/5)*5; sig=rv_d.get(d,0.35)
            if sig is None or not (0.15<=sig<=0.75): sig=0.35
            entry=bs(s0,K,sig,tleft(g["dt"].iloc[0]));
            if entry<=0: continue
            entry_cost=entry*(1+spread); tpp=entry*(1+tp) if tp is not None else None; slp=entry*(1-sl) if sl is not None else None
            exit_px=None; why=None
            for i in range(len(g)):
                row=g.iloc[i]; t=tleft(row["dt"])
                ph=bs(float(row["high"]),K,sig,t); pl=bs(float(row["low"]),K,sig,t)
                if slp is not None and pl<=slp: exit_px=slp; why="stop"; break
                if tpp is not None and ph>=tpp: exit_px=tpp; why="target"; break
            if exit_px is None:
                exit_px=bs(float(g["close"].iloc[-1]),K,sig,tleft(g["dt"].iloc[-1])); why="eod"
            pnl=exit_px*(1-spread)-entry_cost
            res.append((d,pnl/entry_cost*100,why))
        return res
    def fmt(tp,sl):
        r=[x[1] for x in simulate(tp,sl)]
        if not r: return None
        w=[x for x in r if x>0]; l=[x for x in r if x<=0]
        wh=[x[2] for x in simulate(tp,sl)]
        return (tp,sl,len(r),len(w)/len(r)*100,np.mean(r),np.median(r),np.mean(w),np.mean(l),wh.count("target")/len(r)*100,wh.count("stop")/len(r)*100)
    print()
    print("规则: 每日开盘买当日到期平值call, sigma=近30日已实现波动率, 进/出场各2% spread")
    print("止盈  止损  样本  胜率  期望/笔  中位数  平均盈  平均亏  止盈%  止损%  尾盘%" if False else "止盈% 止损%  n    胜率  期望/笔  中位   平均盈   平均亏  止盈% 止损% 尾盘% ")
    for tp,sl in [(0.30,0.30),(0.40,0.30),(0.50,0.30),(0.60,0.30),(0.50,0.20),(0.40,0.20),(0.70,0.35)]:
        x=fmt(tp,sl)
        if x: print(f"{x[0]*100:>3.0f}% {x[1]*100:>3.0f}% {x[2]:>5d} {x[3]:>5.0f}% {x[4]:>+8.2f}% {x[5]:>+8.2f}% {x[6]:>+8.2f}% {x[7]:>+8.2f}% {x[8]:>5.0f}% {x[9]:>5.0f}%")
    # true buy-open sell-close (no target/stop): simulate tp=None sl=None
    r0=[x[1] for x in simulate(None,None)]
    print(f"基准(开盘买,尾盘卖出,不设止盈止损): n={len(r0)} 胜率={sum(1 for x in r0 if x>0)/len(r0)*100:.0f}% avg={np.mean(r0):+.2f}% med={np.median(r0):+.2f}%")

if __name__ == "__main__":
    main()
