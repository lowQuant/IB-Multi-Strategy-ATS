# gui/log.py
from collections import deque
import threading
import time

log_buffer = deque(maxlen=10)
log_lock = threading.Lock()
start_event = threading.Event()

def add_log(message):
    with log_lock:
        log_buffer.append(f"{time.ctime()}: {message}")
