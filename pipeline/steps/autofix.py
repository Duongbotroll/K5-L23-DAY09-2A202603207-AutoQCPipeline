"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file, chuyển người gán            | "needs_label"    |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml             | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Chỉ sửa trong `ds` (bản làm việc), không bao giờ động tới data/raw. Không động tới lỗi WARN.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}          # + mọi mã bắt đầu bằng DUP_IMAGE_


def _is_remove(code):
    return code in REMOVE_CODES or code.startswith("DUP_IMAGE_")


def _fmt(v):
    return f"{v:.6f}".rstrip("0").rstrip(".") or "0"


def _clip(text):
    """Cắt box về [0,1]. Trả dòng mới, hoặc None nếu sau khi cắt box không còn diện tích."""
    cls, x, y, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return " ".join([str(cls), _fmt((x1 + x2) / 2), _fmt((y1 + y2) / 2), _fmt(x2 - x1), _fmt(y2 - y1)])


def fix(ds, issues, cfg):
    fixes = []
    errors = [i for i in issues if i.severity == ERROR]

    # 1) Xoá ảnh (làm trước để các lỗi dòng của ảnh đó được bỏ qua êm)
    removed = set()
    for i in errors:
        if _is_remove(i.code) and i.image not in removed:
            img = ds.image_path(i.image)
            lab = ds.label_path(i.image)
            if img is None and not lab.exists():
                continue                                   # đã xoá từ trước -> idempotent
            if img is not None:
                img.unlink()
            if lab.exists():
                lab.unlink()
            removed.add(i.image)
            fixes.append({"image": i.image, "line": "", "action": "remove_image",
                          "before": img.name if img else "(không có ảnh)", "after": f"xoá ({i.code})"})

    # 2) Ảnh thiếu file nhãn: không bịa nhãn, chỉ ghi lại để người gán
    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            fixes.append({"image": i.image, "line": "", "action": "needs_label",
                          "before": "(không có file)", "after": "chuyển người gán"})

    # 3) Tên lớp trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in errors) and ds.yaml_path.exists():
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        before = data.get("names")
        after = {k: v for k, v in enumerate(cfg["classes"])}
        if ds.yaml_names() != after:
            data["names"] = after
            ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append({"image": "data.yaml", "line": "", "action": "rename_classes",
                          "before": str(before), "after": str(cfg["classes"])})

    # 4) Lỗi theo dòng: gom theo file, ghi lại MỘT lần (số dòng trong issue là số dòng GỐC)
    drop, clip = defaultdict(set), defaultdict(set)
    for i in errors:
        if i.line is None or i.image in removed:
            continue
        if i.code in DROP_CODES:
            drop[i.image].add(int(i.line))
        elif i.code in CLIP_CODES:
            clip[i.image].add(int(i.line))

    for stem in sorted(set(drop) | set(clip)):
        path = ds.label_path(stem)
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()   # giữ cả dòng trống -> đúng số dòng gốc
        out, changed = [], False
        for ln, text in enumerate(raw, 1):
            if ln in drop[stem]:                                     # xoá dòng thắng clip
                fixes.append({"image": stem, "line": ln, "action": "drop_line", "before": text, "after": ""})
                changed = True
                continue
            if ln in clip[stem]:
                try:
                    new = _clip(text)
                except ValueError:
                    new = None
                if new is None:
                    fixes.append({"image": stem, "line": ln, "action": "drop_line", "before": text,
                                  "after": "(box nằm ngoài ảnh)"})
                else:
                    fixes.append({"image": stem, "line": ln, "action": "clip_box", "before": text, "after": new})
                    out.append(new)
                changed = True
                continue
            out.append(text)
        if changed:
            path.write_text("".join(l + "\n" for l in out), encoding="utf-8")

    return fixes
