import json
import logging
import re as _re
from functools import wraps
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from ..models import Task


logger = logging.getLogger(__name__)


class _JsonEncoder(json.JSONEncoder):
    """Handle Decimal and date types in json.dumps."""
    def default(self, obj):
        from decimal import Decimal as _D
        import datetime as _dt
        if isinstance(obj, _D):
            return float(obj)
        if isinstance(obj, (_dt.date, _dt.datetime)):
            return obj.isoformat()
        return super().default(obj)


def _jdumps(obj):
    return json.dumps(obj, cls=_JsonEncoder)


def _month_key(val):
    """TruncMonth on SQLite may return str or datetime."""
    from datetime import datetime as _dt, date as _d
    if val is None: return ''
    if isinstance(val, str): return val[:7]
    if isinstance(val, (_dt, _d)): return val.strftime('%Y-%m')
    return str(val)[:7]


def _day_key(val):
    """TruncDate on SQLite may return str or datetime."""
    from datetime import datetime as _dt, date as _d
    if val is None: return ''
    if isinstance(val, str): return val[:10]
    if isinstance(val, (_dt, _d)): return val.strftime('%Y-%m-%d')
    return str(val)[:10]


def _parse_hours(raw):
    """Parse hours: '2.5', '2,5', '2h30m', '2ч30м', '2:30'."""
    if not raw:
        return None
    raw = raw.strip().lower()
    m = _re.match(r'^(\d+)[hч][:\s]*(\d+)[mм]?$', raw)
    if m:
        return Decimal(m.group(1)) + Decimal(m.group(2)) / 60
    m = _re.match(r'^(\d+):(\d+)$', raw)
    if m:
        return Decimal(m.group(1)) + Decimal(m.group(2)) / 60
    try:
        return Decimal(raw.replace(',', '.'))
    except InvalidOperation:
        raise ValueError(f'Неверный формат: «{raw}». Примеры: 2.5, 2ч30м, 2:30')


def superuser_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseForbidden('Доступ запрещён')
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)
