# 01. 실행과 확인

이 문서는 프로젝트를 실제로 실행하고 확인하는 방법만 담는다.  
시연 기준은 `Spring Boot + MySQL + Python RAG + 로컬 Gemma 또는 fallback 답변 생성`이다.

## 1. MySQL 준비

```bash
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS finance_rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -uroot -e "CREATE USER IF NOT EXISTS 'finance'@'localhost' IDENTIFIED BY 'finance';"
mysql -uroot -e "GRANT ALL PRIVILEGES ON finance_rag.* TO 'finance'@'localhost'; FLUSH PRIVILEGES;"
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

## 3. PDF 다시 적재

원본 PDF 위치:

```text
data/raw/busanbank/product-disclosure/deposit/installment
```

zip을 다시 풀어야 하면:

```bash
python3 scripts/extract_busanbank_zip.py \
  --zip /Users/Joseph/Desktop/적립식예금.zip \
  --dest data/raw/busanbank/product-disclosure/deposit/installment
```

MySQL에 다시 넣으려면:

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

## 4. 로컬 실행

Spring Boot:

```bash
./gradlew build
java -jar build/libs/finance-rag-0.0.1-SNAPSHOT.jar
```

Python RAG:

```bash
cd rag-service
source .venv-rag-py312/bin/activate
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib
RAG_RETRIEVAL_MODE=hybrid \
RAG_GENERATION_MODE=mlx \
MLX_GENERATION_MODEL=mlx-community/gemma-4-e4b-it-4bit \
HF_MAX_NEW_TOKENS=260 \
uvicorn app:app --reload --port 8000
```

LLM 없이 검색과 fallback만 확인하려면:

```bash
cd rag-service
source .venv-rag/bin/activate
RAG_RETRIEVAL_MODE=hybrid uvicorn app:app --reload --port 8000
```

접속:

```text
http://localhost:8080/index.html
```

## 5. 백그라운드 실행

```bash
screen -dmS finance-rag-spring bash -lc 'cd /Users/Joseph/workspaces/temp_RAG && java -jar build/libs/finance-rag-0.0.1-SNAPSHOT.jar > /tmp/finance-rag-spring.log 2>&1'

screen -dmS finance-rag-python bash -lc 'cd /Users/Joseph/workspaces/temp_RAG/rag-service && export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib && RAG_RETRIEVAL_MODE=hybrid RAG_GENERATION_MODE=mlx MLX_GENERATION_MODEL=mlx-community/gemma-4-e4b-it-4bit HF_MAX_NEW_TOKENS=260 .venv-rag-py312/bin/uvicorn app:app --port 8000 > /tmp/finance-rag-python.log 2>&1'
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

## 6. 기능 확인

Spring API:

```bash
curl -s -X POST http://localhost:8080/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"펫 적금 혜택 받으려면 뭘 해야 해?"}'
```

답변근거 API:

```bash
curl -s http://localhost:8080/api/histories/{historyId}/evidence
```

PDF 다운로드:

```bash
curl -D - http://localhost:8080/api/documents/{documentId}/download -o /tmp/bnk-product.pdf
```

피드백 저장:

```bash
curl -s -X POST http://localhost:8080/api/histories/{historyId}/feedback \
  -H 'Content-Type: application/json' \
  -d '{"rating":"HELPFUL","comment":"근거가 명확함"}'
```

대표 질문 전체 확인:

```bash
python3 scripts/check_representative_questions.py \
  --base-url http://localhost:8080 \
  --timeout 90
```

대표 질문은 인사말, 무의미 입력, 예금 종류, 상품 목록, 나이별 추천, 상품별 혜택/서류/가입대상을 확인한다. 앞으로는 여기에 자연스러운 대화 응답과 상품 설명 질문을 더 늘린다.

## 7. Vercel과 Cloudflare 배포

현재 배포 구조는 다음과 같다.

```text
사용자 브라우저
  -> Vercel 정적 프론트
  -> /api/* rewrite
  -> https://api.bnkaichat.xyz
  -> Cloudflare Tunnel
  -> 개인 Mac localhost:8080 Spring Boot
  -> localhost:8000 Python RAG
  -> MySQL
```

Vercel 설정:

```text
GitHub Repository: https://github.com/thisis-joe/financellmchat
Root Directory: repo 루트 또는 src/main/resources/static
Framework Preset: Other
Build Command: 비움
Output Directory: repo 루트 기준이면 src/main/resources/static, 정적 폴더 기준이면 .
```

repo 루트 기준 `vercel.json`:

```json
{
  "buildCommand": null,
  "installCommand": null,
  "outputDirectory": "src/main/resources/static",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://api.bnkaichat.xyz/api/:path*"
    }
  ]
}
```

Cloudflare Tunnel:

```bash
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create finance-rag-api
cloudflared tunnel route dns finance-rag-api api.bnkaichat.xyz
cloudflared tunnel run finance-rag-api
```

터널 ID 확인:

```bash
cloudflared tunnel list
ls ~/.cloudflared/*.json
```

`~/.cloudflared/config.yml` 예시:

```yaml
tunnel: finance-rag-api
credentials-file: /Users/Joseph/.cloudflared/<터널ID>.json

ingress:
  - hostname: api.bnkaichat.xyz
    service: http://localhost:8080
  - service: http_status:404
```

## 8. 커스텀 도메인과 HTTPS

역할을 나눈다.

```text
bnkaichat.xyz
  -> Vercel 정적 프론트

www.bnkaichat.xyz
  -> Vercel 정적 프론트

api.bnkaichat.xyz
  -> Cloudflare Tunnel
  -> 개인 Mac Spring Boot
```

Vercel `Settings > Domains`에 `bnkaichat.xyz`와 필요하면 `www.bnkaichat.xyz`를 추가한다. Cloudflare DNS는 다음처럼 둔다.

```text
Type: A
Name: @
Content: 76.76.21.21
Proxy status: DNS only
```

```text
Type: CNAME
Name: www
Content: cname.vercel-dns-0.com
Proxy status: DNS only
```

`api.bnkaichat.xyz`는 Vercel에 연결하지 않는다. 이 주소는 Cloudflare Tunnel이 사용한다.

확인:

```bash
curl -I https://bnkaichat.xyz
curl -I https://api.bnkaichat.xyz/index.html
python3 scripts/check_representative_questions.py --base-url https://financellmchat.vercel.app --timeout 90
```

`bnkaichat.xyz`에서 1016 오류가 나오면 HTTPS 인증서 문제가 아니라 Cloudflare가 원본 DNS를 못 찾는 문제일 가능성이 크다. Vercel에 도메인이 등록됐는지, Cloudflare `@` 레코드가 Vercel 값으로 되어 있는지, Proxy status가 `DNS only`인지 확인한다.

## 용어 메모

- 가상환경: Python 패키지를 프로젝트별로 분리해 설치하는 실행 환경이다.
- jar: Java 애플리케이션을 실행 가능한 형태로 묶은 파일이다.
- uvicorn: FastAPI 애플리케이션을 실행하는 서버다.
- screen: 터미널 세션을 백그라운드에 분리해 계속 실행하는 도구다.
- rewrite: 프론트 요청 경로를 다른 백엔드 주소로 전달하는 배포 설정이다.
- Cloudflare Tunnel: 로컬 서버를 외부 도메인에 안전하게 연결하는 방식이다.
- Vercel: 정적 프론트엔드 배포에 쓰는 플랫폼이다.
- DNS: 도메인을 실제 서버 주소로 연결하는 시스템이다.
- DNS only: Cloudflare가 트래픽을 중계하지 않고 DNS 응답만 하는 설정이다.
- 1016 Origin DNS Error: Cloudflare가 원본 서버 DNS를 찾지 못할 때 나오는 오류다.
- 대표 질문: 기능 수정 뒤에도 핵심 질문이 계속 잘 동작하는지 확인하는 회귀 테스트 질문이다.
