import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
import httpx

app = FastAPI()

# -----------------------------
# CONFIGURAÇÕES (Railway -> Variáveis de Ambiente)
# -----------------------------
OMIE_APP_KEY = os.getenv("OMIE_APP_KEY")
OMIE_APP_SECRET = os.getenv("OMIE_APP_SECRET")
OMIE_BASE_URL = "https://app.omie.com.br/api/v1"  # Não precisa mudar

DIGISAC_SEND_URL = os.getenv("DIGISAC_SEND_URL")
DIGISAC_TOKEN = os.getenv("DIGISAC_TOKEN")
DIGISAC_SERVICE_ID = os.getenv("DIGISAC_SERVICE_ID")


@app.get("/")
async def home():
    return {"status": "ok", "message": "Webhook Omie -> DigiSac ativo"}


@app.post("/webhooks/omie/contas")
async def omie_webhook(payload: Dict[str, Any], request: Request):

    assunto = payload.get("assunto") or ""
    if "Financas.ContaReceber" not in assunto:
        return {"ok": True, "ignored": True}

    dados = payload.get("dados") or {}
    titulo_id = (
        dados.get("nCodTitulo")
        or dados.get("codigo_lancamento_omie")
        or dados.get("codigo_titulo")
    )

    if not titulo_id:
        raise HTTPException(400, "Webhook recebido sem código de título")

    # -------- 1) Buscar título no Omie ----------
    titulo = await buscar_titulo_omie(titulo_id)
    if not titulo:
        raise HTTPException(404, "Título não encontrado no Omie")

    boleto_info = titulo.get("boleto") or {}

    # Flag informando se o boleto foi gerado
    if boleto_info.get("cGerado") != "S":
        return {"ok": True, "boleto": False}

    # -------- 2) Obter boleto ----------
    boleto = await obter_boleto_omie(titulo_id)

    # -------- 3) Buscar cliente ----------
    cliente_id = titulo.get("codigo_cliente_omie") or titulo.get("nCodCliente")
    cliente = await buscar_cliente_omie(cliente_id)

    nome, celular = extrair_cliente(cliente)

    if not celular:
        return {"ok": False, "reason": "Cliente sem Whatsapp"}

    # -------- 4) Montar mensagem ----------
    mensagem = montar_mensagem(nome, boleto)

    # -------- 5) Enviar DigiSac ----------
    enviado, resposta = await enviar_digisac(celular, mensagem)

    return {
        "ok": enviado,
        "cliente": celular,
        "omie_titulo": titulo_id,
        "digisac_resposta": resposta,
    }


# ----------------- FUNÇÕES OMIE -----------------

async def buscar_titulo_omie(id_titulo: int):
    url = f"{OMIE_BASE_URL}/financas/contareceber/"
    body = {
        "call": "ConsultarContaReceber",
        "app_key": OMIE_APP_KEY,
        "app_secret": OMIE_APP_SECRET,
        "param": [{"nCodTitulo": id_titulo}],
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        return r.json()


async def obter_boleto_omie(id_titulo: int):
    url = f"{OMIE_BASE_URL}/financas/contareceberboleto/"
    body = {
        "call": "ObterBoleto",
        "app_key": OMIE_APP_KEY,
        "app_secret": OMIE_APP_SECRET,
        "param": [{"nCodTitulo": id_titulo}],
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        data = r.json()

    return {
        "vencimento": data.get("dDtVenc"),
        "valor": data.get("nValorTitulo"),
        "linha": data.get("cLinhaDigitavel"),
        "link": data.get("cUrlBoleto"),
    }


async def buscar_cliente_omie(id_cliente: int):
    url = f"{OMIE_BASE_URL}/geral/clientes/"
    body = {
        "call": "ConsultarCliente",
        "app_key": OMIE_APP_KEY,
        "app_secret": OMIE_APP_SECRET,
        "param": [{"codigo_cliente_omie": id_cliente}],
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        return r.json()


def extrair_cliente(cliente):
    nome = cliente.get("razao_social") or cliente.get("nome_fantasia") or cliente.get("nome")

    # telefone padrão do Omie
    ddd = cliente.get("telefone1_ddd")
    num = cliente.get("telefone1_numero")

    celular = None
    if ddd and num:
        digitos = f"55{ddd}{num}"
        celular = "".join(c for c in digitos if c.isdigit())

    return nome, celular


def montar_mensagem(nome, boleto):
    return (
        f"Olá {nome}, sua fatura está disponível.\n\n"
        f"Vencimento: {boleto.get('vencimento')}\n"
        f"Valor: R$ {boleto.get('valor')}\n"
        f"Linha Digitável: {boleto.get('linha')}\n"
        f"Link: {boleto.get('link')}\n\n"
        f"Caso já tenha pago, favor desconsiderar."
    )


async def enviar_digisac(numero, texto):
    headers = {
        "Authorization": f"Bearer {DIGISAC_TOKEN}",
        "Content-Type": "application/json",
    }

    body = {
        "number": numero,
        "text": texto,
        "serviceId": DIGISAC_SERVICE_ID,
        "origin": "bot",
        "dontOpenticket": True,
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(DIGISAC_SEND_URL, json=body, headers=headers)

    try:
        data = r.json()
    except:
        data = r.text

    return r.status_code // 100 == 2, data
