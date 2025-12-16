import httpx
from fastapi import HTTPException

async def buscar_titulo_omie(id_titulo: int):
    url = f"{OMIE_BASE_URL}/financas/contareceber/"
    body = {
        "call": "ConsultarContaReceber",
        "app_key": OMIE_APP_KEY,
        "app_secret": OMIE_APP_SECRET,
        "param": [{"nCodTitulo": id_titulo}],
    }

    headers = {
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Se der 403, fica bem claro para você no log
            detail = f"Erro ao chamar Omie (ConsultarContaReceber): {exc.response.status_code} - {exc.response.text[:300]}"
            raise HTTPException(status_code=502, detail=detail)

    return r.json()
