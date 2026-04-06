import os


def collect_supported_files_from_folder(folder, *, recursive, supported_extensions):
    paths = []
    if recursive:
        for root_dir, _, files in os.walk(folder):
            for name in files:
                if os.path.splitext(name)[1].lower() in supported_extensions and not name.startswith("."):
                    paths.append(os.path.join(root_dir, name))
    else:
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            if not os.path.isfile(full):
                continue
            if os.path.splitext(name)[1].lower() in supported_extensions and not name.startswith("."):
                paths.append(full)
    return sorted(paths)


def add_path_entries(queue, paths, *, settings, engine_label, row_setting_keys, source_root=None):
    existing = {item["path"] for item in queue}
    added_paths = []
    for path in paths:
        if path in existing:
            continue
        queue.append(
            {
                "path": path,
                "engine": engine_label,
                "settings": {key: settings.get(key) for key in row_setting_keys},
                "status": "Queued",
                "source_root": source_root,
            }
        )
        existing.add(path)
        added_paths.append(path)
    return added_paths


def find_queue_rows_by_paths(queue, paths):
    if not paths:
        return []
    targets = set(paths)
    selected_rows = []
    for idx, item in enumerate(queue):
        if item.get("path") in targets:
            selected_rows.append(idx)
    return selected_rows
