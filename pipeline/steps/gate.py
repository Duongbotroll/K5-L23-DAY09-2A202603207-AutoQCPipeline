"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo, chưa người duyệt) / (tổng số ảnh).
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    reviewed = set(reviewed)
    limit = cfg["gate"]["warn_ratio_hold"]

    # Lỗi bắt buộc: đếm TẤT CẢ, kể cả ở ảnh đã duyệt hay lỗi cấp dataset (data.yaml)
    errors = [i for i in issues if i.severity == ERROR]

    # Cảnh báo: chỉ ảnh có trong dataset, chưa được người duyệt; đếm theo ẢNH chứ không theo issue
    warn_images = {i.image for i in issues
                   if i.severity == WARN and i.image in stems and i.image not in reviewed}

    n_images = len(stems)
    ratio = round(len(warn_images) / n_images, 4) if n_images else 0.0

    reasons = []
    if errors:
        decision = "Rework"
        codes = sorted({i.code for i in errors})
        reasons.append(f"còn {len(errors)} lỗi bắt buộc ({', '.join(codes)}): phải sửa trước khi xuất")
    elif ratio >= limit:
        decision = "Hold"
        reasons.append(f"{len(warn_images)}/{n_images} ảnh ({ratio:.1%}) còn cảnh báo chưa người duyệt, "
                       f">= ngưỡng {limit:.0%}")
    else:
        decision = "Release"
        reasons.append(f"không còn lỗi bắt buộc; {len(warn_images)}/{n_images} ảnh ({ratio:.1%}) còn cảnh báo, "
                       f"< ngưỡng {limit:.0%}")

    return {
        "decision": decision,
        "n_errors": len(errors),
        "n_warn_images": len(warn_images),
        "n_images": n_images,
        "warn_ratio": ratio,
        "reasons": reasons,
    }
