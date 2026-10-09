import sys
import os
import time
import feedparser
import requests

# --- NASTAVITVE ---
# En bot (isti token) za vse skupine.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "VNESI_BOT_TOKEN")

# Vsak vir ima svoj RSS, svojo skupino in svojo datoteko z zadnjim ID-jem.
# Vrednosti lahko vpišeš kar sem ali pa jih nastaviš kot okoljske spremenljivke.
VIRI = [
    {
        "ime": "Skupina 1",
        "url": os.getenv("RSS_URL_1", "https://spin3.sos112.si/javno/ODApi/true"),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_1", "VNESI_CHAT_ID_1"),
        "datoteka_id": "last_id.txt",  # ostane ista, da se stanje ohrani
    },
    {
        "ime": "Skupina 2",
        "url": os.getenv("RSS_URL_2", "VNESI_RSS_LINK_2"),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_2", "VNESI_CHAT_ID_2"),
        "datoteka_id": "last_id_2.txt",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


def vir_je_nastavljen(vir):
    """Vir preskočimo, dokler ima še katero od 'VNESI_' vrednosti."""
    return not any("VNESI_" in str(vir[k]) for k in ("url", "chat_id"))


def dobi_zadnji_id(vir):
    """Prebere ID zadnjega poslanega dogodka iz datoteke tega vira."""
    pot = vir["datoteka_id"]
    if os.path.exists(pot):
        try:
            with open(pot, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[{vir['ime']}] Napaka pri branju datoteke: {e}")
    return ""


def shrani_zadnji_id(vir, dogodek_id):
    """Shrani ID najnovejšega poslanega dogodka v datoteko tega vira."""
    try:
        with open(vir["datoteka_id"], "w", encoding="utf-8") as f:
            f.write(str(dogodek_id).strip())
    except Exception as e:
        print(f"[{vir['ime']}] Napaka pri shranjevanju v datoteko: {e}")


def pridobi_id_dogodka(entry):
    """Pridobi čisti ID dogodka iz RSS/JSON vnosa."""
    guid = (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
        or entry.get("title", "")
    )
    return str(guid).strip()


def poslji_telegram_sporocilo(vir, besedilo):
    """Pošlje sporočilo v Telegram skupino tega vira, z obravnavo 429."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    podatki = {
        "chat_id": vir["chat_id"],
        "text": besedilo,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        res = requests.post(url, data=podatki, timeout=10)
        odgovor_json = res.json()

        if res.status_code == 429:
            retry_after = odgovor_json.get("parameters", {}).get("retry_after", 5)
            print(f"⏳ [{vir['ime']}] Telegram omejitev! Čakam {retry_after} s...")
            time.sleep(retry_after + 1)
            return poslji_telegram_sporocilo(vir, besedilo)

        if res.status_code == 200:
            print(f"✅ [{vir['ime']}] Sporočilo uspešno poslano!")
            return True
        else:
            print(f"❌ [{vir['ime']}] Telegram napaka: {res.text}")
            return False

    except Exception as e:
        print(f"❌ [{vir['ime']}] Napaka pri povezavi: {e}")
        return False


def sestavi_sporocilo(entry):
    naslov = entry.get("title", "Brez naslova")
    povezava = entry.get("link", "https://spin3.sos112.si")
    opis = (
        entry.get("summary", "Ni opisa.")
        .replace("<br />", "\n")
        .replace("<br>", "\n")
    )
    return (
        f"🚨 *NOVO SPIN OBVESTILO*\n\n📌 *{naslov}*\n\n📝 {opis}\n\n🔗"
        f" [Odpri v SPIN-u]({povezava})"
    )


def preveri_spin_rss(vir):
    print(f"[{vir['ime']}] Preverjam SPIN vir...")

    try:
        odgovor = requests.get(vir["url"], headers=HEADERS, timeout=15)
        feed = feedparser.parse(odgovor.text)
    except Exception as e:
        print(f"[{vir['ime']}] Napaka pri prenosu podatkov: {e}")
        return

    if not feed.entries:
        print(f"[{vir['ime']}] Vir je prazen ali nedosegljiv.")
        return

    zadnji_shranjen_id = dobi_zadnji_id(vir)
    najnovejsi_entry = feed.entries[0]
    najnovejsi_id = pridobi_id_dogodka(najnovejsi_entry)

    # 1. PRVI ZAGON: pošljemo le 1 najnovejši dogodek in zaklenemo
    if not zadnji_shranjen_id:
        print(f"[{vir['ime']}] Prvi zagon: pošiljam samo 1 najnovejši dogodek...")
        if poslji_telegram_sporocilo(vir, sestavi_sporocilo(najnovejsi_entry)):
            shrani_zadnji_id(vir, najnovejsi_id)
        return

    if zadnji_shranjen_id == najnovejsi_id:
        print(f"[{vir['ime']}] Ni novih dogodkov od zadnjega preverjanja.")
        return

    # 2. REDNO DELOVANJE: iščemo nove dogodke
    novi_dogodki = []
    nasel_staro_stanje = False

    for entry in feed.entries:
        if pridobi_id_dogodka(entry) == zadnji_shranjen_id:
            nasel_staro_stanje = True
            break
        novi_dogodki.append(entry)

    # VAROVALO 1: shranjenega ID-ja ni na seznamu -> pošljemo samo najnovejšega
    if not nasel_staro_stanje:
        print(
            f"[{vir['ime']}] Opozorilo: Shranjenega ID-ja ni na seznamu. "
            "Pošiljam samo najnovejši dogodek..."
        )
        novi_dogodki = [najnovejsi_entry]

    novi_dogodki.reverse()

    # VAROVALO 2: največ 3 obvestila naenkrat
    if len(novi_dogodki) > 3:
        print(
            f"[{vir['ime']}] Zaznanih {len(novi_dogodki)} novih dogodkov. "
            "Pošiljam le zadnje 3..."
        )
        novi_dogodki = novi_dogodki[-3:]

    print(f"[{vir['ime']}] Pošiljam {len(novi_dogodki)} novih dogodkov...")

    for entry in novi_dogodki:
        if poslji_telegram_sporocilo(vir, sestavi_sporocilo(entry)):
            shrani_zadnji_id(vir, pridobi_id_dogodka(entry))
        time.sleep(1.5)


if __name__ == "__main__":
    if "VNESI_" in TELEGRAM_TOKEN:
        print("Bot token še ni nastavljen (TELEGRAM_TOKEN). Končujem.")
        sys.exit(1)

    aktivni_viri = []
    for vir in VIRI:
        if vir_je_nastavljen(vir):
            aktivni_viri.append(vir)
        else:
            print(f"[{vir['ime']}] Še ni nastavljen (manjkajo podatki), preskakujem.")

    # Če ob zagonu podamo argument --boot, pošljemo obvestilo o zagonu v vse skupine
    if len(sys.argv) > 1 and sys.argv[1] == "--boot":
        for vir in aktivni_viri:
            poslji_telegram_sporocilo(
                vir,
                "🖥️ *SPIN Bot strežnik uspešno zagnan!*\n"
                "Spremljanje SPIN obvestil je aktivno.",
            )

    for vir in aktivni_viri:
        try:
            preveri_spin_rss(vir)
        except Exception as e:
            # napaka v enem viru ne sme ustaviti drugega
            print(f"[{vir['ime']}] Nepričakovana napaka: {e}")
