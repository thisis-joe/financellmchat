from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import fitz
import pymysql


PRODUCT_NAMES = [
    "챌린지적금 with 현대자동차",
    "BNK썸농구단 우승기원적금",
    "주택청약종합저축",
    "청년 주택드림 청약통장",
    "Only One 주거래 우대적금",
    "너만솔로 적금",
    "아기천사 적금",
    "아이사랑 적금",
    "부산이라 좋다 Big적금",
    "꿈이룸 적금",
    "부산은행 장병내일준비적금",
    "부산은행 청년도약계좌",
    "부산형 내일채움공제적금",
    "BNK내맘대로 적금",
    "저탄소 실천 적금",
    "펫 적금",
    "일임형 개인종합자산관리계좌(ISA)",
    "BNK지역사랑자유적금",
    "BNK희망가꾸기적금",
    "백세청춘 실버적금",
    "상호부금",
    "정기적금",
    "가계우대정기적금",
    "BNK가을야구적금",
    "부산청년기쁨두배통장",
]


ALIASES = {
    "챌린지적금with현대자동차": "챌린지적금 with 현대자동차",
    "챌린지적금wtih현대자동차": "챌린지적금 with 현대자동차",
    "BNK썸농구단우승기원적금": "BNK썸농구단 우승기원적금",
    "OnlyOne주거래우대적금": "Only One 주거래 우대적금",
    "너만솔로적금": "너만솔로 적금",
    "아기천사적금": "아기천사 적금",
    "아이사랑적금": "아이사랑 적금",
    "부산이라좋다Big적금": "부산이라 좋다 Big적금",
    "꿈이룸적금": "꿈이룸 적금",
    "장병내일준비적금": "부산은행 장병내일준비적금",
    "청년도약계좌": "부산은행 청년도약계좌",
    "부산형내일채움공제적금": "부산형 내일채움공제적금",
    "BNK내맘대로적금": "BNK내맘대로 적금",
    "저탄소실천적금": "저탄소 실천 적금",
    "펫적금": "펫 적금",
    "ISA": "일임형 개인종합자산관리계좌(ISA)",
    "BNK지역사랑자유적금": "BNK지역사랑자유적금",
    "BNK희망가꾸기적금": "BNK희망가꾸기적금",
    "백세청춘실버적금": "백세청춘 실버적금",
    "상호부금": "상호부금",
    "정기적금": "정기적금",
    "가계우대정기적금": "가계우대정기적금",
    "BNK가을야구적금": "BNK가을야구적금",
    "가계우대정기적금": "가계우대정기적금",
    "청년주택드림청약통장": "청년 주택드림 청약통장",
    "부산청년기쁨두배통장": "부산청년기쁨두배통장",
    "주택청약종합저축": "주택청약종합저축",
}


@dataclass
class Chunk:
    title: str
    product_name: str
    file_name: str
    page_number: int
    chunk_index: int
    content: str
    char_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Busan Bank installment deposit PDFs into MySQL.")
    parser.add_argument("--pdf-dir", required=True, type=Path)
    parser.add_argument("--processed-dir", required=True, type=Path)
    parser.add_argument("--replace", action="store_true", help="Delete previous imported installment PDF chunks first")
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-name", default="finance_rag")
    parser.add_argument("--db-user", default="finance")
    parser.add_argument("--db-password", default="finance")
    return parser.parse_args()


def normalize_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value)


def infer_product_name(file_name: str, text_sample: str) -> str:
    file_key = normalize_key(file_name)
    text_key = normalize_key(text_sample[:1000])

    for alias, product_name in sorted(ALIASES.items(), key=lambda item: len(normalize_key(item[0])), reverse=True):
        if normalize_key(alias) in file_key:
            return product_name
    for product_name in sorted(PRODUCT_NAMES, key=lambda item: len(normalize_key(item)), reverse=True):
        if normalize_key(product_name) in file_key:
            return product_name

    target = file_key + text_key
    for alias, product_name in sorted(ALIASES.items(), key=lambda item: len(normalize_key(item[0])), reverse=True):
        if normalize_key(alias) in target:
            return product_name
    for product_name in sorted(PRODUCT_NAMES, key=lambda item: len(normalize_key(item)), reverse=True):
        if normalize_key(product_name) in target:
            return product_name
    return Path(file_name).stem


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text(text: str, max_chars: int = 1400, overlap: int = 180) -> Iterable[str]:
    if len(text) <= max_chars:
        yield text
        return

    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end == len(text):
            break
        start = max(0, end - overlap)


def extract_chunks(pdf_path: Path) -> list[Chunk]:
    document = fitz.open(pdf_path)
    page_texts = [normalize_text(page.get_text("text")) for page in document]
    product_name = infer_product_name(pdf_path.name, "\n".join(page_texts[:2]))
    chunks: list[Chunk] = []

    for page_index, text in enumerate(page_texts, start=1):
        if not text:
            continue
        for chunk_index, chunk_text in enumerate(split_text(text), start=1):
            content = (
                f"[출처파일] {pdf_path.name}\n"
                f"[상품명] {product_name}\n"
                f"[페이지] {page_index}\n\n"
                f"{chunk_text}"
            )
            chunks.append(
                Chunk(
                    title=f"{product_name} 상품공시 PDF p{page_index}-{chunk_index}",
                    product_name=product_name,
                    file_name=pdf_path.name,
                    page_number=page_index,
                    chunk_index=chunk_index,
                    content=content,
                    char_count=len(chunk_text),
                )
            )

    return chunks


def connection(args: argparse.Namespace):
    return pymysql.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def import_chunks(args: argparse.Namespace, chunks: list[Chunk]) -> None:
    insert_sql = """
        insert into financial_documents
            (title, category, institution, product_name, product_type, source, source_url, published_date, content, created_at)
        values
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
    """
    with connection(args) as conn:
        with conn.cursor() as cursor:
            if args.replace:
                cursor.execute(
                    """
                    delete from financial_documents
                    where institution = 'BNK부산은행'
                      and category = '예금상품>적립식예금'
                      and source = '부산은행 상품공시 PDF'
                    """
                )
            for chunk in chunks:
                cursor.execute(
                    insert_sql,
                    (
                        chunk.title,
                        "예금상품>적립식예금",
                        "BNK부산은행",
                        chunk.product_name,
                        "적립식예금",
                        "부산은행 상품공시 PDF",
                        "https://www.busanbank.co.kr/ib20/mnu/BHPFPMD010001001",
                        date.today(),
                        chunk.content,
                    ),
                )
        conn.commit()


def write_outputs(processed_dir: Path, chunks: list[Chunk]) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = processed_dir / "installment_deposit_chunks.jsonl"
    report_path = processed_dir / "import_report.csv"

    with jsonl_path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk.__dict__, ensure_ascii=False) + "\n")

    with report_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["file_name", "product_name", "page_number", "chunk_index", "char_count"],
        )
        writer.writeheader()
        for chunk in chunks:
            writer.writerow(
                {
                    "file_name": chunk.file_name,
                    "product_name": chunk.product_name,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "char_count": chunk.char_count,
                }
            )

    print(f"chunks_jsonl={jsonl_path}")
    print(f"report_csv={report_path}")


def main() -> None:
    args = parse_args()
    pdf_paths = sorted(args.pdf_dir.glob("*.pdf"))
    chunks: list[Chunk] = []
    for pdf_path in pdf_paths:
        chunks.extend(extract_chunks(pdf_path))

    write_outputs(args.processed_dir, chunks)
    import_chunks(args, chunks)

    products = sorted({chunk.product_name for chunk in chunks})
    print(f"pdf_files={len(pdf_paths)}")
    print(f"chunks={len(chunks)}")
    print(f"products={len(products)}")


if __name__ == "__main__":
    main()
