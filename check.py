import os
import json
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ============================ CONFIGURAÇÃO ============================
# Página de convocações a monitorar (HUL-UFS):
URL_HUL = "https://www.gov.br/hubrasil/pt-br/acesso-a-informacao/agentes-publicos/concursos-e-selecoes/concursos/2026/convocacoes/hul-ufs"

# Nova Página de seleções docentes (CMOP-UFS):
URL_CMOP = "https://cmop.ufs.br/pagina/33060-editais-concursos-e-selecoes-docentes-2026"

STATE_FILE = "state.json"

# Retentativa em caso de falha de rede passageira:
TENTATIVAS = 3       # quantas vezes tenta acessar o site
ESPERA_SEG = 10      # pausa (segundos) entre as tentativas
# =====================================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def fetch(url):
    """Baixa a página, tentando algumas vezes se a rede falhar."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    ultimo_erro = None
    for i in range(1, TENTATIVAS + 1):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            return r.text
        except requests.exceptions.RequestException as e:
            ultimo_erro = e
            print(f"Tentativa {i}/{TENTATIVAS} falhou para {url}: {e}")
            if i < TENTATIVAS:
                time.sleep(ESPERA_SEG)
    # esgotou as tentativas: repassa o erro para o main tratar
    raise ultimo_erro


def extract_items_hul(html, base_url):
    """
    Filtro original do HUL. Pega PDFs baseados no prefixo da URL.
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


def extract_items_cmop(html, base_url):
    """
    Filtro novo para a página do CMOP.
    Procura links que contenham palavras-chave no texto ou na URL.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        texto = " ".join(a.get_text().split())
        if not texto:
            continue
            
        texto_lower = texto.lower()
        # Filtra para evitar pegar menus e focar no que importa
        if "edital" in texto_lower or "resultado" in texto_lower or "convocação" in texto_lower or "seleção" in texto_lower or ".pdf" in href.lower():
            full = requests.compat.urljoin(base_url, href)
            items[full] = texto
    return items


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(known_hul, known_cmop):
    state = {
        "known": sorted(known_hul),       # mantido como 'known' para compatibilidade do HUL
        "known_cmop": sorted(known_cmop), # nova chave para o CMOP
        "initialized": True,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def notify(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing, cannot send notification:")
        print(text)
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=30,
    )
    r.raise_for_status()


def main():
    state = load_state()
    # Carrega estados antigos. Usa set para otimizar diferença
    known_hul = set(state.get("known", []))
    known_cmop = set(state.get("known_cmop", []))
    is_initialized = state.get("initialized", False)
    
    current_hul = {}
    current_cmop = {}

    # === Checagem HUL ===
    try:
        html_hul = fetch(URL_HUL)
        current_hul = extract_items_hul(html_hul, URL_HUL)
    except requests.exceptions.RequestException as e:
        print(f"Não foi possível acessar HUL após {TENTATIVAS} tentativas: {e}")

    # === Checagem CMOP ===
    try:
        html_cmop = fetch(URL_CMOP)
        current_cmop = extract_items_cmop(html_cmop, URL_CMOP)
    except requests.exceptions.RequestException as e:
        print(f"Não foi possível acessar CMOP após {TENTATIVAS} tentativas: {e}")

    set_current_hul = set(current_hul.keys())
    set_current_cmop = set(current_cmop.keys())

    # Primeira execução: memoriza tudo sem notificar
    if not is_initialized:
        save_state(set_current_hul, set_current_cmop)
        print(f"Primeira execução: Memorizado HUL ({len(set_current_hul)}) e CMOP ({len(set_current_cmop)}). Sem notificação.")
        return

    # Processa novidades do HUL
    new_hul = set_current_hul - known_hul
    if new_hul:
        linhas = ["🔔 Nova convocação publicada (HUL-UFS):\n"]
        for link in sorted(new_hul):
            linhas.append(f"• {current_hul[link]}\n{link}\n")
        linhas.append(f"\nPágina: {URL_HUL}")
        notify("\n".join(linhas))
        print(f"Notificado sobre {len(new_hul)} novo(s) edital(is) no HUL.")
    else:
        print("Nada novo no HUL.")

    # Processa novidades do CMOP
    new_cmop = set_current_cmop - known_cmop
    if new_cmop:
        linhas = ["🚨 Novos Editais/Concursos publicados (CMOP-UFS):\n"]
        for link in sorted(new_cmop):
            linhas.append(f"• {current_cmop[link]}\n{link}\n")
        linhas.append(f"\nPágina: {URL_CMOP}")
        notify("\n".join(linhas))
        print(f"Notificado sobre {len(new_cmop)} novo(s) edital(is) no CMOP.")
    else:
        print("Nada novo no CMOP.")

    # Só salva a união do que já era conhecido com o que foi encontrado agora.
    # Isso evita perder o histórico se uma página der erro ou vier vazia temporariamente.
    save_state(known_hul | set_current_hul, known_cmop | set_current_cmop)


if __name__ == "__main__":
    main()
