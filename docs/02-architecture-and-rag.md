# 02. 구조와 RAG 원리

이 문서는 프로젝트의 구조와 RAG, LangGraph, embedding, Gemma, LoRA/QLoRA의 위치를 한 번에 설명한다.  
코드가 왜 이렇게 나뉘었는지 이해하려면 이 파일을 위에서 아래로 읽으면 된다.

## 주제와 범위

프로젝트 주제는 `BNK부산은행 상품공시 > 예금상품 > 적립식예금` PDF 기반 RAG다. 부산은행 상품공시는 예금, 대출, 기타상품, 서비스이용수수료까지 범위가 넓다. 하지만 처음부터 전체를 다루면 PDF 수집, 분류, 추출, 검색 품질 문제를 한꺼번에 만나게 된다. 그래서 현재는 사용자가 제공한 적립식예금 PDF만 실제 데이터로 사용한다.

현재 DB의 `category`는 다음처럼 문자열 경로로 저장한다.

```text
예금상품>적립식예금
```

나중에 대출상품이나 수수료 자료를 추가해도 같은 importer 구조를 확장하면 된다.

## 전체 흐름

사용자 질문은 Spring Boot를 거쳐 Python RAG 서비스로 이동한다.

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

이 구조에서 Spring은 단순 프록시가 아니다. Spring은 REST API, 요청 검증, Python 호출, 질문 이력 저장, 피드백 저장, PDF 다운로드, 트랜잭션 관리, 예외 응답, 정적 프론트 제공을 맡는다. Python은 RAG 검색과 답변 생성을 맡는다. 이렇게 나눈 이유는 Spring MVC 학습과 AI 파이프라인 학습을 분리해서 보기 위해서다.

## 데이터 흐름

원본 PDF와 처리 결과는 분리한다.

```text
원본 PDF
  -> scripts/extract_busanbank_zip.py
  -> data/raw
  -> scripts/import_busanbank_installment_pdfs.py
  -> PDF 텍스트 추출
  -> chunk 분리
  -> MySQL financial_documents 저장
  -> Python RAG 검색
  -> Spring API 응답
```

`data/raw`에는 원본 PDF를 둔다. 시연 재현을 위해 원본 PDF는 Git에 포함할 수 있다. `data/processed`에는 JSONL과 import report 같은 다시 만들 수 있는 산출물을 둔다. 처리 산출물은 재생성 가능하므로 Git에서 제외한다.

핵심 테이블은 `financial_documents`다.

```text
financial_documents
  PDF chunk 지식 베이스

query_histories
  질문, 답변, 근거 JSON, 상태 저장

answer_feedbacks
  특정 질문 이력에 대한 사용자 평가 저장
```

`financial_documents`에는 `title`, `category`, `institution`, `product_name`, `product_type`, `source`, `source_url`, `content`를 저장한다. 상품명과 제목을 분리한 이유는 같은 상품에도 상품설명서, 약관, 특약, 변경 공시가 따로 존재할 수 있기 때문이다.

## PDF 처리

PDF 텍스트 추출은 `PyMuPDF`를 사용한다. 페이지별 텍스트를 추출한 뒤 약 1,400자 단위로 chunk를 만든다. PDF 전체를 하나의 본문으로 넣으면 질문과 관련된 작은 구간이 긴 문서 안에 묻힐 수 있기 때문이다.

한계도 있다. 표 안의 글자가 이미지로 들어가 있으면 PyMuPDF가 읽지 못할 수 있다. 이 경우 OCR을 검토해야 한다. 다만 현재 단계에서는 먼저 텍스트 레이어 추출로 가능한 범위를 확인한다.

## Python RAG 흐름

`rag-service/app.py`의 핵심 흐름은 다음이다.

```text
ask
  -> load_documents
  -> retrieve_documents
  -> generate_answer
```

`load_documents`는 MySQL에서 부산은행 문서 chunk를 읽는다. `retrieve_documents`는 질문에 맞는 chunk를 찾는다. `generate_answer`는 검색 근거를 바탕으로 Gemma LLM 답변을 만들고, 실패하면 문서기반 추출 답변으로 돌아간다.

LangGraph는 이 단계를 그래프로 연결한다. 여기서 LangGraph는 자율 에이전트라기보다 RAG 상태가 단계별로 어떻게 바뀌는지 명확히 보여주는 워크플로 도구다.

## 검색 방식

현재 검색은 세 가지를 합친다.

```text
TF-IDF 점수 45%
+ embedding 의미 유사도 55%
+ 상품명/항목명 규칙 보정
= 최종 검색 점수
```

처음 검색은 TF-IDF 문자 n-gram이었다. 구현이 단순하고 한국어 조사 차이에 어느 정도 버티지만, `우대금리`, `가입대상`, `만기해지` 같은 질문 의도를 정확히 이해하지는 못했다. 그래서 상품명 감지, 질문 의도 감지, 강한 항목명 감지를 더했다.

그 뒤에도 `혜택 받으려면 뭘 해야 해?`처럼 자연어 표현과 문서 표현이 다른 문제가 남았다. 이 문제를 해결하기 위해 `intfloat/multilingual-e5-small` embedding 모델을 붙였다. E5 계열은 검색용 모델이라 질문에는 `query:`, 문서에는 `passage:` 접두어를 붙여 encoding한다.

embedding만 단독으로 쓰지 않는 이유는 금융 상품 검색에서는 정확한 상품명이 중요하기 때문이다. 의미 검색은 자연어 질문에 강하지만, 상품명이 비슷하면 엉뚱한 상품이 섞일 수 있다. 그래서 TF-IDF와 규칙 보정을 함께 둔다.

## 답변 생성

답변 생성에는 두 경로가 있다.

```text
RAG_GENERATION_MODE=mlx
  -> Gemma 4 E4B 4bit MLX 모델이 답변 생성

RAG_GENERATION_MODE=template 또는 LLM 실패
  -> 문서 안의 관련 문장을 뽑아 답변 구성
```

시연용 실행은 `mlx-community/gemma-4-e4b-it-4bit`를 사용한다. full `google/gemma-4-E4B-it`는 다운로드는 가능했지만 Mac MPS 실행에서 메모리 문제가 있었다. 그래서 Apple Silicon 로컬 실행은 MLX 4bit 경로를 우선한다.

중요한 점은 LLM이 상품 조건을 외우는 것이 아니라는 점이다. 질문과 검색된 chunk를 프롬프트에 넣고, 모델은 그 근거 안에서 답변을 생성한다. 근거가 부족하거나 모델 실행이 실패하면 fallback 답변으로 돌아간다.

출처는 파일 제목만 보여준다. DB 내부 chunk 제목에는 `p2-1` 같은 구분이 붙을 수 있지만, 사용자가 보기에는 너무 복잡하다. 그래서 최종 답변과 화면의 출처 카드는 원본 파일 제목 중심으로 정리한다.

## Spring MVC 책임

질문 흐름은 다음 파일에서 볼 수 있다.

```text
RagApiController
  -> RagService
  -> RagClient
  -> QueryHistoryRepository
```

피드백 흐름은 다음 파일에서 볼 수 있다.

```text
FeedbackApiController
  -> FeedbackService
  -> QueryHistoryRepository
  -> AnswerFeedbackRepository
```

Controller는 HTTP 입출력을 맡고, Service는 실제 흐름과 트랜잭션 경계를 맡는다. 피드백은 특정 `QueryHistory`에 연결된다. AI 서비스에서는 답변 품질을 다시 시스템으로 회수하는 구조가 중요하기 때문이다.

Python RAG가 꺼져 있으면 Spring 전체가 실패할 수 있다. 그래서 `RagClient`는 Python 호출 실패 시 Spring Repository 기반 fallback 검색을 수행한다. 새 기술을 붙이더라도 사용자 흐름이 멈추지 않게 하는 것이 핵심이다.

출처 PDF 다운로드는 `DocumentDownloadController`와 `DocumentDownloadService`가 맡는다. Citation의 `documentId`로 DB chunk를 찾고, content 안의 `[출처파일]` 값을 읽어 `data/raw` 아래 원본 PDF를 attachment로 내려준다. 외부 공시 목록 링크는 개별 PDF 주소가 아니므로 최종 화면에서는 `원문` 대신 `다운로드`를 제공한다.

## LoRA와 QLoRA의 위치

LoRA와 QLoRA는 RAG의 대체제가 아니다. 금융 상품 조건, 금리, 약관은 바뀔 수 있으므로 모델에 외우게 하면 위험하다. 최신 정보는 문서에서 검색해야 한다.

이 프로젝트에서 LoRA/QLoRA가 적합한 역할은 다음이다.

- 근거 기반 답변 형식 학습
- 금융 상담 말투 학습
- `가입대상`, `금리`, `유의사항`, `출처` 같은 출력 구조 학습
- 작은 모델이 RAG context를 더 잘 요약하도록 보정

순서는 다음이 좋다.

```text
RAG 검색 안정화
-> 답변 피드백 수집
-> 좋은 답변과 나쁜 답변 분류
-> LoRA 학습 데이터 작성
-> QLoRA는 메모리가 부족하거나 큰 모델이 필요할 때 검토
```

## 분산 시스템 관점

현재는 Spring Boot와 Python RAG의 2개 런타임이다. 바로 여러 저장소로 나누기보다 다음 순서가 안전하다.

```text
1. 현재 구조 안정화
2. PDF importer를 batch 모듈로 분리
3. RAG 검색/생성 API 경계 고정
4. 질문 이력과 평가 데이터를 별도 도메인으로 분리
5. 상품, 검색, 생성, 평가 도메인을 MSA 후보로 검토
```

중요한 질문은 기술 이름이 아니다. 어떤 도메인부터 분리할지, 분리 직후 트랜잭션 경계는 어디인지, 문서 적재와 검색 인덱스 정합성은 누가 책임질지, 회귀 검증은 어느 시점에 돌릴지를 먼저 정해야 한다.

## 용어 메모

- RAG: Retrieval-Augmented Generation. 먼저 문서를 검색하고, 그 검색 결과를 근거로 답변하는 방식이다.
- LangGraph: LLM 또는 RAG 작업을 상태 그래프로 구성하는 도구다.
- TF-IDF: 문서 안에서 특정 단어가 얼마나 중요한지 계산하는 전통적 검색 기법이다.
- n-gram: 문자를 N개씩 묶어 보는 방식이다. 한국어 조사 차이를 줄이는 데 도움이 된다.
- embedding: 문장이나 문서를 숫자 벡터로 바꾸는 표현 방식이다.
- hybrid search: 키워드 검색과 의미 검색을 섞는 검색 방식이다.
- PyMuPDF: PDF에서 페이지별 텍스트를 추출하는 Python 라이브러리다.
- chunk: 긴 문서를 검색하기 좋게 나눈 작은 텍스트 조각이다.
- MLX: Apple Silicon에서 모델 실행을 최적화하기 위한 머신러닝 런타임이다.
- LoRA: 큰 모델 전체가 아니라 작은 어댑터만 학습하는 파인튜닝 방식이다.
- QLoRA: 양자화된 모델 위에서 LoRA 학습을 수행해 메모리 사용량을 줄이는 방식이다.
- 트랜잭션: 여러 DB 작업을 하나의 작업 단위로 묶어 성공 또는 실패를 함께 관리하는 방식이다.
- MSA: Microservice Architecture. 기능이나 도메인을 작은 독립 서비스로 나누는 아키텍처 방식이다.
- attachment: 브라우저가 파일을 화면에 열기보다 다운로드하도록 안내하는 HTTP 응답 방식이다.
