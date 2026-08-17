# Raw run artifacts

Mỗi thư mục `S2`, `S3`, `S5`, `S6`, `S10` phải chứa:

- `baseline-run.json`
- `baseline-cases.json`
- `candidate-run.json`
- `candidate-cases.json`
- `comparison.json`

Riêng S10 còn có `gateway-v2.json`, `restore-response.json` và `gateway-restored-v1.json`. Chỉ lưu response body/identity headers cần thiết; không lưu cookie, Authorization header, API key hoặc provider credential.
