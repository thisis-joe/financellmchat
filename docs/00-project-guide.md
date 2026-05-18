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

## 한 문단으로 이해하기

이 프로젝트는 `BNK부산은행 상품공시 > 예금상품 > 적립식예금` PDF를 바탕으로 사용자의 질문에 답하는 RAG 학습 프로젝트다. 사용자가 브라우저 챗봇에 질문하면 Spring Boot가 `/api/ask` 요청을 받고, Python FastAPI RAG 서비스에 질문을 전달한다. Python은 MySQL에 저장된 PDF chunk를 검색하고, 검색된 근거를 Gemma 4 E4B 4bit MLX 모델 또는 문서기반 추출 답변으로 정리한다. Spring은 그 결과를 사용자에게 돌려주고 질문 이력과 피드백을 MySQL에 저장한다.

## 현재 상태

현재 프로젝트는 다음 상태까지 진행되었다.

- Spring Boot MVC 기반 백엔드가 동작한다.
- MySQL에 부산은행 적립식예금 PDF chunk가 저장된다.
- Python FastAPI RAG 서비스가 MySQL 문서를 검색한다.
- LangGraph로 RAG 단계를 연결한다.
- 시연용 Python RAG 실행은 Gemma 4 E4B 4bit MLX 모델로 답변 생성을 시도한다.
- LLM 실패 시 문서에서 관련 문장을 뽑아 질문 의도에 맞게 정리하는 fallback 답변으로 돌아간다.
- 검색은 TF-IDF, 규칙 기반 재점수화, embedding을 섞은 하이브리드 방식으로 개선했다.
- 출처 표시는 chunk 번호가 아니라 사용자가 알아볼 수 있는 파일 제목 중심으로 정리했다.
- Spring은 질문 이력과 답변 피드백을 저장한다.
- 프론트는 `index.html`, `style.css`, `app.js` 세 파일로 끝낸다.

## 현재 아키텍처

```text
브라우저 챗봇
  -> Spring Boot /api/ask
  -> RagService
  -> RagClient
  -> Python FastAPI /ask
  -> MySQL financial_documents 검색
  -> 검색 근거 기반 LLM 답변 또는 fallback 답변 반환
  -> Spring이 query_histories 저장
  -> 사용자가 피드백을 누르면 answer_feedbacks 저장
```

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
- fallback: 외부 서비스나 모델이 실패했을 때 전체 기능이 멈추지 않도록 대체 경로로 응답하는 방식이다.
- LLM: Large Language Model. 자연어 문장을 생성하거나 요약하는 대형 언어 모델이다.
- extractive answer: 문서 안의 관련 문장을 뽑고 정리해 답하는 방식이다. 모델이 새 내용을 꾸며내는 위험을 줄일 수 있다.
- MLX: Apple Silicon에서 모델 실행을 최적화하기 위한 머신러닝 런타임이다.
