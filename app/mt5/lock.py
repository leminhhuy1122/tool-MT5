# -*- coding: utf-8 -*-
"""
VietKey Gold AI — MT5 Thread Safety Lock.

MetaTrader 5 Python C-extension is NOT thread-safe.
Mọi cuộc gọi tới thư viện MetaTrader5 qua bất kỳ thread nào (Bot Runner, FastAPI requests, v.v.)
đều phải được đồng bộ hóa qua khóa threading.RLock() này để ngăn chặn race conditions,
xung đột dữ liệu hoặc crash process.
"""

import threading

# Reentrant Lock cho phép cùng một thread gọi lồng nhau mà không bị deadlock
mt5_lock = threading.RLock()
