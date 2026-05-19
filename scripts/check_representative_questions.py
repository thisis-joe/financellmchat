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
    answer_contains: list[str] = field(default_factory=list)
    answer_not_contains: list[str] = field(default_factory=list)
    status: str | None = None
    citation_product_contains: list[str] = field(default_factory=list)
    citation_product_not_contains: list[str] = field(default_factory=list)
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
        status="RECOMMENDATION",
        answer_contains=["먼저 볼 만한 상품", "BNK내맘대로 적금", "조건이 맞지 않아"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_not_contains=["청년", "장병", "아기", "아이사랑"],
    ),
    Case(
        name="만 50세 추천은 실버 가입연령 고려",
        question="만 50세인데 추천해주세요",
        status="RECOMMENDATION",
        answer_contains=["먼저 볼 만한 상품", "정기적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_not_contains=["청년", "장병", "백세청춘"],
    ),
    Case(
        name="10대 추천은 PDF 가입대상 조건 확인",
        question="10대인데 추천해주세요",
        status="RECOMMENDATION",
        answer_contains=["먼저 볼 만한 상품", "주택청약종합저축", "조건이 맞지 않아"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:"],
        citation_product_not_contains=["청년도약계좌", "청년 주택드림", "장병"],
    ),
    Case(
        name="만 18세 추천은 만 19세 이상 상품 제외",
        question="만 18세인데 추천해주세요",
        status="RECOMMENDATION",
        answer_contains=["먼저 볼 만한 상품", "주택청약종합저축", "만 19세 이상"],
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
        status="RECOMMENDATION",
        answer_contains=["청년층", "청년도약계좌", "BNK내맘대로 적금"],
        answer_not_contains=["핵심 답변", "확인 내용", "출처:", "다운로드"],
        citation_product_contains=["청년도약계좌", "BNK내맘대로 적금"],
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
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check representative RAG chatbot questions.")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Spring API base URL")
    parser.add_argument("--timeout", type=float, default=45.0)
    return parser.parse_args()


def ask(base_url: str, question: str, timeout: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/api/ask"
    body = json.dumps({"question": question}, ensure_ascii=False).encode("utf-8")
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
            payload = ask(args.base_url, case.question, args.timeout)
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
