import argparse
import calendar
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

BASE_PAGE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36",
    "Referer": "https://www.histdata.com/",
}


def month_iter(start_year: int, start_month: int, end_year: int, end_month: int):
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        yield y, m
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1


def extract_token(html: str) -> str | None:
    patterns = [
        r'name=["\']tk["\']\s+value=["\']([^"\']+)["\']',
        r'id=["\']tk["\']\s+value=["\']([^"\']+)["\']',
        r'value=["\']([^"\']+)["\']\s+name=["\']tk["\']',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def find_download_link(html: str) -> str | None:
    patterns = [
        r'href=["\']([^"\']*HISTDATA_COM_ASCII_[^"\']+\.zip)["\']',
        r'href=["\']([^"\']*download/[^"\']+\.zip)["\']',
        r'href=["\']([^"\']+\.zip)["\']',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def download_month(session: requests.Session, pair: str, year: int, month: int, output_dir: Path, sleep_s: float = 1.0):
    pair = pair.lower()
    page_url = urljoin(BASE_PAGE, f"{pair}/{year}")

    r = session.get(page_url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    token = extract_token(r.text)
    if not token:
        raise RuntimeError(f"Token tk non trovato per {pair} {year}-{month:02d}")

    payload = {
        "tk": token,
        "date": f"{year}",
        "datemonth": f"{month:02d}",
        "platform": "ASCII",
        "timeframe": "M1",
        "fxpair": pair,
    }

    r2 = session.post(page_url, data=payload, headers=HEADERS, timeout=60)
    r2.raise_for_status()

    link = find_download_link(r2.text)
    if not link:
        raise RuntimeError(f"Link zip non trovato per {pair} {year}-{month:02d}")

    if not link.startswith("http"):
        link = urljoin("https://www.histdata.com/", link)

    filename = link.rstrip("/").split("/")[-1]
    if not filename.lower().endswith(".zip"):
        filename = f"HISTDATA_COM_ASCII_{pair.upper()}_M1_{year}{month:02d}.zip"

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / filename

    if dest.exists() and dest.stat().st_size > 0:
        print(f"[SKIP] {year}-{month:02d} -> {dest.name} già presente")
        return dest

    with session.get(link, headers=HEADERS, timeout=120, stream=True) as dl:
        dl.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in dl.iter_content(chunk_size=1024 * 128):
                if chunk:
                    f.write(chunk)

    print(f"[OK]   {year}-{month:02d} -> {dest.name}")
    time.sleep(sleep_s)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Scarica zip mensili HistData M1 ASCII")
    parser.add_argument("--pair", required=True, help="Pair HistData, es. eurusd, gbpusd")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--start-month", type=int, default=1)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--end-month", type=int, default=12)
    parser.add_argument("--output-dir", default="data/histdata_zips")
    parser.add_argument("--sleep", type=float, default=1.0, help="Pausa tra download in secondi")
    args = parser.parse_args()

    if not (1 <= args.start_month <= 12 and 1 <= args.end_month <= 12):
        print("Mese non valido", file=sys.stderr)
        return 1
    if (args.start_year, args.start_month) > (args.end_year, args.end_month):
        print("Range date non valido", file=sys.stderr)
        return 1

    session = requests.Session()
    output_dir = Path(args.output_dir) / args.pair.upper()

    ok = 0
    fail = 0
    for y, m in month_iter(args.start_year, args.start_month, args.end_year, args.end_month):
        try:
            download_month(session, args.pair, y, m, output_dir, args.sleep)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"[ERR]  {y}-{m:02d} -> {e}", file=sys.stderr)

    print(f"\nCompletato. OK={ok}, ERR={fail}, cartella={output_dir}")
    if fail:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
