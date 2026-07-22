import os
import json
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ============================ CONFIGURAÇÃO ============================
# Página de convocações a monitorar (HUL-UFS):
URL = "https://www.gov.br/hubrasil/pt-br/acesso-a-informacao/agentes-publicos/concursos-e-selecoes/concursos/2026/convocacoes/hul-ufs"

STATE_FILE = "state.json"
# =====================================================================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def fetch(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def extract_items(html, base_url):
    """
    Retorna {link_do_pdf: texto} apenas dos editais QUE PERTENCEM a esta
    página. O filtro pega os PDFs cujo endereço começa com o caminho da
    própria página — assim o menu do site (que tem outros PDFs) é ignorado.
    """
    soup = BeautifulSoup(html, "html.parser")
    prefix = base_url.rstrip("/") + "/"
    items = {}
    for a in soup.find_all("a", href=True):
        full = requests.compat.urljoin(base_url, a["href"])
        if full.startswith(prefix) and ".pdf" in full.lower():
            # normaliza removendo o /view final, se houver
            key = full[:-5] if full.endswith("/view") else full
            texto = " ".join(a.get_text().split())
            items[key] = texto or key
    return items


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(known):
    state = {
        "known": sorted(known),
        "initialized": True,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def notify(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=30,
    )
    r.raise_for_status()


def main():
    html = fetch(URL)
    items = extract_items(html, URL)
    current = set(items.keys())

    state = load_state()
    known = set(state.get("known", []))

    # Primeira execução: memoriza o que já está publicado e NÃO notifica.
    if not state.get("initialized"):
        save_state(current)
        print(f"Primeira execução: {len(current)} edital(is) memorizado(s). Sem notificação.")
        return

    new = current - known
    if new:
        linhas = ["🔔 Nova convocação publicada (HUL-UFS):\n"]
        for link in sorted(new):
            linhas.append(f"• {items[link]}\n{link}\n")
        linhas.append(f"\nPágina: {URL}")
        notify("\n".join(linhas))
        print(f"Notificado sobre {len(new)} novo(s) edital(is).")
    else:
        print("Nada novo.")

    # Só salva após notificar com sucesso (se falhar, tenta de novo na
    # próxima hora). O last_checked também mantém o agendador ativo.
    save_state(known | current)


if __name__ == "__main__":
    main()
