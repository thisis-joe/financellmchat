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

## 8. 외부 배포 방향

현재 프로젝트는 프론트와 백엔드를 한 번에 같은 플랫폼에 올리는 구조가 아니다. 프론트는 정적 파일 3개라 Vercel 무료 배포에 잘 맞고, 백엔드는 Spring Boot, Python RAG, MySQL, 로컬 모델 실행이 함께 필요하므로 개인 Mac에서 계속 실행한다. 외부 사용자는 Vercel 화면에 접속하고, 화면의 `/api/*` 요청은 Cloudflare Tunnel을 통해 Mac의 Spring Boot로 들어온다.

```text
Vercel 정적 프론트
  -> /api/* rewrite
  -> https://api.bnkaichat.xyz
  -> Cloudflare Tunnel
  -> localhost:8080 Spring Boot
  -> localhost:8000 Python RAG
  -> MySQL
```

전제 조건:

- 개인 Mac이 켜져 있어야 한다.
- MySQL, Spring Boot, Python RAG가 실행 중이어야 한다.
- Mac이 절전으로 들어가면 외부 API도 멈춘다.
- Cloudflare에서 `bnkaichat.xyz`가 활성화되어야 DNS 연결을 안정적으로 진행할 수 있다.

Mac을 시연용 서버처럼 계속 켜둘 때는 절전 설정을 꺼둔다.

```bash
sudo pmset -a sleep 0
```

## 9. Cloudflare 대기 상태 이해

Cloudflare에서 기다리라고 나오는 경우는 보통 가비아에서 Cloudflare nameserver로 바꾼 뒤 전파를 기다리는 상태다. 이때는 코드를 수정해서 해결하는 문제가 아니라 DNS 소유권 확인이 끝날 때까지 기다리는 문제다.

확인할 것:

- 가비아 도메인 관리 화면에서 Cloudflare가 알려준 nameserver 2개를 정확히 입력했는지 확인한다.
- Cloudflare 대시보드에서 `Check nameservers`를 누른다.
- 보통 수 분에서 수 시간이지만, 길면 하루 정도 걸릴 수 있다.
- 활성화 전에도 로컬 실행은 가능하지만, `api.bnkaichat.xyz` 연결은 활성화 뒤 진행하는 편이 안전하다.

## 10. Cloudflare Tunnel 설정

Cloudflare가 활성화되면 Mac에서 `cloudflared`를 준비한다.

```bash
brew install cloudflared
cloudflared tunnel login
```

터널을 만든다.

```bash
cloudflared tunnel create finance-rag-api
```

터널 ID는 다음 명령으로 확인한다.

```bash
cloudflared tunnel list
```

또는 인증 파일 이름에서도 확인할 수 있다.

```bash
ls ~/.cloudflared/*.json
```

`api.bnkaichat.xyz`를 터널에 연결한다.

```bash
cloudflared tunnel route dns finance-rag-api api.bnkaichat.xyz
```

`~/.cloudflared/config.yml`을 만든다. `<터널ID>`는 위에서 확인한 값으로 바꾼다.

```yaml
tunnel: finance-rag-api
credentials-file: /Users/Joseph/.cloudflared/<터널ID>.json

ingress:
  - hostname: api.bnkaichat.xyz
    service: http://localhost:8080
  - service: http_status:404
```

먼저 터널을 직접 실행해서 확인한다.

```bash
cloudflared tunnel run finance-rag-api
```

다른 터미널에서 확인한다.

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.bnkaichat.xyz/index.html
curl -s -X POST https://api.bnkaichat.xyz/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"펫 적금 혜택 받으려면 뭘 해야 해?"}'
```

직접 실행이 성공하면 항상 켜지도록 서비스 등록을 검토한다.

```bash
sudo cloudflared service install
```

서비스가 설정 파일을 못 읽는 환경이면 우선 `screen`으로 터널을 실행해도 된다.

```bash
screen -dmS finance-rag-tunnel bash -lc 'cloudflared tunnel --config /Users/Joseph/.cloudflared/config.yml run finance-rag-api > /tmp/finance-rag-tunnel.log 2>&1'
```

확인:

```bash
screen -ls
tail -n 50 /tmp/finance-rag-tunnel.log
```

## 11. Vercel 프론트 배포

Vercel에는 Spring 프로젝트 전체를 빌드해서 올리는 것이 아니라 정적 프론트 폴더만 올린다.

Vercel 설정:

```text
GitHub Repository: https://github.com/thisis-joe/financellmchat
Root Directory: src/main/resources/static
Framework Preset: Other
Build Command: 비움
Output Directory: .
```

`src/main/resources/static/vercel.json`은 Vercel에서 `/api/*` 요청을 API 도메인으로 넘긴다.

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://api.bnkaichat.xyz/api/:path*"
    }
  ]
}
```

도메인 연결:

- 프론트 도메인은 Vercel 프로젝트에 연결한다. 예: `bnkaichat.xyz` 또는 `www.bnkaichat.xyz`
- API 도메인은 Vercel에 연결하지 않는다. `api.bnkaichat.xyz`는 Cloudflare Tunnel이 사용한다.
- Cloudflare DNS에서 Vercel이 안내하는 프론트용 DNS 값을 입력한다.
- Cloudflare Tunnel 명령이 만든 `api` DNS 레코드는 그대로 둔다.

최종 확인:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.bnkaichat.xyz/index.html
curl -s -X POST https://api.bnkaichat.xyz/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"장병내일준비적금 만기 때 어떤 서류가 필요해?"}'
```

브라우저에서는 Vercel에 연결한 프론트 도메인으로 접속한 뒤 챗봇에서 질문한다. 답변이 나오고 출처 카드의 `다운로드`가 PDF를 내려받으면 배포 흐름이 연결된 것이다.

## 용어 메모

- 가상환경: Python 패키지를 프로젝트별로 분리해 설치하는 실행 환경이다.
- jar: Java 애플리케이션을 실행 가능한 형태로 묶은 파일이다.
- uvicorn: FastAPI 애플리케이션을 실행하는 ASGI 서버다.
- screen: 터미널 세션을 백그라운드에 분리해 계속 실행하게 해주는 도구다.
- embedding 모델: 문장을 숫자 벡터로 바꿔 의미 유사도를 계산하게 해주는 모델이다.
- 답변 생성용 LLM: 검색된 근거를 읽고 최종 답변 문장을 만드는 모델이다.
- MLX 생성 모드: Apple Silicon에서 4bit Gemma 모델로 답변 문장을 생성하는 현재 시연용 실행 방식이다.
- DNS: 사람이 읽는 도메인을 실제 서버 주소로 연결하는 시스템이다.
- nameserver: 특정 도메인의 DNS 정보를 어느 서비스가 관리하는지 알려주는 서버다.
- Cloudflare Tunnel: 로컬 서버를 외부 도메인에 연결하되 공유기 포트포워딩을 하지 않아도 되는 방식이다.
- Vercel rewrite: 프론트에서 호출한 경로를 Vercel이 다른 백엔드 주소로 전달하는 설정이다.
