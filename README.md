# Writing System

AI가 쓴 한국어에서 어색한 표현과 글의 구성 문제를 찾고, **사실·의도·작성자의 말투를 보존하며 고치는 에이전트 스킬**입니다.

단어만 자연스럽게 바꾸는 것으로 해결되지 않는 반복, 추상적인 결론, 빠진 행동 주체를 함께 살핍니다. 문제가 없는 문장은 그대로 둡니다. 원문이 없으면 작성 목적과 사실 자료로 초안을 만듭니다.

## 이런 작업에 사용합니다

- LinkedIn 글, 소개 페이지, 안내문에서 AI 특유의 조립된 표현을 줄이고 싶을 때
- 제목과 본문이 같은 말만 반복하거나, 읽고도 무엇을 해야 할지 모호할 때
- 숫자·조건·주장의 강도를 바꾸지 않고 문장을 다듬어야 할 때

스킬 없이도 좋은 결과를 얻을 수 있습니다. 이 저장소는 반복해서 확인할 편집 기준을 에이전트에 제공하려는 도구이며, 특정 모델보다 좋은 글을 보장하지 않습니다.

## 빠른 시작

Git으로 내려받은 뒤, 로컬 파일을 읽을 수 있는 에이전트에서 아래처럼 요청하세요. 별도 Python 패키지나 API 키는 필요하지 않습니다. 검증 스크립트는 Python 3.11 이상을 사용합니다.

```bash
git clone https://github.com/seeknowzip/writing-system-public.git
cd writing-system-public
python3 -m unittest discover -s tests -p 'test_*.py'
```

```text
이 폴더의 SKILL.md를 읽고 writing-system을 적용해줘.
아래 글에서 어색한 부분을 먼저 진단한 뒤 고쳐줘.
숫자, 조건, 내 판단의 강도와 존댓말은 유지하고,
추가 사실이 필요한 부분은 본문에 지어 넣지 말고 따로 알려줘.

[다듬을 글]
```

자주 사용한다면 **저장소 폴더 전체**를 이용 중인 에이전트의 사용자 스킬 위치에 `writing-system` 이름으로 연결하거나 설치하세요. `SKILL.md` 하나만 복사하면 참조 문서와 검증기가 빠집니다. 스킬을 자동 탐색하지 않는 도구에서도 위와 같이 파일을 직접 지정할 수 있습니다.

## 어떻게 다듬나요?

**보존 목록 → 문제 진단 → 필요한 구간 수정 → 기계 검사 → 의미 대조** 순서입니다.

예를 들어 “접수 후 검토가 진행될 수 있습니다”를 더 시원하게 보이도록 “접수하면 검토합니다”로 바꾸면 조건과 확신이 달라집니다. 이 스킬은 매끄러움과 의미 보존을 별도로 확인합니다. 이 예시는 설명용 합성 문장입니다.

결과에는 수정한 글, 바꾼 이유, 확인할 사실, 검증 결과가 포함됩니다. 글만 요청하면 설명을 줄일 수 있지만 미확인 사실과 실패한 검사는 숨기지 않습니다.

### 새 글 쓰기

```text
SKILL.md의 draft 경로로 안내문을 작성해줘.
독자: 처음 이용하는 관리자
목적: 설정을 마치도록 안내
사실: 관리자는 알림을 켜거나 끌 수 있다. 저장 버튼을 눌러야 반영된다.
말투: 해요체
다음 행동: 알림 설정 저장
자료에 없는 기능이나 효과는 추가하지 말아줘.
```

### 내 글을 참고하게 하기 — 선택 사항

직접 쓴 글이 없어도 사용할 수 있습니다. 참고할 글이 있다면 공개 저장소에 올리지 않고 로컬에 보관하세요.

```bash
mkdir -p local/author-samples
```

해당 폴더에 자신의 글을 넣고 이렇게 요청합니다.

```text
local/author-samples/my-post.md는 내가 직접 쓴 글이야.
references/personalization.md에 따라 표현 선택을 참고해줘.
어떤 특징을 이번 글에 적용했는지 짧게 알려줘.
샘플의 사례·숫자·인물은 새 글의 사실로 가져오지 말아줘.
```

고정 페르소나를 학습시키는 기능은 아닙니다. 지정한 글에서 용어, 격식, 판단을 설명하는 방식을 참고합니다. `local/`은 Git에서 제외되지만, 에이전트가 읽은 내용은 사용 중인 모델 서비스로 전송될 수 있습니다.

## 검증 도구

에이전트가 사용할 검사기이며 글을 자동 작성하는 프로그램은 아닙니다. 아래 합성 예제로 설치 상태를 확인할 수 있습니다.

```bash
python3 scripts/validate_brief.py examples/brief.json
python3 scripts/validate_copy.py --brief examples/brief.json --copy examples/source.md
python3 scripts/validate_rewrite_output.py --source examples/source.md --output examples/source.md --diag examples/diagnosis.json --preserve '["알림"]'
```

자기 글의 진단 틀을 만들 때는 다음 명령을 사용합니다. 생성 직후에는 `pending` 상태이므로 문장별 진단을 마치기 전까지 검사를 통과하지 않습니다.

```bash
mkdir -p local
python3 scripts/validate_rewrite_output.py --source examples/source.md --diagnostic-template > local/diagnosis-template.json
```

기계 검사는 보호 문자열, 숫자, 진단과 수정 범위 등을 확인합니다. 의미 보존과 글의 매력까지 증명하지는 않습니다. 독립 검토 도구가 없으면 자기 검토임을 표시합니다.

## 구성과 공개 범위

- [SKILL.md](SKILL.md): 기존 글 수정·새 글 작성·짧은 UI 문구의 실행 절차
- [references](references): 실패 유형, 수리 방법, 장르별 정보 역할, 개인화 절차
- [scripts](scripts)와 [tests](tests): 입력·수정 범위·발행 상태 검사와 회귀 테스트
- [examples](examples): 실행 확인용 합성 입력. 실제 고객 글이나 품질 비교 결과가 아닙니다.

개인용 저장소에서 공개에 필요한 부분을 별도로 옮겼습니다. 개인 글, Notion 원문, 제삼자 글의 발췌집, 비공개 업무 기록과 과거 모델 평가 데이터는 포함하지 않습니다. 이에 따라 외부 원문 패킷을 자동 선택하는 기능도 포함하지 않습니다. 참고자료가 있으면 사용자가 직접 지정하고, 없으면 장르별 지침으로 작성합니다.

`humanize-korean`은 별도의 선택적 후처리입니다. 이 저장소가 자동 설치하거나 호출하지 않습니다.

## 라이선스

자체 코드와 문서는 [MIT](LICENSE)입니다. 관련 외부 자료와 공개본 제외 범위는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 정리했습니다. 이 라이선스는 다른 사람이 쓴 글이나 사용자가 가져온 자료의 이용 권한까지 부여하지 않습니다.
