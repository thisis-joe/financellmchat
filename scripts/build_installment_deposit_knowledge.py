from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz

from import_busanbank_installment_pdfs import infer_product_name, normalize_text


DEFAULT_PDF_DIR = Path("data/raw/busanbank/product-disclosure/deposit/installment")
DEFAULT_PROCESSED_DIR = Path("data/processed/installment_deposit_ocr")
DEFAULT_KNOWLEDGE_PATH = Path("rag-service/product_knowledge.json")
DEFAULT_DOC_PATH = Path("docs/04-installment-deposit-comparison-insights.md")

COMMON_PROTECTION_NOTE = (
    "부산은행 예금상품 설명서 기준으로 예금자보호 대상인 상품은 원금과 소정의 이자를 합산해 "
    "1인당 1억원까지 보호됩니다. 같은 부산은행의 다른 보호상품과 합산됩니다."
)

TAG_RULES = {
    "부산은행 장병내일준비적금": ["군인", "장병", "목돈마련", "정책성"],
    "부산은행 청년도약계좌": ["청년", "정책성", "자산형성", "소득조건"],
    "청년 주택드림 청약통장": ["청년", "청약", "주거", "소득조건"],
    "부산청년기쁨두배통장": ["청년", "부산", "정책성", "자산형성"],
    "부산형 내일채움공제적금": ["근로자", "부산", "정책성", "기업연계"],
    "백세청춘 실버적금": ["실버", "중장년", "56세이상"],
    "펫 적금": ["반려동물", "강아지", "고양이"],
    "BNK가을야구적금": ["야구", "롯데자이언츠", "스포츠", "이벤트"],
    "BNK썸농구단 우승기원적금": ["농구", "BNK썸", "스포츠", "이벤트"],
    "챌린지적금 with 현대자동차": ["자동차", "현대자동차", "제휴", "이벤트"],
    "Only One 주거래 우대적금": ["직장인", "급여", "주거래", "자동이체"],
    "BNK내맘대로 적금": ["일반", "자유적립", "소액", "기간선택"],
    "정기적금": ["일반", "정액적립", "소액", "기간선택"],
    "가계우대정기적금": ["일반", "가계", "정액적립"],
    "저탄소 실천 적금": ["친환경", "저탄소", "생활실천"],
    "아기천사 적금": ["아동", "영유아", "보호자"],
    "아이사랑 적금": ["아동", "자녀", "보호자"],
    "꿈이룸 적금": ["아동", "청소년", "목표저축"],
    "너만솔로 적금": ["이벤트", "생활"],
    "BNK지역사랑자유적금": ["지역", "자유적립"],
    "BNK희망가꾸기적금": ["취약계층", "지원", "자유적립"],
    "상호부금": ["일반", "부금"],
}

ALIASES = {
    "BNK가을야구적금": ["자이언츠", "롯데", "롯데자이언츠", "야구"],
    "펫 적금": ["펫", "강아지", "고양이", "반려동물"],
    "부산은행 장병내일준비적금": ["군인", "장병", "입대", "전역"],
    "백세청춘 실버적금": ["실버", "60대", "노인", "은퇴"],
    "Only One 주거래 우대적금": ["주거래", "급여이체", "직장인", "과장"],
    "BNK내맘대로 적금": ["내맘대로", "소액", "무난한", "기본"],
    "정기적금": ["기본 적금", "정액적금", "소액"],
    "부산은행 청년도약계좌": ["청년도약", "청년"],
    "청년 주택드림 청약통장": ["주택드림", "청년청약", "청약"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build installment deposit OCR text, product knowledge, and insight doc.")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--knowledge-path", type=Path, default=DEFAULT_KNOWLEDGE_PATH)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser.parse_args()


def compact(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def find_section_start(text: str, patterns: list[str]) -> int | None:
    starts: list[int] = []
    for pattern in patterns:
        offset = 0
        while True:
            found = text.find(pattern, offset)
            if found < 0:
                break
            starts.append(found)
            offset = found + len(pattern)
    if not starts:
        return None

    labeled = [start for start in starts if "▣" in text[start:start + 140]]
    return min(labeled or starts)


def section_between(text: str, start_patterns: list[str], end_patterns: list[str], window: int = 1600) -> str | None:
    start = find_section_start(text, start_patterns)
    if start is None:
        return None
    end = min(start + window, len(text))
    for pattern in end_patterns:
        found = text.find(pattern, start + 1)
        if found >= 0:
            end = min(end, found)
    return compact(text[start:end])


def extract_pdf_text(pdf_path: Path) -> dict[str, Any]:
    document = fitz.open(pdf_path)
    page_texts = []
    for page_index, page in enumerate(document, start=1):
        text = normalize_text(page.get_text("text"))
        page_texts.append({"page": page_index, "text": text, "char_count": len(text)})
    merged_text = "\n\n".join(page["text"] for page in page_texts)
    return {
        "file_name": pdf_path.name,
        "page_count": len(document),
        "char_count": len(merged_text),
        "text": merged_text,
        "pages": page_texts,
    }


def money_to_won(value: str, unit: str) -> int | None:
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return None
    multipliers = {
        "원": 1,
        "천원": 1_000,
        "만원": 10_000,
        "백만원": 1_000_000,
        "천만원": 10_000_000,
        "억원": 100_000_000,
    }
    return int(number * multipliers.get(unit, 1))


def extract_money_values(text: str) -> list[int]:
    values: list[int] = []
    for number, unit in re.findall(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(억원|천만원|백만원|만원|천원|원)", text):
        won = money_to_won(number, unit)
        if won is not None:
            values.append(won)
    return values


def extract_period_months(text: str) -> dict[str, int | None]:
    values: list[int] = []
    for value, unit in re.findall(r"(\d{1,3})\s*(개월|년)", text):
        months = int(value) * (12 if unit == "년" else 1)
        values.append(months)
    if not values:
        return {"min": None, "max": None}
    return {"min": min(values), "max": max(values)}


def extract_age_bounds(text: str) -> dict[str, int | None]:
    min_ages: list[int] = []
    max_ages: list[int] = []
    for start, end in re.findall(r"(?:만\s*)?(\d{1,3})\s*세\s*[~∼-]\s*(?:만\s*)?(\d{1,3})\s*세", text):
        min_ages.append(int(start))
        max_ages.append(int(end))
    for age in re.findall(r"(?:만\s*)?(\d{1,3})\s*세\s*(?:이상|부터)", text):
        min_ages.append(int(age))
    for age in re.findall(r"(?:만\s*)?(\d{1,3})\s*세\s*(?:이하|까지|이내|미만)", text):
        max_ages.append(int(age))
    return {
        "min": max(min_ages) if min_ages else None,
        "max": min(max_ages) if max_ages else None,
    }


def extract_rates(text: str) -> list[float]:
    rates: list[float] = []
    for rate in re.findall(r"연\s*(\d+(?:\.\d+)?)\s*%", text):
        rates.append(float(rate))
    return rates


def extract_max_preferential_rate(text: str) -> float | None:
    candidates = [float(value) for value in re.findall(r"최대\s*(\d+(?:\.\d+)?)\s*%p", text)]
    if candidates:
        return max(candidates)
    candidates = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*%p", text)]
    return max(candidates) if candidates else None


def classify_difficulty(preferential_section: str | None) -> str:
    if not preferential_section:
        return "낮음"
    key = preferential_section.replace(" ", "")
    count = sum(key.count(marker) for marker in ["급여", "카드", "자동이체", "마케팅", "오픈뱅킹", "주택청약", "실적", "동의"])
    if count >= 5:
        return "높음"
    if count >= 2:
        return "보통"
    return "낮음"


def build_product_record(extracted: dict[str, Any]) -> dict[str, Any]:
    text = extracted["text"]
    product_name = infer_product_name(extracted["file_name"], text)
    summary = section_between(text, ["상품 개요 및 특징", "상품 개요", "상품명"], ["거래 조건", "가입대상"], 900)
    eligibility = section_between(text, ["가입대상"], ["상품유형", "가입금액"], 1300)
    amount = section_between(text, ["가입금액"], ["계약기간", "가입기간", "거래방법"], 800)
    period = section_between(text, ["계약기간", "가입기간"], ["거래방법", "이자지급시기"], 700)
    channels = section_between(text, ["거래방법"], ["이자지급시기"], 700)
    interest_payment = section_between(text, ["이자지급시기"], ["원금 및 이자", "기본이율"], 550)
    base_rate = section_between(text, ["기본이율"], ["우대이율", "만기이자", "중도해지"], 1800)
    preferential = section_between(text, ["우대이율"], ["만기이자", "중도해지", "양도", "계약해지"], 2400)
    early_termination = section_between(text, ["중도해지이율", "중도해지 이율"], ["만기후 이율", "만기 후 이율", "연계·제휴"], 1900)
    after_maturity = section_between(text, ["만기후 이율", "만기 후 이율"], ["연계·제휴", "만기앞당김"], 900)
    collateral = section_between(text, ["예금담보대출"], ["재예치", "분할인출", "세제혜택"], 700)
    redeposit = section_between(text, ["재예치"], ["분할인출", "세제혜택"], 500)
    partial = section_between(text, ["분할인출", "부분인출", "일부인출"], ["세제혜택", "예금자보호"], 600)
    tax = section_between(text, ["세제혜택"], ["예금자보호"], 700)
    protection = section_between(text, ["예금자보호여부", "예금자보호"], ["유의 사항", "3   유의"], 900)

    amount_values = extract_money_values(amount or "")
    period_bounds = extract_period_months(period or "")
    base_rates = extract_rates(base_rate or "")
    age_bounds = extract_age_bounds(eligibility or "")

    return {
        "productName": product_name,
        "sourceFile": extracted["file_name"],
        "pageCount": extracted["page_count"],
        "charCount": extracted["char_count"],
        "aliases": ALIASES.get(product_name, []),
        "tags": TAG_RULES.get(product_name, []),
        "summaryExtract": summary,
        "eligibility": eligibility,
        "amount": amount,
        "period": period,
        "channels": channels,
        "interestPayment": interest_payment,
        "baseRate": base_rate,
        "preferentialRate": preferential,
        "earlyTermination": early_termination,
        "afterMaturity": after_maturity,
        "collateralLoan": collateral,
        "redeposit": redeposit,
        "partialWithdrawal": partial,
        "taxBenefit": tax,
        "depositorProtection": protection or COMMON_PROTECTION_NOTE,
        "derived": {
            "ageMin": age_bounds["min"],
            "ageMax": age_bounds["max"],
            "periodMinMonths": period_bounds["min"],
            "periodMaxMonths": period_bounds["max"],
            "minAmountWon": min(amount_values) if amount_values else None,
            "maxAmountWon": max(amount_values) if amount_values else None,
            "baseRates": base_rates,
            "maxBaseRate": max(base_rates) if base_rates else None,
            "maxPreferentialRatePoint": extract_max_preferential_rate(preferential or ""),
            "preferenceDifficulty": classify_difficulty(preferential),
            "hasProtection": bool(protection and "해당" in protection.replace(" ", "")),
            "allowsMobileNew": bool(channels and "모바일" in channels and "신규" in channels),
            "allowsBranchNew": bool(channels and "영업점" in channels and "신규" in channels),
            "allowsPartialWithdrawal": bool(partial and "가능" in partial and "불 가" not in partial and "불가" not in partial),
            "allowsRedeposit": bool(redeposit and "가능" in redeposit and "불 가" not in redeposit and "불가" not in redeposit),
            "allowsCollateralLoan": bool(collateral and "가능" in collateral),
        },
    }


def merge_product_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        product_name = record["productName"]
        current = merged.get(product_name)
        if current is None or record["charCount"] > current["charCount"]:
            next_record = record
            related = []
            if current is not None:
                related.extend(current.get("relatedSourceFiles", [current["sourceFile"]]))
            related.append(record["sourceFile"])
            next_record["relatedSourceFiles"] = sorted(set(related))
            merged[product_name] = next_record
        else:
            current.setdefault("relatedSourceFiles", [current["sourceFile"]])
            current["relatedSourceFiles"] = sorted(set(current["relatedSourceFiles"] + [record["sourceFile"]]))

    return sorted(merged.values(), key=lambda record: record["productName"])


def write_ocr_outputs(processed_dir: Path, extracted_items: list[dict[str, Any]]) -> None:
    text_dir = processed_dir / "texts"
    page_dir = processed_dir / "pages"
    text_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)
    for item in extracted_items:
        stem = Path(item["file_name"]).stem
        (text_dir / f"{stem}.txt").write_text(item["text"], encoding="utf-8")
        (page_dir / f"{stem}.json").write_text(json.dumps(item["pages"], ensure_ascii=False, indent=2), encoding="utf-8")


def product_line(record: dict[str, Any]) -> str:
    d = record["derived"]
    return (
        f"| {record['productName']} | {', '.join(record['tags'][:3]) or '-'} | "
        f"{short(record.get('eligibility'))} | {short(record.get('period'))} | "
        f"{short(record.get('amount'))} | {d.get('maxBaseRate') or '-'} | "
        f"{d.get('maxPreferentialRatePoint') or '-'} | {d.get('preferenceDifficulty')} |"
    )


def short(value: str | None, limit: int = 70) -> str:
    if not value:
        return "-"
    value = compact(value).replace("|", "/")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def top_products(records: list[dict[str, Any]], key: str, reverse: bool = True, limit: int = 5) -> list[dict[str, Any]]:
    candidates = [record for record in records if record["derived"].get(key) is not None]
    return sorted(candidates, key=lambda record: record["derived"][key], reverse=reverse)[:limit]


def build_insight_doc(records: list[dict[str, Any]], source_pdf_count: int) -> str:
    product_records = [record for record in records if "약관" not in record["productName"] and "ISA" not in record["productName"]]
    short_term = [
        record for record in product_records
        if (record["derived"].get("periodMinMonths") is not None and record["derived"]["periodMinMonths"] <= 6)
    ]
    low_amount = [
        record for record in product_records
        if (record["derived"].get("minAmountWon") is not None and record["derived"]["minAmountWon"] <= 1_000)
    ]

    lines = [
        "# 04. 적립식 예금 비교분석 및 인사이트",
        "",
        "이 문서는 부산은행 `예금상품 > 적립식예금` PDF 28개를 다시 텍스트 추출해, 챗봇이 추천·비교 질문에 답할 때 먼저 참고할 기준을 정리한 문서입니다.",
        "PDF 원문은 여전히 최종 근거이고, 이 문서는 사용자가 실제로 묻는 질문에 빠르게 답하기 위한 비교 지도입니다.",
        "",
        "## 1. 이번 재추출 결과",
        "",
        f"- 원본 PDF: {source_pdf_count}개",
        f"- 병합 후 지식 레코드: {len(records)}개",
        f"- 챗봇 상품성 비교 대상: {len(product_records)}개",
        "- 추출 방식: PyMuPDF 기반 페이지별 텍스트 추출. 현재 PDF들은 텍스트 레이어가 충분히 잡혀 OCR 대체 추출이 가능했습니다.",
        "- 산출물: `data/processed/installment_deposit_ocr/texts`, `data/processed/installment_deposit_ocr/pages`, `rag-service/product_knowledge.json`",
        "",
        "## 2. 상품별 비교표",
        "",
        "| 상품 | 성격 태그 | 가입대상 | 기간 | 금액 | 최고 기본금리(추출) | 최대 우대폭(추출) | 우대 난이도 |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    lines.extend(product_line(record) for record in product_records)

    lines.extend([
        "",
        "## 3. 질문 유형별 답변 기준",
        "",
        "### 수익성",
        "",
        "- 기본금리·최고금리 질문은 `product_knowledge.json`의 `baseRate`, `preferentialRate`, `derived.maxBaseRate`, `derived.maxPreferentialRatePoint`를 먼저 봅니다.",
        "- 최고금리는 대부분 우대조건 충족이 필요합니다. 따라서 챗봇은 `누구나 받는 금리`와 `조건 충족 시 금리`를 분리해서 말해야 합니다.",
        "- 세후 이자는 일반 과세 기준으로 이자소득세와 지방소득세 합계 15.4%를 차감해 계산합니다.",
        "- 적금은 매월 납입금마다 예치 기간이 달라 단순히 `납입총액 x 연금리`로 계산하면 과대평가됩니다.",
        "",
        "### 안전성",
        "",
        "- 부산은행은 은행권 금융기관입니다.",
        "- 설명서 기준 예금자보호 대상 상품은 원금과 소정의 이자를 합산해 1인당 1억원까지 보호됩니다.",
        "- 같은 부산은행의 다른 보호상품과 합산되므로, 이미 부산은행 예금이 있다면 총액 기준으로 봐야 합니다.",
        "- 1억원을 넘겨 보관하려면 다른 금융기관으로 분산하는 안내가 필요합니다.",
        "",
        "### 가입 조건",
        "",
        "- 가입대상은 추천의 1순위 필터입니다. 청년·장병·아동·실버·정책성 상품은 조건이 맞지 않으면 추천에서 제외해야 합니다.",
        "- 30대 직장인/과장처럼 직업과 나이가 같이 들어오면 `Only One 주거래 우대적금`, `BNK내맘대로 적금`, `정기적금`을 우선 비교합니다.",
        "- 60대 이상이면 청년 전용 상품을 제외하고 `백세청춘 실버적금`, `BNK내맘대로 적금`, `정기적금`을 먼저 봅니다.",
        "",
        "### 우대금리",
        "",
        "- 우대금리 질문은 `최대 우대폭`만 답하면 부족합니다. 조건 개수와 현실성까지 같이 말해야 합니다.",
        "- 카드 실적·급여이체·자동이체·마케팅 동의처럼 사용자의 행동 비용이 필요한 조건은 `우대 난이도`를 높게 봅니다.",
        "- 우대금리 때문에 불필요한 소비가 생길 수 있으면, 기본금리가 낮더라도 조건 쉬운 상품을 함께 제시합니다.",
        "",
        "### 기간과 만기",
        "",
        "- 6개월 질문은 `periodMinMonths <= 6 <= periodMaxMonths`인 상품만 후보로 봅니다.",
        "- 2개월 질문은 현재 적립식예금 범위에서는 적합 상품이 매우 제한적이거나 없을 수 있으므로, `현재 자료 기준 명확히 추천하기 어렵다`고 말해야 합니다.",
        "- 만기 후 방치하면 일반적으로 낮은 만기후이율이 적용되므로 만기 알림과 재가입 여부 확인을 안내합니다.",
        "",
        "### 중도해지",
        "",
        "- 중도해지 질문은 금리보다 손실 가능성을 먼저 설명합니다.",
        "- 대부분 중도해지이율은 경과 기간에 따라 약정이율보다 낮아집니다.",
        "- 긴급자금 가능성이 크면 높은 금리 상품보다 기간이 짧거나 부담금액이 낮은 상품이 더 나을 수 있습니다.",
        "",
        "### 실제 수령액",
        "",
        "- 사용자가 금액과 기간을 주면 `세전 이자`, `세후 이자`, `예상 만기 수령액`을 계산해야 합니다.",
        "- 적금 계산은 납입 방식에 따라 달라집니다. 정기적립식은 매월 같은 금액을 넣는 가정, 자유적립식은 사용자가 실제 납입 일정을 알려줘야 더 정확합니다.",
        "- 일반 안내는 `예상치`로 표현하고, 실제 적용금리는 가입 시점 고시와 개인 조건에 따라 달라진다고 붙입니다.",
        "",
        "## 4. 현재 자료 기준 빠른 결론",
        "",
        "### 소액으로 시작하기 쉬운 후보",
    ])
    for record in low_amount[:8]:
        lines.append(f"- {record['productName']}: {short(record.get('amount'), 100)}")

    lines.extend(["", "### 6개월 전후 단기 후보"])
    for record in short_term[:8]:
        lines.append(f"- {record['productName']}: {short(record.get('period'), 100)}")

    lines.extend(["", "### 최고 기본금리 추출 상위"])
    for record in top_products(product_records, "maxBaseRate", limit=7):
        lines.append(f"- {record['productName']}: 최고 기본금리 추출값 연 {record['derived']['maxBaseRate']}%")

    lines.extend(["", "### 최대 우대폭 추출 상위"])
    for record in top_products(product_records, "maxPreferentialRatePoint", limit=7):
        lines.append(f"- {record['productName']}: 최대 우대폭 추출값 {record['derived']['maxPreferentialRatePoint']}%p, 난이도 {record['derived']['preferenceDifficulty']}")

    lines.extend([
        "",
        "## 5. 목적별 추천 초안",
        "",
        "- 30대 직장인/과장: `Only One 주거래 우대적금`, `BNK내맘대로 적금`, `정기적금`",
        "- 60대 이상: `백세청춘 실버적금`, `BNK내맘대로 적금`, `정기적금`",
        "- 군 복무 중: `부산은행 장병내일준비적금`",
        "- 반려동물: `펫 적금`",
        "- 롯데자이언츠/야구: `BNK가을야구적금`",
        "- 청약/주거: `주택청약종합저축`, `청년 주택드림 청약통장`",
        "- 청년 정책성 자산형성: `부산은행 청년도약계좌`, `부산청년기쁨두배통장`",
        "- 조건을 많이 신경 쓰기 싫은 사용자: `정기적금`, `BNK내맘대로 적금`",
        "- 소액·짧은 기간 우선: `정기적금`, `BNK내맘대로 적금`을 먼저 확인",
        "",
        "## 6. 챗봇 답변 원칙",
        "",
        "1. 상품 선택은 LLM 감이 아니라 구조화 데이터와 규칙으로 한다.",
        "2. 금리·기간·금액·나이는 먼저 필터링하고, 그다음 추천한다.",
        "3. `제일 좋은 상품`은 단일 정답이 아니라 기준별 최고를 제시한다.",
        "4. `혜택이 많은 상품`은 최대 우대폭과 우대 난이도를 함께 말한다.",
        "5. 출처와 다운로드는 유지하되, 본문에는 원문 조각을 길게 나열하지 않는다.",
        "",
        "## 7. 한계와 다음 작업",
        "",
        "- 현재 문서는 부산은행 적립식예금 PDF만 기준으로 합니다. 거치식예금, 입출금자유예금, 타행 상품 비교는 아직 범위 밖입니다.",
        "- 금리 정보는 PDF 작성일 기준이므로 실제 가입 시점의 고시금리와 다를 수 있습니다.",
        "- 표 안의 일부 문구는 PDF 텍스트 레이어 추출 결과에 의존합니다. 이미지-only PDF가 추가되면 Tesseract 또는 별도 OCR 엔진을 붙여야 합니다.",
        "- 현재 `product_knowledge.json`은 챗봇의 비교·추천 로직에 연결되어 있습니다.",
        "- 다음 단계에서는 세후 이자 계산, 우대조건 비용 판단, 복합 자격 조건 추출 정확도를 높입니다.",
        "",
        "## 용어 메모",
        "",
        "- 기본금리: 우대조건 없이 상품 자체에 적용되는 기준 금리입니다.",
        "- 우대금리: 급여이체, 카드 실적, 자동이체 등 조건을 만족할 때 추가되는 금리입니다.",
        "- 세전/세후: 세전은 세금 차감 전 이자, 세후는 이자소득세와 지방소득세를 뺀 뒤의 금액입니다.",
        "- 중도해지이율: 만기 전에 해지할 때 적용되는 낮은 이율입니다.",
        "- 만기후이율: 만기 후 돈을 찾아가지 않고 방치했을 때 적용되는 이율입니다.",
        "- 예금자보호: 금융기관이 지급불능 상태가 되었을 때 법정 한도 안에서 예금을 보호하는 제도입니다.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    pdf_paths = sorted(args.pdf_dir.glob("*.pdf"))
    extracted_items = [extract_pdf_text(pdf_path) for pdf_path in pdf_paths]
    records = merge_product_records([build_product_record(item) for item in extracted_items])

    write_ocr_outputs(args.processed_dir, extracted_items)
    args.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    args.knowledge_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    args.doc_path.parent.mkdir(parents=True, exist_ok=True)
    args.doc_path.write_text(build_insight_doc(records, len(pdf_paths)), encoding="utf-8")

    print(f"pdf_files={len(pdf_paths)}")
    print(f"knowledge={args.knowledge_path}")
    print(f"doc={args.doc_path}")
    print(f"processed={args.processed_dir}")


if __name__ == "__main__":
    main()
