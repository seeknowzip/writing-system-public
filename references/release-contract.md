# Release status contract

최종 문안과 검토 상태를 서로 다른 파일로 보존한다.

- `final.md`: 고객에게 전달할 문안만 포함한다.
- `release-status.json`: 사람 검토, 미확인 항목, compliance 대조, 초안→최종 신규 명제를
  포함한다.

본문에 `내부 검토용` 주석을 섞지 않는다. 대신 sidecar가 어느 문안을 검토했는지
`copy_sha256`으로 결박한다.

```json
{
  "schema_version": 1,
  "copy_path": "final.md",
  "copy_sha256": "sha256 hex digest",
  "status": "internal_review_only",
  "human_reviews": [
    {"item": "법무 최종 확인", "status": "pending"}
  ],
  "unverified_items": ["동의 철회 경로"],
  "compliance_review": {"status": "pending"},
  "semantic_review": {
    "status": "pending",
    "checks": {
      "facts": "pending",
      "actors": "pending",
      "timings": "pending",
      "conditions": "pending",
      "exceptions": "pending",
      "certainty": "pending",
      "new_claims": "pending"
    },
    "reviewed_by": null,
    "checked_at": null
  },
  "new_claims": [
    {"text": "초안에 없던 최종 문장의 명제", "fact_refs": ["UNVERIFIED"]}
  ],
  "touch_rate": 0.18
}
```

## Status

- `internal_review_only`: 검토·미확인·compliance 대조가 남아 있다.
- `review_complete`: sidecar에 기록한 차단 항목이 모두 해결됐다.

`review_complete`는 발행·전송·배포 승인이 아니다. 외부 전달 권한은 이 스킬 밖에 있다.

## Semantic review

`payment`, `personal_data`, `incident`, `regulated` trigger가 있거나 `human_review` 항목이 있는
high-stakes brief는 `semantic_review`를 반드시 가진다. `facts`, `actors`, `timings`,
`conditions`, `exceptions`, `certainty`, `new_claims` 일곱 축을 원문·brief와 독립 대조한다.
각 축은 `pending | complete | issue_found`이고, 일곱 축이 모두 `complete`이며 검토자와 날짜가
있을 때만 semantic status를 `review_complete`로 바꿀 수 있다.

validator는 객체의 존재, 일곱 축, 상태 완결성만 검사한다. 자유 형식 문안의 사실·행위자·시점·
조건·예외·확신 수준을 parser가 의미적으로 증명하지 않는다. semantic `review_complete`도
본문의 `review_complete`와 마찬가지로 발행 승인이나 외부 전달 권한이 아니다.

## Human and compliance review

brief의 모든 `human_review` 항목은 sidecar에서 같은 문자열로 상태를 가진다. 승인된
항목은 `reviewed_by`와 `checked_at`을 기록한다. compliance trigger가 있으면 brief의
`compliance_source`와 직접 대조한 역할·날짜를 기록한다.

## New claims and touch rate

high-stakes의 두 번째 대조는 첫 검증 통과본에 없고 최종본에 생긴 명제를 전수로 적는다.
각 명제는 `facts[n]`에 연결하거나 `UNVERIFIED`로 남긴다. 문장 터치율은 수정 범위를
설명하는 보고값이며 합격 기준으로 쓰지 않는다.

```bash
python3 scripts/validate_release.py --brief brief.json --copy final.md --status release-status.json
```
