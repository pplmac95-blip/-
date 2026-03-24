#!/usr/bin/env python3
"""領収証PDFの内容を読み取り、ルールに沿ってファイル名を変更するCLIアプリ。"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Literal, Optional

Engine = Literal["auto", "pypdf", "pdftotext"]


@dataclass
class ReceiptInfo:
    issue_date: Optional[str]
    amount: Optional[str]
    issuer: Optional[str]


DATE_PATTERNS = [
    re.compile(r"(20\d{2})[./年-]\s*(\d{1,2})[./月-]\s*(\d{1,2})\s*日?"),
    re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})"),
]

AMOUNT_PATTERNS = [
    re.compile(r"(?:¥|￥|JPY\s?)\s?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"),
    re.compile(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\s?円"),
]

ISSUER_PATTERNS = [
    re.compile(r"(?:発行者|発行元|店舗名|会社名)\s*[:：]\s*([^\n\r]{2,40})"),
    re.compile(r"([^\n\r]{2,40})(?:株式会社|合同会社|有限会社)"),
]


class TextExtractionError(RuntimeError):
    """PDFからテキストを抽出できなかった場合の例外。"""


def extract_text_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise TextExtractionError(
            "pypdf が未インストールです。`pip install -r requirements.txt` を実行してください。"
        ) from exc

    reader = PdfReader(str(path))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks)


def extract_text_pdftotext(path: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise TextExtractionError(
            "pdftotext コマンドが見つかりません。インストールするか、--engine pypdf を使ってください。"
        )

    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown error"
        raise TextExtractionError(f"pdftotext 実行失敗: {stderr}")
    return result.stdout


def extract_text(path: Path, engine: Engine = "auto") -> str:
    errors: list[str] = []

    if engine in ("auto", "pypdf"):
        try:
            return extract_text_pypdf(path)
        except TextExtractionError as exc:
            errors.append(f"pypdf: {exc}")
            if engine == "pypdf":
                raise

    if engine in ("auto", "pdftotext"):
        try:
            return extract_text_pdftotext(path)
        except TextExtractionError as exc:
            errors.append(f"pdftotext: {exc}")
            if engine == "pdftotext":
                raise

    raise TextExtractionError(" / ".join(errors) if errors else "テキスト抽出に失敗しました。")


def normalize_date(text: str) -> Optional[str]:
    for idx, pattern in enumerate(DATE_PATTERNS):
        m = pattern.search(text)
        if not m:
            continue

        if idx == 0:
            year, month, day = m.groups()
        else:
            month, day, year = m.groups()

        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def extract_amount(text: str) -> Optional[str]:
    matches: list[int] = []
    for pattern in AMOUNT_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(1).replace(",", "")
            if raw.isdigit():
                matches.append(int(raw))

    if not matches:
        return None

    return str(max(matches))


def extract_issuer(text: str) -> Optional[str]:
    for pattern in ISSUER_PATTERNS:
        m = pattern.search(text)
        if m:
            value = m.group(1).strip()
            value = sanitize_filename_part(value)
            if value:
                return value
    return None


def sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", value)
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._-")
    return cleaned[:50]


def parse_receipt(text: str) -> ReceiptInfo:
    return ReceiptInfo(
        issue_date=normalize_date(text),
        amount=extract_amount(text),
        issuer=extract_issuer(text),
    )


def build_filename(info: ReceiptInfo) -> str:
    date = info.issue_date or "unknown-date"
    issuer = info.issuer or "unknown-issuer"
    amount = f"{info.amount}yen" if info.amount else "unknown-amount"
    return f"{date}_{issuer}_{amount}.pdf"


def ensure_unique(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 2
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def rename_receipts(directory: Path, dry_run: bool = True, engine: Engine = "auto") -> list[tuple[Path, Path]]:
    updates: list[tuple[Path, Path]] = []

    for pdf in sorted(directory.glob("*.pdf")):
        try:
            text = extract_text(pdf, engine=engine)
        except TextExtractionError as exc:
            print(f"[WARN] {pdf.name}: {exc}")
            continue

        info = parse_receipt(text)
        target_name = build_filename(info)
        target = ensure_unique(pdf.with_name(target_name))

        if pdf.resolve() == target.resolve():
            continue

        updates.append((pdf, target))

        if not dry_run:
            shutil.move(str(pdf), str(target))

    return updates


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="領収証PDFを解析してファイル名を変更します。")
    parser.add_argument("directory", type=Path, help="PDFが入っているフォルダ")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="実際にリネームを適用します（指定なしはプレビューのみ）",
    )
    parser.add_argument(
        "--engine",
        choices=["auto", "pypdf", "pdftotext"],
        default="auto",
        help="PDFテキスト抽出エンジン (default: auto)",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    directory: Path = args.directory

    if not directory.exists() or not directory.is_dir():
        print(f"エラー: フォルダが存在しません: {directory}")
        return 1

    updates = rename_receipts(directory=directory, dry_run=not args.apply, engine=args.engine)

    if not updates:
        print("対象PDFがないか、変更が必要なファイルがありません。")
        return 0

    mode = "[APPLY]" if args.apply else "[DRY-RUN]"
    for src, dst in updates:
        print(f"{mode} {src.name} -> {dst.name}")

    if not args.apply:
        print("\nプレビューのみです。実際に変更するには --apply を指定してください。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
