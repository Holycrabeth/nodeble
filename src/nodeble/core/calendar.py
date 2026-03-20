import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")


def is_market_open() -> bool:
    """Check if US market is currently open (NYSE hours, trading day).

    Fail-open: returns True on error so library/import issues
    don't silently block all live executions.
    """
    try:
        import pandas_market_calendars as mcal
        nyse = mcal.get_calendar("NYSE")
        now_ny = datetime.now(NY)
        today = now_ny.date()
        schedule = nyse.schedule(start_date=today, end_date=today)
        if schedule.empty:
            return False
        market_open = schedule.iloc[0]["market_open"].to_pydatetime()
        market_close = schedule.iloc[0]["market_close"].to_pydatetime()
        return market_open <= now_ny <= market_close
    except Exception as e:
        logger.warning(f"Market hours check failed (allowing execution): {e}")
        return True
