# -*- coding: utf-8 -*-
"""全局配置：路径、密钥、配色、代码名称映射"""
import os
from pathlib import Path

# 面板所在目录 & 原脚本根目录（dashboard 的上一级）
DASHBOARD_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = DASHBOARD_DIR.parent
DEFAULT_DATA_DIR = SCRIPTS_DIR / "stock_data"
DEFAULT_OUTPUT_DIR = DASHBOARD_DIR / "output"


def get_tickflow_key() -> str:
    """API 密钥只从环境变量读取，不在代码里明文保存。"""
    return os.environ.get("TICKFLOW_API_KEY", "").strip()


# ---------- 浅色简洁风配色 ----------
PRIMARY = "#2563EB"      # 主色：蓝
UP = "#E5484D"           # A股习惯：涨 = 红
DOWN = "#12A150"         # 跌 = 绿
MUTED = "#64748B"
GRID = "#EEF1F6"
PALETTE = ["#2563EB", "#F59E0B", "#10B981", "#8B5CF6", "#EF4444",
           "#06B6D4", "#EC4899", "#84CC16", "#F97316", "#0EA5E9"]

# ---------- 常用 ETF / 基金代码 -> 名称（来自 stock_data/rename.py） ----------
FUND_MAPPING = {
    "159201": "自由现金流ETF华夏", "159501": "纳指ETF嘉实", "159545": "恒生红利低波ETF易方达",
    "159655": "标普500ETF华夏", "159915": "创业板ETF易方达", "510500": "中证500ETF南方",
    "510880": "红利ETF华泰柏瑞", "511360": "短融ETF海富通", "512100": "中证1000ETF南方",
    "512890": "红利低波ETF华泰柏瑞", "513100": "纳指ETF国泰", "513130": "恒生科技ETF华泰柏瑞",
    "513260": "恒生科技ETF汇添富", "518800": "黄金ETF国泰", "518850": "黄金ETF华夏",
}

# 指数 MA20 工具的默认指数池（来自 指数MA20分析工具_分列版.py）
INDEX_CONFIG = {
    "沪深300": "000300.SH",
    "创业板指": "399006.SZ",
    "中证500": "000905.SH",
    "中证1000": "000852.SH",
    "中证红利低波": {"source": "akshare_csindex", "code": "H30269"},
    "国证自由现金流": "980092.SZ",
    "标普500": {"source": "akshare_us", "code": ".INX"},
    "纳斯达克综合": {"source": "akshare_us", "code": ".IXIC"},
}

# 期货品种前缀 -> 名称（来自 Futures_Spread_Analysis.py）
CONTRACT_PREFIXES = {
    'IC': '中证500股指', 'IF': '沪深300股指', 'IH': '上证50股指', 'IM': '中证1000股指',
    'TL': '30年国债', 'T': '10年国债', 'TF': '5年国债', 'TS': '2年国债',
    'CU': '沪铜', 'AL': '沪铝', 'ZN': '沪锌', 'PB': '沪铅', 'NI': '沪镍', 'SN': '沪锡',
    'AU': '沪金', 'AG': '沪银', 'RB': '螺纹钢', 'WR': '线材', 'HC': '热轧卷板', 'SS': '不锈钢',
    'BU': '沥青', 'RU': '天然橡胶', 'SP': '纸浆', 'FU': '燃油', 'LU': '低硫燃油', 'PG': '液化石油气',
    'M': '豆粕', 'Y': '豆油', 'P': '棕榈油', 'C': '玉米', 'CS': '玉米淀粉', 'A': '豆一', 'B': '豆二',
    'L': '聚乙烯', 'V': '聚氯乙烯', 'PP': '聚丙烯', 'J': '焦炭', 'JM': '焦煤', 'I': '铁矿石',
    'EG': '乙二醇', 'EB': '苯乙烯', 'CF': '棉花', 'SR': '白糖', 'TA': 'PTA', 'MA': '甲醇',
    'FG': '玻璃', 'RM': '菜籽粕', 'OI': '菜籽油', 'SF': '硅铁', 'SM': '锰硅', 'AP': '苹果',
    'CJ': '红枣', 'SA': '纯碱', 'PX': '对二甲苯', 'SI': '工业硅', 'LC': '碳酸锂',
}
