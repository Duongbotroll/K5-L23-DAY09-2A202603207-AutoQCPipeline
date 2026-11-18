"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line

NAME = "label_format"


def run(ds, cfg):
    c = cfg["label_format"]
    n_cls = len(ds.classes)
    issues = []

    for lab in ds.label_files():                      # đã sắp xếp theo tên -> kết quả ổn định
        stem = lab.stem
        lines = ds.read_label_lines(stem) or []       # (số dòng gốc, nội dung); dòng trống đã bỏ nhưng số dòng giữ nguyên
        size = ds.image_size(stem)                    # (W, H) hoặc None nếu không có ảnh / ảnh hỏng
        prev = []                                     # các box hợp lệ ở dòng TRƯỚC: (lớp, (cx, cy, w, h))

        for ln, text in lines:
            # 1) định dạng: dòng hỏng không được làm script chết
            try:
                cls, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue(NAME, ERROR, "BAD_FORMAT", stem, f"dòng sai định dạng ({e}): {text.strip()!r}", ln))
                continue

            # 2) id lớp
            if not 0 <= cls < n_cls:
                issues.append(Issue(NAME, ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls} ngoài 0..{n_cls - 1}", ln))
                continue

            # 3) box rỗng
            if w <= 0 or h <= 0:
                issues.append(Issue(NAME, ERROR, "BOX_ZERO", stem, f"box không có diện tích (w={w}, h={h})", ln))
                continue

            # 4) tràn ảnh: lấy mức tràn lớn nhất trong 4 mép
            overflow = max(0 - (x - w / 2), (x + w / 2) - 1, 0 - (y - h / 2), (y + h / 2) - 1)
            if overflow > c["overflow_tol"]:
                issues.append(Issue(NAME, ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"box tràn ra ngoài ảnh {overflow:.4f}", ln, {"overflow": round(overflow, 6)}))
                # không continue: một dòng có thể vừa tràn vừa trùng

            # 5) box lặp: so với các dòng trước, cùng lớp
            box = (x, y, w, h)
            for pcls, pbox in prev:
                if pcls == cls and iou_xywh(pbox, box) > c["dup_box_iou"]:
                    issues.append(Issue(NAME, ERROR, "DUP_BOX", stem,
                                        f"trùng box cùng lớp ở dòng trước (IoU={iou_xywh(pbox, box):.3f})", ln))
                    break

            # 6) cảnh báo kích thước
            if size:
                W, H = size
                short = min(w * W, h * H)
                if short < c["min_box_px"]:
                    issues.append(Issue(NAME, WARN, "BOX_TINY", stem, f"cạnh ngắn {short:.1f}px < {c['min_box_px']}px",
                                        ln, {"short_px": round(short, 2)}))
            if w * h > c["max_box_frac"]:
                issues.append(Issue(NAME, WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.0%} ảnh", ln))

            prev.append((cls, box))

    return issues
