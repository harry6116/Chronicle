"""Full-page context and colour detail views for comic transcription."""

import io

from PIL import Image

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - optional in lightweight environments
    cv2 = None
    np = None


def detect_comic_regions(image):
    """Find provisional bordered regions; these are hints, not a panel count."""
    if cv2 is None:
        return []
    preview = image.convert("RGB")
    preview.thumbnail((2400, 2400))
    width, height = preview.size
    gray = cv2.cvtColor(np.asarray(preview), cv2.COLOR_RGB2GRAY)

    def area(box):
        return box[2] * box[3]

    def overlap(a, b):
        left, top = max(a[0], b[0]), max(a[1], b[1])
        right = min(a[0] + a[2], b[0] + b[2])
        bottom = min(a[1] + a[3], b[1] + b[3])
        return max(0, right - left) * max(0, bottom - top)

    def contains(parent, child):
        return overlap(parent, child) >= area(child) * 0.96

    boxes = []
    for threshold in range(110, 191, 5):
        binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            box = cv2.boundingRect(contour)
            _, _, w, h = box
            contour_area = cv2.contourArea(contour)
            if contour_area <= width * height * 0.025 or contour_area / area(box) <= 0.65:
                continue
            if w <= width * 0.12 or h <= height * 0.06:
                continue
            duplicates = [old for old in boxes if overlap(old, box) / (area(old) + area(box) - overlap(old, box)) > 0.8]
            if duplicates:
                boxes = [old for old in boxes if old not in duplicates] + [max(duplicates + [box], key=area)]
            else:
                boxes.append(box)

    boxes = sorted(set(boxes), key=lambda box: (box[1], box[0], box[2], box[3]))
    containers = [box for box in boxes if any(contains(box, child) and area(child) < area(box) * 0.8 for child in boxes if child != box)]
    regions = [box for box in boxes if box not in containers]
    # Broken borders can merge a row with its title. Recover the large remaining
    # rectangles around detected children instead of treating that row as one panel.
    for parent in sorted(containers, key=area):
        remaining = [parent]
        for x, y, w, h in [box for box in regions if contains(parent, box)]:
            pieces = []
            for left, top, rw, rh in remaining:
                right, bottom = left + rw, top + rh
                ix, iy = max(left, x), max(top, y)
                ir, ib = min(right, x + w), min(bottom, y + h)
                if ix >= ir or iy >= ib:
                    pieces.append((left, top, rw, rh))
                    continue
                pieces.extend([(left, top, rw, iy - top), (left, ib, rw, bottom - ib),
                               (left, iy, ix - left, ib - iy), (ir, iy, right - ir, ib - iy)])
            remaining = pieces
        for box in remaining:
            if box[2] > width * 0.12 and box[3] > height * 0.06 and area(box) > width * height * 0.025:
                if not any(overlap(box, old) / area(box) > 0.8 for old in regions):
                    regions.append(box)
    if not regions or len(regions) > 16:
        return []
    sx, sy = image.width / width, image.height / height
    return [(round(x * sx), round(y * sy), round(w * sx), round(h * sy))
            for x, y, w, h in sorted(regions, key=lambda box: (box[1], box[0]))]


def build_comic_detail_views(path):
    """Return bounded in-memory crops while retaining the caller's full overview."""
    with Image.open(path) as source:
        image = source.convert("RGB")
    regions = detect_comic_regions(image)
    views = []
    for index, (x, y, w, h) in enumerate(regions):
        padding = max(4, round(image.height * 0.02))
        crop = image.crop((x, y, min(image.width, x + w), min(image.height, y + h + padding)))
        crop.thumbnail((1600, 1600))
        buffer = io.BytesIO()
        crop.save(buffer, "PNG")
        label = (
            f"Detail region {index + 1} of the SAME page, at x={x / image.width:.3f}, y={y / image.height:.3f}, "
            f"width={w / image.width:.3f}, height={h / image.height:.3f}. "
            "These automatically detected regions are provisional detail views, not a prescribed panel count or reading order. "
            "Use the full-page overview to verify actual frame boundaries, merge fragments, and split any region spanning several real frames. "
            "Do not split a single enclosing frame into actions or caption fragments. Keep title art unnumbered. "
            "Associate all narration with its actual frame exactly once, including text outside these crops."
        )
        views.append((label, buffer.getvalue()))
        for kind, top, bottom in (
            ("upper text", y, min(image.height, y + min(200, round(h * 0.4)))),
            ("lower text", max(0, y + h - max(60, round(image.height * 0.03))), min(image.height, y + h + padding)),
        ):
            band = image.crop((x, top, min(image.width, x + w), bottom))
            scale = min(2.0, 3600 / band.width)
            band = band.resize((round(band.width * scale), max(1, round(band.height * scale))))
            buffer = io.BytesIO()
            band.save(buffer, "PNG")
            views.append((
                f"Region {index + 1} {kind} close-up of the SAME page, not another panel. "
                "Copy the actual visible letters, without completing or rewriting sentences. "
                "Retain surrounding legible words when one word is unclear. Use the overview to attach caption fragments to their actual frame once.",
                buffer.getvalue(),
            ))
        if w > image.width * 0.75:
            for column in range(3):
                left = max(x, round(x + w * column / 3 - w * 0.03))
                right = min(image.width, x + w, round(x + w * (column + 1) / 3 + w * 0.03))
                detail = image.crop((left, y, right, min(image.height, y + h + padding)))
                detail = detail.resize((detail.width * 2, detail.height * 2))
                detail.thumbnail((1600, 1600))
                buffer = io.BytesIO()
                detail.save(buffer, "PNG")
                views.append((f"Region {index + 1}, column close-up {column + 1} of the SAME enclosing frame. This is not a new panel. Read the visible lettering exactly; do not substitute plot-based words.", buffer.getvalue()))
        for a, b, c, d in regions:
            if b <= y + image.height * 0.04:
                continue
            left, right = max(x, a), min(x + w, a + c)
            if left >= right or b >= y + h or b + d <= y:
                continue
            detail = image.crop((left, max(0, b - 30), right, min(image.height, b + 30)))
            detail = detail.resize((detail.width * 2, detail.height * 2))
            detail.thumbnail((3600, 400))
            buffer = io.BytesIO()
            detail.save(buffer, "PNG")
            views.append((f"Region {index + 1}, text close-up near an inset or overlapping frame boundary. This is not a new panel. Read the actual letters and keep narration fragments with the frame where they are printed.", buffer.getvalue()))
    return views[:64]


def append_comic_detail_views(contents, path, model, build_payload_fn):
    views = build_comic_detail_views(path)
    if not views:
        return contents
    contents = list(contents)
    for label, data in views:
        if "claude" in model or "gpt" in model:
            contents.extend(build_payload_fn(model, label, mime="image/png", file_bytes=data))
        else:
            from google.genai import types
            contents.extend([label, types.Part.from_bytes(data=data, mime_type="image/png")])
    return contents


def comic_generation_config(contents, model=None):
    if str(model or "").startswith("gemini-3"):
        return {}
    parts = contents if isinstance(contents, (list, tuple)) else [contents]
    if any(isinstance(part, str) and "COMICS / MANGA / GRAPHIC NOVELS RULES:" in part for part in parts):
        return {"temperature": 0}
    return {}
