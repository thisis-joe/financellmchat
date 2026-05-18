# Finance RAG Service

Spring Boot MVC 애플리케이션에서 호출하는 Python RAG 서비스입니다.

## 실행

시연용 실행은 Gemma 4 E4B 4bit MLX 생성 모드를 사용합니다.

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

## 3차 Hugging Face LLM 생성 모드

검색된 근거 chunk를 Hugging Face LLM에 넣어 답변을 생성하려면 Python 3.12 가상환경에서 추가 의존성을 설치한다.

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib python3.12 -m venv .venv-rag-py312
source .venv-rag-py312/bin/activate
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib
pip install -r requirements.txt
pip install -r requirements-llm.txt
```

Apple Silicon 로컬 실행 추천 모드:

```bash
RAG_GENERATION_MODE=mlx \
MLX_GENERATION_MODEL=mlx-community/gemma-4-e4b-it-4bit \
uvicorn app:app --reload --port 8000
```

full PyTorch Transformers 시험 모드:

```bash
RAG_GENERATION_MODE=hf \
HF_GENERATION_MODEL=google/gemma-4-E4B-it \
uvicorn app:app --reload --port 8000
```

현재 Mac 로컬 검증에서는 full PyTorch 모델이 MPS buffer 제한에 걸렸고, `mlx-community/gemma-4-e4b-it-4bit` + `mlx-vlm` 경로는 생성에 성공했다. LLM 생성 실패 시 서비스는 멈추지 않고 문서기반 추출 답변으로 fallback한다.

## 환경 변수

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_NAME=finance_rag
export DB_USERNAME=finance
export DB_PASSWORD=finance
export RAG_GENERATION_MODE=mlx
export HF_GENERATION_MODEL=google/gemma-4-E4B-it
export MLX_GENERATION_MODEL=mlx-community/gemma-4-e4b-it-4bit
```

## API

```bash
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"정기예금 금리를 비교할 때 무엇을 봐야 하나요?"}'
```
