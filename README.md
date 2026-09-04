# META 量化策略研究

> 本仓库是**本次对话**围绕「只做 META 这一只股票」做的一套量化研究、回测与结论。只收录对话中产出的代码与文档，**不包含任何 API 密钥**。

## 内容

| 文件 | 说明 |
|---|---|
| `META_单票最佳方法.md` | 结论：**SMA20/50 趋势过滤 + 只做多 + 破位空仓** 为单票最优；买入持有 +217%、最大回撤 77%，趋势法 **+417%、回撤 33%、夏普 1.07**；含样本内/样本外分段验证 |
| `量化策略全景与最佳方法.md` | 策略生态分类、外部研究方法论（walk-forward / 样本外 / 成本 / 防过拟合 / Deflated Sharpe）、新策略 10 项评分卡 |
| `META_kdj_options_backtest.py` | KDJ(9,3,3) 金叉死叉 + 止损回测（验证 KDJ 在单票趋势里偏弱势） |
| `META_末日期权模型回测.py` | 用真实 META M5 分钟线 + Black-Scholes 合成“当日到期平值call”，回测“开盘买 → 止盈/止损卖出”（618 个交易日，全部组合期望为负） |
| `quant_data.py` | 自包含数据层：用 Webull 沙盒拉取 META 日线 / M5；密钥从本机 `.env` 或环境变量读取（不入库） |

## 克隆运行（快速上手）

```bash
git clone https://github.com/jia-eython/meta-quant.git
cd meta-quant
python -m pip install -r requirements.txt
cp .env.example .env        # 填入你自己的 Webull 沙盒密钥
python META_kdj_options_backtest.py
python META_末日期权模型回测.py
```

- 需要 **Python >= 3.10**，以及一个 **Webull 沙盒**账号的 `SANDBOX_APP_KEY / SANDBOX_APP_SECRET`。
- 密钥只填本机 `.env`（已被 `.gitignore` 排除），**不要提交到仓库**。

## 数据源

- 标的/分钟线：**微牛 Webull 沙盒**（只读行情）。
- 内置自包含数据层 `quant_data.py`，从本机 `.env` 或环境变量读取 `SANDBOX_APP_KEY / SANDBOX_APP_SECRET`（真实密钥**不入库**）。

## 安全说明（重要）

- 本仓库**不含任何 API 密钥 / 令牌**。
- Webull 沙盒/实盘密钥、推送 token 存放于本机 `.env` 文件，已被 `.gitignore` 排除，**绝不纳入版本控制**。
- 提交前请确认：没有把 `.env` 写入任何文件，也没有把真实密钥硬编码进代码。

## 结论

- 只做 META：最优是**趋势过滤 + 只做多**（金叉进场、死叉空仓，不反手做空、不买 put）。
- **买入末日(当日到期)期权、盘中按止盈/止损卖出，实测 618 个交易日全为负期望**，不建议作为赚钱方法；要加期权，优先考虑卖方/时间价值（如 covered call）。