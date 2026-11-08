"""
Tools package for Lab 2 – Tool-Using Agent (Campus Data Assistant).

Exports:
    calculator  – arithmetic operations (sum, average)
    csv_reader  – reads event-signup CSV
    events_api  – mock event metadata API
    notifier    – draft-only notification tool (Assignment 1)
"""

from tools.calculator import calculator
from tools.csv_reader import read_csv
from tools.events_api import get_event_info
from tools.notifier import send_notification

__all__ = ["calculator", "read_csv", "get_event_info", "send_notification"]

