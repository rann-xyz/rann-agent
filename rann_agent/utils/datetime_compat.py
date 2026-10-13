"""
Datetime compatibility module for Python 3.10-3.12+ compatibility.

Python 3.11+ has datetime.UTC which doesn't exist in earlier versions.
This module provides a compatible UTC constant.
"""

from datetime import datetime, timedelta, timezone

# Python 3.10 compatibility
UTC = timezone.utc