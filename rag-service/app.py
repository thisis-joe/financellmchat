from __future__ import annotations

from functools import lru_cache
import json
import os
import re
import urllib.error
import urllib.request
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


SUPPORTED_CATEGORY = "예금상품>적립식예금"

DEPOSIT_PRODUCT_CATEGORIES = [
    "적립식예금",
    "거치식예금",
    "입출금자유예금",
    "주택청약관련예금",
    "외화예금",
    "예금금리조회",
]

NON_RECOMMENDABLE_PRODUCT_KEYWORDS = ("약관", "ISA")
YOUTH_OR_SPECIAL_PURPOSE_KEYWORDS = ("청년", "장병", "아기", "아이사랑", "주택드림", "기쁨두배")
ELIGIBILITY_LABELS = ("가입대상", "가입자격", "가입제한")

TEEN_RECOMMENDATIONS = [
    "주택청약종합저축",
    "BNK내맘대로 적금",
    "정기적금",
    "저탄소 실천 적금",
]

AGE_NEUTRAL_RECOMMENDATIONS = [
    "BNK내맘대로 적금",
    "Only One 주거래 우대적금",
    "정기적금",
    "가계우대정기적금",
    "저탄소 실천 적금",
    "펫 적금",
]

SENIOR_RECOMMENDATIONS = [
    "백세청춘 실버적금",
    "BNK내맘대로 적금",
    "Only One 주거래 우대적금",
    "정기적금",
]

YOUTH_RECOMMENDATIONS = [
    "부산은행 청년도약계좌",
    "청년 주택드림 청약통장",
    "부산청년기쁨두배통장",
]

SENIOR_CONTEXT_RECOMMENDATIONS = [
    "백세청춘 실버적금",
    "BNK내맘대로 적금",
    "정기적금",
]

MILITARY_MARKERS = ("군인", "장병", "군복무", "복무", "입대", "전역", "현역", "병사")

PURPOSE_PRODUCT_HINTS = {
    "반려동물": ["펫 적금"],
    "펫": ["펫 적금"],
    "강아지": ["펫 적금"],
    "고양이": ["펫 적금"],
    "환경": ["저탄소 실천 적금"],
    "저탄소": ["저탄소 실천 적금"],
    "야구": ["BNK가을야구적금"],
    "농구": ["BNK썸농구단 우승기원적금"],
    "주거래": ["Only One 주거래 우대적금"],
    "급여": ["Only One 주거래 우대적금"],
    "군인": ["부산은행 장병내일준비적금"],
    "장병": ["부산은행 장병내일준비적금"],
    "청약": ["주택청약종합저축", "청년 주택드림 청약통장"],
}


GUIDE_QUESTION_EXAMPLES = [
    "예금 종류를 알려주세요",
    "적립식예금 상품 목록을 알려주세요",
    "50대인데 추천해주세요",
    "펫 적금 혜택 받으려면 뭘 해야 해?",
    "장병내일준비적금 만기 때 어떤 서류가 필요해?",
]

UNSUPPORTED_SCOPE_KEYWORDS = (
    "대출",
    "카드",
    "외환",
    "환전",
    "송금",
    "수수료",
    "동백전",
    "모락",
    "사고신고",
    "전자금융",
    "수출입",
)


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
    "상품설명": ["설명", "알려줘", "알려", "내용", "정리", "뭐야", "무슨상품", "어떤상품"],
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
    "상품설명": ["상품 개요", "상품개요", "상품특징", "특징", "거래 조건", "거래조건", "가입대상"],
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


def fetch_documents() -> pd.DataFrame:
    sql = """
        select id, title, category, institution, product_name, product_type, source, source_url, content
        from financial_documents
        where institution = 'BNK부산은행'
          and category = %s
        order by created_at desc
    """
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (os.getenv("RAG_CATEGORY", SUPPORTED_CATEGORY),))
            return pd.DataFrame(cursor.fetchall())


def load_documents(_: RagState) -> RagState:
    documents = fetch_documents()
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


def analyze_question(question: str, documents: pd.DataFrame) -> Dict[str, Any]:
    products = detect_products(question, documents)
    intents = detect_intents(question)
    keywords = extract_keywords(question)
    age_info = detect_age_info(question)
    terms = build_focus_terms(question, products, intents, keywords)
    return {
        "products": products,
        "intents": intents,
        "keywords": keywords,
        "terms": terms,
        "age": age_info,
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
    question_without_age = re.sub(r"(?:만\s*)?\d{1,3}\s*(?:대|세)", " ", question)
    for token in re.split(r"\s+", question_without_age):
        keyword = re.sub(r"[^0-9A-Za-z가-힣]", "", token).strip()
        if re.fullmatch(r"\d+", keyword):
            continue
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


def rerank_score(row: pd.Series, base_score: float, focus: Dict[str, Any]) -> float:
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
    product_mismatch_penalty = 0.0
    if focus["products"] and product_name not in focus["products"]:
        product_mismatch_penalty = 0.75

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
    score -= age_product_penalty(product_name, title, focus)
    score -= product_mismatch_penalty
    return score


def summary_section_boost(content_key: str, focus: Dict[str, Any]) -> float:
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


def detect_age_info(question: str) -> Dict[str, Optional[int]]:
    age_match = re.search(r"(?:만\s*)?(\d{1,3})\s*세", question)
    if age_match:
        age = int(age_match.group(1))
        return {"age": age, "age_group": (age // 10) * 10}

    age_group_match = re.search(r"(\d{2,3})\s*대", question)
    if age_group_match:
        age_group = int(age_group_match.group(1))
        if age_group % 10 != 0:
            age_group = (age_group // 10) * 10
        return {"age": None, "age_group": age_group}

    return {"age": None, "age_group": None}


def age_floor(age_info: Dict[str, Optional[int]]) -> Optional[int]:
    if age_info.get("age") is not None:
        return int(age_info["age"])
    if age_info.get("age_group") is not None:
        return int(age_info["age_group"])
    return None


def age_range(age_info: Dict[str, Optional[int]]) -> Tuple[Optional[int], Optional[int], bool]:
    if age_info.get("age") is not None:
        age = int(age_info["age"])
        return age, age, True
    if age_info.get("age_group") is not None:
        start = int(age_info["age_group"])
        return start, start + 9, False
    return None, None, False


def has_age_info(age_info: Dict[str, Optional[int]]) -> bool:
    return age_info.get("age") is not None or age_info.get("age_group") is not None


def age_product_penalty(product_name: str, title: str, focus: Dict[str, Any]) -> float:
    floor = age_floor(focus.get("age", {}))
    if floor is None or floor < 35:
        return 0.0

    product_text = f"{product_name} {title}"
    explicit_products = " ".join(focus.get("products", []))
    if product_name and product_name in explicit_products:
        return 0.0

    if any(keyword in product_text for keyword in YOUTH_OR_SPECIAL_PURPOSE_KEYWORDS):
        return 0.65
    return 0.0


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


def build_direct_response(question: str) -> Optional[AskResponse]:
    question = question.strip()
    conversation_answer = build_conversation_answer(question)
    if conversation_answer is not None:
        return AskResponse(
            question=question,
            answer=conversation_answer,
            citations=[],
            status="DIRECT",
        )

    situation_response = build_situation_response(question)
    if situation_response is not None:
        return situation_response

    if is_low_information_question(question):
        return AskResponse(
            question=question,
            answer=build_guidance_answer("질문을 조금만 더 구체적으로 입력해 주세요."),
            citations=[],
            status="DIRECT",
        )

    if is_deposit_catalog_question(question):
        documents = fetch_documents()
        return AskResponse(
            question=question,
            answer=build_deposit_catalog_answer(question, documents),
            citations=[],
            status="DIRECT",
        )

    if is_recommendation_question(question):
        documents = fetch_documents()
        answer, citations = build_recommendation_answer(question, documents)
        return AskResponse(
            question=question,
            answer=answer,
            citations=[Citation(**citation) for citation in citations],
            status="RECOMMENDATION",
        )

    return None


def build_situation_response(question: str) -> Optional[AskResponse]:
    age_info = detect_age_info(question)
    key = normalize_key(question)
    documents: Optional[pd.DataFrame] = None

    if is_child_context(age_info):
        return AskResponse(
            question=question,
            answer=build_child_context_answer(age_info),
            citations=[],
            status="DIRECT",
        )

    if is_military_context_question(question):
        documents = fetch_documents()
        product_names = ["부산은행 장병내일준비적금"]
        citations = build_recommendation_citations(documents, product_names)
        return AskResponse(
            question=question,
            answer=build_military_context_answer(),
            citations=[Citation(**citation) for citation in citations],
            status="RECOMMENDATION",
        )

    if is_senior_context(age_info) and not is_recommendation_question(question):
        documents = fetch_documents()
        candidates, _ = choose_recommendation_products_for_order(documents, SENIOR_CONTEXT_RECOMMENDATIONS, age_info)
        citations = build_recommendation_citations(documents, candidates)
        return AskResponse(
            question=question,
            answer=build_senior_context_answer(candidates),
            citations=[Citation(**citation) for citation in citations],
            status="RECOMMENDATION",
        )

    if has_age_info(age_info) and not is_recommendation_question(question) and not any(marker in key for marker in ("가입", "금리", "이율", "서류", "해지", "납입")):
        return AskResponse(
            question=question,
            answer=build_age_context_answer(age_info),
            citations=[],
            status="DIRECT",
        )

    return None


def is_child_context(age_info: Dict[str, Optional[int]]) -> bool:
    return age_info.get("age") is not None and int(age_info["age"]) < 14


def is_senior_context(age_info: Dict[str, Optional[int]]) -> bool:
    floor = age_floor(age_info)
    return floor is not None and floor >= 65


def is_military_context_question(question: str) -> bool:
    key = normalize_key(question)
    if not any(marker in key for marker in MILITARY_MARKERS):
        return False
    if detect_intents(question):
        return False
    return not any(normalize_key(alias) in key for alias in PRODUCT_ALIAS_HINTS)


def build_child_context_answer(age_info: Dict[str, Optional[int]]) -> str:
    age = age_info.get("age")
    prefix = f"{age}세라면 아직 어린이" if age is not None else "어린이라면"
    return (
        f"{prefix}라서 본인이 직접 예금 상품 가입을 진행하기는 어렵습니다.\n\n"
        "아이 명의로 저축을 준비하려는 상황이라면 보호자와 함께 가입 가능 여부와 필요 서류를 확인하는 게 먼저예요. "
        "지금 조건에서는 특정 상품을 바로 추천하기보다 보호자 동반 확인이 더 안전합니다."
    )


def build_military_context_answer() -> str:
    return (
        "부산은행은 국군장병을 응원합니다.\n\n"
        "군 복무 중이라면 먼저 볼 상품은 부산은행 장병내일준비적금입니다. "
        "군 복무자를 위한 적금 성격이 가장 직접적이고, 가입자격이나 제출서류, 만기 수령 조건은 복무 구분에 따라 달라질 수 있어요."
    )


def build_senior_context_answer(candidates: List[str]) -> str:
    if candidates:
        products = ", ".join(candidates[:3])
        return (
            "건강하고 편안한 금융생활을 응원합니다.\n\n"
            f"연령 조건만 놓고 보면 청년 전용 상품보다는 {products}부터 확인해 보는 편이 자연스럽습니다. "
            "특히 백세청춘 실버적금은 고령층 조건과 직접 맞닿아 있어요. "
            "다만 실제 가입 가능 여부와 우대금리는 가입 시점과 개인 조건에 따라 확인이 필요합니다."
        )
    return (
        "건강하고 편안한 금융생활을 응원합니다.\n\n"
        "지금 자료만으로는 연령 조건에 맞는 상품을 충분히 고르지 못했습니다. "
        "원하시면 `90세에게 맞는 적금 추천해줘`처럼 다시 물어봐 주세요."
    )


def build_age_context_answer(age_info: Dict[str, Optional[int]]) -> str:
    floor = age_floor(age_info)
    if floor is None:
        return "나이를 알려주셨네요. 가입 가능 여부는 상품마다 달라서, 추천을 원하면 `추천해줘`라고 이어서 물어봐 주세요."
    if floor < 19:
        return "만 19세 미만이면 청년 전용 상품 중에도 가입이 안 되는 경우가 있어요. 보호자 동반 여부와 상품별 가입대상을 먼저 확인하는 게 좋습니다."
    if floor >= 40:
        return "연령 조건을 고려해서 볼 수 있는 적금이 몇 가지 있습니다. 추천을 원하면 `추천해줘`라고 이어서 물어봐 주세요."
    return "청년층이라면 청년 전용 상품과 일반 적금을 함께 비교해 볼 수 있어요. 원하면 조건에 맞는 후보를 골라드릴게요."


def build_conversation_answer(question: str) -> Optional[str]:
    if is_help_question(question):
        return build_guidance_answer("제가 잘 답할 수 있는 질문은 부산은행 적립식예금 상품공시를 근거로 찾는 질문입니다.")

    if is_unsupported_scope_question(question):
        return build_guidance_answer(
            "아직 그 분야의 PDF 자료는 적재되어 있지 않습니다. 현재는 예금상품 > 적립식예금 자료만 근거로 답변할 수 있어요."
        )

    if has_searchable_finance_intent(question):
        return None

    if is_greeting_question(question):
        return build_guidance_answer("안녕하세요! 궁금한 적립식예금 상품을 같이 찾아볼게요.")

    if is_farewell_question(question):
        return build_brief_conversation_answer("네, 편하게 다시 찾아오세요. 다음에 궁금한 적립식예금 조건이 생기면 바로 찾아드릴게요.")

    if is_thanks_question(question):
        return build_brief_conversation_answer("도움이 되었다면 다행입니다. 이어서 궁금한 상품 조건을 물어보셔도 좋아요.")

    if is_low_information_question(question):
        return build_guidance_answer("질문을 조금만 더 구체적으로 입력해 주세요.")

    if is_casual_or_non_finance_question(question):
        return build_brief_conversation_answer("말 걸어주셔서 좋아요. 저는 부산은행 상품공시를 찾아 답하는 챗봇이라, 적립식예금 쪽 질문이면 더 정확히 도와드릴 수 있어요.")

    if not has_age_info(detect_age_info(question)) and not is_military_context_question(question):
        return build_guidance_answer("말씀은 이해했어요. 지금 제가 정확히 확인할 수 있는 범위는 부산은행 적립식예금 상품공시라서, 상품명이나 조건을 함께 말해주면 바로 찾아드릴게요.")

    return None


def build_guidance_answer(prefix: str) -> str:
    lines = [
        prefix,
        "",
        "현재는 아래 자료를 기준으로 답할 수 있어요.",
        "- 예금상품 > 적립식예금 PDF",
        "",
        "이런 식으로 물어보면 좋아요.",
    ]
    lines.extend(f"- {example}" for example in GUIDE_QUESTION_EXAMPLES)
    lines.append("")
    lines.append("대출, 카드, 외환, 수수료 자료는 아직 넣지 않았어요.")
    return "\n".join(lines)


def build_brief_conversation_answer(prefix: str) -> str:
    return (
        f"{prefix}\n\n"
        "지금은 예금상품 > 적립식예금 PDF를 기준으로 답할 수 있습니다. "
        "`펫 적금 설명해줘`, `50대에게 맞는 적금 추천해줘`처럼 물어보면 바로 찾아드릴게요."
    )


def conversation_key(question: str) -> str:
    return re.sub(r"[\s~!?.。…,.]+", "", question.lower())


def is_greeting_question(question: str) -> bool:
    compact = conversation_key(question)
    return compact in {
        "ㅎㅇ",
        "ㅎㅇㅎㅇ",
        "하이요",
        "하이",
        "헬로",
        "안녕",
        "안뇽",
        "안녕하세요",
        "안녕하세요반가워요",
        "반가워",
        "방가",
        "hi",
        "hello",
        "hey",
    }


def is_farewell_question(question: str) -> bool:
    compact = conversation_key(question)
    return compact in {
        "ㅂ2",
        "ㅂㅇ",
        "바이",
        "빠이",
        "빠잉",
        "잘가",
        "잘가요",
        "안녕히계세요",
        "안녕히가세요",
        "다음에봐",
        "또봐",
        "bye",
        "goodbye",
    }


def is_thanks_question(question: str) -> bool:
    compact = conversation_key(question)
    if compact in {"ㅅㄱ", "ㄱㅅ", "감사", "고마워", "고마워요", "땡큐", "thanks", "thankyou"}:
        return True
    return any(keyword in compact for keyword in ("수고", "감사해", "고맙", "도움됐"))


def is_low_information_question(question: str) -> bool:
    key = normalize_key(question)
    return len(key) < 2


def is_help_question(question: str) -> bool:
    key = normalize_key(question)
    return any(
        keyword in key
        for keyword in (
            "뭐물어",
            "뭘물어",
            "무엇을물어",
            "질문예시",
            "사용법",
            "도움말",
            "뭐할수",
            "무엇을할수",
            "어떻게물어",
            "주요질문",
        )
    )


def is_unsupported_scope_question(question: str) -> bool:
    key = normalize_key(question)
    if not any(normalize_key(keyword) in key for keyword in UNSUPPORTED_SCOPE_KEYWORDS):
        return False

    supported_markers = ("예금", "적금", "청약", "금리", "이율")
    product_markers = tuple(normalize_key(alias) for alias in PRODUCT_ALIAS_HINTS)
    return not any(marker in key for marker in supported_markers + product_markers)


def has_searchable_finance_intent(question: str) -> bool:
    key = normalize_key(question)
    if not key:
        return False

    finance_markers = (
        "예금",
        "적금",
        "청약",
        "상품",
        "가입",
        "금리",
        "이율",
        "우대",
        "해지",
        "만기",
        "서류",
        "납입",
        "비과세",
        "소득공제",
        "추천",
        "목록",
        "종류",
    )
    if any(marker in key for marker in finance_markers):
        return True
    return any(normalize_key(alias) in key for alias in PRODUCT_ALIAS_HINTS)


def is_casual_or_non_finance_question(question: str) -> bool:
    key = normalize_key(question)
    compact = conversation_key(question)
    if re.fullmatch(r"[ㅋㅎㅠㅜ]+", compact):
        return True
    return any(
        keyword in key
        for keyword in (
            "뭐해",
            "누구야",
            "정체",
            "심심",
            "날씨",
            "점심",
            "저녁",
            "밥먹",
            "기분",
            "재밌",
        )
    )


def is_deposit_catalog_question(question: str) -> bool:
    key = normalize_key(question)
    if "예금" not in key:
        return False
    return any(keyword in key for keyword in ("종류", "분류", "목록", "상품군", "어떤예금", "뭐있"))


def is_recommendation_question(question: str) -> bool:
    key = normalize_key(question)
    recommendation_terms = ("추천", "골라", "맞는", "어울리는", "뭐가좋", "무엇이좋", "상품좀", "가입하면좋")
    return any(term in key for term in recommendation_terms)


def build_deposit_catalog_answer(question: str, documents: pd.DataFrame) -> str:
    products = product_names_from_documents(documents)
    wants_full_list = any(keyword in normalize_key(question) for keyword in ("전체", "목록", "상품목록", "다보여"))
    examples = products if wants_full_list else products[:10]

    lines = [
        "부산은행 상품공시 기준으로 예금상품은 크게 이렇게 나뉩니다.",
        "",
    ]
    for category in DEPOSIT_PRODUCT_CATEGORIES:
        lines.append(f"- {category}")

    lines.extend(
        [
            "",
            "지금 제가 실제 PDF로 확인할 수 있는 범위는 `예금상품 > 적립식예금`입니다.",
        ]
    )

    if examples:
        lines.append("현재 적재된 적립식예금 상품 예시는 다음과 같습니다.")
        for product in examples:
            lines.append(f"- {product}")
        if not wants_full_list and len(products) > len(examples):
            lines.append(f"- 그 외 {len(products) - len(examples)}개 상품도 적립되어 있습니다. 전체 목록이 필요하면 `적립식예금 상품 목록`이라고 물어보세요.")

    lines.append("")
    lines.append("거치식예금, 입출금자유예금, 대출상품 자료는 아직 넣지 않았어요.")
    return "\n".join(lines)


def product_eligibility_text(documents: pd.DataFrame, product_name: str) -> str:
    rows = documents[documents["product_name"].fillna("").astype(str) == product_name]
    snippets: List[str] = []
    for _, row in rows.iterrows():
        content = strip_import_metadata(none_if_nan(row.get("content")) or "")
        for label in ELIGIBILITY_LABELS:
            index = content.find(label)
            if index >= 0:
                append_unique(snippets, compact_text(content[index:index + 900]))

    if not snippets:
        overview = select_product_overview_row(documents, product_name)
        if overview is not None:
            content = strip_import_metadata(none_if_nan(overview.get("content")) or "")
            append_unique(snippets, compact_text(content[:900]))

    return "\n".join(snippets)


def extract_age_bounds(eligibility_text: str) -> Tuple[Optional[int], Optional[int]]:
    if not eligibility_text:
        return None, None

    min_ages: List[int] = []
    max_ages: List[int] = []

    for start, end in re.findall(r"(?:만\s*)?(\d{1,3})\s*세\s*[~∼-]\s*(?:만\s*)?(\d{1,3})\s*세", eligibility_text):
        min_ages.append(int(start))
        max_ages.append(int(end))

    for age in re.findall(r"(?:만\s*)?(\d{1,3})\s*세\s*(?:이상|부터)", eligibility_text):
        min_ages.append(int(age))

    for age in re.findall(r"(?:만\s*)?(\d{1,3})\s*세\s*(?:이하|까지|이내)", eligibility_text):
        max_ages.append(int(age))

    return (max(min_ages) if min_ages else None, min(max_ages) if max_ages else None)


def product_age_incompatibility_reason(
    product_name: str,
    documents: pd.DataFrame,
    age_info: Dict[str, Optional[int]],
) -> Optional[str]:
    start_age, end_age, is_exact_age = age_range(age_info)
    if start_age is None or end_age is None:
        return None

    eligibility_text = product_eligibility_text(documents, product_name)
    min_age, max_age = extract_age_bounds(eligibility_text)

    if min_age is not None and start_age < min_age:
        if is_exact_age:
            return f"가입대상이 만 {min_age}세 이상이라 현재 나이와 맞지 않아요."
        return f"가입대상이 만 {min_age}세 이상이라 입력한 나이대 전체에 안전하게 맞는 상품으로 보기 어렵습니다."

    if max_age is not None and end_age > max_age:
        if is_exact_age:
            return f"가입대상이 만 {max_age}세 이하라 현재 나이와 맞지 않아요."
        return f"가입대상이 만 {max_age}세 이하라 입력한 나이대 전체에 안전하게 맞는 상품으로 보기 어렵습니다."

    if min_age is None and max_age is None:
        floor = age_floor(age_info)
        if floor is not None and floor >= 35 and any(keyword in product_name for keyword in YOUTH_OR_SPECIAL_PURPOSE_KEYWORDS):
            return "청년/장병/아동 등 특정 대상 성격이 강해 현재 조건에서는 우선순위를 낮췄습니다."
        if floor is not None and floor < 19 and any(keyword in product_name for keyword in YOUTH_OR_SPECIAL_PURPOSE_KEYWORDS):
            return "청년/장병 등 특정 대상 성격이 강해 현재 조건에서는 우선순위를 낮췄습니다."

    return None


def product_eligibility_reason(product_name: str, documents: pd.DataFrame) -> Optional[str]:
    eligibility_text = product_eligibility_text(documents, product_name)
    min_age, max_age = extract_age_bounds(eligibility_text)
    normalized = normalize_key(eligibility_text)

    if min_age is not None and max_age is not None:
        return f"가입대상에 만 {min_age}세 이상 만 {max_age}세 이하 조건이 있습니다."
    if min_age is not None:
        return f"가입대상에 만 {min_age}세 이상 조건이 있습니다."
    if max_age is not None:
        return f"가입대상에 만 {max_age}세 이하 조건이 있습니다."
    if any(keyword in normalized for keyword in ("제한없음", "연령에관계없이", "연령에상관없이")):
        return "가입대상에 연령 제한이 없다고 안내되어 있습니다."
    return None


def build_recommendation_answer(question: str, documents: pd.DataFrame) -> Tuple[str, List[Dict[str, Any]]]:
    if documents.empty:
        return "추천에 사용할 상품공시 문서가 아직 적재되어 있지 않습니다.", []

    age_info = detect_age_info(question)
    candidates, exclusions = choose_recommendation_products(question, documents, age_info)
    citations = build_recommendation_citations(documents, candidates)

    if not candidates:
        return (
            "지금 말만으로는 어떤 상품을 골라야 할지 기준이 조금 부족합니다.\n\n"
            "아래 중 하나만 더 알려주면 훨씬 잘 골라드릴 수 있어요.\n"
            "- 나이대\n"
            "- 목적: 목돈 마련, 주거래, 청약, 반려동물, 친환경, 급여 실적 등\n"
            "- 선호: 자유적립식 또는 정액적립식\n\n"
            "예: `50대에게 맞는 적금 추천해줘`, `반려동물 키우는데 혜택 있는 적금 추천해줘`",
            [],
        )

    lines = [build_recommendation_lead(question, age_info), "", "먼저 볼 만한 상품은 이쪽입니다."]
    for index, product_name in enumerate(candidates, start=1):
        lines.append(f"{index}. {product_name}: {recommendation_reason(product_name, age_info, documents)}")

    if exclusions:
        lines.extend(["", "조건이 맞지 않아 제외한 대표 상품도 있어요."])
        lines.extend(f"- {exclusion}" for exclusion in exclusions[:4])

    lines.append("")
    lines.append("실제 가입 가능 여부와 우대금리는 가입 시점, 개인 조건, 은행 확인 결과에 따라 달라질 수 있습니다.")
    return "\n".join(lines), citations


def product_names_from_documents(documents: pd.DataFrame) -> List[str]:
    if documents.empty or "product_name" not in documents:
        return []

    products = []
    for product_name in documents["product_name"].dropna().astype(str).tolist():
        if not product_name.strip():
            continue
        if any(keyword in product_name for keyword in ("약관",)):
            continue
        append_unique(products, product_name.strip())
    return sorted(products)


def choose_recommendation_products(
    question: str,
    documents: pd.DataFrame,
    age_info: Dict[str, Optional[int]],
) -> Tuple[List[str], List[str]]:
    products = product_names_from_documents(documents)
    if not products:
        return [], []

    available = set(products)
    preferred_order = recommendation_preferred_order(question, age_info)
    explicit_products = detect_products(question, documents)
    question_key = normalize_key(question)

    scored: List[Tuple[float, str]] = []
    exclusions: List[str] = []
    for product in products:
        if any(keyword in product for keyword in NON_RECOMMENDABLE_PRODUCT_KEYWORDS):
            continue
        incompatibility_reason = product_age_incompatibility_reason(product, documents, age_info)
        if incompatibility_reason:
            if should_explain_exclusion(product, preferred_order, explicit_products, age_info):
                append_unique(exclusions, f"{product}: {incompatibility_reason}")
            continue

        score = 0.0
        if product in preferred_order:
            score += max(0, 8 - preferred_order.index(product))
        if product in explicit_products:
            score += 10
        for purpose, hinted_products in PURPOSE_PRODUCT_HINTS.items():
            if normalize_key(purpose) in question_key and product in hinted_products:
                score += 8
        if product in AGE_NEUTRAL_RECOMMENDATIONS:
            score += 1.5
        if "청약" in question_key and "청약" in product:
            score += 4
        if score > 0:
            scored.append((score, product))

    scored.sort(key=lambda item: (-item[0], products.index(item[1])))
    selected = [product for _, product in scored[:3] if product in available]
    if selected:
        return selected, exclusions

    fallback_order = [product for product in AGE_NEUTRAL_RECOMMENDATIONS if product in available]
    filtered_fallback = [
        product
        for product in fallback_order
        if not product_age_incompatibility_reason(product, documents, age_info)
    ]
    return filtered_fallback[:3], exclusions


def choose_recommendation_products_for_order(
    documents: pd.DataFrame,
    preferred_order: List[str],
    age_info: Dict[str, Optional[int]],
) -> Tuple[List[str], List[str]]:
    products = set(product_names_from_documents(documents))
    selected: List[str] = []
    exclusions: List[str] = []
    for product in preferred_order:
        if product not in products:
            continue
        reason = product_age_incompatibility_reason(product, documents, age_info)
        if reason:
            append_unique(exclusions, f"{product}: {reason}")
            continue
        append_unique(selected, product)
    return selected[:3], exclusions


def should_explain_exclusion(
    product_name: str,
    preferred_order: List[str],
    explicit_products: List[str],
    age_info: Dict[str, Optional[int]],
) -> bool:
    floor = age_floor(age_info)
    if product_name in explicit_products or product_name in preferred_order:
        return True
    if floor is not None and floor < 20 and any(keyword in product_name for keyword in YOUTH_OR_SPECIAL_PURPOSE_KEYWORDS):
        return True
    if floor is not None and floor >= 40 and any(keyword in product_name for keyword in YOUTH_OR_SPECIAL_PURPOSE_KEYWORDS):
        return True
    return False


def recommendation_preferred_order(question: str, age_info: Dict[str, Optional[int]]) -> List[str]:
    key = normalize_key(question)
    order: List[str] = []

    for purpose, products in PURPOSE_PRODUCT_HINTS.items():
        if normalize_key(purpose) in key:
            for product in products:
                append_unique(order, product)

    if any(marker in key for marker in MILITARY_MARKERS):
        append_unique(order, "부산은행 장병내일준비적금")

    floor = age_floor(age_info)
    if is_under_19_request(age_info):
        for product in TEEN_RECOMMENDATIONS:
            append_unique(order, product)
    elif floor is not None and floor < 40:
        for product in YOUTH_RECOMMENDATIONS:
            append_unique(order, product)
    elif is_age_mature(age_info):
        for product in SENIOR_RECOMMENDATIONS:
            append_unique(order, product)

    for product in AGE_NEUTRAL_RECOMMENDATIONS:
        append_unique(order, product)
    return order


def is_under_19_request(age_info: Dict[str, Optional[int]]) -> bool:
    if age_info.get("age") is not None:
        return int(age_info["age"]) < 19
    return age_info.get("age_group") == 10


def is_age_mature(age_info: Dict[str, Optional[int]]) -> bool:
    floor = age_floor(age_info)
    return floor is not None and floor >= 40


def build_recommendation_lead(question: str, age_info: Dict[str, Optional[int]]) -> str:
    if any(marker in normalize_key(question) for marker in MILITARY_MARKERS):
        return "군 복무 중이라면 군인 관련 적금부터 확인하는 게 가장 자연스럽습니다. 부산은행은 국군장병을 응원합니다."
    if is_under_19_request(age_info):
        return "10대 또는 만 19세 미만이라면 청년 전용 상품을 바로 추천하기보다, 가입대상에서 연령 제한이 없는 상품을 먼저 보는 게 안전합니다."
    if is_age_mature(age_info):
        return "50대 이상이라면 청년 전용 상품보다 가입대상 제한이 없거나 중장년 조건에 맞는 적립식예금을 먼저 보는 편이 좋습니다."
    if age_floor(age_info) is not None and age_floor(age_info) < 40:
        return "청년층이라면 청년 전용 상품과 목적형 적금을 함께 비교해 볼 수 있습니다."
    return "나이, 목적, 거래실적에 따라 추천이 달라져서 질문에서 확인되는 조건에 맞춰 후보를 골랐습니다."


def recommendation_reason(
    product_name: str,
    age_info: Dict[str, Optional[int]],
    documents: pd.DataFrame,
) -> str:
    eligibility_reason = product_eligibility_reason(product_name, documents)
    if eligibility_reason:
        return eligibility_reason
    if product_name == "백세청춘 실버적금":
        if age_info.get("age_group") == 50 and age_info.get("age") is None:
            return "문서상 가입대상이 만 56세 이상이라 50대 중 만 56세 이상이면 우선 확인할 만합니다."
        return "만 56세 이상 개인 대상 상품이라 중장년층 조건에 가장 직접적으로 맞습니다."
    if product_name == "BNK내맘대로 적금":
        return "목적을 넓게 잡기 좋은 자유적립식 성격의 후보입니다."
    if product_name == "Only One 주거래 우대적금":
        return "급여 입금이나 주거래 실적이 있다면 우대조건을 확인할 만합니다."
    if product_name == "정기적금":
        return "특정 연령 전용이 아닌 기본 적금 후보로 비교 기준으로 삼기 좋습니다."
    if product_name == "가계우대정기적금":
        return "일반 가계 저축 목적의 적금 후보로 볼 수 있습니다."
    if product_name == "저탄소 실천 적금":
        return "친환경 실천 조건에 관심이 있으면 우대조건을 확인할 만합니다."
    if product_name == "펫 적금":
        return "반려동물 관련 조건이나 혜택에 관심이 있을 때 검토할 만합니다."
    if "청년" in product_name:
        return "청년층 전용 성격이 강하므로 연령 조건을 먼저 확인해야 합니다."
    if "장병" in product_name:
        return "군 복무 대상 여부가 핵심 조건이므로 해당 여부를 먼저 확인해야 합니다."
    return "질문 조건과 상품공시 내용이 일부 맞아 후보로 골랐습니다."


def build_recommendation_citations(
    documents: pd.DataFrame,
    products: List[str],
) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    seen_titles = set()
    for index, product_name in enumerate(products, start=1):
        row = select_product_overview_row(documents, product_name)
        if row is None:
            continue
        raw_content = str(row["content"])
        title = source_file_title(row, raw_content)
        if title in seen_titles:
            continue
        content = strip_import_metadata(raw_content)
        terms = [product_name, "가입대상", "상품특징", "우대이율", "기본이율"]
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
                "score": round(1.0 - (index * 0.05), 4),
                "snippet": build_text_window(content, terms, max_chars=260),
            }
        )
        seen_titles.add(title)
    return citations


def select_product_overview_row(documents: pd.DataFrame, product_name: str) -> Optional[pd.Series]:
    rows = documents[documents["product_name"].fillna("").astype(str) == product_name]
    if rows.empty:
        return None

    best_score = -1
    best_row = None
    for _, row in rows.iterrows():
        content = strip_import_metadata(none_if_nan(row.get("content")) or "")
        title = none_if_nan(row.get("title")) or ""
        score = 0
        if "p1" in title.lower():
            score += 3
        if "상품 개요" in content or "상품 개요 및 특징" in content:
            score += 3
        if "가입대상" in content:
            score += 2
        if "기본이율" in content or "우대이율" in content:
            score += 1
        if score > best_score:
            best_score = score
            best_row = row
    return best_row


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

    if generation_mode == "openai":
        try:
            return {"answer": finalize_generated_answer(generate_openai_answer(state), state), "status": "OK"}
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
    facts = extract_answer_facts(state["question"], contexts, citations, intents)

    lines = [build_answer_lead(unique_products, intents, state["question"])]
    if facts:
        lines.append("")
        for fact in facts[:4]:
            lines.append(f"- {fact}")
    if not facts:
        lines.append("")
        lines.append("검색된 문서에서 질문과 바로 연결되는 문장을 충분히 찾지 못했습니다. 답변근거에서 검색된 문서를 확인해 주세요.")

    lines.append("")
    lines.append("실제 적용 여부는 가입 시점의 고시일, 개인 조건, 은행 확인 결과에 따라 달라질 수 있습니다.")

    if fallback_reason:
        lines.append("")
        lines.append("문서 내용 중심으로 안전하게 요약했습니다.")
    return "\n".join(lines)


def finalize_generated_answer(answer: str, state: RagState) -> str:
    normalized_lines = []
    for line in answer.splitlines():
        line = line.strip()
        if not line:
            normalized_lines.append("")
            continue
        line = strip_visible_answer_label(line)
        if line is None:
            continue
        normalized_lines.append(normalize_answer_line(line))

    normalized = "\n".join(normalized_lines).strip()
    normalized = remove_incomplete_tail(normalized)
    caveat = "실제 적용 여부는 가입 시점의 고시일, 개인 조건, 은행 확인 결과에 따라 달라질 수 있습니다."
    if caveat not in normalized and "가입 시점" not in normalized:
        normalized += f"\n\n{caveat}"
    return normalized


def normalize_answer_line(line: str) -> str:
    line = re.sub(r"^\*\s+", "- ", line)
    line = re.sub(r"^[-*]\s{2,}", "- ", line)
    return line


def remove_incomplete_tail(answer: str) -> str:
    lines = answer.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        return answer

    tail = lines[-1].strip()
    incomplete_endings = ("하시면", "하시면 됩니다만", "통해", "통해서", "문의하시면", "확인하시면")
    if tail.endswith(incomplete_endings):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines).strip()


def build_answer_lead(products: List[str], intents: List[str], question: str) -> str:
    product_text = ", ".join(products[:2]) if products else "검색된 상품"
    question_key = normalize_key(question)
    if "상품설명" in intents:
        return f"좋아요. {product_text}에 대해 상품공시에서 확인되는 내용을 먼저 쉽게 정리해 드릴게요."
    if "가입대상" in intents:
        return f"{product_text}은 문서에 나온 가입자격과 제한 조건을 먼저 확인해야 합니다."
    if "금리" in intents:
        if "혜택" in question_key or "우대" in question_key or "받" in question_key:
            return f"{product_text}은 문서에 나온 우대이율 조건을 충족해야 금리 혜택을 받을 수 있습니다."
        return f"{product_text}의 금리는 기본이율과 우대이율 조건을 나누어 보면 이해하기 쉽습니다."
    if "서류" in intents:
        if "만기" in question_key:
            return f"{product_text}의 만기 관련 서류는 문서의 만기해지와 제출서류 항목을 기준으로 확인하면 됩니다."
        return f"{product_text}의 필요 서류는 문서의 신청서류와 제출서류 항목을 기준으로 준비하면 됩니다."
    if "해지" in intents:
        return f"{product_text}의 해지는 중도해지, 만기해지, 특별중도해지 조건을 구분해서 보면 됩니다."
    if "납입" in intents:
        return f"{product_text}의 납입은 가입금액, 월 납입한도, 적립방법을 중심으로 보면 됩니다."
    return f"{product_text}에 대해 검색된 상품공시 내용에서 질문과 관련된 부분을 정리했습니다."


def strip_visible_answer_label(line: str) -> Optional[str]:
    hidden_prefixes = ("출처:", "근거 문서:", "사용 가능한 출처 파일 제목:")
    if line.startswith(hidden_prefixes):
        return None

    removable_prefixes = ("핵심 답변:", "확인 내용:", "추가 확인 필요:", "답변:")
    for prefix in removable_prefixes:
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            return value or None
    return line


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
    marked = re.sub(
        r"\s+(구 분|내 용|기본정보|상품 개요 및 특징|상품개요|상품특징|거래 조건|거래조건|가입대상|가입자격|우대이율|우대금리|기본이율|신청서류|만기해지)",
        r"\n\1",
        marked,
    )
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
    if "상품설명" in intents and any(
        normalize_key(word) in segment_key
        for word in ("상품 개요", "상품개요", "상품특징", "특징", "가입대상", "거래조건", "가입금액", "가입기간")
    ):
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
    system = (
        "당신은 BNK부산은행 상품공시 PDF를 근거로 답변하는 RAG 챗봇입니다. "
        "근거에 있는 내용만 사용하고, 모르는 내용은 추측하지 마세요. "
        "문서 제목만 나열하지 말고 질문에 직접 답하세요. "
        "은행 상담원처럼 자연스럽고 간결한 한국어로 답변하세요. "
        "답변 본문에 '핵심 답변', '확인 내용', '출처', '추가 확인 필요' 같은 양식 제목을 쓰지 마세요. "
        "출처와 다운로드 링크는 시스템이 별도로 보여주므로 본문에는 파일명이나 출처 목록을 쓰지 마세요."
    )
    user = (
        f"질문: {state['question']}\n\n"
        f"검색 근거:\n{build_context_text(state)}\n\n"
        "위 근거에서 질문과 직접 관련된 내용만 골라 답변하세요.\n"
        "문서 제목 목록만 반복하지 마세요.\n"
        "구분선, 굵은 글씨, 근거 번호, 장식 문자는 쓰지 말고, 같은 문장을 반복하지 마세요.\n"
        "첫 문장은 질문 의도에 맞게 자연스럽게 시작하세요. 예를 들어 군인, 어린이, 고령층 같은 상황이 드러나면 그 상황을 먼저 이해한 듯 답하세요.\n"
        "조건, 서류, 수치, 예외는 필요할 때만 최대 3개 bullet로 짧게 정리하세요.\n"
        "본문에 출처, 파일명, 다운로드 안내를 쓰지 마세요.\n"
        "마지막에는 실제 적용이 가입 시점과 개인 조건에 따라 달라질 수 있음을 자연스러운 문장으로만 덧붙이세요."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_plain_prompt(state: RagState) -> str:
    messages = build_messages(state)
    return "\n\n".join(f"{message['role']}:\n{message['content']}" for message in messages)


def generate_openai_answer(state: RagState) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    messages = build_messages(state)
    model = os.getenv("OPENAI_MODEL", "gpt-5.1")
    max_output_tokens = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "450"))
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))

    payload = {
        "model": model,
        "instructions": messages[0]["content"],
        "input": messages[1]["content"],
        "max_output_tokens": max_output_tokens,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API 호출 실패: HTTP {error.code} {detail[:300]}") from error

    answer = extract_openai_output_text(body)
    if not answer:
        raise RuntimeError("OpenAI API가 빈 답변을 반환했습니다.")
    return answer


def extract_openai_output_text(payload: Dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    texts: List[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                texts.append(str(content["text"]))
    return "\n".join(texts).strip()


def build_mlx_prompt(state: RagState) -> str:
    return (
        "BNK부산은행 상품공시 PDF 검색 근거만 사용해 질문에 답하세요. "
        "근거에 없는 내용은 추측하지 마세요. "
        "은행 상담원처럼 자연스럽고 간결한 한국어로 답변하세요. "
        "답변 본문에 '핵심 답변', '확인 내용', '출처', '추가 확인 필요' 같은 양식 제목을 쓰지 마세요. "
        "출처와 다운로드 링크는 시스템이 별도로 보여주므로 본문에는 파일명이나 출처 목록을 쓰지 마세요.\n\n"
        f"질문:\n{state['question']}\n\n"
        f"검색 근거:\n{build_context_text(state)}\n\n"
        "첫 문장은 질문 의도에 맞게 자연스럽게 시작하세요. "
        "조건, 서류, 수치, 예외는 필요할 때만 최대 3개 bullet로 짧게 정리하세요. "
        "같은 내용을 반복하지 말고, 굵은 글씨와 근거 번호는 쓰지 마세요. "
        "본문에 출처, 파일명, 다운로드 안내를 쓰지 마세요.\n\n"
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
    answer = answer.replace("**", "")
    answer = re.sub(r"\s*\(근거\s*\d+\)", "", answer)
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

    cleaned_lines = []
    for line in answer.splitlines():
        stripped = strip_visible_answer_label(line.strip())
        if stripped is not None:
            cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines).strip()


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
    direct_response = build_direct_response(request.question)
    if direct_response is not None:
        return direct_response

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
