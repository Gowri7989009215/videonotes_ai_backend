"""
Simple in-process background task queue using ThreadPoolExecutor.
Replaces BullMQ + Redis for single-server deployments.
"""

import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict


# Thread pool for CPU/IO-bound video processing work
_executor = ThreadPoolExecutor(max_workers=5)

_handlers: Dict[str, Callable] = {}
_main_loop = None

def register_handler(name: str, handler: Callable) -> None:
    """Register a named job handler function."""
    global _main_loop
    try:
        _main_loop = asyncio.get_running_loop()
    except RuntimeError:
        _main_loop = asyncio.get_event_loop()
    _handlers[name] = handler

def run_async_in_main(coro):
    """Run an async function safely on the main event loop from a worker thread."""
    if _main_loop is None:
        raise RuntimeError("Main loop not captured. Register handler first.")
    future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
    return future.result()


def submit_job(name: str, data: Dict[str, Any]) -> None:
    """
    Submit a job to run in the background thread pool.
    The handler is called synchronously in a worker thread.
    """
    handler = _handlers.get(name)
    if not handler:
        print(f"[Background] No handler registered for job type: {name}")
        return

    def _run():
        try:
            print(f"[Background] Starting job '{name}' with data keys: {list(data.keys())}")
            handler(data)
            print(f"[Background] Job '{name}' completed successfully.")
        except Exception as e:
            print(f"[Background] Job '{name}' failed: {e}")
            traceback.print_exc()

    _executor.submit(_run)


def shutdown():
    """Gracefully shutdown the thread pool."""
    _executor.shutdown(wait=False)
    print("[Background] Thread pool shut down.")
