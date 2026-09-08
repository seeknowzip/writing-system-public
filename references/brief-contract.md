# Brief contract

## Required fields

```json
{
  "genre": "guide",
  "channel": "web",
  "delivery_format": "help_article",
  "audience": "처음 기능을 쓰는 기업 관리자",
  "situation": "설정을 시작하기 직전",
  "reader_tension": null,
  "purpose": "준비물과 완료 조건을 이해한다",
  "primary_action": "설정 시작",
  "positioning": null,
  "customer_language": [],
  "facts": [
    {"text": "관리자만 설정할 수 있다", "source": "제품 정책 문서"}
  ],
  "required_strings": ["설정 시작"],
  "protected_strings": ["관리자"],
  "forbidden_strings": ["누구나"],
  "voice": {"register": "해요체", "rules": ["과장 금지"]},
  "compliance_triggers": [],
  "compliance_source": null
}
```

필수 non-empty text는 `genre`, `channel`, `delivery_format`, `audience`, `situation`,
`purpose`, `primary_action`이다. `facts`, `required_strings`, `protected_strings`,
`forbidden_strings`는 빈 배열일 수 있지만 필드 자체는 필수다. `voice` 객체와 non-empty
`voice.register`도 필수이며 `voice.rules`는 선택 목록이다.

`reader_tension`, `positioning`, `customer_language`, deterministic field 목록,
`human_review`, `compliance_triggers`, `compliance_source`는 선택 필드다. 다만 trigger가 하나라도
있으면 네 식별 필드를 가진 `compliance_source` 객체가 필수다. 선택 필드도 제공했다면 아래에
정의한 타입을 지켜야 한다. 예시의 `null`과 빈 배열은 “현재 값 없음”을 명시할 때 쓰는 권장
직렬화이며, 선택 필드를 무조건 생성하라는 뜻은 아니다.

## Rewrite 최소 계약

`rewrite` 경로(원문이 있을 때)는 이 JSON 전체를 요구하지 않는다. 최소 입력은
`references/rewrite-contract.md`가 정의한다: `source_text`(필수), `voice`, `protected_strings`,
`facts`, `audience_familiarity`, `adapter`. `genre`·`channel`·`delivery_format`·`positioning`·
`reader_tension`은 받지 않으며 패킷 선택도 하지 않는다. `high-stakes` 트리거가 있으면 위 입력에서
`facts`·`protected_strings`·`voice`·`compliance_*`만 가진 축약 brief를 만들어 validator에 넘긴다.

## Creative inputs

`landing`, `marketing`, `editorial`, `social`에서는 다음 필드가 생성 품질을 높인다. 이
필드는 사실 validator의 합격 조건이 아니라 creative direction의 재료다.

- `reader_tension`: 독자의 현재 상황 안에 있는 감정, 마찰, 선택. 확인된 리서치와 내부
  가설을 구분한다.
- `positioning`: 현재 방식이나 현실적인 대안과 비교했을 때 중요한 차이. 반드시 `facts`로
  뒷받침할 수 있어야 한다.
- `customer_language`: 실제 문의·리뷰·검색어에서 확인한 표현의 non-empty `text`와 `source`
  객체 배열. 출처 없는 문구는 고객 발화로 넣지 않는다.

값이 없으면 agent는 사실 원장에서 내부 creative hypothesis를 만들 수 있지만, 고객 발화나
우월성 주장처럼 쓰지 않는다. 차별점을 지지할 사실이 없으면 구체적 작동 방식으로 범위를
낮추고 확인 항목으로 남긴다.

## Channel and delivery format

| channel | delivery_format | 산출물 슬롯 |
|---|---|---|
| `email` | `subject_body` | 제목줄과 본문 |
| `app` | `app_notice` | 제목, 본문, 필요한 경우 CTA |
| `app` | `ui_copy` | 화면·컴포넌트별 문구 |
| `web` | `landing_page` | 랜딩 페이지 구획과 CTA |
| `web` | `help_article` | 제목, 본문, 다음 도움 경로 |
| `web` | `article` | 제목, 리드, 본문 |
| `web` | `web_notice` | 제목, 영향·행동·예외·문의 |
| `web` | `ui_copy` | 화면·컴포넌트별 문구 |
| `instagram` | `caption` | 캡션과 이동·참여 경로 |
| `linkedin` | `post` | 본문(훅·장면·판단), 필요 시 마지막 줄 행동 |
| `blog` | `article` | 제목, 리드, 본문 |
| `press_wire` | `press_release` | 제목, 요약, 리드, 본문 |

장르는 정보 역할을, channel과 delivery format은 실제 전달 슬롯을 결정한다. 예를 들어
`notice + email + subject_body`는 본문 H1과 별개인 이메일 제목줄이 필요하다. 이 계약은
CTA 위치나 문장 종결을 고정하지 않는다.

## Optional deterministic fields

- `allowed_numbers`: 문안에 새로 등장해도 되는 숫자·날짜 토큰
- `avoided_terms`: 쓰면 안 되는 용어 변형
- `allowed_cta_labels`: 사용할 수 있는 CTA 라벨
- `max_cta_types`: 서로 다른 CTA 라벨 최대 개수
- `required_sections`: 반드시 있어야 하는 마크다운 헤딩 또는 레이블. 문자열은 정확한
  독립 줄에서만 통과하며, 필요하면 `{"label": "변경 내용", "kind": "heading"}`처럼
  구조를 고정한다.
- `human_review`: 사람이 확인해야 할 쟁점 배열
- `compliance_triggers`: `advertising | payment | personal_data | incident | regulated`
- `compliance_source`: trigger가 있을 때 사용하는 승인 근거 객체

`allowed_cta_labels` 또는 `max_cta_types`를 쓰는 Markdown 문안은 실제 버튼·링크 슬롯을
독립된 `[라벨]` 또는 `[라벨](URL)` 줄로 표시한다. 본문 속 “문의하세요” 같은 동사를
CTA로 추측하지 않는다. 위치는 고정하지 않으며, 이 표시는 allowlist와 종류 수를
결정적으로 검사하기 위한 직렬화 계약이다.

`allowed_terms`는 지원하지 않는다. 자유 형식 문안에는 닫힌 용어 집합이 없어 임의의 신규
고유명사를 결정적으로 검출할 수 없기 때문이다. 반드시 그대로 쓸 용어는
`protected_strings`, 금지할 변형은 `avoided_terms`에 둔다.

`compliance_source`는 다음 네 필드를 모두 가진다.

```json
{
  "source_ref": "정책·법무·채널 체크리스트의 식별자 또는 경로",
  "version": "검토한 버전",
  "approved_by": "승인한 역할 또는 팀",
  "checked_at": "2026-08-13"
}
```

validator는 이 식별 정보의 구조만 검사한다. 실제 원문과 승인 상태를 대조했다는 증거로
해석하지 않는다.

## Facts

각 사실은 `text`와 `source`를 가진다. 날짜·금액·비율·기간·자격·예외는 한 사실에
뭉치지 말고 각각 기록한다. 출처가 없는 항목은 `assumption: true`로 표시하고 최종 문안에
확정형으로 쓰지 않는다.

## Protection

`protected_strings`는 부분 일치가 아니라 정확한 문자열 보존 계약이다. 법정 문구나 긴
인용은 파일로 분리하지 말고 brief에 그대로 넣어 validator가 대조할 수 있게 한다.
