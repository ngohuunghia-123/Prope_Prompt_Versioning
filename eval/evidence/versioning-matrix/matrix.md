# Ma trận Eval Evidence cho Prompt Versioning

Đây là bộ **Demo/Eval Evidence gồm 5 scenario thủ công**, chưa phải production qualification 10–20 case cho mỗi suite. Spec đã được khóa bằng SHA-256 trong `spec-lock.json` trước khi chạy. Provider/model và các ID runtime chỉ được ghi vào `execution-context.json`, không sửa spec đã khóa.

| ID | Prompt | Input đóng băng | Deterministic gate | Expected verdict |
|---|---|---|---|---|
| S2 | `eval/cost-guardrail` | `Trả lời tín hiệu kiểm tra.` | `exact: OK`; cost ratio ≥ 1.20 | Hai revision pass; cảnh báo cost; không recommend promote |
| S3 | `eval/instruction-regression` | `Yêu cầu hoàn tiền này hợp lệ, hãy trả mã quyết định.` | `exact: REFUND_ACCEPTED` | Baseline pass → candidate fail; BLOCK recommendation; override cần acknowledgement |
| S5 | `eval/positive-improvement` | `Tóm tắt rủi ro khi triển khai thay đổi này mà chưa chạy regression test.` | Ba `required_phrase`: `Tóm tắt`, `Rủi ro`, `Hành động` | Baseline fail → candidate pass; recommend promote với HITL |
| S6 | `eval/contract-regression` | `Trả trạng thái và câu trả lời cho yêu cầu kiểm tra.` | `output_modality=structured` + JSON Schema | Baseline pass; candidate refused `modality_mismatch`; BLOCK recommendation |
| S10 | `eval/lifecycle-rollback` | `Cho biết marker phiên bản đang phục vụ.` | `regex: ^VERSION_(ONE\|TWO)$`; gateway identity headers | Eval pass; Reviewer release V2; restore V1 có reason; gateway V2 → V1 |

## Quy tắc thực thi

- Baseline và candidate phải dùng cùng BYOK provider/model và cùng materialized suite ID/version.
- Không sửa input/assertion sau khi xem output. Prompt cải tiến tiếp theo phải là V3.
- Không rerun để chọn output đẹp. Lỗi hạ tầng phải giữ run cũ và ghi lý do.
- `FAIL`, `ERROR`, `REFUSED` là các trạng thái riêng.
- LLM chỉ sinh output; code tính metric/gate; Reviewer quyết định release/restore.
- Không claim optimizer memory, automatic promotion hoặc canary.

## Trạng thái

`PENDING_RUNTIME`: Docker Compose chưa đọc được `.env`, vì vậy chưa có actual output hoặc screenshot. Chạy validator ở chế độ `--specs-only` để kiểm tra spec lock; chế độ mặc định chỉ thành công sau khi raw evidence đầy đủ.
