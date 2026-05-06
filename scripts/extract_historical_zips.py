#!/usr/bin/env python3
"""
Estrae tutti i file ZIP da data/historical/<SYMBOL>/
e sposta i CSV estratti nella cartella del simbolo.
"""

import os
import shutil
import zipfile
import tempfile
from pathlib import Path

HISTORICAL_DIR = Path(r"C:\trading-agent\.claude\worktrees\loving-thompson-867af8\data\historical")

success_count = 0
skip_count = 0
fail_count = 0

for symbol_dir in sorted(HISTORICAL_DIR.iterdir()):
    if not symbol_dir.is_dir():
        continue

    symbol = symbol_dir.name
    zip_files = list(symbol_dir.glob("*.zip"))

    if not zip_files:
        print(f"[{symbol}] Nessun ZIP trovato")
        continue

    print(f"\n[{symbol}] {len(zip_files)} file ZIP da elaborare")

    for zip_path in zip_files:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Estrai in temp dir
                temp_dir = Path(tempfile.mkdtemp())
                zf.extractall(temp_dir)

                # Trova tutti i CSV
                csv_files = list(temp_dir.rglob("*.csv"))

                if not csv_files:
                    print(f"  [!] Nessun CSV in {zip_path.name}")
                    shutil.rmtree(temp_dir)
                    fail_count += 1
                    continue

                for csv_file in csv_files:
                    dest = symbol_dir / csv_file.name

                    if dest.exists():
                        print(f"  [SKIP] {csv_file.name} (esiste già)")
                        skip_count += 1
                    else:
                        shutil.move(str(csv_file), str(dest))
                        print(f"  [OK] {csv_file.name}")
                        success_count += 1

                # Pulisci temp dir
                shutil.rmtree(temp_dir)

            # Elimina lo ZIP dopo estrazione riuscita
            zip_path.unlink()

        except Exception as e:
            print(f"  [ERRORE] {zip_path.name}: {e}")
            fail_count += 1

print(f"\n{'='*50}")
print(f"Riepilogo: {success_count} estratti, {skip_count} saltati, {fail_count} errori")
