#!/usr/bin/env python3
"""
Monitor de stoc multi-magazin (Altex, Flanco, etc.)
-----------------------------------------------------
Verifica periodic mai multe pagini de produs si trimite o notificare
Telegram pentru FIECARE produs care redevine disponibil (nu mai apare
"stoc epuizat").

Notificarea foloseste un bot de Telegram (gratuit, fara restrictii).

CUM IL FOLOSESTI:
1. Instaleaza dependintele:
     pip install curl_cffi beautifulsoup4 --break-system-packages

2. Creeaza un bot de Telegram:
   - Cauta @BotFather in Telegram, trimite-i /newbot
   - Alege un nume si un username pentru bot
   - Copiaza TOKEN-ul primit

3. Porneste o conversatie cu botul tau (cauta-l dupa username, apasa
   Start sau trimite-i orice mesaj).

4. Afla Chat ID-ul tau accesand in browser (inlocuind TOKEN-ul):
     https://api.telegram.org/botTOKEN_TAU/getUpdates
   Cauta "chat":{"id":NUMAR - acel NUMAR e Chat ID-ul tau.

5. Completeaza sectiunea CONFIGURARE de mai jos:
   - TELEGRAM_BOT_TOKEN si TELEGRAM_CHAT_ID
   - lista PRODUCTS cu URL-urile pe care vrei sa le monitorizezi

6. Ruleaza scriptul manual o data ca sa testezi:
     python monitor_stoc_multi.py

7. Ca sa ruleze automat periodic:

   -- Pe Mac/Linux (crontab) --
   crontab -e
   Adauga linia (verifica la fiecare 10 minute):
     */10 * * * * /usr/bin/python3 /calea/catre/monitor_stoc_multi.py >> /tmp/monitor_stoc.log 2>&1

   -- Pe Windows (Task Scheduler) --
   Creeaza un task nou care ruleaza:
     python.exe C:\\calea\\catre\\monitor_stoc_multi.py
   la fiecare 10 minute.

Pentru fiecare produs se creeaza un fisier separat de tip "flag" ca sa
nu primesti notificari repetate pentru acelasi produs. Sterge fisierul
flag corespunzator (vezi folderul unde ruleaza scriptul) daca vrei sa
reiei monitorizarea pentru acel produs.

NOTA TEHNICA: unele magazine (Altex, Media Galaxy, Flanco) folosesc
sisteme de protectie anti-bot care blocheaza cereri facute cu librarii
Python standard. De aceea folosim curl_cffi, care imita amprenta
tehnica a unui browser Chrome real.
"""

from curl_cffi import requests
import requests as std_requests
from bs4 import BeautifulSoup
import os
import re
import sys
from datetime import datetime

# ============ CONFIGURARE ============

# Date bot Telegram (creat prin @BotFather)
# IMPORTANT: token-ul si chat ID-urile se citesc din variabile de mediu
# (TELEGRAM_BOT_TOKEN si TELEGRAM_CHAT_IDS), NU sunt scrise direct in cod.
# Asta permite folosirea GitHub Secrets fara sa expui datele sensibile.
#
# Local (pe PC-ul tau), poti seta variabilele astfel inainte sa rulezi scriptul:
#   Windows (cmd):   set TELEGRAM_BOT_TOKEN=token_tau
#                    set TELEGRAM_CHAT_IDS=1679664606,987654321
#   Mac/Linux:       export TELEGRAM_BOT_TOKEN=token_tau
#                    export TELEGRAM_CHAT_IDS=1679664606,987654321
#
# Pe GitHub Actions, aceste variabile vin automat din Secrets (vezi monitor.yml).

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [
    cid.strip()
    for cid in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",")
    if cid.strip()
]

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
    print("EROARE: lipsesc variabilele de mediu TELEGRAM_BOT_TOKEN si/sau TELEGRAM_CHAT_IDS.")
    sys.exit(1)

# Lista produselor de monitorizat.
# "nume"           -> ce apare in SMS, ca sa stii despre ce produs e vorba
# "url"            -> link-ul direct catre pagina produsului
# "out_of_stock"   -> textul care apare pe pagina cand NU e stoc
#                     (scris cu litere mici; comparatia ignora majusculele)
PRODUCTS = [
    {
        "nume": "PS5 Pro 2TB White - Altex",
        "url": "https://altex.ro/consola-playstation-5-pro-digital-edition-ps5-2tb-white/cpd/CNSPS5PRO2TB/",
        "out_of_stock": "stoc epuizat",
    },
    {
        "nume": "PS5 Pro 2TB Alb - Flanco",
        "url": "https://www.flanco.ro/consola-sony-playstation-5-ps5-pro-2-tb-ssd-8k-4k-120-hz-ray-tracing-alb.html",
        "out_of_stock": "text_fals_de_test",
    },
    {
        "nume": "PS5 Pro 2TB White - Media Galaxy",
        "url": "https://mediagalaxy.ro/consola-playstation-5-pro-digital-edition-ps5-2tb-white/cpd/CNSPS5PRO2TB/",
        "out_of_stock": "stoc epuizat",
    },
    # Adauga aici alte produse dupa acelasi model, ex:
    # {
    #     "nume": "Alt produs - Alt magazin",
    #     "url": "https://exemplu.ro/produs",
    #     "out_of_stock": "indisponibil",
    # },
]

# Folderul unde se salveaza fisierele "flag" (ca sa nu duplicam SMS-uri)
FLAG_DIR = os.path.dirname(os.path.abspath(__file__))

# ======================================


def slugify(text: str) -> str:
    """Transforma numele produsului intr-un nume de fisier valid."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return slug.strip("_")


def is_in_stock(html_text: str, out_of_stock_text: str) -> bool:
    """Returneaza True daca produsul PARE sa fie in stoc."""
    soup = BeautifulSoup(html_text, "html.parser")
    page_text = soup.get_text(separator=" ").lower()
    return out_of_stock_text.lower() not in page_text


def send_telegram_notification(product_name: str, product_url: str):
    message = f"🎮 {product_name} e din nou in stoc!\n{product_url}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    erori = []
    for chat_id in TELEGRAM_CHAT_IDS:
        response = std_requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": message,
            },
            timeout=15,
        )
        if response.status_code != 200:
            erori.append(f"chat_id {chat_id}: status {response.status_code}: {response.text}")

    if erori:
        raise Exception("Erori la trimiterea notificarii catre unii utilizatori:\n" + "\n".join(erori))


def check_product(product: dict):
    name = product["nume"]
    url = product["url"]
    out_of_stock_text = product["out_of_stock"]

    flag_file = os.path.join(FLAG_DIR, f"stoc_gasit_{slugify(name)}.flag")

    if os.path.exists(flag_file):
        print(f"[{datetime.now()}] [{name}] Deja notificat anterior. "
              f"Sterge '{flag_file}' ca sa reincepi monitorizarea.")
        return

    try:
        response = requests.get(url, impersonate="chrome", timeout=30)
        if response.status_code != 200:
            print(f"[{datetime.now()}] [{name}] Site-ul a raspuns cu status {response.status_code}.")
            return
    except Exception as e:
        print(f"[{datetime.now()}] [{name}] Eroare la accesarea paginii: {e}")
        return

    if is_in_stock(response.text, out_of_stock_text):
        print(f"[{datetime.now()}] [{name}] PRODUS IN STOC! Trimit notificare Telegram...")
        try:
            send_telegram_notification(name, url)
            with open(flag_file, "w") as f:
                f.write(f"Notificat la {datetime.now()}\n")
            print(f"[{name}] Notificare trimisa cu succes.")
        except Exception as e:
            print(f"[{name}] Eroare la trimiterea notificarii: {e}")
    else:
        print(f"[{datetime.now()}] [{name}] Inca stoc epuizat.")


def main():
    if not PRODUCTS:
        print("Nu ai configurat niciun produs in lista PRODUCTS.")
        sys.exit(1)

    for product in PRODUCTS:
        check_product(product)


if __name__ == "__main__":
    main()
