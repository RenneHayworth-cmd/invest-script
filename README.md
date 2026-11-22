# A股投资工具箱 · 可视化面板

本地运行的投资研究面板：后端 **FastAPI**（Python），前端 **原生 HTML / JavaScript + ECharts**，浅色简洁风，图表都可以缩放、悬停看数值、保存图片。

整合了 `python脚本` 文件夹里的 26 个脚本：ETF / 场外基金 / 美股数据下载、滚动年化与回撤、均线与 RSI、指数 MA20 偏离率、期货价差、动量轮动回测、SPMO 风险调整动量选基。

```bash
pip install -r requirements.txt
python server.py          # 浏览器打开 http://127.0.0.1:8520
```

## 一、启动

1. 双击 **`启动面板.bat`**
2. 第一次运行会自动安装依赖（fastapi、uvicorn、pandas、tickflow、akshare 等），大约 1–3 分钟
3. 浏览器自动打开 `http://127.0.0.1:8520`；关闭黑色窗口即可退出

- 默认端口 **8520**，如果被占用会**自动顺延**到 8521、8522……（黑色窗口里会显示实际地址）
- 想固定用别的端口：`set INVEST_PORT=8600` 后再运行 `python server.py`
- 不想自动打开浏览器：`python server.py --no-browser`

## 二、设置 TickFlow 密钥（推荐）

面板**只从环境变量读取密钥**，代码和配置文件里都不保存，可以放心公开到 GitHub。在命令行运行一次（把引号里换成你的密钥）：

```
setx TICKFLOW_API_KEY "你的密钥"
```

然后**重新打开** `启动面板.bat`。没设置时会退回到 TickFlow 免费版，能下载的数据条数有限。左侧栏底部会显示密钥是否已读取。

## 三、页面与原脚本对照

| 页面 | 功能 | 整合的原脚本 |
|---|---|---|
| 🏠 总览 | 所有品种快照：近 1 月 / 3 月 / 今年 / 1 年涨幅、距高点、RSI、近一年走势小图、收益对比；点击行直接进入单品种分析 | — |
| 📥 数据中心 · ETF/A股 | TickFlow 批量下载日线，前复权 / 后复权 / 不复权，可选"成立以来" | ETFdataget.py、ETFdataget-后复权.py、datagetfree.py |
| 📥 数据中心 · 美股 | 自动加 `.US` 后缀，前复权 | tickflow_USdata_fetcher.py |
| 📥 数据中心 · 场外基金 | 东财接口抓全部历史或最新净值，支持批量 | fund_complete_data_get.py、批量脚本/jjjz.py |
| 📥 数据中心 · 微盘股 | BK1158（可改板块）按总市值取最小 N 只 | wpg.py、wpg30.py |
| 🔍 单品种 · 滚动年化 & 回撤 | 价格与回撤、1/2/3/5 年滚动年化、最大 5 次回撤波段、年度涨幅与年内回撤、全部回撤波段明细 | fund_3-Year Rolling…、fund_analysis_gui_fixed.py、ETF-3-Year Rolling…、批量脚本/3yearsanddrawdown.py |
| 🔍 单品种 · 均线 | 任选 5/10/20/30/60/120/250 日均线、偏离度、多空排列判断 | fund_20&60&120&250day_moving_average.py |
| 🔍 单品种 · RSI | RSI(14) 与价格百分位仪表盘、20/60 日涨幅、波动率、YTD、自定义基准日涨幅 | fund_RSI&percentile_analyzer.py |
| 🌐 指数 MA 偏离率 | 8 个指数 MA20（可改）偏离率横向对比、走势、小图矩阵，分列 CSV 导出 | 指数MA20分析工具_分列版.py |
| 🌐 期货价差 | 多合约收盘价与价差走势、均值、分位、Z 值 | Futures_Spread_Analysis.py |
| 🔁 轮动回测 · 多基金 | 前 N 名等权、周/月调仓、滑点、手续费、整手；夏普/索提诺/卡玛/月胜率；月度热力图 | fund_rotation_tool_v4.py |
| 🔁 轮动回测 · 双标的 | 每周一按动量二选一，可用本地文件或在线拉后复权数据 | donglianglhcv2.py |
| 🏆 SPMO 选基 | 标准 12-1 月 / 三周期等权 / 40-35-25 加权，附 RSI 状态与建议权重 | SPMO.py、SPMO近一年.py、SPMO多周期.py、SPMO多周期403525加权.py、SPMO+RSI.py |
| ⚙️ 设置 | 修改数据文件夹、报告输出文件夹，查看密钥状态 | — |

`stock_data/rename.py` 里的代码-名称对照表已经内置，文件名或数据里带 6 位代码时会自动显示基金名称。

## 四、数据文件

- 数据文件夹默认是上一级的 `stock_data`，可在「设置」页修改（保存在本地 `settings.json`，不会上传）
- 自动识别列名：TickFlow 的 `trade_date / close / open / high / low`，东财的 `日期 / 累计净值`，以及含"收盘""净值"的列
- 每个选择器旁边都有「上传文件」，可以直接把 CSV / Excel 拖进数据文件夹
- 结果区有 Excel / CSV 下载按钮，图表右上角可以保存图片；回测页可一键把报告存到 `output` 文件夹

## 五、目录结构

```
server.py        FastAPI 服务入口（接口 + 静态页面）
api.py           业务逻辑层：把计算结果整理成 JSON / Excel
core/            计算核心（与界面无关，和原脚本逐一核对过）
  analytics.py   滚动年化、回撤、均线、RSI、SPMO
  backtest.py    多基金轮动 v4、双标的动量轮动
  fetchers.py    TickFlow / 东方财富 / AkShare 数据获取
  io.py          CSV / Excel 读取与列名识别
  config.py      路径、密钥读取、代码名称映射
static/          前端：index.html、css/、js/、vendor/echarts.min.js（已打包，可离线使用）
```

## 六、和原脚本的结果差异（已核对）

- **滚动年化收益**：结果与原脚本完全一致，算法改成了向量化，计算更快
- **多基金轮动 v4**：用 512890 + 159915 实测，逐日净值与原引擎完全一致（期末 549,408.85）
- **SPMO 三种评分**：6 只 ETF 的得分与原脚本逐一一致。改动两处：① 原脚本不认识 TickFlow 数据的 `close` 列，现在能识别；② 负分品种的建议权重记为 0（原脚本可能算出负权重）
- **双标的动量轮动**：修正了原脚本换仓日忽略旧持仓"上周五收盘 → 周一开盘"跳空的问题，结果会和原脚本略有不同
- **数据下载日期**：原 ETFdataget 的毫秒时间戳多加了 8 小时，可能漏掉开始日当天的数据，已修正

## 七、常见问题

- **akshare 安装失败**：Python 3.14 较新，akshare 的个别依赖可能还没适配。只影响「指数与期货」页，其他页面照常可用
- **页面打不开**：确认黑色窗口还开着，并按窗口里显示的地址访问
- **东财接口失败**：检查网络或代理设置后重试

数据仅供研究参考，不构成投资建议。
