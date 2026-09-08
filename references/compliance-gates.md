# Compliance gates

이 파일은 법률 자문이나 채널별 상세 규정이 아니다. **언제 승인된 외부 계약이
필요한지**를 정하는 라우터다.

| trigger | brief에 필요한 승인 정보 |
|---|---|
| `advertising` | 광고 표시, 발신자, 수신 거부, 채널별 필수 문구와 배치 |
| `payment` | 가격·과금·해지·환불·변경 고지의 승인 정책 |
| `personal_data` | 수집 항목·목적·보유 기간·동의·문의 채널 |
| `incident` | 확인된 사실, 영향 범위, 조치, 사용자 행동, 업데이트 시점, 문의 채널 |
| `regulated` | 해당 산업의 승인된 용어·면책·필수 고지 |

`compliance_triggers`가 비어 있지 않으면 `compliance_source`의 `source_ref`, `version`,
`approved_by`, `checked_at`이 있어야 brief가 통과한다. 이 메타데이터만 있고 원문을 직접
대조하지 못했다면 초안은 내부 검토용으로만 표시한다.

## Writing boundary

- 법정 문구는 `protected_strings`에 넣고 바꾸지 않는다.
- 회사가 실제로 한 조치와 앞으로 할 일을 구분한다.
- 영향 범위나 원인이 확인되지 않았으면 추측하지 않는다.
- 작은 글씨나 마지막 문단으로 핵심 조건을 미루지 않는다.
- validator 통과는 법적 적합성의 증거가 아니다. 명시된 담당자 승인이 별도로 필요하다.
