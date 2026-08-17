# Kết quả Eval Evidence

Trạng thái: **EXECUTED / EVIDENCE_VALID**. Đây là Demo/Eval Evidence gồm 5 scenario, chưa phải production qualification 10–20 case cho mỗi suite.

| Scenario | Baseline actual | Candidate actual | Tokens/cost | Deterministic verdict | Quyết định human |
|---|---|---|---|---|---|
| S2 | `OK` | `OK` | B 61/1, 0.0000208000 USD; C 535/1, 0.0001630000 USD; ratio 7.837 | Cả hai pass; `cost_warning=true` | Không promote |
| S3 | `REFUND_ACCEPTED` | `REFUND_REVIEW_REQUIRED` | B 82/4, 0.0000346000 USD; C 86/6, 0.0000408000 USD | pass → fail; BLOCK recommendation | Request changes / blocked |
| S5 | `Cần chạy kiểm thử trước triển khai.` | Có đủ `Tóm tắt`, `Rủi ro`, `Hành động` | B 67/9, 0.0000426000 USD; C 125/83, 0.0002450000 USD | fail → pass; không error | Reviewer/Admin release V2 |
| S6 | `{"status":"ok","answer":"Đã kiểm tra"}` | `REFUSED: modality_mismatch` | B 107/12, 0.0000621000 USD; candidate không dispatch case result | Baseline pass; candidate refused; BLOCK recommendation | Request changes / blocked |
| S10 | `VERSION_ONE` | `VERSION_TWO` | B 59/3, 0.0000252000 USD; C 59/3, 0.0000252000 USD | Cả hai pass; gateway header V2 → V1 sau 35.919 giây | Reviewer/Admin release V2, restore V1 |

- S3/S6: “BLOCK recommendation; human override requires acknowledgement”.
- S10 kiểm tra HITL + release + restore, không phải canary.
- Không claim optimizer memory hoặc automatic promotion.
- Attempt đầu của baseline S2 được giữ trong `runs/S2/attempts/`: run này không hợp lệ vì executor chưa compose `revision.body`. Evidence chính được chạy sau bản sửa và không chọn lại output vì lý do chất lượng.
