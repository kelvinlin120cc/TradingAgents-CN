"""
实时估值指标计算模块
基于实时行情和财务数据计算PE/PB等指标
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def calculate_realtime_pe_pb(
    symbol: str,
    db_client=None
) -> Optional[Dict[str, Any]]:
    """
    基于实时行情和 Tushare TTM 数据计算动态 PE/PB

    计算逻辑：
    1. 从 stock_basic_info 获取 Tushare 的 pe_ttm（基于昨日收盘价）
    2. 反推 TTM 净利润 = 总市值 / pe_ttm
    3. 使用实时股价计算实时市值
    4. 计算动态 PE_TTM = 实时市值 / TTM 净利润

    Args:
        symbol: 6位股票代码
        db_client: MongoDB客户端（可选，用于同步调用）

    Returns:
        {
            "pe": 22.5,              # 动态市盈率（基于 TTM）
            "pb": 3.2,               # 动态市净率
            "pe_ttm": 23.1,          # 动态市盈率（TTM）
            "price": 11.0,           # 当前价格
            "market_cap": 110.5,     # 实时市值（亿元）
            "ttm_net_profit": 4.8,   # TTM 净利润（亿元，从 Tushare 反推）
            "updated_at": "2025-10-14T10:30:00",
            "source": "realtime_calculated",
            "is_realtime": True
        }
        如果计算失败返回 None
    """
    try:
        # 获取数据库连接（确保是同步客户端）
        if db_client is None:
            from tradingagents.config.database_manager import get_database_manager
            db_manager = get_database_manager()
            if not db_manager.is_mongodb_available():
                logger.debug("MongoDB不可用，无法计算实时PE/PB")
                return None
            db_client = db_manager.get_mongodb_client()

        # 检查是否是异步客户端（AsyncIOMotorClient）
        # 如果是异步客户端，需要转换为同步客户端
        client_type = type(db_client).__name__
        if 'AsyncIOMotorClient' in client_type or 'Motor' in client_type:
            # 这是异步客户端，创建同步客户端
            from pymongo import MongoClient
            from app.core.config import settings
            logger.debug(f"检测到异步客户端 {client_type}，转换为同步客户端")
            db_client = MongoClient(settings.MONGO_URI)

        db = db_client['tradingagents']
        code6 = str(symbol).zfill(6)

        logger.info(f"🔍 [实时PE计算] 开始计算股票 {code6}")

        # 1. 获取实时行情（market_quotes）
        quote = db.market_quotes.find_one({"code": code6})
        if not quote:
            logger.warning(f"⚠️ [实时PE计算-失败] 未找到股票 {code6} 的实时行情数据")
            return None

        realtime_price = quote.get("close")
        pre_close = quote.get("pre_close")  # 昨日收盘价
        quote_updated_at = quote.get("updated_at", "N/A")

        if not realtime_price or realtime_price <= 0:
            logger.warning(f"⚠️ [实时PE计算-失败] 股票 {code6} 的实时价格无效: {realtime_price}")
            return None

        logger.info(f"   ✓ 实时股价: {realtime_price}元 (更新时间: {quote_updated_at})")
        logger.info(f"   ✓ 昨日收盘价: {pre_close}元")

        # 2. 获取估值指标 - 优先从 stock_financial_data（Tushare financial_sync 写入，含 pe_ttm/pb/total_mv）
        #    如果没有，再从 stock_basic_info 查询（可能由其他同步写入）
        #    注意：stock_basic_info 仅含代码/名称/行业等基础信息，不含 pe_ttm
        logger.info(f"🔍 [MongoDB查询] 查询条件: code={code6}, data_source=tushare")

        # 2a: 优先从 stock_financial_data 获取估值指标
        fin_data = db.stock_financial_data.find_one(
            {"code": code6, "data_source": "tushare"},
            sort=[("updated_at", -1)]
        )
        if not fin_data:
            fin_data = db.stock_financial_data.find_one(
                {"symbol": code6, "data_source": "tushare"},
                sort=[("updated_at", -1)]
            )

        # 2b: 如果 stock_financial_data 没有，再从 stock_basic_info 查询
        basic_info = None
        if not fin_data:
            logger.info(f"   stock_financial_data 未找到 {code6} 的数据，尝试 stock_basic_info")
            basic_info = db.stock_basic_info.find_one({"code": code6, "source": "tushare"})
            if not basic_info:
                basic_info = db.stock_basic_info.find_one({"code": code6})

        # 合并数据源：优先使用 stock_financial_data，降级到 stock_basic_info
        valuation_source = fin_data or basic_info
        if not valuation_source:
            logger.warning(f"⚠️ [动态PE计算-失败] 未找到股票 {code6} 的估值数据")
            logger.warning(f"   建议: 运行 Tushare 数据同步任务，确保 stock_financial_data 集合有数据")
            return None

        data_source_name = "stock_financial_data" if fin_data else "stock_basic_info"
        logger.info(f"   ✓ 使用数据源: {data_source_name}")

        # 获取估值指标（从 valuation_source 统一读取）
        # stock_financial_data 中 total_mv 单位是万元，需转为亿元
        # stock_basic_info 中 total_mv 可能已经是亿元
        pe_ttm_tushare = valuation_source.get("pe_ttm")
        pe_tushare = valuation_source.get("pe")
        pb_tushare = valuation_source.get("pb")
        raw_total_mv = valuation_source.get("total_mv")
        total_share = valuation_source.get("total_share")  # 总股本（万股）
        valuation_updated_at = valuation_source.get("updated_at")  # 更新时间

        # 处理 total_mv 单位差异
        # stock_financial_data: total_mv 单位是万元 → 转为亿元
        # stock_basic_info: total_mv 可能是亿元
        if raw_total_mv and raw_total_mv > 0:
            if fin_data:
                # stock_financial_data 的 total_mv 单位是万元
                total_mv_yi = raw_total_mv / 10000  # 万元 → 亿元
            else:
                # stock_basic_info 的 total_mv 可能已经是亿元
                total_mv_yi = raw_total_mv
        else:
            total_mv_yi = None

        # 如果 stock_financial_data 没有 total_share，尝试从 stock_basic_info 获取
        if not total_share and basic_info:
            total_share = basic_info.get("total_share")
            if not total_mv_yi:
                raw_mv = basic_info.get("total_mv")
                if raw_mv and raw_mv > 0:
                    total_mv_yi = raw_mv  # stock_basic_info 的 total_mv 可能是亿元

        logger.info(f"   ✓ Tushare PE_TTM: {pe_ttm_tushare}倍 (来源: {data_source_name})")
        logger.info(f"   ✓ Tushare PE: {pe_tushare}倍")
        logger.info(f"   ✓ Tushare 总市值: {total_mv_yi}亿元")
        logger.info(f"   ✓ 总股本: {total_share}万股")
        logger.info(f"   ✓ 数据更新时间: {valuation_updated_at}")

        # 🔥 3. 判断是否需要重新计算市值
        # 如果估值数据的更新时间在今天收盘后（15:00之后），说明数据已经是最新的
        from datetime import datetime, time as dtime
        from zoneinfo import ZoneInfo

        need_recalculate = True
        if valuation_updated_at:
            # 确保时间带有时区信息
            if isinstance(valuation_updated_at, datetime):
                if valuation_updated_at.tzinfo is None:
                    valuation_updated_at = valuation_updated_at.replace(tzinfo=ZoneInfo("Asia/Shanghai"))

                # 获取今天的日期
                today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
                update_date = valuation_updated_at.date()
                update_time = valuation_updated_at.time()

                # 如果更新日期是今天，且更新时间在15:00之后，说明数据已经是今天收盘后的最新数据
                if update_date == today and update_time >= dtime(15, 0):
                    need_recalculate = False
                    logger.info(f"   💡 估值数据已在今天收盘后更新，直接使用其数据")

        if not need_recalculate:
            # 直接使用估值数据，不需要重新计算
            logger.info(f"   ✓ 使用 {data_source_name} 的最新数据（无需重新计算）")
            
            # 🔥 修复：优先使用 PE_TTM 而不是静态 PE
            pe_to_use = round(pe_ttm_tushare, 2) if pe_ttm_tushare else (round(pe_tushare, 2) if pe_tushare else None)

            result = {
                "pe": pe_to_use,
                "pb": round(pb_tushare, 2) if pb_tushare else None,
                "pe_ttm": round(pe_ttm_tushare, 2) if pe_ttm_tushare else None,
                "price": round(realtime_price, 2),
                "market_cap": round(total_mv_yi, 2) if total_mv_yi else None,
                "updated_at": quote.get("updated_at"),
                "source": f"{data_source_name}_latest",
                "is_realtime": False,
                "note": f"使用{data_source_name}收盘后最新数据，优先使用PE_TTM",
            }

            logger.info(f"✅ [动态PE计算-成功] 股票 {code6}: PE={result['pe']}倍 (使用PE_TTM={pe_ttm_tushare}或PE={pe_tushare}), PB={result['pb']}倍 (来自{data_source_name})")
            return result

        # 4. 🔥 计算总股本（需要判断估值数据的市值是昨天的还是今天的）
        total_shares_wan = None
        yesterday_mv_yi = None

        # 方案1：优先使用估值数据中的 total_share（如果有）
        if total_share and total_share > 0:
            total_shares_wan = total_share
            logger.info(f"   ✓ 使用 total_share: {total_shares_wan:.2f}万股")

            # 计算昨日市值 = 总股本 × 昨日收盘价
            if pre_close and pre_close > 0:
                yesterday_mv_yi = (total_shares_wan * pre_close) / 10000
                logger.info(f"   ✓ 昨日市值: {total_shares_wan:.2f}万股 × {pre_close:.2f}元 / 10000 = {yesterday_mv_yi:.2f}亿元")
            elif total_mv_yi and total_mv_yi > 0:
                yesterday_mv_yi = total_mv_yi
                logger.info(f"   ⚠️ market_quotes 中无 pre_close，使用估值数据市值作为昨日市值: {yesterday_mv_yi:.2f}亿元")
            else:
                logger.warning(f"⚠️ [动态PE计算-失败] 无法获取昨日市值: pre_close={pre_close}, total_mv={total_mv_yi}")
                return None

        # 方案2：使用 market_quotes 的 pre_close（昨日收盘价）反推股本
        elif pre_close and pre_close > 0 and total_mv_yi and total_mv_yi > 0:
            # 判断估值数据是否是昨天的数据
            is_yesterday_data = True
            if valuation_updated_at and isinstance(valuation_updated_at, datetime):
                if valuation_updated_at.tzinfo is None:
                    valuation_updated_at = valuation_updated_at.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
                update_date = valuation_updated_at.date()
                update_time = valuation_updated_at.time()
                if update_date == today and update_time >= dtime(15, 0):
                    is_yesterday_data = False

            if is_yesterday_data:
                total_shares_wan = (total_mv_yi * 10000) / pre_close
                yesterday_mv_yi = total_mv_yi
                logger.info(f"   ✓ 估值数据是昨天的，用 pre_close 反推总股本: {total_mv_yi:.2f}亿元 / {pre_close:.2f}元 = {total_shares_wan:.2f}万股")
            else:
                total_shares_wan = (total_mv_yi * 10000) / realtime_price
                yesterday_mv_yi = (total_shares_wan * pre_close) / 10000
                logger.info(f"   ✓ 估值数据是今天的，用 realtime_price 反推总股本: {total_mv_yi:.2f}亿元 / {realtime_price:.2f}元 = {total_shares_wan:.2f}万股")
                logger.info(f"   ✓ 昨日市值: {total_shares_wan:.2f}万股 × {pre_close:.2f}元 / 10000 = {yesterday_mv_yi:.2f}亿元")

        # 方案3：只有 total_mv_yi，没有 pre_close（market_quotes 数据不完整）
        elif total_mv_yi and total_mv_yi > 0:
            total_shares_wan = (total_mv_yi * 10000) / realtime_price
            yesterday_mv_yi = total_mv_yi
            logger.warning(f"   ⚠️ market_quotes 中无 pre_close，假设估值数据中的 total_mv 是昨日市值")
            logger.info(f"   ✓ 用 realtime_price 反推总股本: {total_mv_yi:.2f}亿元 / {realtime_price:.2f}元 = {total_shares_wan:.2f}万股")
            logger.info(f"   ✓ 昨日市值（假设）: {yesterday_mv_yi:.2f}亿元")

        # 方案4：如果都没有，无法计算
        else:
            logger.warning(f"⚠️ [动态PE计算-失败] 无法获取总股本数据")
            logger.warning(f"   - total_share: {total_share}")
            logger.warning(f"   - pre_close: {pre_close}")
            logger.warning(f"   - total_mv: {total_mv_yi}")
            return None

        # 5. 从 Tushare pe_ttm 反推 TTM 净利润（使用昨日市值）

        if not pe_ttm_tushare or pe_ttm_tushare <= 0 or not yesterday_mv_yi or yesterday_mv_yi <= 0:
            logger.warning(f"⚠️ [动态PE计算-失败] 无法反推TTM净利润: pe_ttm={pe_ttm_tushare}, yesterday_mv={yesterday_mv_yi}")
            logger.warning(f"   💡 提示: 可能是亏损股票（PE为负或空）")
            return None

        # 反推 TTM 净利润（亿元）= 昨日市值 / PE_TTM
        ttm_net_profit_yi = yesterday_mv_yi / pe_ttm_tushare
        logger.info(f"   ✓ 反推 TTM净利润: {yesterday_mv_yi:.2f}亿元 / {pe_ttm_tushare:.2f}倍 = {ttm_net_profit_yi:.2f}亿元")

        # 6. 计算实时市值（亿元）= 总股本（万股）× 实时股价（元）/ 10000
        realtime_mv_yi = (realtime_price * total_shares_wan) / 10000
        logger.info(f"   ✓ 实时市值: {realtime_price:.2f}元 × {total_shares_wan:.2f}万股 / 10000 = {realtime_mv_yi:.2f}亿元")

        # 7. 计算动态 PE_TTM = 实时市值 / TTM净利润
        dynamic_pe_ttm = realtime_mv_yi / ttm_net_profit_yi
        logger.info(f"   ✓ 动态PE_TTM计算: {realtime_mv_yi:.2f}亿元 / {ttm_net_profit_yi:.2f}亿元 = {dynamic_pe_ttm:.2f}倍")

        # 8. 获取财务数据（用于计算 PB）
        financial_data = db.stock_financial_data.find_one({"code": code6}, sort=[("report_period", -1)])
        pb = None
        total_equity_yi = None

        if financial_data:
            total_equity = financial_data.get("total_equity")  # 净资产（元）
            if total_equity and total_equity > 0:
                total_equity_yi = total_equity / 100000000  # 转换为亿元
                pb = realtime_mv_yi / total_equity_yi
                logger.info(f"   ✓ 动态PB计算: {realtime_mv_yi:.2f}亿元 / {total_equity_yi:.2f}亿元 = {pb:.2f}倍")
            else:
                logger.warning(f"   ⚠️ PB计算失败: 净资产无效 ({total_equity})")
        else:
            logger.warning(f"   ⚠️ 未找到财务数据，无法计算PB")
            # 使用 Tushare 的 PB 作为降级
            if pb_tushare:
                pb = pb_tushare
                logger.info(f"   ✓ 使用 Tushare PB: {pb}倍")

        # 9. 构建返回结果
        result = {
            "pe": round(dynamic_pe_ttm, 2),  # 动态PE（基于TTM）
            "pb": round(pb, 2) if pb else None,
            "pe_ttm": round(dynamic_pe_ttm, 2),  # 动态PE_TTM
            "price": round(realtime_price, 2),
            "market_cap": round(realtime_mv_yi, 2),  # 实时市值（亿元）
            "ttm_net_profit": round(ttm_net_profit_yi, 2),  # TTM净利润（亿元）
            "updated_at": quote.get("updated_at"),
            "source": "realtime_calculated_from_market_quotes",
            "is_realtime": True,
            "note": "基于market_quotes实时股价和pre_close计算",
            "total_shares": round(total_shares_wan, 2),  # 总股本（万股）
            "yesterday_close": round(pre_close, 2) if pre_close else None,  # 昨日收盘价（参考）
            "tushare_pe_ttm": round(pe_ttm_tushare, 2),  # Tushare PE_TTM（参考）
            "tushare_pe": round(pe_tushare, 2) if pe_tushare else None,  # Tushare PE（参考）
        }

        logger.info(f"✅ [动态PE计算-成功] 股票 {code6}: 动态PE_TTM={result['pe_ttm']}倍, PB={result['pb']}倍")
        return result
        
    except Exception as e:
        logger.error(f"计算股票 {symbol} 的实时PE/PB失败: {e}", exc_info=True)
        return None


def validate_pe_pb(pe: Optional[float], pb: Optional[float]) -> bool:
    """
    验证PE/PB是否在合理范围内
    
    Args:
        pe: 市盈率
        pb: 市净率
    
    Returns:
        bool: 是否合理
    """
    # PE合理范围：-100 到 1000（允许负值，因为亏损企业PE为负）
    if pe is not None and (pe < -100 or pe > 1000):
        logger.warning(f"PE异常: {pe}")
        return False
    
    # PB合理范围：0.1 到 100
    if pb is not None and (pb < 0.1 or pb > 100):
        logger.warning(f"PB异常: {pb}")
        return False
    
    return True


def get_pe_pb_with_fallback(
    symbol: str,
    db_client=None
) -> Dict[str, Any]:
    """
    获取PE/PB，智能降级策略

    策略：
    1. 优先使用动态 PE（基于实时股价 + Tushare TTM 净利润）
    2. 如果动态计算失败，降级到 Tushare 静态 PE（基于昨日收盘价）

    优势：
    - 动态 PE 能反映实时股价变化
    - 使用 Tushare 官方 TTM 净利润（反推），避免单季度数据错误
    - 计算准确，日志详细

    Args:
        symbol: 6位股票代码
        db_client: MongoDB客户端（可选）

    Returns:
        {
            "pe": 22.5,              # 市盈率
            "pb": 3.2,               # 市净率
            "pe_ttm": 23.1,          # 市盈率（TTM）
            "pb_mrq": 3.3,           # 市净率（MRQ）
            "source": "realtime_calculated_from_tushare_ttm" | "daily_basic",
            "is_realtime": True | False,
            "updated_at": "2025-10-14T10:30:00",
            "ttm_net_profit": 4.8    # TTM净利润（亿元，仅动态计算时有）
        }
    """
    logger.info(f"🔄 [PE智能策略] 开始获取股票 {symbol} 的PE/PB")

    # 准备数据库连接
    try:
        if db_client is None:
            from tradingagents.config.database_manager import get_database_manager
            db_manager = get_database_manager()
            if not db_manager.is_mongodb_available():
                logger.error("❌ [PE智能策略-失败] MongoDB不可用")
                return {}
            db_client = db_manager.get_mongodb_client()

        # 检查是否是异步客户端
        client_type = type(db_client).__name__
        if 'AsyncIOMotorClient' in client_type or 'Motor' in client_type:
            from pymongo import MongoClient
            from app.core.config import settings
            logger.debug(f"检测到异步客户端 {client_type}，转换为同步客户端")
            db_client = MongoClient(settings.MONGO_URI)

    except Exception as e:
        logger.error(f"❌ [PE智能策略-失败] 数据库连接失败: {e}")
        return {}

    # 1. 优先使用动态 PE 计算（基于实时股价 + Tushare TTM）
    logger.info("   → 尝试方案1: 动态PE计算 (实时股价 + Tushare TTM净利润)")
    logger.info("   💡 说明: 使用实时股价和Tushare官方TTM净利润，准确反映当前估值")

    realtime_metrics = calculate_realtime_pe_pb(symbol, db_client)
    if realtime_metrics:
        # 验证数据合理性
        pe = realtime_metrics.get('pe')
        pb = realtime_metrics.get('pb')
        if validate_pe_pb(pe, pb):
            logger.info(f"✅ [PE智能策略-成功] 使用动态PE: PE={pe}, PB={pb}")
            logger.info(f"   └─ 数据来源: {realtime_metrics.get('source')}")
            logger.info(f"   └─ TTM净利润: {realtime_metrics.get('ttm_net_profit')}亿元 (从Tushare反推)")
            return realtime_metrics
        else:
            logger.warning(f"⚠️ [PE智能策略-方案1异常] 动态PE/PB超出合理范围 (PE={pe}, PB={pb})")

    # 2. 降级到数据库中的 Tushare 估值数据（基于昨日收盘价）
    logger.info("   → 尝试方案2: 从数据库获取Tushare估值数据")
    logger.info("   💡 说明: 优先从stock_financial_data获取PE_TTM，降级到stock_basic_info")

    try:
        db = db_client['tradingagents']
        code6 = str(symbol).zfill(6)

        # 2a: 优先从 stock_financial_data 获取估值指标（Tushare financial_sync 写入）
        fin_data = db.stock_financial_data.find_one(
            {"code": code6, "data_source": "tushare"},
            sort=[("updated_at", -1)]
        )
        if not fin_data:
            fin_data = db.stock_financial_data.find_one(
                {"symbol": code6, "data_source": "tushare"},
                sort=[("updated_at", -1)]
            )

        # 2b: 如果 stock_financial_data 没有，再从 stock_basic_info 查询
        basic_info = None
        if not fin_data:
            basic_info = db.stock_basic_info.find_one({"code": code6, "source": "tushare"})
            if not basic_info:
                basic_info = db.stock_basic_info.find_one({"code": code6})

        # 合并数据源
        valuation_source = fin_data or basic_info
        if valuation_source:
            pe_static = valuation_source.get("pe")
            pb_static = valuation_source.get("pb")
            pe_ttm = valuation_source.get("pe_ttm")
            pb_mrq = valuation_source.get("pb_mrq")
            updated_at = valuation_source.get("updated_at", "N/A")
            data_source_name = "stock_financial_data" if fin_data else "stock_basic_info"

            if pe_ttm or pe_static or pb_static:
                # 🔥 修复：优先使用 PE_TTM 而不是静态 PE
                pe_to_use = pe_ttm if pe_ttm else pe_static
                pe_type_used = "PE_TTM" if pe_ttm else "PE(静态)"
                
                logger.info(f"✅ [PE智能策略-成功] 使用Tushare PE: PE={pe_to_use}, 原始PE_TTM={pe_ttm}, 原始PE(静态)={pe_static}")
                logger.info(f"   └─ 选择原因: 优先使用{pe_type_used}以获得更准确的估值指标")
                logger.info(f"   └─ 数据来源: {data_source_name} (更新时间: {updated_at})")

                return {
                    "pe": pe_to_use,
                    "pb": pb_static,
                    "pe_ttm": pe_ttm,
                    "pb_mrq": pb_mrq,
                    "source": data_source_name,
                    "is_realtime": False,
                    "updated_at": updated_at,
                    "note": f"从{data_source_name}获取，优先使用PE_TTM"
                }

        logger.warning("⚠️ [PE智能策略-方案2失败] 数据库中无Tushare估值数据")

    except Exception as e:
        logger.warning(f"⚠️ [PE智能策略-方案2异常] {e}")

    # 3. 最终降级：直接从 Tushare API 获取
    logger.info("   → 尝试方案3: 直接从Tushare API获取PE_TTM")
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
        provider = get_tushare_provider()
        if provider.connected:
            ts_code = f"{code6}.SZ" if code6.startswith(('0', '3')) else f"{code6}.SH"
            daily_basic = provider._run_async(provider.api.daily_basic, ts_code=ts_code, trade_date=datetime.now().strftime('%Y%m%d'), fields='ts_code,pe,pe_ttm,pb')
            if daily_basic is not None and not daily_basic.empty:
                row = daily_basic.iloc[0]
                pe_ttm_api = float(row.get('pe_ttm', 0)) if row.get('pe_ttm') else None
                pe_api = float(row.get('pe', 0)) if row.get('pe') else None
                pb_api = float(row.get('pb', 0)) if row.get('pb') else None

                pe_to_use = pe_ttm_api if pe_ttm_api else pe_api
                if pe_to_use:
                    logger.info(f"✅ [PE智能策略-成功] 从Tushare API获取: PE={pe_to_use}")
                    return {
                        "pe": pe_to_use,
                        "pb": pb_api,
                        "pe_ttm": pe_ttm_api,
                        "source": "tushare_api",
                        "is_realtime": False,
                        "updated_at": datetime.now().isoformat(),
                        "note": "从Tushare API直接获取，优先使用PE_TTM"
                    }
    except Exception as e:
        logger.warning(f"⚠️ [PE智能策略-方案3异常] Tushare API获取失败: {e}")

    logger.error(f"❌ [PE智能策略-全部失败] 无法获取股票 {symbol} 的PE/PB")
    return {}

