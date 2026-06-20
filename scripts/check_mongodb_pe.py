#!/usr/bin/env python3
"""
检查 MongoDB 中 002463 的 PE 数据
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)

# 设置 Django 环境
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.core.settings')

import django
django.setup()

from app.core.config import settings
from pymongo import MongoClient


def check_mongodb_pe_data():
    """检查 MongoDB 中的 PE 数据"""
    try:
        client = MongoClient(settings.MONGO_URI)
        db = client['tradingagents']
        
        code6 = "002463"
        logger.info(f"🔍 检查股票 {code6} 的 MongoDB PE 数据")
        
        # 1. 检查 stock_basic_info 集合
        logger.info("\n" + "="*80)
        logger.info("📋 1. stock_basic_info 集合 (Tushare 数据)")
        logger.info("="*80)
        
        basic_info = db.stock_basic_info.find_one({"code": code6, "source": "tushare"})
        if basic_info:
            logger.info(f"✅ 找到 Tushare 数据:")
            logger.info(f"   更新时间: {basic_info.get('updated_at', 'N/A')}")
            logger.info(f"   PE: {basic_info.get('pe', 'N/A')}")
            logger.info(f"   PE_TTM: {basic_info.get('pe_ttm', 'N/A')}")
            logger.info(f"   PB: {basic_info.get('pb', 'N/A')}")
            logger.info(f"   总市值 (total_mv): {basic_info.get('total_mv', 'N/A')} 亿元")
            logger.info(f"   流通市值 (circ_mv): {basic_info.get('circ_mv', 'N/A')} 亿元")
            logger.info(f"   总股本 (total_share): {basic_info.get('total_share', 'N/A')} 万股")
            logger.info(f"   净利润 (net_profit): {basic_info.get('net_profit', 'N/A')} 万元")
            
            # 计算验证
            pe_ttm = basic_info.get('pe_ttm')
            total_mv = basic_info.get('total_mv')
            
            if pe_ttm and total_mv and pe_ttm > 0:
                # 反推 TTM 净利润
                ttm_net_profit_yi = total_mv / pe_ttm
                logger.info(f"\n   📊 计算验证:")
                logger.info(f"   TTM净利润 = 总市值 / PE_TTM = {total_mv}亿 / {pe_ttm} = {ttm_net_profit_yi:.2f}亿元")
        else:
            logger.info(f"❌ 未找到 Tushare 数据")
            
        # 2. 检查 market_quotes 集合
        logger.info("\n" + "="*80)
        logger.info("📋 2. market_quotes 集合")
        logger.info("="*80)
        
        quote = db.market_quotes.find_one({"code": code6})
        if quote:
            logger.info(f"✅ 找到行情数据:")
            logger.info(f"   最新价: {quote.get('close', 'N/A')} 元")
            logger.info(f"   昨日收盘: {quote.get('pre_close', 'N/A')} 元")
            logger.info(f"   更新时间: {quote.get('updated_at', 'N/A')}")
            
            # 计算市值
            if quote.get('close') and basic_info and basic_info.get('total_share'):
                price = quote.get('close')
                total_share = basic_info.get('total_share')
                calculated_mv = price * total_share / 10000
                logger.info(f"\n   📊 计算市值:")
                logger.info(f"   市值 = 股价 × 总股本 = {price}元 × {total_share}万股 / 10000 = {calculated_mv:.2f}亿元")
        else:
            logger.info(f"❌ 未找到行情数据")
        
        # 3. 检查 stock_financial_data 集合
        logger.info("\n" + "="*80)
        logger.info("📋 3. stock_financial_data 集合")
        logger.info("="*80)
        
        financial_data = db.stock_financial_data.find_one(
            {"code": code6},
            sort=[("report_period", -1)]
        )
        if financial_data:
            logger.info(f"✅ 找到财务数据:")
            logger.info(f"   报告期: {financial_data.get('report_period', 'N/A')}")
            logger.info(f"   数据来源: {financial_data.get('data_source', 'N/A')}")
            logger.info(f"   PE: {financial_data.get('pe', 'N/A')}")
            logger.info(f"   PE_TTM: {financial_data.get('pe_ttm', 'N/A')}")
            logger.info(f"   PB: {financial_data.get('pb', 'N/A')}")
            logger.info(f"   净利润 (net_profit): {financial_data.get('net_profit', 'N/A')} 元")
            logger.info(f"   净资产 (total_equity): {financial_data.get('total_equity', 'N/A')} 元")
        else:
            logger.info(f"❌ 未找到财务数据")
        
        # 4. 手动计算 PE 验证
        logger.info("\n" + "="*80)
        logger.info("📊 4. PE 计算验证")
        logger.info("="*80)
        
        if basic_info and quote:
            pe_ttm = basic_info.get('pe_ttm')
            total_mv = basic_info.get('total_mv')
            price = quote.get('close')
            pre_close = quote.get('pre_close')
            
            if pe_ttm and total_mv and price and pre_close:
                # 手动计算动态 PE
                ttm_net_profit = total_mv / pe_ttm  # 亿元
                realtime_mv = price * basic_info.get('total_share', 0) / 10000
                dynamic_pe = realtime_mv / ttm_net_profit if ttm_net_profit > 0 else None
                
                logger.info(f"   Tushare PE_TTM: {pe_ttm} 倍")
                logger.info(f"   总市值: {total_mv} 亿元")
                logger.info(f"   反推 TTM净利润: {ttm_net_profit:.2f} 亿元")
                logger.info(f"   实时股价: {price} 元")
                logger.info(f"   实时市值: {realtime_mv:.2f} 亿元")
                logger.info(f"   计算动态 PE: {realtime_mv:.2f} / {ttm_net_profit:.2f} = {dynamic_pe:.2f} 倍")
        
        # 5. 直接查询所有 002463 的 stock_basic_info 数据
        logger.info("\n" + "="*80)
        logger.info("📋 5. 所有 stock_basic_info 数据")
        logger.info("="*80)
        
        all_basic_info = list(db.stock_basic_info.find({"code": code6}))
        logger.info(f"找到 {len(all_basic_info)} 条记录:")
        for i, info in enumerate(all_basic_info):
            logger.info(f"\n   记录 {i+1}:")
            logger.info(f"   数据源: {info.get('source', 'N/A')}")
            logger.info(f"   更新时间: {info.get('updated_at', 'N/A')}")
            logger.info(f"   PE: {info.get('pe', 'N/A')}")
            logger.info(f"   PE_TTM: {info.get('pe_ttm', 'N/A')}")
            logger.info(f"   PB: {info.get('pb', 'N/A')}")
            logger.info(f"   总市值: {info.get('total_mv', 'N/A')} 亿元")
        
        client.close()
        
    except Exception as e:
        logger.error(f"❌ 检查失败: {e}", exc_info=True)


if __name__ == "__main__":
    check_mongodb_pe_data()
