import os
import httpx
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()


@app.get("/")
def health():
    return {"status": "online"}


@app.post("/webhooks/omie/contas")
async def omie_webhook(request: Request):
    body = await request.json()
    dados = body.get("dados", {})

    numero_documento = dados.get("numero_documento")
    if not numero_documento:
        raise HTTPException(
            400,
            "Webhook Omie não enviou numero_documento (obrigatório)"
        )

    titulo = await buscar_titulo_por_documento(numero_documento)

    return {
        "ok": True,
        "titulo": {
            "numero_documento": titulo.get("numero_documento"),
            "valor": titulo.get("valor_documento"),
            "vencimento": titulo.get("data_vencimento"),
            "cliente": titulo.get("codigo_cliente_fornecedor"),
            "codigo_lancamento_omie": titulo.get("codigo_lancamento_omie")
        }
    }


# ==================================================
# BUSCA CORRETA NO OMIE (CONTRATO REAL)
# ==================================================
async def buscar_titulo_por_documento(numero_documento: str):
    OMIE_APP_KEY = os.getenv("OMIE_APP_KEY")
    OMIE_APP_SECRET = os.getenv("OMIE_APP_SECRET")

    if not OMIE_APP_KEY or not OMIE_APP_SECRET:
        raise HTTPException(
            500,
            "OMIE_APP_KEY ou OMIE_APP_SECRET não configurados"
        )

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://app.omie.com.br/api/v1/financas/contareceber/",
            json={
                "call": "ListarContasReceber",
                "app_key": OMIE_APP_KEY,
                "app_secret": OMIE_APP_SECRET,
                "param": [
                    {
                        "numero_documento": numero_documento,
                        "pagina": 1,
                        "registros_por_pagina": 10,
                        "apenas_importado_api": "N"
                    }
                ]
            }
        )

        if r.status_code == 403:
            raise HTTPException(
                403,
                "Acesso negado ao Omie (verifique permissões)"
            )

        if r.status_code >= 400:
            raise HTTPException(
                r.status_code,
                r.text
            )

        data = r.json()
        lista = data.get("conta_receber_cadastro", [])

        if not lista:
            raise HTTPException(
                404,
                "Título não encontrado no Omie"
            )

        return lista[0]
