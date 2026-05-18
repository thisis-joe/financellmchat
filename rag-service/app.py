from __future__ import annotations

from functools import lru_cache
import os
import re
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import numpy as np
import pandas as pd
import pymysql
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # LangGraph 설치 전에도 1차 실습 흐름을 확인하기 위한 fallback
    END = "__END__"
    StateGraph = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class Citation(BaseModel):
    documentId: int
    title: str
    category: str
    institution: Optional[str] = None
    productName: Optional[str] = None
    productType: Optional[str] = None
    source: str
    sourceUrl: Optional[str] = None
    score: float
    snippet: str


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: List[Citation]
    status: str


class RagState(TypedDict):
    question: str
    documents: pd.DataFrame
    citations: List[Dict[str, Any]]
    contexts: List[Dict[str, Any]]
    answer: str
    status: str


PRODUCT_ALIAS_HINTS = {
    "청년도약계좌": "부산은행 청년도약계좌",
    "장병내일준비적금": "부산은행 장병내일준비적금",
    "청년주택드림청약통장": "청년 주택드림 청약통장",
    "주택드림청약통장": "청년 주택드림 청약통장",
    "주택청약종합저축": "주택청약종합저축",
    "내맘대로적금": "BNK내맘대로 적금",
    "bnk내맘대로": "BNK내맘대로 적금",
    "onlyone주거래우대적금": "Only One 주거래 우대적금",
    "너만솔로적금": "너만솔로 적금",
    "아기천사적금": "아기천사 적금",
    "아이사랑적금": "아이사랑 적금",
    "저탄소실천적금": "저탄소 실천 적금",
    "펫적금": "펫 적금",
    "가을야구적금": "BNK가을야구적금",
}


INTENT_KEYWORDS = {
    "가입대상": ["가입", "가입대상", "가입 대상", "가입자격", "가입조건", "가입 조건", "대상", "자격", "요건", "누가"],
    "금리": ["금리", "이율", "이자율", "우대금리", "우대 금리", "우대이율", "최고금리", "기본금리", "기본이율", "혜택"],
    "가입기간": ["가입기간", "가입 기간", "계약기간", "계약 기간", "기간", "만기"],
    "납입": ["납입", "입금", "월부금", "납부", "한도", "금액"],
    "해지": ["해지", "중도해지", "만기해지", "해약"],
    "세제": ["세제", "비과세", "소득공제", "과세"],
    "서류": ["서류", "준비물", "증빙", "제출"],
    "유의사항": ["유의", "주의", "제한", "불가"],
}


STRONG_INTENT_KEYWORDS = {
    "가입대상": ["가입대상", "가입 대상", "가입자격", "가입조건", "가입 조건"],
    "금리": ["우대금리", "우대 금리", "우대이율", "최고금리", "기본금리", "기본이율", "이자율"],
    "가입기간": ["가입기간", "가입 기간", "계약기간", "계약 기간"],
    "납입": ["납입금액", "저축금액", "월부금", "납입한도", "월 납입"],
    "해지": ["중도해지", "만기해지", "특별중도해지"],
    "세제": ["비과세", "소득공제", "세제혜택"],
    "서류": ["신청서류", "제출서류", "징구서류", "증빙서류"],
    "유의사항": ["유의사항", "반드시 확인", "제한사항"],
}


app = FastAPI(title="Finance RAG Service")
EMBEDDING_CACHE: Dict[Tuple[Any, ...], np.ndarray] = {}


def db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USERNAME", "finance"),
        password=os.getenv("DB_PASSWORD", "finance"),
        database=os.getenv("DB_NAME", "finance_rag"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def load_documents(_: RagState) -> RagState:
    sql = """
        select id, title, category, institution, product_name, product_type, source, source_url, content
        from financial_documents
        where institution = 'BNK부산은행'
        order by created_at desc
    """
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            documents = pd.DataFrame(cursor.fetchall())
    return {"documents": documents}


def retrieve_documents(state: RagState) -> RagState:
    documents = state["documents"]
    if documents.empty:
        return {"citations": [], "status": "NO_DOCUMENTS"}

    question = state["question"]
    focus = analyze_question(question, documents)
    corpus = build_search_corpus(documents)
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=7000,
    )
    matrix = vectorizer.fit_transform(corpus)
    query_vector = vectorizer.transform([question])
    tfidf_scores = cosine_similarity(query_vector, matrix).flatten()
    embedding_scores = calculate_embedding_scores(question, documents)
    base_scores = combine_retrieval_scores(tfidf_scores, embedding_scores)
    scores = np.array(
        [
            rerank_score(documents.iloc[index], float(score), focus)
            for index, score in enumerate(base_scores)
        ]
    )

    top_k = int(os.getenv("RAG_TOP_K", "4"))
    top_indexes = np.argsort(scores)[::-1][:top_k]
    citations = []
    seen_citation_titles = set()
    contexts = []
    for index in top_indexes:
        score = float(scores[index])
        if score <= 0:
            continue

        row = documents.iloc[index]
        raw_content = str(row["content"])
        content = strip_import_metadata(raw_content)
        title = source_file_title(row, raw_content)
        snippet = build_text_window(content, focus["terms"], max_chars=260)
        context_content = build_text_window(content, focus["terms"], max_chars=1200)
        if title not in seen_citation_titles:
            citations.append(
                {
                    "documentId": int(row["id"]),
                    "title": title,
                    "category": str(row["category"]),
                    "institution": none_if_nan(row.get("institution")),
                    "productName": none_if_nan(row.get("product_name")),
                    "productType": none_if_nan(row.get("product_type")),
                    "source": str(row["source"]),
                    "sourceUrl": none_if_nan(row.get("source_url")),
                    "score": score,
                    "snippet": snippet,
                }
            )
            seen_citation_titles.add(title)
        contexts.append(
            {
                "title": title,
                "productName": none_if_nan(row.get("product_name")),
                "content": context_content,
                "score": score,
            }
        )

    return {
        "citations": citations,
        "contexts": contexts,
        "status": "RETRIEVED" if citations else "NO_MATCH",
    }


def calculate_embedding_scores(question: str, documents: pd.DataFrame) -> Optional[np.ndarray]:
    retrieval_mode = os.getenv("RAG_RETRIEVAL_MODE", "hybrid").lower()
    if retrieval_mode not in {"hybrid", "embedding"}:
        return None

    try:
        model = embedding_model()
        matrix = document_embedding_matrix(documents)
        query_embedding = model.encode(
            [f"query: {question}"],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        query_embedding = np.asarray(query_embedding, dtype=np.float32)
        return np.dot(matrix, query_embedding)
    except Exception:
        return None


def combine_retrieval_scores(tfidf_scores: np.ndarray, embedding_scores: Optional[np.ndarray]) -> np.ndarray:
    retrieval_mode = os.getenv("RAG_RETRIEVAL_MODE", "hybrid").lower()
    normalized_tfidf = normalize_scores(tfidf_scores)

    if embedding_scores is None:
        return normalized_tfidf

    normalized_embedding = normalize_scores(embedding_scores)
    if retrieval_mode == "embedding":
        return normalized_embedding

    return (normalized_tfidf * 0.45) + (normalized_embedding * 0.55)


def normalize_scores(scores: np.ndarray) -> np.ndarray:
    scores = np.nan_to_num(scores.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
    min_score = float(np.min(scores))
    max_score = float(np.max(scores))
    if max_score - min_score < 1e-9:
        return np.zeros_like(scores)
    return (scores - min_score) / (max_score - min_score)


@lru_cache(maxsize=1)
def embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError("sentence-transformers가 설치되어 있지 않습니다. rag-service/requirements.txt를 다시 설치하세요.") from error

    model_id = os.getenv("RAG_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    return SentenceTransformer(model_id)


def document_embedding_matrix(documents: pd.DataFrame) -> np.ndarray:
    model_id = os.getenv("RAG_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    cache_key = build_embedding_cache_key(model_id, documents)
    cached = EMBEDDING_CACHE.get(cache_key)
    if cached is not None:
        return cached

    texts = build_embedding_texts(documents)
    matrix = embedding_model().encode(
        texts,
        batch_size=16,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    matrix = np.asarray(matrix, dtype=np.float32)
    EMBEDDING_CACHE.clear()
    EMBEDDING_CACHE[cache_key] = matrix
    return matrix


def build_embedding_cache_key(model_id: str, documents: pd.DataFrame) -> Tuple[Any, ...]:
    rows = tuple(
        (
            int(row["id"]),
            len(str(row["title"])),
            len(str(row["product_name"])),
            len(str(row["content"])),
        )
        for _, row in documents.iterrows()
    )
    return model_id, rows


def build_embedding_texts(documents: pd.DataFrame) -> List[str]:
    texts: List[str] = []
    for _, row in documents.iterrows():
        product_name = none_if_nan(row.get("product_name")) or ""
        title = none_if_nan(row.get("title")) or ""
        category = none_if_nan(row.get("category")) or ""
        content = strip_import_metadata(none_if_nan(row.get("content")) or "")
        texts.append(
            "passage: "
            f"상품명: {product_name}\n"
            f"문서: {title}\n"
            f"분류: {category}\n"
            f"내용: {content[:1600]}"
        )
    return texts


def build_search_corpus(documents: pd.DataFrame) -> List[str]:
    title = documents["title"].fillna("").astype(str)
    category = documents["category"].fillna("").astype(str)
    product_name = documents["product_name"].fillna("").astype(str)
    product_type = documents["product_type"].fillna("").astype(str)
    content = documents["content"].fillna("").astype(str).map(strip_import_metadata)

    return (
        title
        + category
        + "\n"
        + product_name
        + "\n"
        + product_type
        + "\n"
        + content
    ).tolist()


def analyze_question(question: str, documents: pd.DataFrame) -> Dict[str, List[str]]:
    products = detect_products(question, documents)
    intents = detect_intents(question)
    keywords = extract_keywords(question)
    terms = build_focus_terms(question, products, intents, keywords)
    return {
        "products": products,
        "intents": intents,
        "keywords": keywords,
        "terms": terms,
    }


def detect_products(question: str, documents: pd.DataFrame) -> List[str]:
    question_key = normalize_key(question)
    product_names = sorted(
        {
            str(product_name)
            for product_name in documents["product_name"].dropna().unique().tolist()
            if str(product_name).strip()
        },
        key=lambda value: len(normalize_key(value)),
        reverse=True,
    )

    detected: List[str] = []
    for product_name in product_names:
        product_key = normalize_key(product_name)
        if product_key and product_key in question_key:
            detected.append(product_name)

    for alias, product_name in PRODUCT_ALIAS_HINTS.items():
        if normalize_key(alias) in question_key and product_name not in detected:
            detected.append(product_name)

    return detected


def detect_intents(question: str) -> List[str]:
    question_key = normalize_key(question)
    intents: List[str] = []
    for intent, aliases in INTENT_KEYWORDS.items():
        if any(normalize_key(alias) in question_key for alias in aliases):
            intents.append(intent)
    return intents


def extract_keywords(question: str) -> List[str]:
    keywords: List[str] = []
    for token in re.split(r"\s+", question):
        keyword = re.sub(r"[^0-9A-Za-z가-힣]", "", token).strip()
        if len(keyword) >= 2 and keyword not in keywords:
            keywords.append(keyword)
    return keywords


def build_focus_terms(question: str, products: List[str], intents: List[str], keywords: List[str]) -> List[str]:
    terms: List[str] = []
    for intent in intents:
        for keyword in STRONG_INTENT_KEYWORDS.get(intent, []):
            append_unique(terms, keyword)
        for keyword in INTENT_KEYWORDS[intent]:
            append_unique(terms, keyword)
    for value in keywords + products:
        append_unique(terms, value)

    compact_question = normalize_key(question)
    if len(compact_question) >= 4:
        append_unique(terms, compact_question)

    return sorted(terms, key=len, reverse=True)


def rerank_score(row: pd.Series, base_score: float, focus: Dict[str, List[str]]) -> float:
    title = none_if_nan(row.get("title")) or ""
    product_name = none_if_nan(row.get("product_name")) or ""
    content = strip_import_metadata(none_if_nan(row.get("content")) or "")
    title_key = normalize_key(title + " " + product_name)
    content_key = normalize_key(content)

    product_boost = 0.0
    for product in focus["products"]:
        if normalize_key(product) in title_key:
            product_boost = 0.20
            break

    intent_boost = 0.0
    for intent in focus["intents"]:
        strong_aliases = STRONG_INTENT_KEYWORDS.get(intent, [])
        if any(normalize_key(alias) in content_key for alias in strong_aliases):
            intent_boost += 0.16
        elif any(normalize_key(alias) in content_key for alias in INTENT_KEYWORDS[intent]):
            intent_boost += 0.04

    keyword_boost = 0.0
    for keyword in focus["keywords"]:
        keyword_key = normalize_key(keyword)
        if not keyword_key:
            continue
        if not focus["products"] and keyword_key in title_key:
            keyword_boost += 0.025
        if keyword_key in content_key:
            keyword_boost += 0.012

    score = base_score * 0.75
    score += product_boost
    score += min(intent_boost, 0.32)
    score += min(keyword_boost, 0.12)
    score += summary_section_boost(content_key, focus)
    return score


def summary_section_boost(content_key: str, focus: Dict[str, List[str]]) -> float:
    boost = 0.0
    has_summary_section = any(
        normalize_key(label) in content_key
        for label in ("기본정보", "상품 개요 및 특징", "거래 조건")
    )

    if "가입대상" in focus["intents"] and any(
        normalize_key(label) in content_key
        for label in ("가입대상", "가입자격")
    ):
        boost += 0.04

    if "금리" in focus["intents"] and any(
        normalize_key(label) in content_key
        for label in ("우대금리", "우대이율", "기본금리", "기본이율", "이자율")
    ):
        boost += 0.04

    if has_summary_section and boost >= 0.08:
        boost += 0.10

    return boost


def strip_import_metadata(content: str) -> str:
    return re.sub(
        r"^\[출처파일\].*?\n\[상품명\].*?\n\[페이지\].*?\n\n",
        "",
        content,
        flags=re.DOTALL,
    ).strip()


def source_file_title(row: pd.Series, raw_content: str) -> str:
    match = re.search(r"^\[출처파일\]\s*(.+)$", raw_content, flags=re.MULTILINE)
    if match:
        return clean_source_title(match.group(1))
    return clean_source_title(str(row.get("title", "")))


def clean_source_title(title: str) -> str:
    title = title.strip()
    title = re.sub(r"\.pdf$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*상품공시\s*PDF\s*p\d+(?:-\d+)?$", "", title)
    title = re.sub(r"\s+p\d+(?:-\d+)?$", "", title)
    return title.strip()


def build_text_window(content: str, terms: List[str], max_chars: int) -> str:
    content = content.strip()
    if len(content) <= max_chars:
        return compact_text(content)

    index = find_first_term_index(content, terms)
    if index < 0:
        return compact_text(content[:max_chars]) + "..."

    start = max(0, index - max_chars // 3)
    end = min(len(content), start + max_chars)
    start = max(0, end - max_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return prefix + compact_text(content[start:end]) + suffix


def find_first_term_index(content: str, terms: List[str]) -> int:
    lowered_content = content.lower()
    for term in terms:
        index = lowered_content.find(term.lower())
        if term and index >= 0:
            return index
    return -1


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def append_unique(values: List[str], value: str) -> None:
    value = value.strip()
    if value and value not in values:
        values.append(value)


def normalize_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).lower()


def none_if_nan(value: Any) -> Optional[str]:
    if value is None:
        return None
    if pd.isna(value):
        return None
    return str(value)


def generate_answer(state: RagState) -> RagState:
    citations = state["citations"]
    if not citations:
        return {
            "answer": "등록된 금융 문서에서 질문과 직접적으로 관련된 근거를 찾지 못했습니다.",
            "status": state["status"],
        }

    generation_mode = os.getenv("RAG_GENERATION_MODE", "template").lower()
    if generation_mode == "hf":
        try:
            return {"answer": finalize_generated_answer(generate_hf_answer(state), state), "status": "OK"}
        except Exception as error:
            return {"answer": build_template_answer(state, str(error)), "status": "LLM_FALLBACK"}

    if generation_mode == "mlx":
        try:
            return {"answer": finalize_generated_answer(generate_mlx_answer(state), state), "status": "OK"}
        except Exception as error:
            return {"answer": build_template_answer(state, str(error)), "status": "LLM_FALLBACK"}

    return {"answer": build_template_answer(state), "status": "OK"}


def build_template_answer(state: RagState, fallback_reason: Optional[str] = None) -> str:
    citations = state["citations"]
    contexts = state.get("contexts", [])
    intents = detect_intents(state["question"])
    product_names = [
        citation["productName"]
        for citation in citations
        if citation.get("productName")
    ]
    unique_products = list(dict.fromkeys(product_names))
    source_titles = list(dict.fromkeys(citation["title"] for citation in citations))
    facts = extract_answer_facts(state["question"], contexts, citations, intents)

    lines = [build_answer_lead(unique_products, intents, state["question"])]
    lines.append("")
    lines.append("확인 내용:")
    for fact in facts[:4]:
        lines.append(f"- {fact}")
    if not facts:
        lines.append("- 검색된 문서에서 질문과 직접 관련된 문장을 충분히 추출하지 못했습니다. 아래 출처 원문 확인이 필요합니다.")

    if source_titles:
        lines.append("")
        lines.append(f"출처: {', '.join(source_titles[:3])}")

    lines.append("")
    lines.append("추가 확인 필요: 실제 적용 여부는 가입 시점의 고시일, 개인 조건, 은행 확인 결과에 따라 달라질 수 있습니다.")

    if fallback_reason:
        lines.append("")
        lines.append(f"LLM 생성은 실패해 문서 내용 기반 요약으로 대체했습니다. 원인: {fallback_reason}")
    return "\n".join(lines)


def finalize_generated_answer(answer: str, state: RagState) -> str:
    source_titles = list(dict.fromkeys(citation["title"] for citation in state.get("citations", [])))
    normalized_lines = []
    for line in answer.splitlines():
        line = line.strip()
        if not line:
            normalized_lines.append("")
            continue
        if line.startswith("근거 문서:"):
            line = "출처:" + line[len("근거 문서:") :]
        if line.startswith("출처:") and source_titles:
            line = f"출처: {', '.join(source_titles[:3])}"
        normalized_lines.append(line)

    normalized = "\n".join(normalized_lines).strip()
    if source_titles and "출처:" not in normalized:
        normalized += f"\n\n출처: {', '.join(source_titles[:3])}"
    if "추가 확인 필요:" not in normalized:
        normalized += "\n\n추가 확인 필요: 실제 적용 여부는 가입 시점의 고시일, 개인 조건, 은행 확인 결과에 따라 달라질 수 있습니다."
    return normalized


def build_answer_lead(products: List[str], intents: List[str], question: str) -> str:
    product_text = ", ".join(products[:2]) if products else "검색된 상품"
    question_key = normalize_key(question)
    if "가입대상" in intents:
        return f"핵심 답변: {product_text}은 문서에 나온 가입자격과 제한 조건을 충족해야 가입할 수 있습니다. 핵심 조건은 아래와 같습니다."
    if "금리" in intents:
        if "혜택" in question_key or "우대" in question_key or "받" in question_key:
            return f"핵심 답변: {product_text}은 문서에 나온 우대이율 조건을 충족하면 금리 혜택을 받을 수 있습니다. 핵심 조건은 아래와 같습니다."
        return f"핵심 답변: {product_text}의 금리 정보는 기본이율과 우대이율 조건을 나누어 확인하면 됩니다. 핵심 내용은 아래와 같습니다."
    if "서류" in intents:
        if "만기" in question_key:
            return f"핵심 답변: {product_text}의 만기 관련 서류는 문서의 만기해지와 제출서류 항목을 기준으로 준비하면 됩니다. 핵심 내용은 아래와 같습니다."
        return f"핵심 답변: {product_text}의 필요 서류는 문서의 신청서류와 제출서류 항목을 기준으로 준비하면 됩니다. 핵심 내용은 아래와 같습니다."
    if "해지" in intents:
        return f"핵심 답변: {product_text}의 해지는 중도해지, 만기해지, 특별중도해지 조건을 구분해서 보면 됩니다. 핵심 내용은 아래와 같습니다."
    if "납입" in intents:
        return f"핵심 답변: {product_text}의 납입은 가입금액, 월 납입한도, 적립방법을 중심으로 보면 됩니다. 핵심 내용은 아래와 같습니다."
    return f"핵심 답변: {product_text}에 대해 검색된 상품공시 내용에서 질문과 직접 관련된 항목을 정리했습니다."


def extract_answer_facts(
    question: str,
    contexts: List[Dict[str, Any]],
    citations: List[Dict[str, Any]],
    intents: List[str],
) -> List[str]:
    terms = answer_focus_terms(question, intents)
    facts: List[str] = []

    for context in contexts:
        content = str(context.get("content", ""))
        for segment in split_fact_candidates(content):
            if not is_relevant_segment(segment, terms, intents):
                continue
            append_unique(facts, clean_fact(segment))
            if len(facts) >= 5:
                break
        if len(facts) >= 5:
            break

    if facts:
        return facts

    for citation in citations:
        append_unique(facts, clean_fact(str(citation.get("snippet", ""))))
        if len(facts) >= 3:
            break
    return facts


def answer_focus_terms(question: str, intents: List[str]) -> List[str]:
    terms: List[str] = []
    for intent in intents:
        for keyword in STRONG_INTENT_KEYWORDS.get(intent, []):
            append_unique(terms, keyword)
        for keyword in INTENT_KEYWORDS.get(intent, []):
            append_unique(terms, keyword)
    for keyword in extract_keywords(question):
        append_unique(terms, keyword)
    return sorted(terms, key=len, reverse=True)


def split_fact_candidates(content: str) -> List[str]:
    marked = re.sub(r"(▣|ㅇ|※|☞|①|②|③|④|⑤|[•·])", r"\n\1", content)
    marked = re.sub(r"\s+(구 분|내 용|가입대상|가입자격|우대이율|우대금리|기본이율|신청서류|만기해지)", r"\n\1", marked)
    candidates = []
    for line in marked.splitlines():
        line = compact_text(line)
        if len(line) >= 12:
            candidates.append(line)
    return candidates


def is_relevant_segment(segment: str, terms: List[str], intents: List[str]) -> bool:
    segment_key = normalize_key(segment)
    if any(normalize_key(term) in segment_key for term in terms if len(normalize_key(term)) >= 2):
        return True
    if "금리" in intents and re.search(r"\d+(?:\.\d+)?\s*%p?", segment):
        return True
    if "서류" in intents and any(word in segment for word in ("증명서", "확인서", "등본", "원본", "제출")):
        return True
    return False


def clean_fact(segment: str) -> str:
    segment = re.sub(r"^[▣ㅇ※☞①②③④⑤•·]\s*", "", segment).strip()
    segment = re.sub(r"\s+", " ", segment)
    if len(segment) > 230:
        segment = segment[:230].rstrip() + "..."
    return segment


def build_context_text(state: RagState) -> str:
    context_blocks = []
    for idx, context in enumerate(state.get("contexts", []), start=1):
        product_name = context.get("productName") or "상품명 미상"
        context_blocks.append(
            f"[근거 {idx}]\n"
            f"문서: {context['title']}\n"
            f"상품: {product_name}\n"
            f"내용:\n{context['content']}"
        )

    return "\n\n".join(context_blocks)


def build_messages(state: RagState) -> List[Dict[str, str]]:
    source_titles = ", ".join(dict.fromkeys(citation["title"] for citation in state.get("citations", [])))
    system = (
        "당신은 BNK부산은행 상품공시 PDF를 근거로 답변하는 RAG 챗봇입니다. "
        "근거에 있는 내용만 사용하고, 모르는 내용은 추측하지 마세요. "
        "문서 제목만 나열하지 말고 질문에 직접 답하세요. 한국어로 간결하게 답변하세요. "
        "출처에는 페이지나 chunk 번호를 쓰지 말고 파일 제목만 쓰세요."
    )
    user = (
        f"질문: {state['question']}\n\n"
        f"검색 근거:\n{build_context_text(state)}\n\n"
        f"사용 가능한 출처 파일 제목: {source_titles}\n\n"
        "위 근거에서 질문과 직접 관련된 내용만 골라 답변하세요.\n"
        "문서 제목 목록만 반복하지 마세요.\n"
        "구분선이나 장식 문자는 쓰지 말고, 같은 문장을 반복하지 마세요.\n"
        "확인 내용은 문서 안의 조건, 서류, 수치, 예외를 질문 의도에 맞게 요약하세요.\n"
        "다음 형식으로 완성된 문장을 작성하세요.\n\n"
        "핵심 답변: ...\n"
        "확인 내용:\n"
        "- ...\n"
        "- ...\n"
        "출처: 파일 제목만 작성\n"
        "추가 확인 필요: ..."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_plain_prompt(state: RagState) -> str:
    messages = build_messages(state)
    return "\n\n".join(f"{message['role']}:\n{message['content']}" for message in messages)


def build_mlx_prompt(state: RagState) -> str:
    source_titles = ", ".join(dict.fromkeys(citation["title"] for citation in state.get("citations", [])))
    return (
        "BNK부산은행 상품공시 PDF 검색 근거만 사용해 질문에 답하세요. "
        "근거에 없는 내용은 추측하지 마세요. "
        "출처에는 페이지나 chunk 번호를 쓰지 말고 파일 제목만 쓰세요.\n\n"
        f"질문:\n{state['question']}\n\n"
        f"검색 근거:\n{build_context_text(state)}\n\n"
        f"사용 가능한 출처 파일 제목:\n{source_titles}\n\n"
        "아래 형식으로만 답하세요. 같은 내용을 반복하지 마세요.\n"
        "핵심 답변: 질문에 대한 직접 답변\n"
        "확인 내용:\n"
        "- 문서 근거에서 뽑은 조건이나 내용\n"
        "- 문서 근거에서 뽑은 조건이나 내용\n"
        "출처: 파일 제목만 작성\n"
        "추가 확인 필요: 부족하거나 애매한 정보\n\n"
        "답변:\n"
    )


@lru_cache(maxsize=1)
def hf_model_and_tokenizer():
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoProcessor, AutoTokenizer
    except ImportError as error:
        raise RuntimeError("torch/transformers가 설치되어 있지 않습니다. rag-service/requirements-llm.txt를 설치하세요.") from error

    model_id = os.getenv("HF_GENERATION_MODEL", "google/gemma-4-E4B-it")
    model_kwargs: Dict[str, Any] = {"dtype": "auto"}
    if torch.backends.mps.is_available():
        model_kwargs["device_map"] = {"": "mps"}
    else:
        model_kwargs["device_map"] = "auto"

    if "gemma-" in model_id.lower():
        processor = AutoProcessor.from_pretrained(model_id)
        model = AutoModelForImageTextToText.from_pretrained(model_id, **model_kwargs)
        return model, processor, "image-text-to-text"

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)
    return model, tokenizer, "causal-lm"


@lru_cache(maxsize=1)
def mlx_model_and_processor():
    try:
        from mlx_vlm import load
    except ImportError as error:
        raise RuntimeError("mlx-vlm이 설치되어 있지 않습니다. rag-service/requirements-llm.txt를 설치하세요.") from error

    model_id = os.getenv("MLX_GENERATION_MODEL", "mlx-community/gemma-4-e4b-it-4bit")
    return load(model_id)


def generate_mlx_answer(state: RagState) -> str:
    try:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
    except ImportError as error:
        raise RuntimeError("mlx-vlm이 설치되어 있지 않습니다. rag-service/requirements-llm.txt를 설치하세요.") from error

    model, processor = mlx_model_and_processor()
    max_new_tokens = int(os.getenv("HF_MAX_NEW_TOKENS", "360"))
    prompt = apply_chat_template(processor, model.config, build_mlx_prompt(state))
    result = generate(
        model,
        processor,
        prompt,
        max_tokens=max_new_tokens,
        temperature=0.0,
        skip_special_tokens=True,
        verbose=False,
    )
    generated = clean_generated_answer(result.text)
    if not generated:
        raise RuntimeError("MLX LLM이 빈 답변을 반환했습니다.")
    return generated


def generate_hf_answer(state: RagState) -> str:
    model, tokenizer_or_processor, model_kind = hf_model_and_tokenizer()
    messages = build_messages(state)
    max_new_tokens = int(os.getenv("HF_MAX_NEW_TOKENS", "360"))

    if model_kind == "image-text-to-text":
        processor = tokenizer_or_processor
        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            repetition_penalty=1.08,
            no_repeat_ngram_size=4,
        )
        generated_ids = outputs[0][inputs["input_ids"].shape[-1]:]
        generated = clean_generated_answer(processor.decode(generated_ids, skip_special_tokens=True))
        if not generated:
            raise RuntimeError("LLM이 빈 답변을 반환했습니다.")
        return generated

    tokenizer = tokenizer_or_processor
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([prompt], return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        repetition_penalty=1.08,
        no_repeat_ngram_size=4,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    generated_ids = outputs[0][inputs.input_ids.shape[-1]:]
    generated = clean_generated_answer(tokenizer.decode(generated_ids, skip_special_tokens=True))
    if not generated:
        raise RuntimeError("LLM이 빈 답변을 반환했습니다.")
    return generated


def clean_generated_answer(text: str) -> str:
    answer = text.strip()
    while answer.startswith("-"):
        answer = answer.lstrip("-").strip()
    if answer.startswith("답변:"):
        answer = answer[len("답변:") :].strip()

    separator_index = answer.find("\n\n---")
    if separator_index > 0:
        answer = answer[:separator_index].strip()

    marker = "핵심 답변:"
    first_marker = answer.find(marker)
    second_marker = answer.find(marker, first_marker + len(marker)) if first_marker >= 0 else -1
    if second_marker > 0:
        answer = answer[:second_marker].strip()

    strong_marker = "**핵심 답변:**"
    first_strong_marker = answer.find(strong_marker)
    second_strong_marker = (
        answer.find(strong_marker, first_strong_marker + len(strong_marker))
        if first_strong_marker >= 0
        else -1
    )
    if second_strong_marker > 0:
        answer = answer[:second_strong_marker].strip()

    return answer


def run_fallback_graph(question: str) -> RagState:
    state: RagState = {
        "question": question,
        "documents": pd.DataFrame(),
        "citations": [],
        "contexts": [],
        "answer": "",
        "status": "STARTED",
    }
    for step in (load_documents, retrieve_documents, generate_answer):
        state.update(step(state))
    return state


def build_langgraph():
    if StateGraph is None:
        return None

    graph = StateGraph(RagState)
    graph.add_node("load_documents", load_documents)
    graph.add_node("retrieve_documents", retrieve_documents)
    graph.add_node("generate_answer", generate_answer)
    graph.set_entry_point("load_documents")
    graph.add_edge("load_documents", "retrieve_documents")
    graph.add_edge("retrieve_documents", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()


compiled_graph = build_langgraph()


@app.get("/health")
def health():
    return {"status": "UP", "langgraph": compiled_graph is not None}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    if compiled_graph is None:
        result = run_fallback_graph(request.question)
    else:
        result = compiled_graph.invoke({"question": request.question})

    return AskResponse(
        question=request.question,
        answer=result["answer"],
        citations=[Citation(**citation) for citation in result["citations"]],
        status=result["status"],
    )
