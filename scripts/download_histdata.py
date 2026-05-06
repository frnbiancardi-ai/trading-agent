#!/usr/bin/env python3
"""
Script per scaricare dati storici M1 da HistData.com
per EURUSD e altri simboli forex.
Scarica automaticamente i file ZIP e li estrae in data/histdata/<SIMBOLO>/

Configurazione via .env:
    HISTDATA_SYMBOLS=EURUSD,GBPUSD,USDJPY
    HISTDATA_START_YEAR=2016
    HISTDATA_END_YEAR=2026
    HISTDATA_REQUEST_DELAY=3
    HISTDATA_FORMAT=ascii
    HISTDATA_TIMEFRAME=m1
"""

import os
import sys
import ssl
import time
import shutil
import zipfile
import urllib3
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Carica variabili da .env
load_dotenv()

# Configurazione da .env con fallback
BASE_URL = os.getenv("HISTDATA_BASE_URL", "https://www.histdata.com")
DOWNLOAD_URL = f"{BASE_URL}/get.php"
DATA_DIR = Path(os.getenv("HISTDATA_DATA_DIR", "data/histdata"))

# HistData ha spesso certificati SSL scaduti, default a False per evitarlo
VERIFY_SSL = os.getenv("HISTDATA_VERIFY_SSL", "false").lower() == "true"

if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # Forza il bypass SSL a livello globale
    ssl._create_default_https_context = ssl._create_unverified_context

# Simboli da .env (separati da virgola) o default
SYMBOLS_STR = os.getenv("HISTDATA_SYMBOLS", "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD,EURGBP,EURJPY")
SYMBOLS = [s.strip().upper() for s in SYMBOLS_STR.split(",") if s.strip()]

# Anni da .env o default (ultimi 10 anni)
current_year = datetime.now().year
START_YEAR = int(os.getenv("HISTDATA_START_YEAR", current_year - 9))
END_YEAR = int(os.getenv("HISTDATA_END_YEAR", current_year))
YEARS = list(range(START_YEAR, END_YEAR + 1))

# Delay tra le richieste (secondi)
REQUEST_DELAY = float(os.getenv("HISTDATA_REQUEST_DELAY", "3.0"))

# Formato e timeframe
HISTDATA_FORMAT = os.getenv("HISTDATA_FORMAT", "ascii").lower()
HISTDATA_TIMEFRAME = os.getenv("HISTDATA_TIMEFRAME", "m1").lower()

# User-Agent realistico per evitare blocchi
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def setup_session() -> requests.Session:
    """Crea una sessione HTTP con headers appropriati."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    session.verify = VERIFY_SSL
    return session


def get_download_page_url(symbol: str, year: int) -> str:
    """Costruisce l'URL della pagina di download per un simbolo e anno."""
    return (
        f"{BASE_URL}/download-free-forex-data/"
        f"?/{HISTDATA_FORMAT}/{HISTDATA_TIMEFRAME}-bar-quotes/{symbol.lower()}/{year}"
    )


def extract_csrf_token(session: requests.Session, page_url: str) -> Optional[dict]:
    """
    Estrae il token CSRF e i parametri dal form di download.
    Restituisce un dict con tutti i campi nascosti del form.
    """
    try:
        response = session.get(page_url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Cerca il div nascosto che contiene il form
        hidden_div = soup.find("div", style="display:none;")
        if not hidden_div:
            print(f"  [!] Div nascosto non trovato in {page_url}")
            return None

        # Estrai tutti i campi hidden
        form_data = {}
        for input_tag in hidden_div.find_all("input", type="hidden"):
            name = input_tag.get("name")
            value = input_tag.get("value", "")
            if name:
                form_data[name] = value

        if not form_data.get("tk"):
            print(f"  [!] Token CSRF 'tk' non trovato")
            return None

        return form_data

    except requests.RequestException as e:
        print(f"  [!] Errore nel caricare la pagina: {e}")
        return None


def download_zip(
    session: requests.Session,
    form_data: dict,
    symbol: str,
    year: int,
    output_dir: Path,
) -> Optional[Path]:
    """
    Scarica il file ZIP usando i dati del form.
    Restituisce il percorso del file scaricato o None in caso di errore.
    """
    try:
        # Prepara i dati per il POST
        post_data = {
            "tk": form_data.get("tk", ""),
            "date": form_data.get("date", str(year)),
            "datemonth": form_data.get("datemonth", str(year)),
            "platform": form_data.get("platform", "ASCII"),
            "timeframe": form_data.get("timeframe", "M1"),
            "fxpair": form_data.get("fxpair", symbol),
        }

        # Referer deve essere l'URL della pagina che abbiamo visitato
        referer_url = get_download_page_url(symbol, year)

        response = session.post(
            DOWNLOAD_URL,
            data=post_data,
            headers={
                "Referer": referer_url,
                "Origin": BASE_URL,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=60,
            stream=True,
        )
        response.raise_for_status()

        # Controlla che sia davvero un file ZIP
        content_type = response.headers.get("Content-Type", "")
        content_length = int(response.headers.get("Content-Length", 0))

        if "zip" not in content_type.lower() and content_length < 1000:
            print(f"  [!] Risposta non è un file ZIP valido (Content-Type: {content_type})")
            return None

        # Crea directory di output se non esiste
        output_dir.mkdir(parents=True, exist_ok=True)

        # Salva il file ZIP
        zip_filename = f"HISTDATA_COM_{symbol}_M1_{year}.zip"
        zip_path = output_dir / zip_filename

        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Verifica che il file sia stato scaricato correttamente
        file_size = zip_path.stat().st_size
        if file_size < 100:
            print(f"  [!] File troppo piccolo ({file_size} bytes), possibile errore")
            zip_path.unlink()
            return None

        print(f"  [+] Scaricato: {zip_filename} ({file_size:,} bytes)")
        return zip_path

    except requests.RequestException as e:
        print(f"  [!] Errore nel download: {e}")
        return None


def extract_zip(zip_path: Path, symbol: str, year: int) -> bool:
    """
    Estrae il contenuto del file ZIP nella directory del simbolo.
    Rinomina il file estratto per includere simbolo e anno.
    """
    try:
        # Directory di destinazione per il simbolo
        symbol_dir = DATA_DIR / symbol.upper()
        symbol_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Lista dei file nello ZIP
            file_list = zf.namelist()

            if not file_list:
                print(f"  [!] ZIP vuoto: {zip_path}")
                return False

            # Estrai tutti i file in una directory temporanea
            temp_dir = zip_path.parent / "temp_extract"
            temp_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(temp_dir)

            # Trova i file estratti
            extracted_files = list(temp_dir.rglob("*"))
            extracted_files = [f for f in extracted_files if f.is_file()]

            if not extracted_files:
                print(f"  [!] Nessun file trovato nello ZIP")
                return False

            for extracted_file in extracted_files:
                # Crea un nome file standardizzato
                ext = extracted_file.suffix
                new_filename = f"{symbol.upper()}_M1_{year}{ext}"
                dest_path = symbol_dir / new_filename

                # Copia il file nella directory del simbolo
                shutil.copy2(extracted_file, dest_path)
                print(f"  [+] Estratto: {dest_path.name}")

            # Pulisci la directory temporanea
            shutil.rmtree(temp_dir, ignore_errors=True)

        return True

    except zipfile.BadZipFile:
        print(f"  [!] File ZIP corrotto: {zip_path}")
        return False
    except Exception as e:
        print(f"  [!] Errore nell'estrazione: {e}")
        return False


def download_symbol_year(
    session: requests.Session,
    symbol: str,
    year: int,
    temp_dir: Path,
) -> bool:
    """
    Download e estrazione per un singolo simbolo e anno.
    Restituisce True se tutto è andato a buon fine.
    """
    print(f"\n{'='*60}")
    print(f"Simbolo: {symbol} | Anno: {year}")
    print(f"{'='*60}")

    # 1. Ottieni la pagina di download
    page_url = get_download_page_url(symbol, year)
    print(f"  URL: {page_url}")

    form_data = extract_csrf_token(session, page_url)
    if not form_data:
        print(f"  [!] Saltato - impossibile ottenere token CSRF")
        return False

    time.sleep(REQUEST_DELAY)

    # 2. Scarica lo ZIP
    zip_path = download_zip(session, form_data, symbol, year, temp_dir)
    if not zip_path:
        print(f"  [!] Saltato - download fallito")
        return False

    time.sleep(REQUEST_DELAY)

    # 3. Estrai lo ZIP
    success = extract_zip(zip_path, symbol, year)
    if not success:
        print(f"  [!] Estrazione fallita")
        return False

    # 4. Pulisci il file ZIP
    zip_path.unlink()

    return True


def main():
    """Funzione principale."""
    print("=" * 60)
    print("HistData.com - Download Dati M1 Forex")
    print("=" * 60)
    print(f"Simboli: {', '.join(SYMBOLS)}")
    print(f"Anni: {YEARS[0]}-{YEARS[-1]}")
    print(f"Directory dati: {DATA_DIR.absolute()}")
    print()

    # Conferma prima di procedere
    total_downloads = len(SYMBOLS) * len(YEARS)
    estimated_time = total_downloads * (REQUEST_DELAY * 2 + 5)  # secondi
    print(f"Download totali previsti: {total_downloads}")
    print(f"Tempo stimato: ~{estimated_time // 60} minuti")
    print()

    print("[ATTENZIONE] HistData.com limita i download eccessivi.")
    print("Questo script include delay tra le richieste per rispettare il server.")
    print()

    response = input("Procedere con il download? (y/N): ")
    if response.lower() != "y":
        print("Download annullato.")
        sys.exit(0)

    # Setup
    session = setup_session()
    temp_dir = DATA_DIR / "temp_downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    fail_count = 0

    # Loop principale
    for symbol in SYMBOLS:
        for year in YEARS:
            success = download_symbol_year(session, symbol, year, temp_dir)
            if success:
                success_count += 1
            else:
                fail_count += 1

            # Delay tra i download per evitare il ban
            time.sleep(REQUEST_DELAY)

    # Riepilogo
    print("\n" + "=" * 60)
    print("RIEPILOGO DOWNLOAD")
    print("=" * 60)
    print(f"Successi: {success_count}")
    print(f"Fallimenti: {fail_count}")
    print(f"Totale: {success_count + fail_count}")
    print(f"\nDati salvati in: {DATA_DIR.absolute()}")

    # Lista delle directory create
    if DATA_DIR.exists():
        print("\nDirectory simboli create:")
        for d in sorted(DATA_DIR.iterdir()):
            if d.is_dir() and d.name not in ("temp_downloads", "temp_downloads"):
                file_count = len(list(d.glob("*")))
                print(f"  {d.name}/ ({file_count} file)")

    # Pulisci directory temporanea
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("\nDownload completato!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDownload interrotto dall'utente.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Errore imprevisto: {e}")
        sys.exit(1)
