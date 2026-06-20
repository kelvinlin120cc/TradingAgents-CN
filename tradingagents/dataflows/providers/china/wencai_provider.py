#!/usr/bin/env python3
"""
同花顺问财数据提供器
整合 hithink-astock-selector skill 获取 PE、PB、PEG 等估值数据
"""

import os
import sys
import json
import secrets
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..base_provider import BaseStockDataProvider

logger = None


def _get_logger():
    global logger
    if logger is None:
        try:
            from tradingagents.utils.logging_manager import get_logger
            logger = get_logger('dataflow.wencai')
        except Exception:
            import logging
            logger = logging.getLogger('wencai_provider')
    return logger


class WencaiAPIError(Exception):
    """API 错误异常类"""
    def __init__(self, message: str, status_code: int = None, response: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class WencaiProvider(BaseStockDataProvider):
    """
    同花顺问财数据提供器
    通过 hithink-astock-selector skill 获取股票估值数据
    """
    
    SKILL_NAME = "hithink-astock-selector"
    SKILL_VERSION = "1.0.0"
    API_URL = "https://openapi.iwencai.com/v1/query2data"
    
    def __init__(self):
        super().__init__("Wencai")
        self.api_key = None
        self._load_api_key()
    
    def _load_api_key(self):
        """加载问财 API Key，优先级：环境变量 > skill config.json"""
        # 1. 优先从环境变量获取
        self.api_key = os.environ.get("IWENCAI_API_KEY", "")
        
        # 2. 如果环境变量没有，尝试从 skill 目录的 config.json 读取
        if not self.api_key:
            skill_config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "skills", "hithink-astock-selector", "config.json"
            )
            if os.path.exists(skill_config_path):
                try:
                    with open(skill_config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                        self.api_key = config.get("api_key", "").strip()
                except Exception:
                    pass
        
        # 3. 如果还是没有，尝试从数据库获取
        if not self.api_key:
            try:
                from app.core.database import get_mongo_db_sync
                db = get_mongo_db_sync()
                config_collection = db.system_configs
                config_data = config_collection.find_one(
                    {"is_active": True},
                    sort=[("version", -1)]
                )
                if config_data and config_data.get('data_source_configs'):
                    for ds_config in config_data['data_source_configs']:
                        if ds_config.get('type') == 'wencai':
                            self.api_key = ds_config.get('api_key', '')
                            break
            except Exception:
                pass
        
        if self.api_key:
            log = _get_logger()
            if self.api_key != "your-api-key":
                log.info(f"✅ 问财 API Key 已加载 (长度: {len(self.api_key)})")
            else:
                log.warning("⚠️ 问财 API Key 为占位符")
        else:
            _get_logger().warning("⚠️ 问财 API Key 未配置")
    
    @property
    def connected(self) -> bool:
        """检查是否已配置有效的 API Key"""
        return bool(self.api_key and self.api_key != "your-api-key")
    
    def _generate_trace_id(self) -> str:
        """生成 64 字符十六进制全局唯一追踪 ID"""
        return secrets.token_hex(32)
    
    def _build_headers(self, trace_id: str, call_type: str = "normal") -> dict:
        """构造符合问财网关规范的请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Claw-Call-Type": call_type,
            "X-Claw-Skill-Id": self.SKILL_NAME,
            "X-Claw-Skill-Version": self.SKILL_VERSION,
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": trace_id,
        }
    
    def query(self, query: str, page: str = "1", limit: str = "10", timeout: int = 30) -> Dict:
        """
        调用问财 API 查询
        
        Args:
            query: 查询字符串
            page: 分页参数
            limit: 每页条数
            timeout: 超时时间（秒）
            
        Returns:
            包含 datas、code_count 等字段的字典
        """
        if not self.connected:
            raise WencaiAPIError("问财 API Key 未配置")
        
        trace_id = self._generate_trace_id()
        payload = {
            "query": query,
            "page": page,
            "limit": limit,
            "is_cache": "1",
            "expand_index": "true",
        }
        
        headers = self._build_headers(trace_id)
        request = urllib.request.Request(
            self.API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                result["trace_id"] = trace_id
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise WencaiAPIError(f"HTTP 错误 {e.code}: {e.reason}", status_code=e.code, response=error_body)
        except urllib.error.URLError as e:
            raise WencaiAPIError(f"网络错误: {e.reason}")
    
    async def get_stock_valuation(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票估值数据（PE、PB、PEG等）
        
        Args:
            symbol: 股票代码，如 "002463" 或 "002463.SZ"
            
        Returns:
            包含估值指标的字典，如 {'pe': 25.5, 'pb': 3.2, 'peg': 1.5} 或 None
        """
        # 标准化股票代码
        code = symbol.replace(".SZ", "").replace(".SH", "")
        
        try:
            _get_logger().info(f"🔍 正在从问财获取 {code} 的估值数据...")
            
            # 查询估值指标
            query = f"{code} 市盈率PE 市净率PB PEG 滚动PE"
            result = self.query(query, limit="5", timeout=30)
            
            if "datas" in result and result["datas"]:
                data = result["datas"][0]
                valuation = self._parse_valuation_data(data)
                _get_logger().info(f"✅ 问财获取 {code} 估值成功: PE={valuation.get('pe')}, PB={valuation.get('pb')}, PEG={valuation.get('peg')}")
                return valuation
            else:
                _get_logger().warning(f"⚠️ 问财未返回 {code} 的估值数据")
                return None
                
        except WencaiAPIError as e:
            _get_logger().error(f"❌ 问财获取 {code} 估值失败: {e}")
            return None
        except Exception as e:
            _get_logger().error(f"❌ 问财获取 {code} 估值异常: {e}")
            return None
    
    def _parse_valuation_data(self, data: Dict) -> Dict[str, Any]:
        """
        解析问财返回的估值数据
        
        Args:
            data: 问财返回的单条数据
            
        Returns:
            包含估值指标的字典
        """
        valuation = {}
        
        # 遍历所有字段，查找估值相关指标
        for key, value in data.items():
            if value is None or value == "":
                continue
            
            key_lower = key.lower()
            
            # PE 市盈率
            if any(x in key_lower for x in ["市盈率", "pe", "pe_ttm", "滚动pe"]) and isinstance(value, (int, float)):
                if "pe" not in valuation or valuation["pe"] is None:
                    valuation["pe"] = round(float(value), 2)
            
            # PB 市净率
            if any(x in key_lower for x in ["市净率", "pb", "book"]) and isinstance(value, (int, float)):
                if "pb" not in valuation or valuation["pb"] is None:
                    valuation["pb"] = round(float(value), 2)
            
            # PEG
            if any(x in key_lower for x in ["peg", "净利润增长率", "利润增长率"]) and isinstance(value, (int, float)):
                if "peg" not in valuation or valuation["peg"] is None:
                    valuation["peg"] = round(float(value), 2)
            
            # EPS 每股收益
            if any(x in key_lower for x in ["每股收益", "eps"]) and isinstance(value, (int, float)):
                valuation["eps"] = round(float(value), 4)
            
            # 每股净资产
            if any(x in key_lower for x in ["每股净资产", "bps", "净资产"]) and isinstance(value, (int, float)):
                valuation["bps"] = round(float(value), 4)
        
        return valuation
    
    async def get_financial_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取财务指标数据（兼容旧接口）
        
        Args:
            symbol: 股票代码
            
        Returns:
            包含财务指标的字典
        """
        return await self.get_stock_valuation(symbol)


def get_wencai_provider() -> WencaiProvider:
    """获取问财数据提供器单例"""
    return WencaiProvider()
