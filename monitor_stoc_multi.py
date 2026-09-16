#!/usr/bin/env python3

from curl_cffi import requests
import requests as std_requests
from bs4 import BeautifulSoup
import os
import re
import sys
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [
    cid.strip()
    for cid in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",")
    if cid.strip()
]

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
    print("EROARE: lipsesc variabilele de mediu TELEGRAM_BOT_TOKEN si/sau TELEGRAM_CHAT_IDS.")
    sys.exit(1)

PRODUCTS = [
    {
        "nume": "PS5 Pro 2TB White - Altex",
        "url": "https://altex.ro/consola-playstation-5-pro-digital-edition-ps5-2tb-white/cpd/CNSPS5PRO2TB/",
        "out_of_stock": "stoc epuizat",
    },
    {
        "nume": "PS5 Pro 2TB Alb - Flanco",
        "url": "https://www.flanco.ro/consola-sony-playstation-5-ps5-pro-2-tb-ssd-8k-4k-120-hz-ray-tracing-alb.html",
        "out_of_stock": "stoc epuizat",
    },
    {
    "nume": "PS5 Pro 2TB White - ForIT",
    "url": "https://www.forit.ro/consola-jocuri-sony-game-console-sony-playstation-5-pro-2tb-cfi-7121-bp677960",
    "out_of_stock": "stoc epuizat",
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
