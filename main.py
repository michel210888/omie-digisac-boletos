import os
import httpx
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()


# ===============================
# HEALTHCHECK
# ===============================
@app.get("/")
def health():
    return {"status": "online"}


# ===============================
# WEBHOOK OMIE
# ===============================
@app.post("/webhooks/omie/contas")
async def omie_webhook(request: Request):
    body = await request.json()
    dados = body.get("dados", {})

    codigo_lancamento = dados.get("codigo_lancamento_omie")
    if not codigo_lancamento:
        raise HTTPException(
            400,
            "Webhook Omie não enviou codigo_lancamento_omie"
        )

    titulo = await buscar_titulo_por_codigo(codigo_lancamento)

    return {
        "ok": True,
        "titulo": {
            "codigo_lancamento_omie": titulo.get("codigo_lancamento_omie"),
            "numero_documento": titulo.get("numero_documento"),
            "valor": titulo.get("valor_documento"),
            "vencimento": titulo.get("data_vencimento"),
            "cliente": titulo.get("codigo_cliente_fornecedor")
        }
    }


# ==================================================
# BUSCA DEFINITIVA NO OMIE (COM PAGINAÇÃO)
# ==================================================
async def buscar_titulo_por_codigo(codigo_lancamento_omie: int):
    OMIE_APP_KEY = os.getenv("OMIE_APP_KEY")
    OMIE_APP_SECRET = os.getenv("OMIE_APP_SECRET")

    if not OMIE_APP_KEY or not OMIE_APP_SECRET:
        raise HTTPException(
            500,
            "OMIE_APP_KEY ou OMIE_APP_SECRET não configurados"
        )

    pagina = 1
    limite_paginas = 60  # segurança (60 x 100 = 6.000 títulos)

    async with httpx.AsyncClient(timeout=30) as client:
        while pagina <= limite_paginas:
            r = await client.post(
                "https://app.omie.com.br/api/v1/financas/contareceber/",
                json={
                    "call": "ListarContasReceber",
                    "app_key": OMIE_APP_KEY,
                    "app_secret": OMIE_APP_SECRET,
                    "param": [
                        {
                            "pagina": pagina,
                            "registros_por_pagina": 100,
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
                break

            for titulo in lista:
                if titulo.get("codigo_lancamento_omie") == codigo_lancamento_omie:
                    return titulo

            total_paginas = data.get("total_de_paginas", 1)
            if pagina >= total_paginas:
                break

            pagina += 1

    raise HTTPException(
        404,
        "Título não encontrado no Omie após varrer todas as páginas"
    )
