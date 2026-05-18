# 03. 1차 사고 흐름

1차의 목표는 멋진 AI 서비스를 만드는 것이 아니었다.  
처음 목표는 Spring MVC와 Python RAG가 MySQL을 중심으로 어떻게 연결되는지 가장 작은 형태로 확인하는 것이었다.

처음에는 금융 문서를 화면에서 등록하고, 등록된 문서에 대해 질문하는 구조를 생각했다. 그래서 Spring Boot 프로젝트를 만들고 Controller, Service, Repository, Entity를 나누었다. 이때 중요한 판단은 Controller에 모든 코드를 넣지 않는 것이었다. 질문 하나를 처리하더라도 나중에는 외부 API 호출, DB 저장, 오류 처리, 피드백 저장이 붙기 때문에 Controller는 입구로만 두고 Service가 흐름을 관리하도록 했다.

`FinancialDocument`는 RAG의 지식 베이스로 만들었다. 제목, 카테고리, 출처, 게시일, 본문이 필요했다. `QueryHistory`는 사용자가 무엇을 질문했고 어떤 답변을 받았는지 저장하기 위해 만들었다. 근거 문서 목록은 처음부터 별도 테이블로 나누지 않고 JSON 문자열로 저장했다. 이유는 1차 목표가 정규화된 분석 시스템이 아니라 "질문하고 저장되는 흐름"을 이해하는 것이었기 때문이다.

Python 쪽에는 FastAPI 서비스를 만들었다. Spring이 `/api/ask` 요청을 받으면 Python의 `/ask`로 질문을 넘기고, Python은 MySQL 문서를 읽어 관련 문서를 찾는다. 처음 검색은 `TfidfVectorizer`를 사용했다. 최신 방식은 아니지만 RAG가 문서를 검색하고 그 결과를 답변에 쓰는 흐름을 이해하기에는 가장 단순했다.

한국어 검색에서 바로 문제가 생겼다. 단어 기준 TF-IDF는 `금리`와 `금리를`처럼 조사가 붙은 표현을 다르게 볼 수 있었다. 그래서 단어가 아니라 문자 n-gram 기준으로 바꾸었다. 이 변경은 검색 품질을 완벽히 해결하려는 것이 아니라 한국어 문장 검색의 첫 장애물을 넘기기 위한 선택이었다.

LangGraph는 `load_documents -> retrieve_documents -> generate_answer` 단계를 연결하는 용도로 넣었다. 여기서 LangGraph를 "자동으로 판단하는 에이전트"로 쓰지는 않았다. 초급 단계에서는 먼저 상태가 어떤 단계에서 어떻게 바뀌는지 보는 것이 중요했기 때문이다. LangGraph가 설치되지 않아도 같은 함수들을 순서대로 실행하는 fallback graph를 둔 것도 같은 이유다. 새 기술 때문에 전체 학습 흐름이 멈추면 안 된다고 판단했다.

Spring에서 Python을 호출할 때도 문제가 있었다. FastAPI를 직접 호출하면 잘 되는데 Spring에서 호출하면 `422`가 났다. 원인은 JSON body와 `Content-Type` 처리였다. `RagClient`에서 `ObjectMapper`로 요청 DTO를 JSON 문자열로 바꾸고, `MediaType.APPLICATION_JSON`을 명시했다. 이후에도 HTTP 클라이언트와 uvicorn 조합에서 이상한 upgrade 요청이 섞여 `SimpleClientHttpRequestFactory`를 지정했다. 이 문제를 통해 서버 간 통신은 URL만 맞으면 끝나는 것이 아니라 method, header, body 형식이 함께 맞아야 한다는 점을 확인했다.

또 하나의 중요한 판단은 fallback이었다. Python RAG가 꺼져 있으면 Spring 화면 전체가 실패할 수 있었다. 그래서 `RagClient`가 Python 호출 실패를 잡고 Spring Repository 기반 검색으로 대체하도록 했다. 이 기능은 완성도 높은 검색 기능이라기보다 외부 AI 런타임 장애가 사용자 흐름 전체를 멈추지 않게 하는 안전장치였다.

1차에서 수정한 핵심 파일은 Spring의 `rag`, `document`, `query` 패키지와 Python의 `rag-service/app.py`였다. Gradle 설정, 테스트용 H2 설정, MySQL 설정도 함께 다루었다. 이 단계의 결론은 "RAG 서비스도 결국 웹 백엔드이고, 요청 흐름과 저장 흐름이 먼저 안정되어야 한다"는 것이었다.

## 1차에서 남긴 트러블슈팅

Gradle이 로컬에 없어도 `./gradlew build`로 빌드되게 Gradle Wrapper를 사용했다.  
MySQL이 항상 떠 있지 않아도 테스트가 가능하도록 테스트 프로필에서는 H2를 사용했다.  
Java 21 toolchain과 로컬 JDK 25의 차이는 `options.release = 21`로 완화했다.  
Python 경고나 LangGraph 설치 문제는 전체 흐름을 막는 오류인지, 나중에 정리할 환경 문제인지 구분했다.

1차의 가장 큰 학습은 "빌드 성공"과 "실제 실행 성공"이 다르다는 점이었다. 컴파일은 통과해도 서버 시작 시 초기화 코드에서 오류가 날 수 있고, API 직접 호출은 되지만 Spring을 통한 서버 간 호출은 실패할 수 있다. 그래서 이후 단계부터는 중간중간 빌드와 실제 기동을 같이 확인하는 원칙을 세웠다.

## 용어 메모

- Controller: HTTP 요청을 받는 Spring 계층이다.
- Service: 비즈니스 흐름과 트랜잭션을 담당하는 Spring 계층이다.
- Repository: DB 접근을 담당하는 Spring Data JPA 계층이다.
- Entity: DB 테이블과 매핑되는 Java 객체다.
- JSON: 서버끼리 데이터를 주고받을 때 자주 쓰는 텍스트 기반 데이터 형식이다.
- H2: 테스트에 자주 쓰는 가벼운 인메모리 데이터베이스다.
- Gradle Wrapper: 로컬 Gradle 설치 없이 프로젝트가 지정한 Gradle로 빌드하게 해주는 스크립트다.
- HTTP 422: 서버가 요청 형식은 받았지만 내용이 기대한 구조가 아니라 처리할 수 없다는 의미의 응답이다.
