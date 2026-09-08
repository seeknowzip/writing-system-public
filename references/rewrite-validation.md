# Rewrite validation

문장 정렬·진단 기록·문자·보호 토큰을 검사한다. 의미 보존과 자연스러움은 별도 검토한다.
원문과 산출물은 메타데이터를 뺀 동일한 본문 범위로 입력한다. 경로는 스킬 디렉터리 기준이다.

```bash
python3 scripts/validate_rewrite_output.py --source source.md --diagnostic-template
python3 scripts/validate_rewrite_output.py --source source.md --output final.md --diag diagnosis.json --preserve '["보호 문자열"]'
```

템플릿은 `schema_version: 2`, 원문 문장마다 `sentence`(1 기반)·`text`·`decision: pending`·
빈 `reason`·빈 `hits`를 출력한다. 그대로 제출하면 실패한다. 실제 대조 뒤 `decision`을
`no-op` 또는 `change`로 바꾸고 판단 근거를 `reason`에 적는다. `change`에는 FT ID 또는
surface 항목과 근거를 `hits`에 넣고, `no-op`은 빈 목록을 유지한다. hits 항목은 문자열 또는
비어 있지 않은 `id`·`evidence` 객체다. 이 형식은 판단 기록의 누락을 잡으며 판단의 진실성을 증명하지 않는다.

```json
{"schema_version": 2, "sentences": [{
  "sentence": 1, "text": "원문입니다.", "decision": "no-op",
  "reason": "문맥과 표현을 대조했고 별도 읽기 문제가 없어 보존", "hits": []
}]}
```

빠진 행·중복 번호·다른 원문의 행·미완료 판단은 오류다. 진단이 무효여도 문자 손상·보호 문자열
검사는 계속한다. 무개입 수정·삭제 검사는 유효한 진단이 있어야 하므로 수행되지 않은 경우를 통과로 세지 않는다.

- 지목하지 않은 문장의 수정·삭제를 막는다. 지목 자체의 타당성, 지목된 문장의 명제 삭제 여부는 의미 대조가 맡는다.
- 문장을 나눌 때 `insertions`에 나눈 모든 산출 문장의 `output_sentence`, 원문의 `source_sentences` 배열,
  `reason`을 적는다. 원문 참조는 지목된 문장이어야 한다. 이 매핑은 변경 추적이지 새 명제의 승인이 아니다.
- 손상 후보는 정렬된 원문 문장(분할이면 명시적으로 참조한 원문)과만 비교한다. 다른 문장의 유사 어절은 근거로 삼지 않는다.
- `possible_syllable_corruption`은 휴리스틱이라 정상 표현도 잡을 수 있다. 오타면 고친다. 정상 표현이면 아래처럼
  해당 원문·산출 **문장**의 해시에 묶인 검토를 남긴다. 다른 문장 변경은 기록을 무효화하지 않는다.

```json
{"warning_reviews": [{
  "code": "possible_syllable_corruption", "source_token": "원문어절", "token": "산출어절",
  "source_sentence_sha256": "정렬된 원문 문장 SHA-256", "output_sentence_sha256": "산출 문장 SHA-256",
  "reason": "해당 문맥에서 정상 표현인 이유", "reviewed_by": "실제 검토자", "checked_at": "YYYY-MM-DD"
}]}
```

문장 해시는 분할기의 `text` 값(바깥 공백 제거, 문장 내부 그대로)으로 계산한다. 여러 원문을 참조한
분할 문장은 원문 text를 한 칸 공백으로 이어 붙인다. 검토자가 생성자와 같으면 자기 검토로 표시한다.
검토 기록은 오탐 판단이며 의미 보존·독립 검토·사람 채택을 대신하지 않는다.

과거 기록은 `--legacy-diagnostic`(API는 `allow_legacy_diag=True`)으로만 호환 검사한다. 신형 v2의
완료 판정을 대신하지 않으며 원기록에 이유나 판단을 사후 보충하지 않는다. `--diag` 생략은 문자 검사만
할 때 쓴다. 진단 파일을 명시했는데 내용이 `null`이면 입력 오류다. rewrite 완료 검사는 v2 진단이 필수다.
