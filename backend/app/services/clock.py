from datetime import datetime
from app.config import get_settings


def now() -> datetime:
    s = get_settings().as_of_date
    if s:
        d = datetime.strptime(s, "%Y-%m-%d")
        t = datetime.utcnow()
        return d.replace(hour=t.hour, minute=t.minute, second=t.second)
    return datetime.utcnow()
