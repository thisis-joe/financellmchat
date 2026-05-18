# Busan Bank Product RAG

부산은행 상품설명 자료를 기반으로 질문 의도에 맞는 답변을 생성하는 Spring Boot MVC + Python RAG 학습 프로젝트입니다.

## 구성

- Spring Boot MVC: 정적 챗봇 화면, RAG REST API, 질문 기록 저장
- Spring Data JPA: 질문 이력과 답변 피드백 저장
- MySQL: 상품설명 자료와 질문 기록 저장
- Python FastAPI: MySQL 문서 기반 하이브리드 검색, LangGraph 워크플로, Gemma MLX 답변 생성
- Frontend: `index.html`, `style.css`, `app.js` 정적 파일 3개

## 실행 순서

로컬 MySQL에 DB와 계정을 준비합니다.

```bash
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS finance_rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -uroot -e "CREATE USER IF NOT EXISTS 'finance'@'localhost' IDENTIFIED BY 'finance';"
mysql -uroot -e "GRANT ALL PRIVILEGES ON finance_rag.* TO 'finance'@'localhost'; FLUSH PRIVILEGES;"
```

Spring Boot를 실행합니다.

```bash
./gradlew bootRun
```

다른 터미널에서 RAG 서비스를 실행합니다.

```bash
cd rag-service
source .venv-rag-py312/bin/activate
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib
RAG_RETRIEVAL_MODE=hybrid \
RAG_GENERATION_MODE=mlx \
MLX_GENERATION_MODEL=mlx-community/gemma-4-e4b-it-4bit \
HF_MAX_NEW_TOKENS=180 \
uvicorn app:app --reload --port 8000
```

브라우저에서 `http://localhost:8080`에 접속합니다.

## 학습 문서

문서는 번호 순서대로 읽으면 자연스럽게 이해되도록 정리했습니다.

- `docs/00-project-guide.md`: 전체 개요와 읽는 순서
- `docs/01-runbook.md`: 실행, 빌드, API 확인
- `docs/02-architecture-and-rag.md`: 도메인, Spring, RAG, LangGraph, embedding, Gemma, LoRA/QLoRA
- `docs/03-phase-1-thinking.md`: 1차 사고 흐름
- `docs/04-phase-2-thinking.md`: 2차 사고 흐름
- `docs/05-phase-3-thinking.md`: 3차 사고 흐름
- `docs/06-phase-4-thinking.md`: 4차 사고 흐름

## 적립식예금 PDF 적재

시연 재현을 위해 부산은행 적립식예금 원본 PDF는 `data/raw/busanbank/product-disclosure/deposit/installment` 아래에 포함한다.
`data/processed` 산출물은 Git에 포함하지 않고 필요할 때 다시 생성한다.

```bash
python3 scripts/extract_busanbank_zip.py \
  --zip /Users/Joseph/Desktop/적립식예금.zip \
  --dest data/raw/busanbank/product-disclosure/deposit/installment

rag-service/.venv-rag/bin/python scripts/import_busanbank_installment_pdfs.py \
  --pdf-dir data/raw/busanbank/product-disclosure/deposit/installment \
  --processed-dir data/processed/busanbank/product-disclosure/deposit/installment \
  --replace
```
