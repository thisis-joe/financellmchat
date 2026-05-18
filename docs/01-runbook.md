# 01. 실행 및 확인

이 문서는 프로젝트를 실제로 실행하고 확인하는 방법만 담는다.  
시연 기준은 `Spring Boot + MySQL + Python RAG + Gemma 4 E4B 4bit MLX 답변 생성`이다.

## 1. MySQL 준비

```bash
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS finance_rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -uroot -e "CREATE USER IF NOT EXISTS 'finance'@'localhost' IDENTIFIED BY 'finance';"
mysql -uroot -e "GRANT ALL PRIVILEGES ON finance_rag.* TO 'finance'@'localhost'; FLUSH PRIVILEGES;"
```

확인:

```bash
mysqladmin ping
```

## 2. Python 환경 준비

기본 검색과 PDF 적재용 환경:

```bash
cd rag-service
python3 -m venv .venv-rag
source .venv-rag/bin/activate
pip install -r requirements.txt
cd ..
```

Gemma MLX 답변 생성용 환경:

```bash
cd rag-service
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib python3.12 -m venv .venv-rag-py312
source .venv-rag-py312/bin/activate
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib
pip install -r requirements.txt
pip install -r requirements-llm.txt
cd ..
```

첫 질문 때 `intfloat/multilingual-e5-small` embedding 모델이나 `mlx-community/gemma-4-e4b-it-4bit` 생성 모델을 확인하느라 응답이 느릴 수 있다.

## 3. PDF 다시 적재

원본 PDF는 다음 폴더에 둔다.

```text
data/raw/busanbank/product-disclosure/deposit/installment
```

zip을 다시 풀어야 하면:

```bash
python3 scripts/extract_busanbank_zip.py \
  --zip /Users/Joseph/Desktop/적립식예금.zip \
  --dest data/raw/busanbank/product-disclosure/deposit/installment
```

MySQL에 다시 적재하려면:

```bash
rag-service/.venv-rag/bin/python scripts/import_busanbank_installment_pdfs.py \
  --pdf-dir data/raw/busanbank/product-disclosure/deposit/installment \
  --processed-dir data/processed/busanbank/product-disclosure/deposit/installment \
  --replace
```

확인:

```bash
mysql -ufinance -pfinance -e "select count(*) documents, count(distinct product_name) products from financial_documents where institution='BNK부산은행';" finance_rag
```

## 4. Spring 실행

개발 중에는 다음을 사용한다.

```bash
./gradlew bootRun
```

빌드된 jar로 실행하려면:

```bash
./gradlew build
java -jar build/libs/finance-rag-0.0.1-SNAPSHOT.jar
```

접속:

```text
http://localhost:8080/index.html
```

## 5. Python RAG 실행

시연용 실행:

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

LLM 없이 검색과 문서기반 추출 답변만 확인하려면:

```bash
cd rag-service
source .venv-rag/bin/activate
RAG_RETRIEVAL_MODE=hybrid uvicorn app:app --reload --port 8000
```

상태 확인:

```bash
curl -s http://localhost:8000/health
```

## 6. 기능 확인

정적 화면:

```bash
curl -s http://localhost:8080/index.html | grep "BNK부산은행 AI챗봇"
```

Python RAG 직접 확인:

```bash
curl -s -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"펫 적금 혜택 받으려면 뭘 해야 해?"}'
```

Spring API 확인:

```bash
curl -s -X POST http://localhost:8080/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"장병내일준비적금 만기 때 어떤 서류가 필요해?"}'
```

출처 PDF 다운로드 확인:

```bash
curl -D - http://localhost:8080/api/documents/{documentId}/download -o /tmp/bnk-product.pdf
```

답변 피드백 저장:

```bash
curl -s -X POST http://localhost:8080/api/histories/{historyId}/feedback \
  -H 'Content-Type: application/json' \
  -d '{"rating":"HELPFUL","comment":"근거 문서가 함께 보여서 좋음"}'
```

최근 피드백 조회:

```bash
curl -s http://localhost:8080/api/feedback
```

## 7. screen 백그라운드 실행

```bash
screen -dmS finance-rag-spring bash -lc 'cd /Users/Joseph/workspaces/temp_RAG && java -jar build/libs/finance-rag-0.0.1-SNAPSHOT.jar > /tmp/finance-rag-spring.log 2>&1'
screen -dmS finance-rag-python bash -lc 'cd /Users/Joseph/workspaces/temp_RAG/rag-service && export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib && RAG_RETRIEVAL_MODE=hybrid RAG_GENERATION_MODE=mlx MLX_GENERATION_MODEL=mlx-community/gemma-4-e4b-it-4bit HF_MAX_NEW_TOKENS=180 .venv-rag-py312/bin/uvicorn app:app --port 8000 > /tmp/finance-rag-python.log 2>&1'
```

확인:

```bash
screen -ls
curl -s http://localhost:8000/health
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/index.html
```

중지:

```bash
screen -S finance-rag-spring -X quit
screen -S finance-rag-python -X quit
```

## 용어 메모

- 가상환경: Python 패키지를 프로젝트별로 분리해 설치하는 실행 환경이다.
- jar: Java 애플리케이션을 실행 가능한 형태로 묶은 파일이다.
- uvicorn: FastAPI 애플리케이션을 실행하는 ASGI 서버다.
- screen: 터미널 세션을 백그라운드에 분리해 계속 실행하게 해주는 도구다.
- embedding 모델: 문장을 숫자 벡터로 바꿔 의미 유사도를 계산하게 해주는 모델이다.
- 답변 생성용 LLM: 검색된 근거를 읽고 최종 답변 문장을 만드는 모델이다.
- MLX 생성 모드: Apple Silicon에서 4bit Gemma 모델로 답변 문장을 생성하는 현재 시연용 실행 방식이다.
