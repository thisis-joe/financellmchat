# 00. 프로젝트 가이드

이 문서는 전체 문서의 입구다.  
처음에는 이 파일을 위에서 아래로 읽고, 실행이 필요하면 `01-runbook.md`, 구조와 RAG 원리가 궁금하면 `02-architecture-and-rag.md`로 넘어가면 된다.

## 문서 읽는 순서

1. `00-project-guide.md`
   - 프로젝트가 무엇인지, 어떤 순서로 읽어야 하는지 잡는다.

2. `01-runbook.md`
   - 실제 실행, 빌드, API 확인 방법만 본다.

3. `02-architecture-and-rag.md`
   - Spring Boot, MySQL, Python RAG, LangGraph, embedding, Gemma, LoRA/QLoRA가 어떻게 연결되는지 본다.

4. `03-phase-1-thinking.md`
   - 1차에서 왜 Spring MVC와 기본 RAG 골격부터 만들었는지 읽는다.

5. `04-phase-2-thinking.md`
   - 2차에서 왜 부산은행 적립식예금 PDF로 범위를 좁혔는지 읽는다.

6. `05-phase-3-thinking.md`
   - 3차에서 왜 Hugging Face LLM과 Spring 피드백 기능을 붙였는지 읽는다.

7. `06-phase-4-thinking.md`
   - 4차에서 검색 품질을 어떻게 발견하고 개선했는지 읽는다.

8. `07-phase-5-thinking.md`
   - 5차에서 왜 Vercel 정적 프론트와 Cloudflare Tunnel API 배포로 나누었는지 읽는다.

9. `08-phase-6-thinking.md`
   - 6차에서 왜 모든 질문을 RAG 검색으로 보내지 않고 질문 유형을 먼저 나누었는지 읽는다.

10. `09-custom-domain-https.md`
   - `bnkaichat.xyz` 커스텀 도메인과 HTTPS 연결 방법을 확인한다.

11. `10-lora-qlora-dataset.md`
   - LoRA/QLoRA를 어디에 쓰고, 학습 데이터셋을 어떤 포맷으로 만들지 본다.

12. `11-phase-7-thinking.md`
   - 7차에서 답변근거 API와 LoRA 데이터셋 설계를 왜 추가했는지 읽는다.

## 한 문단으로 이해하기

이 프로젝트는 `BNK부산은행 상품공시 > 예금상품 > 적립식예금` PDF를 바탕으로 사용자의 질문에 답하는 RAG 학습 프로젝트다. 사용자가 브라우저 챗봇에 질문하면 Spring Boot가 `/api/ask` 요청을 받고, Python FastAPI RAG 서비스에 질문을 전달한다. Python은 MySQL에 저장된 PDF chunk를 검색하고, 검색된 근거를 Gemma 4 E4B 4bit MLX 모델 또는 문서기반 추출 답변으로 정리한다. Spring은 그 결과를 사용자에게 돌려주고 질문 이력, 검색 근거, 피드백을 MySQL에 저장한다.

이 프로젝트는 큰 금융 플랫폼을 흉내 내는 것이 아니라, 작지만 명확하게 동작하는 RAG 챗봇을 목표로 한다. 그래서 프론트는 단일 정적 화면으로 유지하고, 문서 적재는 raw PDF와 importer로 처리하며, 답변 품질은 대표 질문이 안정적으로 맞는지로 검증한다.

## 현재 상태

현재 프로젝트는 다음 상태까지 진행되었다.

- Spring Boot MVC 기반 백엔드가 동작한다.
- MySQL에 부산은행 적립식예금 PDF chunk가 저장된다.
- Python FastAPI RAG 서비스가 MySQL 문서를 검색한다.
- LangGraph로 RAG 단계를 연결한다.
- 시연용 Python RAG 실행은 Gemma 4 E4B 4bit MLX 모델로 답변 생성을 시도한다.
- LLM 실패 시 문서에서 관련 문장을 뽑아 질문 의도에 맞게 정리하는 fallback 답변으로 돌아간다.
- 검색은 TF-IDF, 규칙 기반 재점수화, embedding을 섞은 하이브리드 방식으로 개선했다.
- 인사말, 예금 종류 안내, 추천 질문은 RAG 검색 전에 직접 응답 또는 추천 전용 흐름으로 처리한다.
- `50대 추천`처럼 조건이 있는 질문은 청년 전용 상품이 섞이지 않도록 연령 기반 필터를 적용한다.
- `10대 추천`, `만 18세 추천`처럼 나이가 중요한 질문은 PDF의 `가입대상/가입자격` 내용을 확인한 뒤 만 19세 이상 상품을 제외한다.
- 출처 표시는 chunk 번호가 아니라 사용자가 알아볼 수 있는 파일 제목 중심으로 정리했다.
- 답변 하단의 작은 `답변근거` 버튼으로 검색 점수, 발췌문, 근거 문서를 확인할 수 있다.
- Spring은 질문 이력과 답변 피드백을 저장한다.
- LoRA/QLoRA는 상품 지식 암기가 아니라 RAG 근거를 읽고 안전한 답변 형식을 학습하는 방향으로 데이터셋 포맷을 설계했다.
- 프론트는 `index.html`, `style.css`, `app.js` 세 파일로 끝낸다.
- 배포는 Vercel 정적 프론트와 Cloudflare Tunnel로 공개한 로컬 Spring API를 연결하는 방식으로 정리했다.
- Vercel 기본 도메인 `https://financellmchat.vercel.app`은 정적 화면과 `/api/*` rewrite 동작을 확인했다.
- 커스텀 도메인 `bnkaichat.xyz`와 `www.bnkaichat.xyz`는 Vercel 프론트 도메인으로 연결하고, `api.bnkaichat.xyz`는 Cloudflare Tunnel API 도메인으로 유지한다.

## 현재 아키텍처

```text
브라우저 챗봇
  -> Spring Boot /api/ask
  -> RagService
  -> RagClient
  -> Python FastAPI /ask
  -> 질문 유형 분류
  -> 직접 응답, 추천 응답, 또는 MySQL financial_documents 검색
  -> 검색 근거 기반 LLM 답변 또는 문서기반 fallback 답변 반환
  -> Spring이 query_histories 저장
  -> 사용자가 피드백을 누르면 answer_feedbacks 저장
```

배포 후 외부 접속 흐름은 다음처럼 본다.

```text
사용자 브라우저
  -> Vercel 정적 프론트
  -> /api/* 요청 rewrite
  -> https://api.bnkaichat.xyz
  -> Cloudflare Tunnel
  -> 개인 Mac의 Spring Boot :8080
  -> Python RAG :8000
  -> MySQL
```

## 지금 중요한 기능

- 대화성 입력: `ㅎㅇ`, `안녕`, `ㅂ2`, `ㅂㅇ`, `ㅅㄱ`, `수고`, `잘가` 같은 입력에는 상품 추천이 아니라 자연스러운 안내를 돌려준다.
- 예금 종류: `예금 종류`라고 물으면 예금상품 분류와 현재 답변 가능한 범위를 알려준다.
- 상품 질문: `펫 적금 혜택`처럼 상품명이 있으면 해당 상품 문서를 우선 검색한다.
- 추천 질문: `50대 추천`처럼 조건이 있으면 부적합한 청년/장병 전용 상품을 제외한다.
- 가입대상 검증: 추천 후보를 고를 때 PDF의 `가입대상`, `가입자격`, `가입제한` 구간에서 나이 조건을 확인한다.
- 출처 확인: 답변 하단에서 원본 PDF를 다운로드할 수 있다.
- 답변근거 확인: 답변 하단의 작은 `답변근거` 버튼을 누르면 검색 근거와 score를 볼 수 있다.

## 현재 한계

현재 추천 검증은 PDF에서 추출 가능한 텍스트를 기준으로 한다. `만 19세 이상`, `만 34세 이하`, `제한없음`, `연령에 관계없이`처럼 비교적 명확한 나이 조건은 읽어서 후보를 걸러낸다. 다만 소득, 거주지, 무주택, 군복무, 위탁기관 선정 여부처럼 여러 조건이 결합된 경우에는 아직 완전한 자격 판정이 아니라 `추가 확인 필요`로 안내하는 단계다. 표가 이미지로 들어간 PDF나 OCR이 필요한 영역도 현재는 놓칠 수 있다.

## 앞으로 할 일

다음 목표는 기능을 늘리는 것이 아니라 시연 안정성을 높이는 것이다.

1. 대표 질문 10개는 `scripts/check_representative_questions.py`로 고정했고, 수정 때마다 이 스크립트를 실행한다.
2. Vercel 화면과 Cloudflare Tunnel API는 같은 대표 질문 스크립트를 배포 주소에 실행해 확인한다.
3. `bnkaichat.xyz` 커스텀 도메인은 Vercel 프론트 도메인으로 연결하고, `api.bnkaichat.xyz`는 Cloudflare Tunnel API 전용으로 유지한다.
4. 새 PDF를 추가할 때도 raw 폴더와 importer 흐름을 유지한다.
5. 피드백 데이터를 모아 나중에 LoRA/QLoRA 학습 데이터 후보로 검토한다.
6. `답변근거`로 검색이 빗나간 사례를 모아 대표 질문과 학습 데이터 후보를 보강한다.
7. 추천 검증은 나이 조건 다음으로 소득, 거주지, 무주택, 군복무 같은 비연령 조건을 단계적으로 구조화한다.

지금은 MSA, 관리자 페이지, OCR, 벡터 DB, 복잡한 추천 알고리즘을 성급하게 붙이지 않는다. 이 프로젝트의 강점은 작은 구조 안에서 Spring MVC, MySQL, Python RAG, LLM 생성 흐름을 끝까지 설명할 수 있다는 점이다.

## 코드에서 먼저 볼 파일

Spring 질문 흐름:

- `src/main/java/com/example/financerag/rag/RagApiController.java`
- `src/main/java/com/example/financerag/rag/RagService.java`
- `src/main/java/com/example/financerag/rag/RagClient.java`

Spring 피드백 흐름:

- `src/main/java/com/example/financerag/feedback/FeedbackApiController.java`
- `src/main/java/com/example/financerag/feedback/FeedbackService.java`
- `src/main/java/com/example/financerag/feedback/AnswerFeedback.java`

Python RAG 흐름:

- `rag-service/app.py`

대표 질문 확인:

- `scripts/check_representative_questions.py`

PDF 적재:

- `scripts/extract_busanbank_zip.py`
- `scripts/import_busanbank_installment_pdfs.py`

프론트:

- `src/main/resources/static/index.html`
- `src/main/resources/static/style.css`
- `src/main/resources/static/app.js`

## 앞으로 "문서정리"의 의미

앞으로 사용자가 "문서정리"라고 말하면 다음 작업을 수행한다.

1. `docs` 안의 모든 문서를 순서대로 읽는다.
2. 중복 내용을 합친다.
3. 가능한 적은 수의 파일로 정리한다.
4. 번호 순서대로 읽으면 자연스럽게 이해되도록 다시 구성한다.
5. 설명이 필요한 용어는 각 파일 최하단에 용어 메모로 남긴다.
6. 차수별 사고 흐름 문서는 별도 파일로 유지한다.

## 용어 메모

- RAG: Retrieval-Augmented Generation. 먼저 문서를 검색하고, 그 검색 결과를 근거로 답변하는 방식이다.
- Spring Boot: Java 백엔드 애플리케이션을 빠르게 만들기 위한 Spring 기반 프레임워크다.
- FastAPI: Python으로 REST API를 만들 때 쓰는 웹 프레임워크다.
- MySQL: 문서 chunk, 질문 이력, 피드백을 저장하는 관계형 데이터베이스다.
- chunk: 긴 PDF 본문을 검색하기 좋게 나눈 작은 텍스트 조각이다.
- citation: 답변이 어떤 문서를 근거로 했는지 보여주는 출처 정보다.
- 답변근거: 저장된 citation을 디버그용으로 다시 보여주는 기능이다. 사용자에게는 작게 보이고, 개발자에게는 검색 품질 확인 도구가 된다.
- fallback: 외부 서비스나 모델이 실패했을 때 전체 기능이 멈추지 않도록 대체 경로로 응답하는 방식이다.
- LLM: Large Language Model. 자연어 문장을 생성하거나 요약하는 대형 언어 모델이다.
- extractive answer: 문서 안의 관련 문장을 뽑고 정리해 답하는 방식이다. 모델이 새 내용을 꾸며내는 위험을 줄일 수 있다.
- MLX: Apple Silicon에서 모델 실행을 최적화하기 위한 머신러닝 런타임이다.
- Vercel: 정적 프론트엔드와 웹 프로젝트를 쉽게 배포하는 플랫폼이다.
- Cloudflare Tunnel: 집이나 회사 PC의 로컬 서버를 포트포워딩 없이 외부 도메인에 안전하게 연결하는 방식이다.
- rewrite: 브라우저가 호출한 경로를 배포 플랫폼이 다른 서버 주소로 전달하는 설정이다.
- 커스텀 도메인: Vercel이 기본으로 주는 주소가 아니라 사용자가 구매한 도메인이다.
- apex domain: `bnkaichat.xyz`처럼 앞에 `www`나 `api`가 붙지 않은 루트 도메인이다.
- 질문 유형 분류: 사용자의 입력이 인사말, 목록 요청, 추천 요청, 문서 검색 요청 중 무엇인지 먼저 나누는 처리다.
- 대화성 입력: 상품 문서 검색보다 인사, 감사, 종료, 도움말 안내에 가까운 짧은 채팅 표현이다.
- 회귀 질문: 코드를 고친 뒤 이전에 잘 되던 답변이 계속 잘 되는지 확인하기 위해 정해 둔 대표 질문이다.
- 가입대상 검증: 추천 전에 상품 PDF의 가입 가능 조건을 읽고 사용자 조건과 맞지 않는 상품을 제외하는 처리다.
- SFT: 질문과 정답 답변 예시로 모델을 지도학습하는 방식이다.
- adapter: LoRA/QLoRA에서 원본 모델 전체가 아니라 추가로 학습하는 작은 모듈이다.
