import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
import httpx

app = FastAPI()

# --------------------------------------------------------------
# VARIÁVEIS DE AMBIENTE (Railway)
# --------------------------------------------------------------
OMIE_APP_KEY = os.getenv("OMIE_APP_KEY")
OMIE_APP_SECRET = os.getenv("OMIE_APP_SECRET")

DIGISAC_SEND_URL = os.getenv("DIGISAC_SEND_URL")
DIGISAC_TOKEN = os.getenv("DIGISAC_TOKEN")
DIGISAC_SERVICE_ID = os.getenv("DIGISAC_SERVICE_ID")

OMIE_BASE_URL = "https://app.omie.com.br/api/v1"

HEADERS_JSON = {"Content-Type": "application/json"}


@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Webhook Omie → DigiSac ativo"}


# --------------------------------------------------------------
# ENDPOINT PRINCIPAL DO WEBHOOK
# --------------------------------------------------------------
@app.post("/webhooks/omie/contas")
async def omie_webhook(payload: Dict[str, Any]):

    assunto = payload.get("assunto", "")
    if "Financas.ContaReceber" not in assunto:
        return {"ok": True, "ignored": True}

    dados = payload.get("dados", {})

    titulo_id = (
        dados.get("nCodTitulo")
        or dados.get("codigo_lancamento_omie")
        or dados.get("codigo_titulo")
    )

    if not titulo_id:
        raise HTTPException(400, "Webhook Omie sem código de título")

    # ----------------------------------------------------------
    # 1) Buscar título no Omie
    # ----------------------------------------------------------
    titulo = await omie_buscar_titulo(titulo_id)

    boleto_info = titulo.get("boleto") or {}

    if boleto_info.get("cGerado") != "S":
        # Título ainda não possui boleto gerado
        return {"ok": True, "boleto": False}

    # ----------------------------------------------------------
    # 2) Buscar dados completos do boleto
    # ----------------------------------------------------------
    boleto = await omie_obter_boleto(titulo_id)

    # ----------------------------------------------------------
    # 3) Buscar cliente no Omie
    # ----------------------------------------------------------
    cliente_id = (
        titulo.get("codigo_cliente_omie")
        or titulo.get("nCodCliente")
        or titulo.get("codigo_cliente")
    )

    if not cliente_id:
        raise HTTPException(400, "Título sem cliente associado")

    cliente = await omie_buscar_cliente(cliente_id)

    nome_cliente, celular = extrair_dados_cliente(cliente)

    if not celular:
        return {
            "ok": False,
            "reason": "Cliente sem número válido",
            "cliente_id": cliente_id,
        }

    # ----------------------------------------------------------
    # 4) Montar mensagem
    # ----------------------------------------------------------
    mensagem = montar_mensagem_boleto(nome_cliente, boleto)

    # ----------------------------------------------------------
    # 5) Enviar para DigiSac
    # ----------------------------------------------------------
    enviado, resposta = await digisac_enviar(celular, mensagem)

    return {
        "ok": enviado,
        "cliente_whatsapp": celular,
        "titulo": titulo_id,
        "digisac_resposta": resposta,
    }


# --------------------------------------------------------------
# FUNÇÕES OMIE
# --------------------------------------------------------------
async def omie_buscar_titulo(titulo_id: int):
    url = f"{OMIE_BASE_URL}/financas/contareceber/"

    body = {
        "call": "ConsultarContaReceber",
        "app_key": OMIE_APP_KEY,
        "app_secret": OMIE_APP_SECRET,
        "param": [{"nCodTitulo": titulo_id}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=body, headers=HEADERS_JSON)
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                502,
                detail=f"Erro ao consultar título no Omie: {exc.response.status_code} - {exc.response.text[:300]}"
            )

    return r.json()


async def omie_obter_boleto(titulo_id: int):
    url = f"{OMIE_BASE_URL}/financas/contareceberboleto/"

    body = {
        "call": "ObterBoleto",
        "app_key": OMIE_APP_KEY,
        "app_secret": OMIE_APP_SECRET,
        "param": [{"nCodTitulo": titulo_id}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=body, headers=HEADERS_JSON)
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                502,
                detail=f"Erro ao obter boleto no Omie: {exc.response.status_code} - {exc.response.text[:300]}"
            )

    data = r.json()

    return {
        "vencimento": data.get("dDtVenc"),
        "valor": data.get("nValorTitulo"),
        "linha": data.get("cLinhaDigitavel"),
        "link": data.get("cUrlBoleto"),
    }


async def omie_buscar_cliente(cliente_id: int):
    url = f"{OMIE_BASE_URL}/geral/clientes/"

    body = {
        "call": "ConsultarCliente",
        "app_key": OMIE_APP_KEY,
        "app_secret": OMIE_APP_SECRET,
        "param": [{"codigo_cliente_omie": cliente_id}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=body, headers=HEADERS_JSON)
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                502,
                detail=f"Erro ao consultar cliente no Omie: {exc.response.status_code} - {exc.response.text[:300]}"
            )

    return r.json()


# --------------------------------------------------------------
# TRATAMENTO DO CLIENTE (Extração do WhatsApp)
# --------------------------------------------------------------
def extrair_dados_cliente(cliente: Dict[str, Any]):
    nome = (
        cliente.get("razao_social")
        or cliente.get("nome_fantasia")
        or cliente.get("nome")
    )

    ddd = cliente.get("telefone1_ddd")
    numero = cliente.get("telefone1_numero")

    celular = None
    if ddd and numero:
        raw = f"55{ddd}{numero}"
        celular = "".join(c for c in raw if c.isdigit())

    return nome, celular


# --------------------------------------------------------------
# MENSAGEM PARA DIGISAC
# --------------------------------------------------------------
def montar_mensagem_boleto(nome: str, boleto: Dict[str, Any]) -> str:
    return (
        f"Olá {nome}, sua fatura está disponível para pagamento.\n\n"
        f"Vencimento: {boleto.get('vencimento')}\n"
        f"Valor: R$ {boleto.get('valor')}\n"
        f"Linha digitável: {boleto.get('linha')}\n"
        f"Link do boleto: {boleto.get('link')}\n\n"
        "Caso já tenha pago, favor desconsiderar."
    )


# --------------------------------------------------------------
# ENVIO PARA DIGISAC
# --------------------------------------------------------------
async def digisac_enviar(numero: str, texto: str):

    if not DIGISAC_SEND_URL or not DIGISAC_TOKEN:
        raise HTTPException(500, "Configuração da DigiSac ausente")

    body = {
        "number": numero,
        "text": texto,
        "serviceId": DIGISAC_SERVICE_ID,
        "origin": "bot",
        "dontOpenticket": True,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DIGISAC_TOKEN}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(DIGISAC_SEND_URL, json=body, headers=headers)
        except Exception as exc:
            return False, f"Erro ao chamar DigiSac: {exc}"

    try:
        data = r.json()
    except:
        data = r.text

    return r.status_code // 100 == 2, data
