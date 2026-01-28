import os
import httpx
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

OMIE_APP_KEY = os.getenv("2725566274431")
OMIE_APP_SECRET = os.getenv("b475d9536c02348d9b16462fb1620c9f")

DIGISAC_TOKEN = os.getenv("DIGISAC_TOKEN")
DIGISAC_SEND_URL = os.getenv("DIGISAC_SEND_URL")

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/webhooks/omie/contas")
async def omie_webhook(request: Request):
    payload = await request.json()

    assunto = payload.get("assunto", "")
    if "Financas.ContaReceber" not in assunto:
        return {"ok": True, "ignored": True}

    dados = payload.get("dados", {})
    codigo_lancamento = dados.get("codigo_lancamento_omie")

    if not codigo_lancamento:
        raise HTTPException(400, "codigo_lancamento_omie ausente")

    titulo = await buscar_titulo_omie(codigo_lancamento)

    cliente_id = (
        titulo.get("codigo_cliente_fornecedor")
        or titulo.get("codigo_cliente")
    )

    boleto = titulo.get("boleto", {})
    if boleto.get("cGerado") != "S":
        return {"ok": True, "boleto": False}

    linha_digitavel = titulo.get("codigo_barras_ficha_compensacao")

    telefone = await buscar_telefone_cliente(cliente_id)
    if not telefone:
        raise HTTPException(400, "Cliente sem telefone válido")

    if not DIGISAC_TOKEN or not DIGISAC_SEND_URL:
        raise HTTPException(500, "Configuração da DigiSac ausente (URL ou TOKEN).")

    msg = (
        f"Olá! Seu boleto está disponível.\n\n"
        f"Valor: R$ {titulo.get('valor_documento')}\n"
        f"Vencimento: {titulo.get('data_vencimento')}\n\n"
        f"Linha digitável:\n{linha_digitavel}"
    )

    async with httpx.AsyncClient() as client:
        r = await client.post(
            DIGISAC_SEND_URL,
            headers={
                "Authorization": f"Bearer {DIGISAC_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "to": telefone,
                "text": msg
            }
        )
        r.raise_for_status()

    return {"ok": True, "telefone": telefone}


async def buscar_titulo_omie(codigo_lancamento):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://app.omie.com.br/api/v1/financas/contareceber/",
            json={
                "call": "ConsultarContaReceber",
                "app_key": OMIE_APP_KEY,
                "app_secret": OMIE_APP_SECRET,
                "param": [
                    {"codigo_lancamento_omie": codigo_lancamento}
                ]
            }
        )
        r.raise_for_status()
        return r.json()


async def buscar_telefone_cliente(codigo_cliente):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://app.omie.com.br/api/v1/geral/clientes/",
            json={
                "call": "ConsultarCliente",
                "app_key": OMIE_APP_KEY,
                "app_secret": OMIE_APP_SECRET,
                "param": [
                    {"codigo_cliente_omie": codigo_cliente}
                ]
            }
        )
        r.raise_for_status()
        data = r.json()
        tel = data.get("telefone1") or data.get("telefone2")
        if tel:
            tel = tel.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")
            if not tel.startswith("55"):
                tel = "55" + tel
        return tel
