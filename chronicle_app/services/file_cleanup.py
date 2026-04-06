import gc
import os
import time


def remove_with_retries(
    path,
    *,
    remove_fn=os.remove,
    exists_fn=os.path.exists,
    sleep_fn=time.sleep,
    gc_collect_fn=gc.collect,
    attempts=4,
):
    if not path or not exists_fn(path):
        return True, None
    last_error = None
    for attempt in range(max(1, attempts)):
        try:
            remove_fn(path)
            return True, None
        except Exception as ex:
            last_error = ex
            if attempt < attempts - 1:
                try:
                    gc_collect_fn()
                except Exception:
                    pass
                sleep_fn(0.2 * (attempt + 1))
    return False, last_error
