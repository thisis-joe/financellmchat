from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Case:
    name: str
    question: str
    history: list[dict[str, str]] = field(default_factory=list)
    answer_contains: list[str] = field(default_factory=list)
    answer_not_contains: list[str] = field(default_factory=list)
    status: str | None = None
    citation_product_contains: list[str] = field(default_factory=list)
    citation_product_not_contains: list[str] = field(default_factory=list)
    min_citation_count: int | None = None
    allow_no_citations: bool = False


CASES = [
    Case(
        name="인사말은 검색하지 않음",
        question="ㅎㅇ",
        status="DIRECT",
        answer_contains=["안녕하세요", "예금 종류"],
        allow_no_citations=True,
    ),
    Case(
        name="짧은 무의미 입력 안내",
        question="s%",
        status="DIRECT",
        answer_contains=["구체적으로", "예금 종류"],
        allow_no_citations=True,
    ),
    Case(
        name="가벼운 대화는 자연스럽게 응답",
        question="ㅋㅋ",
        status="DIRECT",
        answer_contains=["적립식예금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드"],
        allow_no_citations=True,
    ),
    Case(
        name="종료 인사는 검색하지 않음",
        question="잘가",
        status="DIRECT",
        answer_contains=["다시", "적립식예금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드"],
        allow_no_citations=True,
    ),
    Case(
        name="예금 종류 안내",
        question="예금 종류",
        status="DIRECT",
        answer_contains=["적립식예금", "거치식예금", "입출금자유예금"],
        allow_no_citations=True,
    ),
    Case(
        name="적립식예금 상품 목록",
        question="적립식예금 상품 목록",
        status="DIRECT",
        answer_contains=["BNK내맘대로 적금", "펫 적금", "청년 주택드림 청약통장"],
        allow_no_citations=True,
    ),
    Case(
        name="50대 추천은 청년상품 제외",
        question="50대인데 추천해주세요",
        status="DIRECT",
        answer_contains=["먼저 볼 만합니다", "BNK내맘대로 적금", "정기적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_not_contains=["청년", "장병", "아기", "아이사랑"],
    ),
    Case(
        name="만 50세 추천은 실버 가입연령 고려",
        question="만 50세인데 추천해주세요",
        status="DIRECT",
        answer_contains=["먼저 볼 만합니다", "정기적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_not_contains=["청년", "장병", "백세청춘"],
    ),
    Case(
        name="10대 추천은 PDF 가입대상 조건 확인",
        question="10대인데 추천해주세요",
        status="DIRECT",
        answer_contains=["먼저 볼 만합니다", "주택청약종합저축", "BNK내맘대로 적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_not_contains=["청년도약계좌", "청년 주택드림", "장병"],
    ),
    Case(
        name="만 18세 추천은 만 19세 이상 상품 제외",
        question="만 18세인데 추천해주세요",
        status="DIRECT",
        answer_contains=["먼저 볼 만합니다", "주택청약종합저축", "BNK내맘대로 적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_not_contains=["청년도약계좌", "청년 주택드림", "장병"],
    ),
    Case(
        name="어린이 조건은 자연스럽게 안내",
        question="나 5세임",
        status="DIRECT",
        answer_contains=["어린이", "보호자"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드"],
        allow_no_citations=True,
    ),
    Case(
        name="군인 조건은 장병 상품으로 연결",
        question="나군인인데",
        status="RECOMMENDATION",
        answer_contains=["국군장병", "장병내일준비적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_contains=["장병내일준비적금"],
    ),
    Case(
        name="고령 조건은 자연스럽게 안내",
        question="나 90세임",
        status="RECOMMENDATION",
        answer_contains=["건강", "백세청춘 실버적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_contains=["백세청춘 실버적금"],
    ),
    Case(
        name="펫 적금 혜택은 펫 문서만 사용",
        question="펫 적금 혜택 받으려면 뭘 해야 해?",
        answer_contains=["펫 적금", "동물등록증"],
        citation_product_contains=["펫 적금"],
        citation_product_not_contains=["아이사랑", "청년", "장병"],
    ),
    Case(
        name="상품 설명 요청은 본문 요약 제공",
        question="펫 적금 설명해줘",
        answer_contains=["펫 적금", "핵심만", "반려동물"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드", "준법감시인"],
        citation_product_contains=["펫 적금"],
        citation_product_not_contains=["아이사랑", "청년", "장병"],
    ),
    Case(
        name="자이언츠 별칭은 가을야구적금으로 연결",
        question="롯데 자이언츠",
        answer_contains=["BNK가을야구적금", "롯데자이언츠"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드"],
        citation_product_contains=["BNK가을야구적금"],
        citation_product_not_contains=["펫 적금", "아이사랑", "청년", "장병"],
    ),
    Case(
        name="자이언츠 설명은 가을야구적금 PDF 사용",
        question="자이언츠 적금 설명해줘",
        answer_contains=["BNK가을야구적금", "롯데자이언츠", "핵심만"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드", "펫 적금", "준법감시인"],
        citation_product_contains=["BNK가을야구적금"],
        citation_product_not_contains=["펫 적금", "아이사랑", "청년", "장병"],
    ),
    Case(
        name="자이언츠 오타도 가을야구적금으로 연결",
        question="자언츠 적금 설명해줘",
        answer_contains=["BNK가을야구적금", "롯데자이언츠", "핵심만"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드", "펫 적금", "준법감시인"],
        citation_product_contains=["BNK가을야구적금"],
        citation_product_not_contains=["펫 적금", "아이사랑", "청년", "장병"],
    ),
    Case(
        name="강아지 오타도 펫 적금으로 연결",
        question="강이지 적금 설명해줘",
        answer_contains=["펫 적금", "반려동물", "핵심만"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드", "자이언츠", "준법감시인"],
        citation_product_contains=["펫 적금"],
        citation_product_not_contains=["아이사랑", "청년", "장병"],
    ),
    Case(
        name="청년 주택드림 설명은 사전 요약 사용",
        question="청년 주택드림 청약통장 설명해줘",
        answer_contains=["청년 주택드림 청약통장", "주택 마련", "핵심만"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드", "자가 주택청약", "준법감시인"],
        citation_product_contains=["청년 주택드림 청약통장"],
    ),
    Case(
        name="상품명 오타도 청년도약계좌로 연결",
        question="청년도약게좌 가입대상 알려줘",
        answer_contains=["청년도약계좌", "가입"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드"],
        citation_product_contains=["청년도약계좌"],
    ),
    Case(
        name="20대 추천은 청년 조건과 일반 적금 비교",
        question="20대 조건에 맞는 적립식예금 추천해줘",
        status="DIRECT",
        answer_contains=["청년도약계좌", "BNK내맘대로 적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드"],
        citation_product_contains=["청년도약계좌", "BNK내맘대로 적금"],
    ),
    Case(
        name="청년 추천은 청년 대상 상품 우선",
        question="청년 추천",
        status="DIRECT",
        answer_contains=["청년도약계좌", "청년 주택드림", "부산청년기쁨두배"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드"],
        citation_product_contains=["청년도약계좌", "청년 주택드림", "부산청년기쁨두배"],
    ),
    Case(
        name="군인 맥락 뒤 청년 추천은 청년 상품으로 전환",
        question="청년 추천",
        history=[{"role": "user", "content": "군인이야"}],
        status="DIRECT",
        answer_contains=["청년도약계좌", "청년 주택드림", "부산청년기쁨두배"],
        answer_not_contains=["장병내일준비적금은 군 복무"],
        citation_product_contains=["청년도약계좌", "청년 주택드림", "부산청년기쁨두배"],
    ),
    Case(
        name="장병내일준비적금 서류",
        question="장병내일준비적금 만기 때 어떤 서류가 필요해?",
        answer_contains=["확인서", "제출"],
        citation_product_contains=["장병내일준비적금"],
    ),
    Case(
        name="청년도약계좌 가입대상",
        question="청년도약계좌 가입대상 알려줘",
        answer_contains=["청년도약계좌", "가입"],
        citation_product_contains=["청년도약계좌"],
    ),
    Case(
        name="주택청약종합저축 가입자격",
        question="주택청약종합저축 가입자격 알려줘",
        answer_contains=["주택청약종합저축", "가입"],
        citation_product_contains=["주택청약종합저축"],
    ),
    Case(
        name="30대 과장 추천은 직장인 상품 우선",
        question="30대 과장인데 적금 추천해줘",
        status="DIRECT",
        answer_contains=["Only One 주거래 우대적금", "BNK내맘대로 적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_contains=["Only One 주거래 우대적금"],
    ),
    Case(
        name="60대 추천은 50대가 아닌 실버 기준",
        question="나 60대 추천",
        status="DIRECT",
        answer_contains=["백세청춘 실버적금", "BNK내맘대로 적금"],
        answer_not_contains=["50대 이상이라면"],
        citation_product_contains=["백세청춘 실버적금"],
    ),
    Case(
        name="우대금리 높은 순서",
        question="우대금리 제일 높은게 뭐야",
        status="DIRECT",
        answer_contains=["우대금리", "챌린지적금 with 현대자동차", "우대 난이도"],
        answer_not_contains=["말씀은 이해했어요"],
    ),
    Case(
        name="6개월 가능 상품",
        question="6개월만 해도 되는 거 있어?",
        status="DIRECT",
        answer_contains=["6개월 조건", "정기적금", "BNK내맘대로 적금"],
        answer_not_contains=["펫 적금은 반려동물"],
    ),
    Case(
        name="2개월 단기 상품은 특수상품 남발 금지",
        question="2달만 적금하려하는데 혜택 있어?",
        status="DIRECT",
        answer_contains=["2개월 조건", "부산이라 좋다 Big적금"],
        answer_not_contains=["청년 주택드림", "장병내일준비적금"],
    ),
    Case(
        name="소액 시작 추천",
        question="자이언츠 적금은 처음에 넣어야 되는 예금이 많아서 소규모로 시작할수있는 적금 추천",
        status="DIRECT",
        answer_contains=["금액 부담", "정기적금", "BNK내맘대로 적금"],
        answer_not_contains=["BNK가을야구적금은 롯데자이언츠"],
    ),
    Case(
        name="전체 종류 나열",
        question="종류 있는대로 다 알려줘봐",
        status="DIRECT",
        answer_contains=["현재 PDF로 확인한", "BNK내맘대로 적금", "펫 적금", "BNK가을야구적금"],
        answer_not_contains=["그 외"],
        allow_no_citations=True,
    ),
    Case(
        name="5개 추천 개수 준수",
        question="한 5개만 추천해봐",
        status="DIRECT",
        answer_contains=["1. BNK내맘대로 적금", "5. 펫 적금"],
        answer_not_contains=["펫 적금은 반려동물"],
        min_citation_count=5,
    ),
    Case(
        name="10개 추천은 다운로드 근거도 10개 제공",
        question="10개추천",
        status="DIRECT",
        answer_contains=["1. BNK내맘대로 적금", "10."],
        min_citation_count=10,
    ),
    Case(
        name="20대 후속 추천은 청년 맥락 유지",
        question="추천",
        history=[{"role": "user", "content": "나 20대"}],
        status="DIRECT",
        answer_contains=["청년도약계좌", "청년"],
        answer_not_contains=["구체적으로", "말씀은 이해했어요"],
        citation_product_contains=["청년도약계좌"],
    ),
    Case(
        name="제일 좋은 상품은 기준별 안내",
        question="제일 좋은게 뭐야",
        status="DIRECT",
        answer_contains=["기준에 따라", "BNK내맘대로 적금", "조건 부담"],
        answer_not_contains=["말씀은 이해했어요"],
    ),
    Case(
        name="37세 후속 ㄱㄱ는 나이 맥락으로 추천",
        question="ㄱㄱ",
        history=[{"role": "user", "content": "나 37세"}],
        status="DIRECT",
        answer_contains=["Only One 주거래 우대적금", "BNK내맘대로 적금"],
        answer_not_contains=["구체적으로", "말씀은 이해했어요"],
    ),
    Case(
        name="청년도약 후속 보호 질문은 직전 의도 유지",
        question="아니 청년도약 그거",
        history=[{"role": "user", "content": "예금자보호돼?"}],
        status="DIRECT",
        answer_contains=["청년도약계좌", "예금자보호"],
        answer_not_contains=["추천", "먼저 볼 만합니다"],
    ),
    Case(
        name="롯데팬 후속 가입조건은 가을야구적금 기준",
        question="가입조건 알려줘",
        history=[{"role": "user", "content": "롯데팬임"}],
        status="DIRECT",
        answer_contains=["BNK가을야구적금", "가입조건", "실명의 개인"],
        citation_product_contains=["BNK가을야구적금"],
        citation_product_not_contains=["펫 적금"],
    ),
    Case(
        name="임산부는 전용상품 없음과 대안 안내",
        question="임산부인데 추천가능?",
        status="DIRECT",
        answer_contains=["임산부 전용", "BNK내맘대로 적금", "아기천사 적금"],
        answer_not_contains=["말씀은 이해했어요"],
    ),
    Case(
        name="불만 표현은 먼저 사과",
        question="왜 이런 기능도 없는거야?",
        status="DIRECT",
        answer_contains=["죄송", "확인할 수 있는 범위"],
        allow_no_citations=True,
    ),
    Case(
        name="고액 예치는 보호한도와 분산 우선",
        question="10억넣어도됨?",
        status="DIRECT",
        answer_contains=["1억원", "분산", "보호"],
        answer_not_contains=["말씀은 이해했어요"],
        allow_no_citations=True,
    ),
    Case(
        name="중도해지 손해 일반 질문",
        question="손해가 큰가?",
        status="DIRECT",
        answer_contains=["중도해지", "약정이율보다 낮은"],
        answer_not_contains=["말씀은 이해했어요"],
    ),
    Case(
        name="결혼계획은 목적형 추천",
        question="나 결혼계획있어",
        status="DIRECT",
        answer_contains=["결혼자금", "BNK내맘대로 적금", "정기적금"],
        answer_not_contains=["말씀은 이해했어요"],
    ),
    Case(
        name="여성 조건은 전용상품 없고 일반 후보 안내",
        question="나 여성임",
        status="DIRECT",
        answer_contains=["여성 전용", "BNK내맘대로 적금"],
        answer_not_contains=["말씀은 이해했어요"],
    ),
    Case(
        name="만기일 임박은 다음 선택지 안내",
        question="적금 상품 옮기려고해. 만기일 다돼가",
        status="DIRECT",
        answer_contains=["만기일", "새 상품", "BNK내맘대로 적금"],
        answer_not_contains=["준법감시인"],
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check representative RAG chatbot questions.")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Spring API base URL")
    parser.add_argument("--timeout", type=float, default=45.0)
    return parser.parse_args()


def ask(base_url: str, question: str, timeout: float, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/api/ask"
    body = json.dumps({"question": question, "history": history or []}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "finance-rag-check/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def validate(case: Case, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    answer = str(payload.get("answer", ""))
    status = str(payload.get("status", ""))
    citations = payload.get("citations") or []
    citation_products = [str(citation.get("productName") or "") for citation in citations]

    if case.status and status != case.status:
        errors.append(f"status expected={case.status}, actual={status}")

    if not case.allow_no_citations and not citations:
        errors.append("citations expected, actual=none")

    if case.min_citation_count is not None and len(citations) < case.min_citation_count:
        errors.append(f"citation count expected>={case.min_citation_count}, actual={len(citations)}")

    for text in case.answer_contains:
        if text not in answer:
            errors.append(f"answer missing `{text}`")

    for text in case.answer_not_contains:
        if text in answer:
            errors.append(f"answer should not contain `{text}`")

    for expected in case.citation_product_contains:
        if not any(expected in product for product in citation_products):
            errors.append(f"citation product missing `{expected}`")

    for forbidden in case.citation_product_not_contains:
        if any(forbidden in product for product in citation_products):
            errors.append(f"citation product should not contain `{forbidden}`: {citation_products}")

    return errors


def main() -> int:
    args = parse_args()
    failures = 0
    for index, case in enumerate(CASES, start=1):
        try:
            payload = ask(args.base_url, case.question, args.timeout, case.history)
            errors = validate(case, payload)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            errors = [f"request failed: {error}"]

        if errors:
            failures += 1
            print(f"[FAIL] {index}. {case.name} - {case.question}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"[PASS] {index}. {case.name}")

    print()
    if failures:
        print(f"대표 질문 확인 실패: {failures}/{len(CASES)}")
        return 1

    print(f"대표 질문 확인 성공: {len(CASES)}/{len(CASES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
