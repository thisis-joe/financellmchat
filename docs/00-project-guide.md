# 00. 읽는 순서와 현재 상태

이 문서는 프로젝트 전체를 처음 이해하기 위한 입구다.  
위에서 아래로 읽으면 지금 무엇을 만들었고, 왜 다음 작업이 필요한지 잡을 수 있다.

## 문서 읽는 순서

1. `00-project-guide.md`
   - 프로젝트의 목표, 현재 상태, 앞으로의 계획을 먼저 잡는다.

2. `01-runbook.md`
   - 로컬 실행, 빌드, 대표 질문 확인, Vercel/Cloudflare 배포 확인 방법만 본다.

3. `02-architecture-and-rag.md`
   - Spring Boot, MySQL, Python RAG, LangGraph, Gemma, GPT API 선택 모드가 어떻게 연결되는지 본다.

4. `03-phase-thinking.md`
   - 1차부터 현재까지 어떤 문제를 발견했고, 왜 파일과 구조를 그렇게 바꿨는지 흐름으로 읽는다.

5. `04-installment-deposit-comparison-insights.md`
   - 적립식예금 PDF를 다시 읽어 만든 상품 비교 지식표와 추천 기준을 본다.

6. `docs/rag/deposit-chatbot-knowledge.md`
   - 챗봇이 상담할 때 참고하는 상품 지식, 추천 규칙, 대화 맥락 처리 규칙을 본다.

7. `05-lora-qlora-dataset.md`
   - LoRA/QLoRA를 언제, 어디서, 왜 쓰고 어떤 데이터셋으로 학습할지 본다.

8. `06-interview-qa.md`
   - 면접에서 나올 수 있는 Spring, DB, RAG, AI, LoRA/QLoRA 질문과 답변을 본다.

## 프로젝트 한 문단 요약

이 프로젝트는 `BNK부산은행 상품공시 > 예금상품 > 적립식예금` PDF를 바탕으로 질문에 답하는 RAG 챗봇이다. 사용자가 웹 챗봇에 질문하면 Spring Boot가 `/api/ask`를 받고, Python FastAPI RAG 서비스가 MySQL에 저장된 PDF chunk와 `product_knowledge.json` 상품 비교 지식표, `docs/rag/deposit-chatbot-knowledge.md` 상담 규칙을 함께 사용한다. 추천, 기간, 금리, 소액, 목록 질문은 구조화된 비교 지식표가 먼저 판단하고, 세부 근거가 필요한 질문은 PDF chunk 검색으로 보강한다. Spring은 질문 이력, 검색 근거, 피드백을 저장하고, 화면은 단일 HTML/CSS/JS 프론트로 유지한다. 근거와 PDF 다운로드는 작은 `답변근거` 버튼으로 확인한다.

더 자연스러운 답변이 필요할 때는 `RAG_GENERATION_MODE=openai`로 OpenAI Responses API를 선택할 수 있다. 이 경우에도 PDF 검색은 그대로 RAG가 맡고, GPT API는 검색된 근거를 자연스럽게 답변하는 역할만 한다.

## 현재 상태

현재 프로젝트는 작지만 실행 가능한 RAG 챗봇 형태까지 왔다.

- Spring Boot MVC 백엔드가 질문 API, 이력 저장, 피드백 저장, PDF 다운로드를 담당한다.
- MySQL에는 부산은행 적립식예금 PDF chunk가 저장된다.
- Python FastAPI는 LangGraph 흐름으로 문서를 읽고 검색하고 답변을 생성한다.
- 검색은 TF-IDF, embedding, 상품명/질문 의도 규칙 보정을 섞은 hybrid 방식이다.
- `product_knowledge.json`은 금리, 기간, 최소금액, 우대조건, 대상 태그를 담아 추천·비교 질문을 먼저 처리한다.
- 프론트는 최근 대화 히스토리를 함께 보내고, Python은 `user_age`, `active_product`, `last_intent` 같은 conversation state로 후속 질문을 재해석한다.
- `docs/rag/deposit-chatbot-knowledge.md`는 상품별 지식, 추천 규칙, 답변 길이, 예외 처리, 검증 기준을 담은 상담용 지식 문서다.
- 현재 생성 모델은 로컬 실행 가능한 `mlx-community/gemma-4-e4b-it-4bit`를 우선 사용한다.
- 선택적으로 `RAG_GENERATION_MODE=openai`와 `OPENAI_API_KEY`를 설정해 GPT API 답변 생성 모드를 사용할 수 있다.
- 모델 실행 실패 시 문서에서 관련 문장을 뽑아 답하는 fallback이 있다.
- `ㅎㅇ`, `ㅂㅇ`, `수고` 같은 대화성 입력은 상품 검색으로 보내지 않고 자연스럽게 안내한다.
- `예금 종류`는 예금상품 분류와 현재 답변 가능한 범위를 안내한다.
- `10대 추천`, `60대 추천`, `30대 과장`, `6개월`, `우대금리 높은 순`, `소액 시작`처럼 조건이 있는 질문은 상품 비교 지식표를 기준으로 후보를 고르고, 맞지 않는 상품을 제외한다.
- 답변근거 API로 검색 score, snippet, PDF 다운로드를 확인할 수 있다.
- 프론트는 Vercel에 정적 배포하고, API는 Cloudflare Tunnel로 개인 Mac의 Spring Boot에 연결한다.
- 대표 질문 44개 기준으로 인사, 무의미 입력, 종료 인사, 상품 설명, 추천, 가입대상, 서류, 금리/기간/목록/소액 질문, 후속 맥락 질문을 회귀 검증한다.

## 현재 답변 원칙

현재 가장 중요한 원칙은 답변이 템플릿처럼 보이지 않게 만드는 것이다.  
기본 대화는 GPT처럼 자연스럽게 받고, 금융상품 정보가 필요한 경우에만 RAG 검색을 적극적으로 사용한다.

목표 흐름은 다음과 같다.

```text
사용자 입력
  -> 대화 의도와 금융 의도 파악
  -> 일상 대화면 자연스럽게 응답하고 검색 가능한 질문으로 유도
  -> 추천, 기간, 금리 비교 질문이면 상품 비교 지식표 우선 사용
  -> 상품 설명, 가입대상, 서류 질문이면 RAG 검색으로 근거 보강
  -> 검색 근거를 바탕으로 본문에는 자연스러운 답변 작성
  -> 출처, score, PDF 다운로드는 답변근거 버튼에 숨김
```

따라서 본문에 `핵심 답변`, `확인 내용`, `출처`, `추가 확인 필요` 같은 고정 제목을 드러내는 방식은 줄인다. 사용자는 먼저 자연스러운 상담 답변을 보고, 필요할 때만 답변근거를 펼쳐 근거와 PDF를 확인한다.

## GPT API가 필요한 이유

로컬 Gemma 4bit 모델은 무료로 실행할 수 있고 구조 학습에 좋다. 하지만 한국어 대화의 유연성, 짧은 입력의 의도 해석, 상담 말투는 한계가 있다. `나 5세임`, `나 군인인데`, `이 상품 설명해줘`, `ㅎㅇ` 같은 입력은 단순 검색보다 대화 생성 품질이 중요하다.

그래서 GPT API는 다음 역할로 선택적으로 사용할 수 있게 준비했다.

- RAG 검색 결과를 사람이 읽기 좋은 상담 답변으로 바꾸기
- 짧고 애매한 입력에 자연스럽게 반응하기
- 근거에 없는 내용은 말하지 않도록 제어하기
- 시연 품질을 높이기

단, GPT API가 PDF 검색을 대체하면 안 된다. 최신 상품 조건은 반드시 RAG가 찾은 문서 근거에서 가져와야 한다.

## 남은 마무리 계획

1. `product_knowledge.json`의 금리·기간·우대조건 추출 정확도를 계속 검수한다.
2. 세후 이자, 월 납입액, 만기 수령액 계산 답변을 더 정교하게 만든다.
3. 답변근거를 보고 검색이 빗나간 사례를 모은다.
4. 좋은 답변과 나쁜 답변을 피드백으로 모아 LoRA/QLoRA 학습 데이터 후보를 만든다.
5. LoRA/QLoRA는 상품 지식을 외우게 하는 것이 아니라, RAG 근거를 자연스럽고 안전하게 답하는 습관을 학습시키는 용도로 진행한다.

지금은 MSA, 관리자 페이지, 벡터 DB를 한꺼번에 붙이지 않는다. OCR도 이미지-only PDF가 실제로 추가될 때 도입한다. 이 프로젝트의 강점은 작은 구조 안에서 Spring MVC, MySQL, Python RAG, 구조화 상품 비교, LLM 생성, 피드백, 배포 흐름을 끝까지 설명할 수 있다는 점이다.

## 코드에서 먼저 볼 파일

Spring 질문 흐름:

- `src/main/java/com/example/financerag/rag/RagApiController.java`
- `src/main/java/com/example/financerag/rag/RagService.java`
- `src/main/java/com/example/financerag/rag/RagClient.java`

Spring 피드백과 근거 확인:

- `src/main/java/com/example/financerag/feedback/FeedbackApiController.java`
- `src/main/java/com/example/financerag/feedback/FeedbackService.java`
- `src/main/java/com/example/financerag/rag/RagEvidenceResponse.java`

Python RAG:

- `rag-service/app.py`

대표 질문 확인:

- `scripts/check_representative_questions.py`

상품 비교 지식 생성:

- `scripts/build_installment_deposit_knowledge.py`
- `rag-service/product_knowledge.json`
- `docs/rag/deposit-chatbot-knowledge.md`

PDF 적재:

- `scripts/extract_busanbank_zip.py`
- `scripts/import_busanbank_installment_pdfs.py`

프론트:

- `src/main/resources/static/index.html`
- `src/main/resources/static/style.css`
- `src/main/resources/static/app.js`

## 용어 메모

- RAG: 문서를 먼저 검색하고, 그 검색 결과를 근거로 답변하는 방식이다.
- Spring MVC: Controller, Service, Repository 계층으로 웹 요청을 처리하는 Spring의 전통적인 구조다.
- FastAPI: Python으로 API 서버를 만들 때 쓰는 프레임워크다.
- MySQL: PDF chunk, 질문 이력, 피드백을 저장하는 관계형 데이터베이스다.
- chunk: 긴 PDF 본문을 검색하기 좋게 나눈 작은 텍스트 조각이다.
- citation: 답변이 어떤 문서를 근거로 했는지 나타내는 정보다.
- 답변근거: 검색 score, snippet, PDF 다운로드를 사용자가 필요할 때 확인하는 기능이다.
- fallback: 모델이나 외부 서비스가 실패해도 기본 답변이 나오게 하는 대체 경로다.
- LLM: 자연어 답변을 생성하는 대형 언어 모델이다.
- GPT API: OpenAI의 대화형 모델을 API로 호출하는 방식이다. 이 프로젝트에서는 선택 가능한 자연어 답변 생성 모드로 둔다.
- LoRA: 원본 모델 전체가 아니라 작은 adapter만 학습하는 파인튜닝 방식이다.
- QLoRA: 양자화된 모델 위에서 LoRA 학습을 수행해 메모리 사용량을 줄이는 방식이다.
