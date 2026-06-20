#!/usr/bin/env python3
"""
测试 Tushare PE 数据来源
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_tushare_pe(symbol):
    """测试 Tushare PE 数据"""
    logger.info(f"🔍 测试股票 {symbol} 的 Tushare PE 数据")
    
    try:
        # 初始化 Tushare Provider
        from tradingagents.dataflows.providers.china.tushare import TushareProvider
        
        provider = TushareProvider()
        
        # 同步连接
        connected = provider.connect_sync()
        if not connected:
            logger.error("❌ Tushare 连接失败")
            return
        
        logger.info(f"✅ Tushare 连接成功")
        
        # 获取财务数据
        import asyncio
        financial_data = asyncio.run(provider.get_financial_data(symbol))
        
        if financial_data:
            logger.info(f"\n📊 获取到的财务数据:")
            logger.info(f"   PE: {financial_data.get('pe', 'N/A')}")
            logger.info(f"   PE_TTM: {financial_data.get('pe_ttm', 'N/A')}")
            logger.info(f"   PB: {financial_data.get('pb', 'N/A')}")
            logger.info(f"   PEG: {financial_data.get('peg', 'N/A')}")
            logger.info(f"   总市值: {financial_data.get('total_mv', 'N/A')} 万元")
            logger.info(f"   数据来源: {financial_data.get('data_source', 'N/A')}")
            
            # 显示原始 daily_basic 数据
            if 'raw_data' in financial_data and 'daily_basic' in financial_data['raw_data']:
                daily_basic = financial_data['raw_data']['daily_basic']
                if daily_basic:
                    logger.info(f"\n📋 原始 daily_basic 数据:")
                    for key, value in daily_basic[0].items():
                        logger.info(f"   {key}: {value}")
        
        # 测试 daily_basic 接口
        logger.info(f"\n🔧 直接测试 daily_basic 接口:")
        daily_basic_df = asyncio.run(provider.get_daily_basic('20251225'))
        if daily_basic_df is not None and not daily_basic_df.empty:
            # 查找该股票的数据
            ts_code = f"{symbol}.SZ" if symbol.startswith('0') else f"{symbol}.SH"
            stock_data = daily_basic_df[daily_basic_df['ts_code'] == ts_code]
            if not stock_data.empty:
                logger.info(f"✅ 找到 {ts_code} 的 daily_basic 数据:")
                for col in stock_data.columns:
                    logger.info(f"   {col}: {stock_data[col].iloc[0]}")
            else:
                logger.warning(f"⚠️ 未在 daily_basic 中找到 {ts_code}")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python scripts/test_tushare_pe.py <股票代码>")
        sys.exit(1)
    
    symbol = sys.argv[1]
    test_tushare_pe(symbol)
