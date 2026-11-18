# Báo cáo Day 09 — Nguyễn Thái Dương, 2A202603207

## 1. Kết luận trước
**Hold** (mã thoát 10). Vào **224 ảnh**, bước nhận dữ liệu loại **22 ảnh** (2 hỏng, 3 quá nhỏ, 8 trùng từng byte, 4 trùng gần đúng, 5 rò rỉ từ tập test), còn **202 ảnh** được xuất ra `export/clean_v1` dưới dạng **bản nháp, chưa phát hành**.
Lý do: sau khi máy tự sửa và người duyệt 80/80 ảnh trong ngân sách, **không còn lỗi bắt buộc nào** (0 ERROR), nhưng **38/202 ảnh (18,8%)** vẫn còn cảnh báo chưa người xem, vượt ngưỡng 10% (`08_summary.json`).

## 2. Lỗi và phân việc
Số liệu từ `02_error_list_v1.csv` (trước khi sửa), mẫu số là 224 ảnh quét ở bước 1 và 202 ảnh còn lại ở bước QC nhãn.

| Mã lỗi | Số dòng (số ảnh) | Ai sửa | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE | 2 (2/224) | máy: xoá ảnh | ảnh không mở được thì không dùng được, không có gì để sửa |
| BAD_SIZE | 3 (3/224) | máy: xoá ảnh | cạnh ngắn < 250 px, dưới quy tắc dự án |
| DUP_IMAGE_EXACT | 8 (8/224) | máy: xoá ảnh | trùng md5, chắc chắn 100% |
| DUP_IMAGE_NEAR | 4 (4/224) | máy: xoá ảnh | trùng phash ≤ 10 (ảnh cắt/thu nhỏ), đã mở xem kiểm tra (mục 3) |
| LEAK_TEST | 5 (5/224) | máy: xoá ảnh | ảnh trùng kho test, để lại thì kết quả đánh giá bị "ăn gian" |
| MISSING_LABEL_FILE | 6 (6/202) | **người** gán | máy không được bịa nhãn; `needs_label` đẩy lên đầu hàng đợi |
| BAD_CLASS_NAME | 2 (data.yaml) | máy: `rename_classes` | sửa `names` theo `cfg["classes"]`, không đổi id |
| BAD_FORMAT | 3 (3/202) | máy: `drop_line` | dòng không đúng 5 cột số, không đoán được ý định |
| BAD_CLASS_ID | 6 (6/202) | máy: `drop_line` | id ngoài 0..3, không biết lớp thật |
| BOX_ZERO | 4 (4/202) | máy: `drop_line` | box không có diện tích |
| DUP_BOX | 7 (7/202) | máy: `drop_line` | box cùng lớp lặp lại (IoU > 0.9) |
| BOX_OUT_OF_IMAGE | 8 (8/202) | máy: `clip_box` | cắt về [0,1], giữ lớp; nằm hẳn ngoài ảnh thì xoá dòng |
| POSSIBLE_MISSING | 53 (52 ảnh) | **người** | model lớn thấy vật mà nhãn không có: cần mắt người xác nhận |
| POSSIBLE_LOOSE_BOX | 28 (24 ảnh) | **người** | box lệch/lỏng: model cũng có thể sai |
| POSSIBLE_FALSE_POS | 25 (24 ảnh) | **người** | box nhãn không khớp vật nào model thấy |
| POSSIBLE_WRONG_CLASS | 18 (18 ảnh) | **người** | nhầm lớp hợp lệ (vd. truck ↔ bus): lỗi ngữ nghĩa |
| EMPTY_LABEL | 12 (12 ảnh) | **người** | file rỗng: ảnh nền thật hay quên gán? |
| BOX_TINY / BOX_HUGE / CLASS_RARE | 6 / 3 / 4 | **người** | cảnh báo theo quy tắc dự án, chỉ để người xem |

Máy sửa **35 thay đổi** (`03_fixes.csv`: 20 `drop_line`, 8 `clip_box`, 1 `rename_classes`, 6 `needs_label`). Sau vòng sửa còn đúng 6 lỗi bắt buộc, tất cả là `MISSING_LABEL_FILE`, đúng như thiết kế: máy không tự gán nhãn.

**Hàng đợi** (`05_review_queue.csv`, 125 ảnh) xếp theo tổng trọng số cảnh báo. Đầu hàng là `img_0020` (11,5 điểm: vừa bị xoá dòng, vừa có POSSIBLE_MISSING và POSSIBLE_WRONG_CLASS), tiếp theo là 6 ảnh `NEEDS_LABEL` (trọng số 10). Ảnh chưa có nhãn phải được người gán thì mới hết lỗi bắt buộc, còn WRONG_CLASS là lỗi ngữ nghĩa nặng nhất (trọng số 3). Ngân sách 80 ảnh chỉ phủ **80/125 = 64%** hàng đợi. Sau khi duyệt, số cảnh báo ngữ nghĩa giảm từ 123 xuống 57 (MISSING 53→13, WRONG_CLASS 18→3, LOOSE 28→20, FALSE_POS 24→21, theo `04` và `07`). 45 ảnh cuối hàng không được ai xem.

## 3. Calibration (2 ngưỡng)
Số liệu từ `submission/calibration/calibration_report.md` (39 ảnh calib có đáp án). P / R = precision / recall.

| Tham số | Khởi đầu | Đã chọn | P / R (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **10** | DUP_IMAGE_NEAR: 1.00 / 0.50 → 1.00 / 0.67 | Từ 4 đến 14, P và R trên calib không đổi (bằng phẳng). Chọn 10 ở giữa khoảng để chịu được ảnh nén lại/cắt nhẹ mà vẫn giữ precision. **Không chọn 16** dù F1 calib cao nhất (0.91), xem bên dưới. |
| `second_opinion.conf` | 0.25 | **0.6** | WRONG_CLASS: 0.56 / 0.83 → 0.62 / 0.83; MISSING: 0.50 / 1.00 → 0.57 / 1.00 | Precision tăng mà **recall của MISSING và WRONG_CLASS giữ nguyên**, giảm cảnh báo rác (hàng đợi 130 → 125 ảnh so với 0.5). Ở 0.7 recall MISSING tụt xuống 0.88, ở 0.8 xuống 0.75. Đánh đổi chấp nhận được: LOOSE_BOX tụt còn 0.20 / 0.20 (xem mục 4). |

**Calibration có thể đánh lừa ở đâu.** Trên calib, `phash_dist=16` cho F1 của DUP_IMAGE_NEAR cao nhất (1.00 / 0.83). Nhưng khi chạy trên lô raw, số ảnh bị loại nhảy từ 9 lên **18** (NEAR 4 → 7, LEAK_TEST 5 → 11). Mở xem các cặp mới thì thấy chúng **không hề trùng**: `img_0011` (tay vợt tennis) bị coi là trùng `img_0008` (hai người trượt tuyết), `img_0013` (bàn làm việc) bị coi là trùng `test_087` (sân bóng chày). Ảnh ghép kiểm tra nằm ở `submission/calibration/phash_pairs_check.jpg`; cặp đầu tiên là cặp ở khoảng cách 10, đúng là trùng thật. Calib chỉ có 39 ảnh và 6 cặp trùng chèn sẵn, nên không có cặp "khác nhau nhưng phash gần" nào để phạt ngưỡng lớn. Precision 1.00 trên calib vì thế không nói lên gì về dữ liệu thật.

Một bẫy thứ hai: chỉ cần đặt `conf=0.8` là pipeline chuyển sang **Release** (16/202 = 7,9% ảnh còn cảnh báo). Nhưng recall của POSSIBLE_MISSING khi đó tụt từ 1.00 xuống 0.75 trên calib, tức là cố tình bỏ qua 1/4 vật thiếu nhãn chỉ để qua cổng. Tôi không chọn giá trị này.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Cửa chặn chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt): kết luận **REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE)**, mã thoát **20**, log in "KHÔNG xuất: còn lỗi bắt buộc", và thư mục `work/exp_nb` **không được tạo**. Gate đếm lỗi ERROR ở mọi ảnh, kể cả ảnh đã duyệt, nên người duyệt không thể "che" lỗi bắt buộc.

**(b) Điểm mù.** Ba điểm có bằng chứng từ calib:
1. **Box lỏng nhẹ**: ở `conf=0.6`, POSSIBLE_LOOSE_BOX chỉ bắt được **1/5** box lỏng chèn sẵn (P 0.20 / R 0.20). Box lệch vừa phải vẫn có IoU ≥ 0.5 với dự đoán nên không bị cờ, và model đôi khi tự vẽ box lệch.
2. **Nhầm lớp mà model lớn cũng nhầm**: WRONG_CLASS bỏ sót **1/6** lỗi chèn sẵn. Khi model cũng gọi sai lớp (truck ↔ bus) thì hai bên "đồng ý" với nhau và không ai cảnh báo.
3. **Ảnh trùng biến đổi mạnh**: DUP_IMAGE_NEAR chỉ bắt **4/6** cặp trùng gần đúng ở `phash_dist=10`. Ảnh lật, cắt mạnh hay đổi màu nhiều có phash cách xa nhau, và nâng ngưỡng thì lại loại nhầm ảnh khác (mục 3).

Ngoài ra, cảnh báo của 45 ảnh không nằm trong ngân sách duyệt vẫn còn nguyên. FALSE_POS precision chỉ 0.36, tức khoảng 2/3 cờ FALSE_POS là cờ sai, tốn thời gian người duyệt.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy: tôi tập trung hoàn thành phần lõi (pipeline, calibration, báo cáo) trước. Dataset `export/clean_v1` đã xuất sẵn để train sau trên Colab.

## 6. Quyết định và ghi chú AI
**(a) Quyết định: Hold.** Không còn lỗi bắt buộc nhưng 18,8% ảnh còn cảnh báo chưa duyệt (≥ 10%). Để chuyển sang Release cần **thêm ngân sách duyệt khoảng 45 ảnh** để phủ hết hàng đợi 125 ảnh (hoặc ít nhất đưa số ảnh còn cảnh báo xuống dưới 21/202), **không** phải nới ngưỡng `conf`. Song song, cần kiểm tra lại 21 cờ FALSE_POS vì precision của chúng thấp.

**(b) Dùng AI** (Claude):
- *Prompt chính:* đưa docstring của từng stub, file test tương ứng và `common.py`, yêu cầu viết module đọc ngưỡng từ `cfg`, không viết cứng số, không đọc `MANIFEST`/`review_reference`, không sửa `data/raw`.
- *Cách kiểm:* chạy `pytest` từng file rồi toàn bộ (79/79 xanh); chạy `make run` và đối chiếu `02_error_list_v1` với ảnh vẽ bằng `viz_labels.py`; chạy `--budget 0` để xác nhận gate ra Rework và không xuất; mở xem các cặp ảnh bị cho là trùng.
- *Một lần AI sai:* ở bước chuẩn bị, AI đưa lệnh `viz_labels.py img_0001 img_0030` (chỉ vẽ 2 ảnh) nhưng lại bảo "mở khoảng 10 ảnh". Tôi phát hiện chỗ mâu thuẫn và phải chạy lại với đủ tên ảnh. Ngoài ra, nếu chỉ nhìn F1 trên calib, AI và cả tôi sẽ chọn `phash_dist=16`; mở ảnh ra mới thấy sai.
