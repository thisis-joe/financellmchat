from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
RAG_SERVICE_DIR = ROOT_DIR / "rag-service"
sys.path.insert(0, str(RAG_SERVICE_DIR))

from app import (  # noqa: E402
    PRODUCT_ALIAS_HINTS,
    PURPOSE_PRODUCT_HINTS,
    hinted_products_from_question,
    normalize_key,
)


MUTATION_CHARS = "가나다라마바사아자차카타파하0123456789"
GENERIC_OR_RISKY_ALIASES = {
    "부금",
    "정기적금",
    "기본적금",
    "일반적금",
    "부산",
    "청년",
    "아이",
    "롯데",
    "사직",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate many typo variants and check product alias matching.")
    parser.add_argument("--limit", type=int, default=10000, help="Number of positive typo cases to verify.")
    return parser.parse_args()


def aliases_for_check() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []

    for alias, product in PRODUCT_ALIAS_HINTS.items():
        key = normalize_key(alias)
        if len(key) < 5 or key in GENERIC_OR_RISKY_ALIASES:
            continue
        pairs.append((alias, product))

    for purpose, products in PURPOSE_PRODUCT_HINTS.items():
        key = normalize_key(purpose)
        if len(key) < 4 or key in GENERIC_OR_RISKY_ALIASES or len(products) != 1:
            continue
        pairs.append((purpose, products[0]))

    seen = set()
    unique_pairs = []
    for alias, product in pairs:
        key = (normalize_key(alias), product)
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append((alias, product))
    return unique_pairs


def typo_variants(alias: str) -> Iterable[str]:
    key = normalize_key(alias)
    if len(key) < 5:
        return

    yield key

    for index in range(1, len(key)):
        yield key[:index] + key[index + 1:]

    for index in range(1, len(key) - 1):
        yield key[:index] + key[index + 1] + key[index] + key[index + 2:]

    for index in range(1, len(key)):
        yield key[:index] + key[index] + key[index:]

    for index in range(1, len(key)):
        for char in MUTATION_CHARS[:4]:
            yield key[:index] + char + key[index:]


def question_from_variant(variant: str, index: int) -> str:
    suffixes = (
        " 설명해줘",
        " 가입대상 알려줘",
        " 혜택 알려줘",
        " 추천해줘",
        " 금리 알려줘",
    )
    return variant + suffixes[index % len(suffixes)]


def main() -> int:
    args = parse_args()
    aliases = aliases_for_check()
    if not aliases:
        print("검증할 별칭이 없습니다.")
        return 1

    checked = 0
    failures: list[str] = []
    seen_questions = set()

    while checked < args.limit:
        progressed = False
        for alias, expected_product in aliases:
            for variant in typo_variants(alias):
                question = question_from_variant(variant, checked)
                if question in seen_questions:
                    continue
                seen_questions.add(question)
                matched_products = hinted_products_from_question(question)
                if expected_product not in matched_products:
                    failures.append(
                        f"question={question!r} alias={alias!r} expected={expected_product!r} matched={matched_products!r}"
                    )
                    if len(failures) >= 20:
                        break
                checked += 1
                progressed = True
                if checked >= args.limit or len(failures) >= 20:
                    break
            if checked >= args.limit or len(failures) >= 20:
                break
        if failures or not progressed:
            break

    negative_questions = [
        "안녕하세요",
        "오늘 날씨 어때",
        "점심 뭐먹지",
        "그냥 찾아",
        "아무거나 설명해줘",
        "대출 카드 외환 알려줘",
    ]
    negative_failures = [
        question for question in negative_questions
        if hinted_products_from_question(question)
    ]

    if failures or negative_failures or checked < args.limit:
        print(f"오타 별칭 검증 실패: checked={checked}/{args.limit}")
        for failure in failures:
            print("- " + failure)
        for question in negative_failures:
            print(f"- negative question matched unexpectedly: {question!r} -> {hinted_products_from_question(question)!r}")
        return 1

    print(f"오타 별칭 검증 성공: {checked}/{args.limit}")
    print(f"검증 별칭 수: {len(aliases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
