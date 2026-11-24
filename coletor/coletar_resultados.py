#!/usr/bin/env python3
# Federal da Sorte - coletor inicial de resultados públicos
# Importa extrações como PENDENTES para conferência humana. Nunca marca como validadas automaticamente.


from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SECRET_KEY", "").strip()

if not SUPABASE_URL or not SERVICE_KEY:
    raise SystemExit("Configure SUPABASE_URL e SUPABASE_SECRET_KEY.")

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "25"))
MAX_BANK_PAGES = int(os.getenv("MAX_BANK_PAGES", "30"))
TZ = "America/Sao_Paulo"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "FederalDaSorteDataCollector/1.0 (+public-results-indexing)"
}
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FederalDaSorteCollector/1.0)",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}

ANIMALS = {
    1:"Avestruz",2:"Águia",3:"Burro",4:"Borboleta",5:"Cachorro",
    6:"Cabra",7:"Carneiro",8:"Camelo",9:"Cobra",10:"Coelho",
    11:"Cavalo",12:"Elefante",13:"Galo",14:"Gato",15:"Jacaré",
    16:"Leão",17:"Macaco",18:"Porco",19:"Pavão",20:"Peru",
    21:"Touro",22:"Tigre",23:"Urso",24:"Veado",25:"Vaca"
}
UF_MAP = {
    "BA":"BA","BAHIA":"BA","MALUCA BAHIA":"BA","PARATODOS BAHIA":"BA",
    "RJ":"RJ","PT-RIO":"RJ","PT RIO":"RJ","RIO DE JANEIRO":"RJ",
    "SP":"SP","PT SP":"SP","PT-SP":"SP","SÃO PAULO":"SP","SAO PAULO":"SP",
    "PB":"PB","LOTEP":"PB","PARATODOS PB":"PB",
    "GO":"GO","LOOK":"GO","LOOK LOTERIAS":"GO",
    "PE":"PE","PERNAMBUCO":"PE","AVAL PERNAMBUCO":"PE",
    "CE":"CE","PARATODOS CE":"CE",
    "SE":"SE","ABAESE":"SE","ITABAIANA":"SE",
    "RS":"RS","BICHO RS":"RS",
    "MG":"MG","MINAS":"MG","MINAS GERAIS":"MG",
    "DF":"DF","BRASÍLIA":"DF","BRASILIA":"DF","LBR":"DF",
}

session = requests.Session()
session.headers.update(HTTP_HEADERS)


@dataclass
class Draw:
    date: str
    time: str
    bank: str
    identifier: str
    uf: str | None
    municipality: str | None
    url: str
    prizes: list
    raw: dict


def rest(method, table, *, params=None, payload=None, prefer=None):
    if DRY_RUN and method.upper() != "GET":
        raise RuntimeError(
            f"DRY_RUN ativo: operação {method.upper()} bloqueada."
        )
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = dict(HEADERS)
    if prefer:
        headers["Prefer"] = prefer
    response = requests.request(
        method, url, headers=headers, params=params, json=payload, timeout=TIMEOUT
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase {method} {table}: HTTP {response.status_code}: {response.text[:800]}")
    if not response.text:
        return []
    try:
        return response.json()
    except ValueError:
        return []


def get_text(url):
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    if len(response.content) > 8_000_000:
        raise RuntimeError(f"Página muito grande, ignorada: {url}")
    return response.text


def parse_uf(bank):
    up = bank.upper()
    for token, uf in UF_MAP.items():
        if token in up:
            return uf
    m = re.search(r"\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b", up)
    return m.group(1) if m else None


def derive_fields(milhar):
    dezena = milhar[-2:]
    centena = milhar[-3:]
    group = 25 if int(dezena) == 0 else ((int(dezena) - 1) // 4) + 1
    return {
        "numero": milhar, "dezena": dezena, "centena": centena,
        "milhar": milhar, "grupo": group, "animal": ANIMALS[group]
    }


def parse_prizes(text, pattern):
    prizes = []
    for m in re.finditer(pattern, text, flags=re.I | re.S):
        pos = int(m.group("pos"))
        number = m.group("number")
        if len(number) != 4:
            continue
        supplied_group = int(m.group("group"))
        fields = derive_fields(number)
        prizes.append({
            "posicao": pos,
            **fields,
            "grupo_informado_fonte": supplied_group,
            "grupo_confere": supplied_group == fields["grupo"],
            "texto_fonte": m.group(0)[:300]
        })
    # Evita repetir posições capturadas por sobreposição de elementos
    unique = {}
    for p in prizes:
        unique[p["posicao"]] = p
    return [unique[k] for k in sorted(unique)]


def parse_hora(url, html):
    soup = BeautifulSoup(html, "html.parser")
    draws = []
    # A página apresenta cada extração em um link/card com o texto integral do resultado.
    for a in soup.find_all("a"):
        text = a.get_text(" ", strip=True)
        if "Este foi o resultado da" not in text or not re.search(r"\b\d{1,2}º", text):
            continue
        footer = re.search(
            r"Este foi o resultado da\s+(.+?)\s+da\s+(.+?),\s*das\s+(\d{2}:\d{2})\s+do dia\s+(\d{2}/\d{2}/\d{4})",
            text, flags=re.I
        )
        if not footer:
            continue
        identifier, bank, clock, date_br = [x.strip() for x in footer.groups()]
        prizes = parse_prizes(
            text,
            r"(?P<pos>\d{1,2})º\s+(?P<number>\d{4})\s+(?P<group>\d{1,2})\s+[A-Za-zÀ-ÿ]+"
        )
        if not prizes:
            continue
        date = datetime.strptime(date_br, "%d/%m/%Y").date().isoformat()
        draws.append(Draw(date, clock, bank, identifier, parse_uf(bank), None,
                          urljoin(url, a.get("href") or url), prizes,
                          {"adapter":"hora_do_bicho","card_text":text[:5000]}))
    return draws


def parse_bancas_detail(url, html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    heading = soup.find(["h1","h2"])
    bank = heading.get_text(" ", strip=True) if heading else (soup.title.get_text(" ", strip=True) if soup.title else "Banca não identificada")
    bank = re.sub(r"^Veja o Resultado da\s+", "", bank, flags=re.I)
    bank = re.sub(r"\s+de\s+\d{2}/\d{2}/\d{4}.*$", "", bank, flags=re.I).strip()
    # A página individual informa a data e hora na chamada do resultado.
    dt = re.search(r"(\d{2}/\d{2}/\d{4})\s*[-–]\s*(\d{1,2}:\d{2})\s*h", text, re.I)
    if not dt:
        dt = re.search(r"(\d{2}/\d{2}/\d{4}).{0,80}?(\d{1,2}:\d{2})\s*h", text, re.I)
    if not dt:
        return []
    date = datetime.strptime(dt.group(1), "%d/%m/%Y").date().isoformat()
    clock = dt.group(2).zfill(5)
    # Nome de banca vem de "Resultado ... - NOME DA BANCA - data - hora".
    prizes = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td","th"])]
        if len(cells) < 3 or not re.search(r"Prêmio\s*\d+º", cells[0], re.I):
            continue
        pos_m = re.search(r"(\d+)º", cells[0])
        num_m = re.search(r"Milhar\s*:?\s*(\d{4})", cells[1], re.I)
        grp_m = re.search(r"Grupo\s*:?\s*(\d{1,2})", cells[2], re.I)
        if not (pos_m and num_m and grp_m):
            continue
        fields = derive_fields(num_m.group(1))
        supplied_group = int(grp_m.group(1))
        prizes.append({
            "posicao":int(pos_m.group(1)), **fields,
            "grupo_informado_fonte":supplied_group,
            "grupo_confere":supplied_group == fields["grupo"],
            "texto_fonte":" | ".join(cells)[:300]
        })
    if not prizes:
        # Fallback para texto linear da tabela
        prizes = parse_prizes(
            text,
            r"Prêmio\s*(?P<pos>\d+)º.{0,100}?Milhar\s*:?\s*(?P<number>\d{4}).{0,100}?Grupo\s*:?\s*(?P<group>\d{1,2})"
        )
    if not prizes:
        return []
    return [Draw(date, clock, bank, bank, parse_uf(bank), None, url, prizes,
                 {"adapter":"bancas_do_bicho","page_title":soup.title.get_text(" ",strip=True) if soup.title else ""})]


def parse_bancas_index(url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        if "resultados-jogo-do-bicho-" in urlparse(href).path:
            if href not in links:
                links.append(href)
    draws = []
    for link in links[:MAX_BANK_PAGES]:
        try:
            page = get_text(link)
            draws.extend(parse_bancas_detail(link, page))
            time.sleep(0.4)
        except Exception as exc:
            print(f"[AVISO] Falha ao consultar página de banca {link}: {exc}")
    return draws


def parse_ojogo(url, html):
    soup = BeautifulSoup(html, "html.parser")
    draws = []
    # Arquivo histórico: cada banca tem cabeçalho e tabela com uma linha por horário.
    for table in soup.find_all("table"):
        prev = table.find_previous(["h2","h3"])
        if not prev:
            continue
        bank_heading = prev.get_text(" ", strip=True)
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", bank_heading)
        if not date_match:
            # A data pode estar no subtítulo imediatamente anterior.
            near = prev.parent.get_text(" ", strip=True) if prev.parent else ""
            date_match = re.search(r"(\d{2}/\d{2}/\d{4})", near)
        if not date_match:
            continue
        date = datetime.strptime(date_match.group(1), "%d/%m/%Y").date().isoformat()
        bank = re.sub(r"\s*[—-]\s*\d{2}/\d{2}/\d{4}.*$", "", bank_heading).strip()
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td","th"])]
            if len(cells) < 2:
                continue
            tm = re.search(r"(\d{1,2}:\d{2})", cells[0])
            if not tm:
                continue
            prizes = []
            for pos, cell in enumerate(cells[1:], start=1):
                mm = re.search(r"(?<!\d)(\d{4})\s*(\d{1,2})\s*·", cell)
                if not mm:
                    # Link label may separate milhar and group from animal.
                    mm = re.search(r"(\d{4})\s+(\d{1,2})\b", cell)
                if not mm:
                    continue
                number, supplied = mm.group(1), int(mm.group(2))
                fields = derive_fields(number)
                prizes.append({"posicao":pos, **fields,
                               "grupo_informado_fonte":supplied,
                               "grupo_confere":supplied == fields["grupo"],
                               "texto_fonte":cell[:300]})
            if prizes:
                draws.append(Draw(date, tm.group(1), bank, cells[0], parse_uf(bank), None,
                                  url, prizes, {"adapter":"o_jogo_do_bicho","bank_heading":bank_heading}))
    return draws


def fetch_source_draws(source):
    url = source.get("url_base") or ""
    host = urlparse(url).netloc.lower()
    html = get_text(url)
    if "horadobicho.com" in host:
        return parse_hora(url, html)
    if "bancasdobicho.com.br" in host:
        return parse_bancas_index(url, html)
    if "ojogodobiicho.com" in host:
        return parse_ojogo(url, html)
    print(f"[IGNORADA] Sem adaptador validado para {host or url}")
    return []


def existing_extraction(draw, source_id, modality_id):
    params = {
        "select":"id,status_conferencia,hash_conteudo",
        "fonte_id":f"eq.{source_id}",
        "data_extracao":f"eq.{draw.date}",
        "horario_local":f"eq.{draw.time}:00",
        "modalidade_id":f"eq.{modality_id}",
        "identificador_origem":f"eq.{draw.identifier}",
        "limit":"1",
    }
    params["uf"] = "is.null" if draw.uf is None else f"eq.{draw.uf}"
    params["municipio"] = "is.null" if draw.municipality is None else f"eq.{draw.municipality}"
    rows = rest("GET", "extracoes_bicho", params=params)
    return rows[0] if rows else None


def import_draw(draw, source, modality_id):
    source_id = source["id"]
    canonical = {
        "fonte_id":source_id, "data_extracao":draw.date, "horario_local":draw.time,
        "modalidade_id":modality_id, "uf":draw.uf, "municipio":draw.municipality,
        "identificador_origem":draw.identifier,
        "prizes":[{k:p[k] for k in ("posicao","numero","grupo")} for p in draw.prizes],
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old = existing_extraction(draw, source_id, modality_id)
    if old:
        if old.get("hash_conteudo") == digest:
            print(f"[DUPLICADA] {draw.bank} {draw.date} {draw.time} — já existe")
        else:
            print(f"[DIVERGÊNCIA] {draw.bank} {draw.date} {draw.time} — registro existente não será sobrescrito")
            if not DRY_RUN:
                rest("PATCH", "extracoes_bicho", params={"id":f"eq.{old['id']}"}, payload={
                    "status_conferencia":"divergente",
                    "observacoes":"Nova versão detectada pela coleta; revisão manual necessária."
                }, prefer="return=minimal")
            else:
                print("[SIMULAÇÃO] Registro existente divergente não será atualizado")
        return "duplicate"
    if DRY_RUN:
        print(f"[SIMULAÇÃO] {draw.bank} {draw.date} {draw.time}: {len(draw.prizes)} prêmios")
        return "dry_run"

    any_group_mismatch = any(not p["grupo_confere"] for p in draw.prizes)
    extraction_payload = {
        "fonte_id":source_id, "modalidade_id":modality_id,
        "data_extracao":draw.date, "horario_local":draw.time,
        "fuso_horario":TZ, "uf":draw.uf, "municipio":draw.municipality,
        "identificador_origem":draw.identifier, "url_resultado":draw.url,
        "status_conferencia":"divergente" if any_group_mismatch else "pendente",
        "payload_original":{"source":source["nome"],"draw":asdict(draw)},
        "hash_conteudo":digest,
        "observacoes":"Coleta automática. Aguardando conferência humana." +
            (" Grupo informado pela fonte diverge do cálculo da dezena." if any_group_mismatch else "")
    }
    created = rest("POST","extracoes_bicho",payload=extraction_payload,prefer="return=representation")
    if not created:
        raise RuntimeError("Supabase não retornou o ID da extração criada.")
    extraction_id = created[0]["id"]
    rows = []
    for p in draw.prizes:
        rows.append({
            "extracao_id":extraction_id, "posicao":p["posicao"], "numero":p["numero"],
            "grupo":p["grupo"], "dezena":p["dezena"], "centena":p["centena"],
            "milhar":p["milhar"], "animal":p["animal"],
            "payload_original":{"fonte":source["nome"],"grupo_informado_fonte":p["grupo_informado_fonte"],
                                "grupo_confere":p["grupo_confere"],"texto":p["texto_fonte"]}
        })
    try:
        rest("POST","resultados_bicho",
             params={"on_conflict":"extracao_id,posicao"},
             payload=rows,
             prefer="resolution=merge-duplicates,return=minimal")
    except Exception:
        rest("PATCH","extracoes_bicho",params={"id":f"eq.{extraction_id}"},
             payload={"status_conferencia":"incompleto","observacoes":"Falha ao gravar todos os prêmios; revisar e reprocessar."},
             prefer="return=minimal")
        raise
    return "inserted"


def main():
    print(f"Federal da Sorte collector | DRY_RUN={DRY_RUN}")
    sources = rest("GET","fontes_resultados_bicho",params={
        "select":"id,nome,url_base,tipo_fonte,ativa,metodo_coleta",
        "ativa":"eq.true","metodo_coleta":"eq.pagina_publica"
    })
    modalities = rest("GET","modalidades_bicho",params={
        "select":"id,codigo","codigo":"eq.banca_local","ativa":"eq.true","limit":"1"
    })
    if not modalities:
        raise RuntimeError("Modalidade banca_local não encontrada/ativa.")
    modality_id = modalities[0]["id"]
    totals = {"inserted":0,"duplicate":0,"dry_run":0,"errors":0,"parsed":0}
    for source in sources:
        try:
            if not source.get("url_base"):
                continue
            print(f"\n[FONTE] {source['nome']} — {source['url_base']}")
            draws = fetch_source_draws(source)
            totals["parsed"] += len(draws)
            print(f"[LEITURA] {len(draws)} extrações interpretadas")
            for draw in draws:
                try:
                    result = import_draw(draw, source, modality_id)
                    totals[result] += 1
                except Exception as exc:
                    totals["errors"] += 1
                    print(f"[ERRO EXTRAÇÃO] {draw.bank} {draw.date} {draw.time}: {exc}")
        except Exception as exc:
            totals["errors"] += 1
            print(f"[ERRO FONTE] {source.get('nome')}: {exc}")
    print("\nRESUMO:", json.dumps(totals, ensure_ascii=False))
    if totals["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
