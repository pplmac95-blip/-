# 領収証PDFリネームアプリ

領収証PDFを読み取り、以下の形式でファイル名を自動生成してリネームするCLIアプリです。

```text
YYYY-MM-DD_発行者_金額yen.pdf
```

例:

```text
2026-03-01_サンプル商事_12800yen.pdf
```

## できること

- PDF本文から **日付 / 金額 / 発行者** を抽出
- リネーム前に **ドライラン（プレビュー）** で確認
- 重複ファイル名がある場合は `_2`, `_3` のように連番で回避
- テキスト抽出エンジンを `pypdf` / `pdftotext` から選択可能

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> `pypdf` のインストールが難しい環境では、OSの `pdftotext` コマンドを使う方法もあります。

## 使い方

### 1) プレビュー（変更しない）

```bash
python receipt_renamer.py /path/to/receipts
```

### 2) 実際に変更する

```bash
python receipt_renamer.py /path/to/receipts --apply
```

### 3) 抽出エンジンを指定する

```bash
# pypdf を使う
python receipt_renamer.py /path/to/receipts --engine pypdf

# pdftotext を使う
python receipt_renamer.py /path/to/receipts --engine pdftotext
```

## 補足

- デフォルトの `--engine auto` は、まず `pypdf` を試し、失敗したら `pdftotext` を試します。
- スキャン画像のみのPDF（文字情報なし）では抽出できない場合があります。
- 抽出ルールは `receipt_renamer.py` 内の正規表現を調整してください。
