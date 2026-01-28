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
    codigo_lancamento = dados.get("codigo_lancamento_omie")

    if not codigo_lancamento:
        raise HTTPException(400, "codigo_lancamento_omie ausente")

    titulo = await buscar_titulo_omie(codigo_lancamento)

    return {
        "ok": True,
        "codigo_lancamento": codigo_lancamento,
        "titulo_resumo": {
            "valor": titulo.get("valor_documento"),
            "vencimento": titulo.get("data_vencimento"),
            "cliente": titulo.get("codigo_cliente_fornecedor")
        }
    }


async def buscar_titulo_omie(codigo_lancamento_omie: int):
    OMIE_APP_KEY = os.getenv("OMIE_APP_KEY")
    OMIE_APP_SECRET = os.getenv("OMIE_APP_SECRET")

    if not OMIE_APP_KEY or not OMIE_APP_SECRET:
        raise HTTPException(500, "OMIE_APP_KEY ou OMIE_APP_SECRET não configurados")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
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

        if r.status_code == 403:
            raise HTTPException(403, "Acesso negado ao Omie (verifique permissões)")

        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)

        return r.json()

