from datetime import date, datetime
from zoneinfo import ZoneInfo

CUIABA_TZ = ZoneInfo("America/Cuiaba")
SP_TZ = ZoneInfo("America/Sao_Paulo")
UTC = ZoneInfo("UTC")


def now(tz: ZoneInfo) -> datetime:
    return datetime.now(tz=tz)


def now_iso(tz: ZoneInfo) -> str:
    return datetime.now(tz=tz).isoformat()


def today(tz: ZoneInfo) -> date:
    return datetime.now(tz=tz).date()
