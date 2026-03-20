# -*- coding: utf-8 -*-
"""
Tiger Broker API 封装

使用 tigeropen SDK 封装常用交易操作：
- 认证连接
- 账户信息（余额、持仓）
- 实时报价
- 下单（市价单、限价单）
- 撤单
- 查询订单状态
"""
import logging
import sys
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/tiger.yaml") -> dict:
    """加载配置文件，找不到时给出友好提示"""
    path = Path(config_path)
    if not path.exists():
        print(f"❌ 配置文件不存在: {path.resolve()}")
        print(f"   请先复制模板并填入你的 API 信息:")
        print(f"   cp config/tiger.yaml.example config/tiger.yaml")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 校验必填字段
    tiger_cfg = cfg.get("tiger", {})
    missing = []
    for key in ("tiger_id", "account", "private_key_path"):
        if not tiger_cfg.get(key):
            missing.append(key)
    if missing:
        print(f"❌ 配置文件缺少必填字段: {', '.join(missing)}")
        print(f"   请编辑 {path.resolve()} 填入对应信息")
        sys.exit(1)

    return cfg


class TigerBroker:
    """Tiger Open API 封装类"""

    def __init__(self, config_path: str = "config/tiger.yaml"):
        self.cfg = load_config(config_path)
        tiger_cfg = self.cfg["tiger"]

        # 延迟导入，方便在没装 tigeropen 时也能看到友好报错
        try:
            from tigeropen.tiger_open_config import TigerOpenClientConfig
            from tigeropen.common.util.signature_utils import read_private_key
            from tigeropen.common.consts import Language
        except ImportError:
            print("❌ 未安装 tigeropen SDK，请先运行:")
            print("   pip install tigeropen")
            sys.exit(1)

        # 构建客户端配置
        is_sandbox = tiger_cfg.get("sandbox", True)
        self._client_config = TigerOpenClientConfig(sandbox_debug=is_sandbox)
        self._client_config.private_key = read_private_key(tiger_cfg["private_key_path"])
        self._client_config.tiger_id = tiger_cfg["tiger_id"]
        self._client_config.account = tiger_cfg["account"]

        # 语言设置
        lang_map = {
            "zh_CN": Language.zh_CN,
            "zh_TW": Language.zh_TW,
            "en_US": Language.en_US,
        }
        self._client_config.language = lang_map.get(tiger_cfg.get("language", "zh_CN"), Language.zh_CN)

        # 初始化交易和行情客户端（懒加载）
        self._trade_client = None
        self._quote_client = None

        logger.info(f"TigerBroker 初始化完成 | sandbox={is_sandbox} | account={tiger_cfg['account']}")

    @property
    def trade_client(self):
        """懒加载 TradeClient"""
        if self._trade_client is None:
            from tigeropen.trade.trade_client import TradeClient
            self._trade_client = TradeClient(self._client_config)
        return self._trade_client

    @property
    def quote_client(self):
        """懒加载 QuoteClient"""
        if self._quote_client is None:
            from tigeropen.quote.quote_client import QuoteClient
            self._quote_client = QuoteClient(self._client_config)
            try:
                self._quote_client.grab_quote_permission()
            except Exception:
                pass
        return self._quote_client

    @property
    def account(self) -> str:
        return self._client_config.account

    # ── 账户信息 ──────────────────────────────────────────

    def get_managed_accounts(self) -> list:
        """获取管理的账户列表"""
        accounts = self.trade_client.get_managed_accounts()
        logger.info(f"获取到 {len(accounts)} 个账户")
        return accounts

    def get_assets(self) -> dict:
        """获取账户资产（Prime 账户）
        
        返回 PortfolioAccount 对象，包含：
        - segments['S'].net_liquidation: 净清算值
        - segments['S'].cash_available_for_trade: 可用资金
        - segments['S'].buying_power: 购买力
        """
        assets = self.trade_client.get_prime_assets()
        logger.info(f"获取资产信息成功")
        return assets

    def get_positions(self, sec_type: str = "STK") -> list:
        """获取持仓列表
        
        Args:
            sec_type: 证券类型，默认 STK（股票）
        
        Returns:
            Position 对象列表
        """
        from tigeropen.common.consts import SecurityType
        sec_type_map = {
            "STK": SecurityType.STK,
            "OPT": SecurityType.OPT,
            "FUT": SecurityType.FUT,
        }
        positions = self.trade_client.get_positions(
            sec_type=sec_type_map.get(sec_type, SecurityType.STK)
        )
        logger.info(f"获取到 {len(positions or [])} 个持仓")
        return positions or []

    # ── 行情 ────────────────────────────────────────────

    def get_quote(self, symbols: list[str]) -> list:
        """获取实时报价（快照）
        
        Args:
            symbols: 股票代码列表，如 ['AAPL', 'GOOG']
        
        Returns:
            报价数据 DataFrame
        """
        from tigeropen.common.consts import QuoteRight
        briefs = self.quote_client.get_briefs(
            symbols=symbols,
            include_ask_bid=True,
            right=QuoteRight.BR,
        )
        logger.info(f"获取 {len(symbols)} 个标的报价")
        return briefs

    def get_stock_price(self, symbol: str) -> float:
        """Get latest stock price with 3-tier fallback.

        Chain: Tiger API → yfinance → Parquet cache.
        Returns 0.0 if all sources fail.
        """
        # 1) Tiger live quote
        try:
            briefs = self.get_quote([symbol])
            if briefs and len(briefs) > 0:
                price = float(getattr(briefs[0], "latest_price", 0) or 0)
                if price > 0:
                    return price
        except Exception as e:
            logger.warning(f"Live quote failed for {symbol}: {e}, trying yfinance")

        # 2) yfinance real-time quote
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            price = float(getattr(ticker.fast_info, "last_price", 0) or 0)
            if price > 0:
                return price
        except Exception as e:
            logger.warning(f"yfinance quote failed for {symbol}: {e}, trying cache")

        # 3) Parquet cache (last close, max 5 days stale)
        try:
            from pathlib import Path as _P
            import pandas as pd
            from datetime import date
            parquet = _P("data/cache") / f"{symbol}.parquet"
            if parquet.exists():
                df = pd.read_parquet(parquet)
                if not df.empty:
                    last_date = df.index[-1].date()
                    if (date.today() - last_date).days <= 5:
                        return float(df["close"].iloc[-1])
        except Exception as e:
            logger.warning(f"Parquet cache failed for {symbol}: {e}")

        return 0.0

    def get_historical_bars(
        self,
        symbols: list[str],
        period: str = "day",
        begin_time: str | None = None,
        end_time: str | None = None,
        limit: int = 251,
    ):
        """Fetch historical OHLCV bars via Tiger quote API.

        Args:
            symbols: Stock symbols, e.g. ['AAPL']
            period: Bar period — 'day', 'week', 'month', etc.
            begin_time: Start date string, e.g. '2024-02-18'
            end_time: End date string, e.g. '2026-02-18'
            limit: Max bars to return (default 251, set higher for multi-year)

        Returns:
            DataFrame with columns: symbol, time, open, high, low, close, volume, amount
        """
        from tigeropen.common.consts import BarPeriod, QuoteRight

        period_map = {
            "day": BarPeriod.DAY,
            "week": BarPeriod.WEEK,
            "month": BarPeriod.MONTH,
        }
        bars = self.quote_client.get_bars(
            symbols=symbols,
            period=period_map.get(period, BarPeriod.DAY),
            begin_time=begin_time,
            end_time=end_time,
            right=QuoteRight.BR,
            limit=limit,
        )
        logger.info(
            f"获取 {symbols} 历史K线 | period={period} | {len(bars) if bars is not None else 0} bars"
        )
        return bars

    def get_market_status(self, market: str = "US") -> list:
        """获取市场状态
        
        Args:
            market: 市场代码，US / HK / CN
        """
        from tigeropen.common.consts import Market
        market_map = {"US": Market.US, "HK": Market.HK, "CN": Market.CN}
        return self.quote_client.get_market_status(
            market_map.get(market, Market.US)
        )

    # ── 下单 ────────────────────────────────────────────

    def place_limit_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        limit_price: float,
        currency: str = "USD",
        time_in_force: str = "DAY",
    ) -> int:
        """下限价单
        
        Args:
            symbol: 股票代码
            action: 'BUY' 或 'SELL'
            quantity: 数量
            limit_price: 限价
            currency: 币种
            time_in_force: 有效期，DAY / GTC
        
        Returns:
            订单全局 ID (order.id)
        """
        from tigeropen.common.util.contract_utils import stock_contract
        from tigeropen.common.util.order_utils import limit_order

        contract = stock_contract(symbol=symbol, currency=currency)
        order = limit_order(
            account=self.account,
            contract=contract,
            action=action.upper(),
            quantity=quantity,
            limit_price=limit_price,
            time_in_force=time_in_force,
        )
        self.trade_client.place_order(order)
        logger.info(f"限价单已提交 | {action} {quantity} {symbol} @ {limit_price} | order_id={order.id}")
        return order.id

    def place_market_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        currency: str = "USD",
    ) -> int:
        """下市价单
        
        Args:
            symbol: 股票代码
            action: 'BUY' 或 'SELL'
            quantity: 数量
            currency: 币种
        
        Returns:
            订单全局 ID (order.id)
        """
        from tigeropen.common.util.contract_utils import stock_contract
        from tigeropen.common.util.order_utils import market_order

        contract = stock_contract(symbol=symbol, currency=currency)
        order = market_order(
            account=self.account,
            contract=contract,
            action=action.upper(),
            quantity=quantity,
        )
        self.trade_client.place_order(order)
        logger.info(f"市价单已提交 | {action} {quantity} {symbol} | order_id={order.id}")
        return order.id

    # ── 撤单 ────────────────────────────────────────────

    def cancel_order(self, order_id: int) -> bool:
        """撤销订单
        
        Args:
            order_id: 全局订单 ID
        
        Returns:
            是否成功发起撤单请求
        """
        self.trade_client.cancel_order(id=order_id)
        logger.info(f"撤单请求已发送 | order_id={order_id}")
        return True

    # ── 查询订单 ──────────────────────────────────────────

    def get_order(self, order_id: int):
        """查询单个订单状态
        
        Args:
            order_id: 全局订单 ID
        
        Returns:
            Order 对象
        """
        order = self.trade_client.get_order(id=order_id)
        logger.info(f"订单查询 | id={order_id} status={order.status}")
        return order

    def get_open_orders(self, sec_type: str = "STK") -> list:
        """获取所有未成交订单

        Args:
            sec_type: 证券类型 STK / OPT / FUT
        """
        from tigeropen.common.consts import SecurityType
        sec_type_map = {
            "STK": SecurityType.STK,
            "OPT": SecurityType.OPT,
            "FUT": SecurityType.FUT,
        }
        orders = self.trade_client.get_open_orders(
            sec_type=sec_type_map.get(sec_type, SecurityType.STK)
        )
        logger.info(f"未成交订单: {len(orders or [])} 个 ({sec_type})")
        return orders or []

    def get_orders(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """获取订单列表
        
        Args:
            start_time: 开始时间，如 '2026-01-01'
            end_time: 结束时间
            limit: 最大返回数量
        """
        orders = self.trade_client.get_orders(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        logger.info(f"获取到 {len(orders or [])} 个订单")
        return orders or []


    # ── 期权 (Options) ──────────────────────────────────────

    def get_option_expirations(self, symbol: str) -> list[dict]:
        """Get available option expiration dates for a symbol.

        Returns:
            List of dicts with keys: date (str), period_tag (str: weekly/monthly)
        """
        expirations = self.quote_client.get_option_expirations(symbols=[symbol])
        result = []
        # SDK returns a DataFrame with columns: symbol, date, period_tag, ...
        if hasattr(expirations, "iterrows"):
            for _, row in expirations.iterrows():
                result.append({
                    "date": str(row.get("date", "")),
                    "period_tag": str(row.get("period_tag", "unknown")),
                })
        else:
            # Fallback for non-DataFrame returns
            for exp in (expirations or []):
                if isinstance(exp, dict):
                    result.append({
                        "date": str(exp.get("date", "")),
                        "period_tag": str(exp.get("period_tag", "unknown")),
                    })
        logger.info(f"Option expirations for {symbol}: {len(result)} dates")
        return result

    def get_option_chain(
        self,
        symbol: str,
        expiry: str,
        option_filter: dict | None = None,
    ) -> list[dict]:
        """Get option chain for a symbol at a specific expiry.

        Args:
            symbol: Underlying symbol (e.g., 'SPY')
            expiry: Expiry date string 'YYYY-MM-DD'
            option_filter: Optional filter dict with keys like
                delta_min, delta_max, open_interest_min, in_the_money

        Returns:
            List of dicts with keys: identifier, strike, put_call, bid_price,
            ask_price, open_interest, delta, implied_vol, etc.
        """
        from tigeropen.quote.domain.filter import OptionFilter

        opt_filter = None
        if option_filter:
            opt_filter = OptionFilter(
                delta_min=option_filter.get("delta_min"),
                delta_max=option_filter.get("delta_max"),
                open_interest_min=option_filter.get("open_interest_min"),
                in_the_money=option_filter.get("in_the_money"),
            )

        chain = self.quote_client.get_option_chain(
            symbol=symbol,
            expiry=expiry,
            option_filter=opt_filter,
        )
        # SDK returns a DataFrame — convert to list of dicts for consistency
        result = []
        if hasattr(chain, "iterrows"):
            for _, row in chain.iterrows():
                result.append(row.to_dict())
        elif chain is not None:
            result = list(chain)
        logger.info(f"Option chain for {symbol} exp={expiry}: {len(result)} items")
        return result

    def get_option_analysis(self, symbols: list[str], market: str = "US") -> list:
        """Get IV analysis (IV rank, percentile, 30-day IV) for symbols.

        Uses 26-week period for IV rank calculation. Changed from 52-week
        (2026-02-24) because 52-week was too anchored to stale high-IV events,
        causing most symbols to show near-zero rank in normal markets.

        Returns:
            List of OptionAnalysis objects with .iv_metric.rank, .implied_vol_30_days, etc.
            May return None for symbols without option data.
        """
        from tigeropen.common.consts import Market, OptionAnalysisPeriod
        market_map = {"US": Market.US, "HK": Market.HK, "CN": Market.CN}
        try:
            analysis = self.quote_client.get_option_analysis(
                symbols=symbols,
                market=market_map.get(market, Market.US),
                period=OptionAnalysisPeriod.TWENTY_SIX_WEEK,
            )
            logger.info(f"Option analysis for {len(symbols)} symbols: {len(analysis or [])} results")
            return analysis or []
        except Exception as e:
            logger.error(f"Option analysis failed: {e}")
            return []

    _BRIEFS_BATCH_SIZE = 30  # Tiger API limit per get_option_briefs call

    def get_option_briefs(self, identifiers: list[str]) -> list:
        """Get real-time quotes for specific option contracts.

        Auto-batches into chunks of 30 (Tiger API limit). Callers can pass
        any number of identifiers without worrying about the limit.

        Args:
            identifiers: Option identifiers, e.g. ["SPY   260320P00540000"]

        Returns:
            List of option brief objects (bid, ask, latest_price, Greeks)
        """
        if not identifiers:
            return []

        all_results = []
        for i in range(0, len(identifiers), self._BRIEFS_BATCH_SIZE):
            batch = identifiers[i:i + self._BRIEFS_BATCH_SIZE]
            raw = self.quote_client.get_option_briefs(identifiers=batch)
            # SDK may return DataFrame — normalize to list of attribute-accessible objects
            if hasattr(raw, "iterrows"):
                for _, row in raw.iterrows():
                    all_results.append(type("Brief", (), row.to_dict())())
            elif raw is not None:
                all_results.extend(raw)

        logger.info(f"Option briefs for {len(identifiers)} contracts: {len(all_results)} results")
        return all_results

    def get_option_positions(self) -> list:
        """Get all option positions."""
        return self.get_positions(sec_type="OPT")

    def place_option_order(
        self,
        identifier: str,
        action: str,
        quantity: int,
        limit_price: float,
        time_in_force: str = "DAY",
    ) -> int:
        """Place a limit order for an option contract.

        Args:
            identifier: Option identifier string (e.g., "SPY   260320P00540000")
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
            limit_price: Limit price per share (not per contract)
            time_in_force: DAY or GTC

        Returns:
            Order ID
        """
        from tigeropen.common.util.contract_utils import option_contract
        from tigeropen.common.util.order_utils import limit_order

        contract = option_contract(identifier=identifier, currency="USD")
        # Round to tick size (0.01) — Tiger rejects prices with float artifacts
        limit_price = round(limit_price, 2)
        order = limit_order(
            account=self.account,
            contract=contract,
            action=action.upper(),
            quantity=quantity,
            limit_price=limit_price,
            time_in_force=time_in_force,
        )
        self.trade_client.place_order(order)
        logger.info(
            f"Option order submitted | {action} {quantity} {identifier} "
            f"@ {limit_price} | order_id={order.id}"
        )
        return order.id

    def place_option_market_order(
        self,
        identifier: str,
        action: str,
        quantity: int,
        time_in_force: str = "DAY",
    ) -> int:
        """Place a market order for an option contract.

        Args:
            identifier: Option identifier string (e.g., "SPY   260320P00540000")
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
            time_in_force: DAY or GTC

        Returns:
            Order ID
        """
        from tigeropen.common.util.contract_utils import option_contract
        from tigeropen.common.util.order_utils import market_order

        contract = option_contract(identifier=identifier, currency="USD")
        order = market_order(
            account=self.account,
            contract=contract,
            action=action.upper(),
            quantity=quantity,
        )
        self.trade_client.place_order(order)
        logger.info(
            f"Option MARKET order submitted | {action} {quantity} {identifier} "
            f"| order_id={order.id}"
        )
        return order.id


# ── 快速测试入口 ──────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    broker = TigerBroker()
    
    # 测试认证：获取账户列表
    accounts = broker.get_managed_accounts()
    for acc in accounts:
        print(f"  账户: {acc.account} | 类型: {acc.capability} | 状态: {acc.status}")

    # 测试获取资产
    assets = broker.get_assets()
    print(f"  资产信息: {assets}")

    # 测试获取持仓
    positions = broker.get_positions()
    for pos in positions:
        print(f"  持仓: {pos.contract.symbol} | 数量: {pos.quantity} | 市值: {pos.market_value}")
