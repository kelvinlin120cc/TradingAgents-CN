#!/usr/bin/env python3
"""
检查 002463 的财务数据来源
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


def check_mongodb_data(code: str):
    """检查 MongoDB 中的财务数据"""
    try:
        from pymongo import MongoClient
        from app.core.config import settings
        
        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB]
        
        code6 = str(code).zfill(6)
        logger.info(f"🔍 检查股票 {code6} 的 MongoDB 数据")
        
        # 1. 检查 stock_basic_info
        logger.info("\n" + "="*80)
        logger.info("📋 1. stock_basic_info 集合")
        logger.info("="*80)
        
        basic_info = db.stock_basic_info.find_one({"code": code6})
        if basic_info:
            logger.info(f"✅ 找到数据，数据源: {basic_info.get('source', 'N/A')}")
            logger.info(f"   更新时间: {basic_info.get('updated_at', 'N/A')}")
            logger.info(f"   PE: {basic_info.get('pe', 'N/A')}")
            logger.info(f"   PE_TTM: {basic_info.get('pe_ttm', 'N/A')}")
            logger.info(f"   PB: {basic_info.get('pb', 'N/A')}")
            logger.info(f"   总股本 (total_share): {basic_info.get('total_share', 'N/A')} 万股")
            logger.info(f"   净利润 (net_profit): {basic_info.get('net_profit', 'N/A')} 万元")
            logger.info(f"   市值 (money_cap): {basic_info.get('money_cap', 'N/A')} 万元")
            logger.info(f"   总市值 (total_mv): {basic_info.get('total_mv', 'N/A')} 万元")
            
            # 尝试手动计算 PE
            total_share = basic_info.get('total_share')
            net_profit = basic_info.get('net_profit')
            money_cap = basic_info.get('money_cap')
            
            if money_cap and net_profit and net_profit > 0:
                calculated_pe = money_cap / net_profit
                logger.info(f"\n   📊 手动计算 PE:")
                logger.info(f"   PE = 市值 / 净利润 = {money_cap} / {net_profit} = {calculated_pe:.2f}")
            elif money_cap and net_profit and net_profit < 0:
                logger.info(f"\n   ⚠️ 净利润为负数: {net_profit} 万元（亏损股）")
        else:
            logger.info(f"❌ 未找到数据")
        
        # 2. 检查 stock_financial_data
        logger.info("\n" + "="*80)
        logger.info("📋 2. stock_financial_data 集合")
        logger.info("="*80)
        
        financial_data = db.stock_financial_data.find_one(
            {"code": code6},
            sort=[("report_period", -1)]
        )
        if financial_data:
            logger.info(f"✅ 找到数据，报告期: {financial_data.get('report_period', 'N/A')}")
            logger.info(f"   数据来源: {financial_data.get('data_source', 'N/A')}")
            logger.info(f"   PE: {financial_data.get('pe', 'N/A')}")
            logger.info(f"   PE_TTM: {financial_data.get('pe_ttm', 'N/A')}")
            logger.info(f"   PB: {financial_data.get('pb', 'N/A')}")
            logger.info(f"   净利润 (net_profit): {financial_data.get('net_profit', 'N/A')} 元")
            logger.info(f"   净利润 TTM (net_profit_ttm): {financial_data.get('net_profit_ttm', 'N/A')} 元")
            logger.info(f"   总资产 (total_assets): {financial_data.get('total_assets', 'N/A')} 元")
            logger.info(f"   净资产 (total_equity): {financial_data.get('total_equity', 'N/A')} 元")
            logger.info(f"   股东权益 (total_hldr_eqy_exc_min_int): {financial_data.get('total_hldr_eqy_exc_min_int', 'N/A')} 元")
        else:
            logger.info(f"❌ 未找到数据")
        
        # 3. 检查 market_quotes
        logger.info("\n" + "="*80)
        logger.info("📋 3. market_quotes 集合")
        logger.info("="*80)
        
        quote = db.market_quotes.find_one({"code": code6})
        if quote:
            logger.info(f"✅ 找到数据")
            logger.info(f"   最新价: {quote.get('close', 'N/A')} 元")
            logger.info(f"   昨日收盘: {quote.get('pre_close', 'N/A')} 元")
            logger.info(f"   涨跌幅: {quote.get('pct_chg', 'N/A')}%")
            logger.info(f"   更新时间: {quote.get('updated_at', 'N/A')}")
        else:
            logger.info(f"❌ 未找到数据")
        
        # 4. 手动计算 PE (使用实时价格)
        logger.info("\n" + "="*80)
        logger.info("📊 4. PE 计算验证")
        logger.info("="*80)
        
        if basic_info and quote:
            price = quote.get('close')
            total_share = basic_info.get('total_share')
            net_profit = basic_info.get('net_profit')
            
            if price and total_share:
                market_cap_wan = price * total_share  # 万元
                logger.info(f"   实时股价: {price} 元")
                logger.info(f"   总股本: {total_share} 万股")
                logger.info(f"   计算市值: {market_cap_wan:.2f} 万元 = {market_cap_wan/10000:.2f} 亿元")
                
                if net_profit and net_profit > 0:
                    pe = market_cap_wan / net_profit
                    logger.info(f"   净利润: {net_profit} 万元")
                    logger.info(f"   计算 PE = 市值 / 净利润 = {market_cap_wan:.2f} / {net_profit:.2f} = {pe:.2f}")
                elif net_profit:
                    logger.info(f"   净利润: {net_profit} 万元（可能为负数）")
        
        client.close()
        
    except Exception as e:
        logger.error(f"❌ 检查失败: {e}", exc_info=True)


if __name__ == "__main__":
    check_mongodb_data("002463")
