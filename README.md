# Daily Quote Agent

FastAPI, LangGraph, LangChain, Amazon Bedrock, DynamoDB, SES를 사용한 오늘의 명언 서비스입니다.

이 애플리케이션은 Asia/Seoul 날짜 기준으로 하루에 하나의 공유 명언을 생성하고, DynamoDB에 저장한 뒤, 같은 날짜에는 저장된 명언을 재사용합니다. EventBridge Scheduler와 Lambda를 함께 사용하면 활성 구독자에게 이메일로 오늘의 명언을 발송할 수 있습니다.

## 주요 기능

- Amazon Bedrock으로 실제 인물의 한국어 명언을 생성합니다.
- 명언, 원문, 저자, 출처, 주제, 짧은 해설, 오늘의 질문을 구조화된 응답으로 받습니다.
- 같은 날짜에는 명언을 중복 생성하지 않고 저장된 값을 재사용합니다.
- 최근 명언 이력을 참고해 비슷한 주제나 맥락이 반복되지 않도록 합니다.
- Tavily 검색과 Bedrock 검증 단계를 통해 명언 출처를 선택적으로 검증합니다.
- EventBridge Scheduler, Lambda, Amazon SES를 사용해 HTML/텍스트 이메일을 발송할 수 있습니다.

## 아키텍처

```text
사용자 또는 스케줄러
  -> FastAPI /daily-quote/today
  -> LangGraph 워크플로우
  -> Amazon Bedrock Runtime
  -> DynamoDB daily quote table

EventBridge Scheduler
  -> Lambda scheduler
  -> FastAPI /daily-quote/today
  -> DynamoDB users table
  -> Amazon SES
```

## 프로젝트 구조

```text
app/
  main.py                 FastAPI 라우트와 의존성 설정
  quote_agent.py          Bedrock 명언 생성 프롬프트와 구조화 응답
  quote_graph.py          LangGraph 명언 생성 워크플로우
  quote_validator.py      Tavily 검색과 Bedrock 검증
  daily_quote_store.py    DynamoDB 저장소
  models.py               Pydantic 응답 모델
infra/
  ecs/                    ECS task definition, IAM policy 예시
  scheduler/              이메일 발송용 Lambda
tests/                    API, 워크플로우, 스케줄러 테스트
```

## 필요 조건

- Python 3.12
- Bedrock Runtime과 DynamoDB를 사용할 수 있는 AWS 자격 증명
- 설정한 Bedrock 모델에 대한 사용 권한
- 선택 사항: 명언 출처 검증용 Tavily API 키
- 선택 사항: 이메일 발송용 Amazon SES 인증 발신자/수신자

## 로컬 실행 준비

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

`.env` 파일을 자신의 AWS 환경에 맞게 수정합니다.

```env
AWS_REGION=ap-northeast-2
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
DYNAMODB_DAILY_QUOTES_TABLE_NAME=daily-quotes
DYNAMODB_USERS_TABLE_NAME=daily-quote-users
DUPLICATE_CHECK_LIMIT=20
QUOTE_GENERATION_ATTEMPTS=20
BEDROCK_TEMPERATURE=1.0
TAVILY_API_KEY=
QUOTE_VALIDATION_ENABLED=true
```

## 실행

```bash
uvicorn app.main:app --reload
```

API 문서는 아래 주소에서 확인할 수 있습니다.

```text
http://127.0.0.1:8000/daily-quote/docs
```

주요 엔드포인트:

```text
GET /daily-quote/health
GET /daily-quote/today
GET /daily-quote/recent?limit=10
```

## 테스트

```bash
pytest
```

## Docker 실행

```bash
docker build -t daily-quote-agent:local .
docker run --rm -p 8000:8000 --env-file .env daily-quote-agent:local
```

## DynamoDB 테이블

오늘의 명언 테이블:

```text
테이블 이름: daily-quotes
파티션 키: quote_date (String)
```

사용자 테이블:

```text
테이블 이름: daily-quote-users
파티션 키: email (String)
속성:
  is_active: Boolean
  send_on_weekends: Boolean
```

## GitHub CI

이 레포지토리에는 GitHub Actions 워크플로우가 포함되어 있습니다.

push 또는 pull request가 생성되면 개발 의존성을 설치한 뒤 `pytest`를 실행합니다.

## 배포 메모

`infra/ecs` 디렉터리의 파일들은 AWS 배포 예시입니다. 실제 배포 전에 계정 ID, IAM Role 이름, ECR 이미지 URI, Secrets Manager ARN을 자신의 환경에 맞게 교체해야 합니다.

스케줄러 Lambda는 아래 환경 변수를 사용합니다.

```text
QUOTE_API_BASE_URL
QUOTE_TODAY_PATH
QUOTE_USERS_TABLE_NAME
QUOTE_USER_EMAILS
QUOTE_EMAIL_SOURCE
QUOTE_API_TIMEOUT_SECONDS
```

`QUOTE_USERS_TABLE_NAME`이 설정되어 있으면 DynamoDB에서 활성 사용자를 읽습니다. `QUOTE_USER_EMAILS`는 사용자 테이블을 쓰지 않을 때만 사용하는 fallback 값입니다.
