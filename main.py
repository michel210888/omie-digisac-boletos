import os
import httpx
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()


# ===============================
# FUNÇÃO: BUSCAR TÍTULO NO OMIE
# ===============================
async def buscar_titulo_omie(codigo_lancamento_omie: int):
    OMIE_APP_KEY = os.getenv("2725566274431")
    OMIE_APP_SECRET = os.getenv("b475d9536c02348d9b16462fb1620c9f")

    if not OMIE_APP_KEY or not OMIE_APP_SECRET:
        raise HTTPException(
            status_code=500,
            detail="OMIE_APP_KEY ou OMIE_APP_SECRET não configurados"
        )

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://app.omie.com.br/api/v1/financas/contareceber/",
            json={
                "call": "ConsultarContaReceberPorCodigo",
                "app_key": OMIE_APP_KEY,
                "app_secret": OMIE_APP_SECRET,
                "param": [
                    {"codigo_lancamento_omie": codigo_lancamento_omie}
                ]
            }
        )

        if response.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail="403 Omie: verifique permissões da API"
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        return response.json()


# ===============================
# FUNÇÃO: ENVIAR PARA DIGISAC
# ===============================
async def enviar_boleto_digisac(titulo: dict):
    DIGISAC_API_URL = os.getenv("https://api.digisac.com.br/v1/messages")
    DIGISAC_TOKEN = os.getenv("daf1131f232778f865cb2aed3413bf54c76dd913")

    if not DIGISAC_API_URL or not DIGISAC_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="DIGISAC_API_URL ou DIGISAC_TOKEN não configurados"
        )

    valor = titulo.get("valor_documento")
    vencimento = titulo.get("data_vencimento")
    codigo_barras = titulo.get("codigo_barras_ficha_compensacao")

    mensagem = (
        f"📄 *Boleto Disponível*\n\n"
        f"💰 Valor: R$ {valor:.2f}\n"
        f"📅 Vencimento: {vencimento}\n\n"
        f"🔢 Código de Barras:\n{codigo_barras}"
    )

    payload = {
        "number": "SEU_NUMERO_TESTE",  # depois ligamos ao telefone real
        "message": mensagem
    }

    headers = {
        "Authorization": f"Bearer {DIGISAC_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{DIGISAC_API_URL}/messages/send",
            json=payload,
            headers=headers
        )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        return response.json()


# ===============================
# WEBHOOK OMIE
# ===============================
@app.post("/webhooks/omie/contas")
async def omie_webhook(request: Request):
    body = await request.json()

    codigo_lancamento = body.get("dados", {}).get("codigo_lancamento_omie")

    if not codigo_lancamento:
        raise HTTPException(
            status_code=400,
            detail="codigo_lancamento_omie não informado"
        )

    titulo = await buscar_titulo_omie(codigo_lancamento)
    digisac = await enviar_boleto_digisac(titulo)

    return {
        "ok": True,
        "codigo_lancamento": codigo_lancamento,
        "digisac": digisac
    }


# ===============================
# HEALTHCHECK
# ===============================
@app.get("/")
def health():
    return {"status": "online"}

            raise HTTPException(
                status_code=403,
                detail="403 Omie: verifique permissões da API"
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        return response.json()


# ===============================
# FUNÇÃO: ENVIAR PARA DIGISAC
# ===============================
async def enviar_boleto_digisac(titulo: dict):
    DIGISAC_API_URL = os.getenv("DIGISAC_API_URL")
    DIGISAC_TOKEN = os.getenv("DIGISAC_TOKEN")

    if not DIGISAC_API_URL or not DIGISAC_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="DIGISAC_API_URL ou DIGISAC_TOKEN não configurados"
        )

    valor = titulo.get("valor_documento")
    vencimento = titulo.get("data_vencimento")
    codigo_barras = titulo.get("codigo_barras_ficha_compensacao")

    mensagem = (
        f"📄 *Boleto Disponível*\n\n"
        f"💰 Valor: R$ {valor:.2f}\n"
        f"📅 Vencimento: {vencimento}\n\n"
        f"🔢 Código de Barras:\n{codigo_barras}"
    )

    payload = {
        "number": "SEU_NUMERO_TESTE",  # depois ligamos ao telefone real
        "message": mensagem
    }

    headers = {
        "Authorization": f"Bearer {DIGISAC_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{DIGISAC_API_URL}/messages/send",
            json=payload,
            headers=headers
        )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        return response.json()


# ===============================
# WEBHOOK OMIE
# ===============================
@app.post("/webhooks/omie/contas")
async def omie_webhook(request: Request):
    body = await request.json()

    codigo_lancamento = body.get("dados", {}).get("codigo_lancamento_omie")

    if not codigo_lancamento:
        raise HTTPException(
            status_code=400,
            detail="codigo_lancamento_omie não informado"
        )

    titulo = await buscar_titulo_omie(codigo_lancamento)
    digisac = await enviar_boleto_digisac(titulo)

    return {
        "ok": True,
        "codigo_lancamento": codigo_lancamento,
        "digisac": digisac
    }


# ===============================
# HEALTHCHECK
# ===============================
@app.get("/")
def health():
    return {"status": "online"}

