import os
import re
import time


def get_page_sequence_number(path):
    name = os.path.basename(path)
    match = re.search(r'(?i)\bpage[\s._-]*0*(\d{1,6})(?!\d)', name)
    if match:
        return int(match.group(1))
    return None


def get_ordered_jobs_for_processing(queue, *, merge_files, page_sequence_fn, basename_fn=os.path.basename):
    jobs = [dict(item, _queue_index=i) for i, item in enumerate(queue)]
    if not merge_files:
        return jobs, False
    has_sequence = any(page_sequence_fn(job['path']) is not None for job in jobs)
    if not has_sequence:
        return jobs, False

    def sort_key(job):
        seq = page_sequence_fn(job['path'])
        if seq is None:
            return (1, 10**9, basename_fn(job['path']).lower())
        return (0, seq, basename_fn(job['path']).lower())

    jobs.sort(key=sort_key)
    return jobs, True


def resolve_merge_output_path(jobs, fmt, *, custom_dest, dest_mode, script_dir, collision_mode, path_exists=os.path.exists, makedirs=os.makedirs, now=None):
    if dest_mode == 1 and custom_dest:
        target_dir = custom_dest
    elif jobs:
        target_dir = os.path.dirname(jobs[0]['path'])
    else:
        target_dir = script_dir
    makedirs(target_dir, exist_ok=True)
    output_path = os.path.join(target_dir, f'Chronicle_Merged.{fmt}')
    if path_exists(output_path):
        stamp = int(time.time() if now is None else now)
        if collision_mode == 'auto':
            output_path = os.path.join(target_dir, f'Chronicle_Merged_{stamp}.{fmt}')
        elif collision_mode == 'skip':
            output_path = os.path.join(target_dir, f'Chronicle_Merged_{stamp}.{fmt}')
    return output_path
