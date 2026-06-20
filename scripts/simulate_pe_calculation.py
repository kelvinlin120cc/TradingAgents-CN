#!/usr/bin/env python3
"""
模拟 PE 计算，检查 002463 的 PE 来源
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


def simulate_pe_calculation():
    """模拟 PE 计算流程"""
    
    # 假设 Tushare 返回的原始数据
    tushare_data = {
        'pe': 194.0,      # Tushare 返回的静态 PE（可能是基于某个季度的每股收益）
        'pe_ttm': 63.03,  # Tushare 返回的 TTM PE
        'pb': 6.78,       # Tushare 返回的 PB
        'total_mv': 802.45,  # 总市值（亿元）
        'circ_mv': 790.12,   # 流通市值（亿元）
        'total_share': 191334.29,  # 总股本（万股）
    }
    
    # 假设实时行情数据
    quote_data = {
        'close': 41.95,   # 当前股价
        'pre_close': 41.70,  # 昨日收盘价
    }
    
    logger.info("="*80)
    logger.info("📊 PE 计算模拟 - 002463 沪电股份")
    logger.info("="*80)
    
    logger.info("\n📋 原始数据:")
    logger.info(f"   Tushare PE: {tushare_data['pe']} 倍")
    logger.info(f"   Tushare PE_TTM: {tushare_data['pe_ttm']} 倍")
    logger.info(f"   Tushare PB: {tushare_data['pb']} 倍")
    logger.info(f"   Tushare 总市值: {tushare_data['total_mv']} 亿元")
    logger.info(f"   Tushare 总股本: {tushare_data['total_share']} 万股")
    logger.info(f"   实时股价: {quote_data['close']} 元")
    logger.info(f"   昨日收盘: {quote_data['pre_close']} 元")
    
    # 方案1：直接使用 Tushare PE（静态）
    logger.info("\n" + "="*80)
    logger.info("📊 方案1: 直接使用 Tushare 静态 PE")
    logger.info("="*80)
    logger.info(f"   PE = {tushare_data['pe']} 倍")
    
    # 方案2：使用 Tushare PE_TTM
    logger.info("\n" + "="*80)
    logger.info("📊 方案2: 直接使用 Tushare PE_TTM")
    logger.info("="*80)
    logger.info(f"   PE_TTM = {tushare_data['pe_ttm']} 倍")
    
    # 方案3：动态计算 PE
    logger.info("\n" + "="*80)
    logger.info("📊 方案3: 动态计算 PE (实时股价 + Tushare TTM净利润)")
    logger.info("="*80)
    
    # 反推 TTM 净利润
    ttm_net_profit = tushare_data['total_mv'] / tushare_data['pe_ttm']
    logger.info(f"   TTM净利润 = 总市值 / PE_TTM = {tushare_data['total_mv']} / {tushare_data['pe_ttm']} = {ttm_net_profit:.2f} 亿元")
    
    # 计算实时市值
    realtime_mv = quote_data['close'] * tushare_data['total_share'] / 10000
    logger.info(f"   实时市值 = 股价 × 总股本 = {quote_data['close']} × {tushare_data['total_share']} / 10000 = {realtime_mv:.2f} 亿元")
    
    # 计算动态 PE
    dynamic_pe = realtime_mv / ttm_net_profit
    logger.info(f"   动态PE = 实时市值 / TTM净利润 = {realtime_mv:.2f} / {ttm_net_profit:.2f} = {dynamic_pe:.2f} 倍")
    
    # 分析：如果 PE = 194，问题可能出在哪里
    logger.info("\n" + "="*80)
    logger.info("🔍 问题分析: 为什么报告中的 PE 是 194 倍？")
    logger.info("="*80)
    
    logger.info("\n📋 可能的原因:")
    
    # 原因1：使用了静态 PE（基于某个季度每股收益）
    logger.info("\n   原因1: 直接使用 Tushare PE (非 TTM)")
    eps_basic = tushare_data['total_mv'] / (tushare_data['pe'] * 10000)  # 亿元
    logger.info(f"   如果使用的是静态 PE {tushare_data['pe']} 倍，说明基于某个季度每股收益")
    logger.info(f"   反推每股收益 = 总市值 / (PE × 10000) = {tushare_data['total_mv']} / ({tushare_data['pe']} × 10000)")
    logger.info(f"   = {eps_basic:.4f} 亿元 = {eps_basic*10000:.2f} 万元")
    
    # 原因2：总股本数据错误
    logger.info("\n   原因2: 总股本数据错误")
    wrong_share = tushare_data['total_mv'] * 10000 / quote_data['close']  # 使用错误 PE 反推
    logger.info(f"   如果 PE = 194，总市值 = {tushare_data['total_mv']}亿，股价 = {quote_data['close']}")
    logger.info(f"   反推需要的总股本 = {tushare_data['total_mv']}亿 × 10000 / {quote_data['close']} = {wrong_share:.2f} 万股")
    logger.info(f"   实际总股本 = {tushare_data['total_share']} 万股")
    
    # 原因3：使用流通市值计算
    logger.info("\n   原因3: 使用流通市值代替总市值")
    float_mv = quote_data['close'] * tushare_data['total_share'] * 0.95 / 10000  # 假设95%流通
    logger.info(f"   如果使用流通市值计算...")
    
    # 原因4：TTM 净利润计算错误
    logger.info("\n   原因4: TTM 净利润数据来源不同")
    logger.info(f"   当前使用的 PE_TTM = {tushare_data['pe_ttm']}，来自 Tushare daily_basic")
    logger.info(f"   但可能 MongoDB 中存储的是不同的 PE 值")
    
    # 最终结论
    logger.info("\n" + "="*80)
    logger.info("📝 结论:")
    logger.info("="*80)
    logger.info(f"   Tushare 原始 PE = {tushare_data['pe']} 倍 ← 这是问题根源！")
    logger.info(f"   Tushare PE_TTM = {tushare_data['pe_ttm']} 倍 ← 这是正确的 TTM PE")
    logger.info(f"   动态计算 PE = {dynamic_pe:.2f} 倍 ← 这是基于实时股价的正确 PE")
    logger.info("")
    logger.info("   ⚠️ 报告中的 PE = 194 倍，很可能是直接使用了 Tushare 的静态 PE")
    logger.info("   ⚠️ 而不是使用 PE_TTM 或动态计算的 PE")
    logger.info("")
    logger.info("   📌 建议修复：在生成报告时，优先使用 PE_TTM 而不是 PE")


if __name__ == "__main__":
    simulate_pe_calculation()
