import os
import uuid
import asyncio
import httpx
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI(title="API Corretora - Motor de API Híbrido")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

banco_de_tickets = {}

class DadosCotacao(BaseModel):
    nome: str
    cpf: str
    placa: str
    email: str
    telefone: str
    pacote_escolhido: str

async def tarefa_do_robo(ticket_id: str, dados_cliente: dict):
    banco_de_tickets[ticket_id] = {"status": "autenticando"}
    
    USUARIO_AGG = os.getenv("AGG_USUARIO")
    SENHA_AGG = os.getenv("AGG_SENHA")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            token_jwt = None

            # Captura o token de autorização durante o login
            async def interceptar_token(request):
                nonlocal token_jwt
                auth = request.headers.get("authorization")
                if auth and "eyJ" in auth:
                    token_jwt = auth

            page.on("request", interceptar_token)

            # --- LOGIN ---
            await page.goto("https://aggilizador.com.br/login")
            await page.locator("input[type='email']").fill(USUARIO_AGG)
            await page.locator("input[type='password']").fill(SENHA_AGG)
            await page.locator("button:has-text('Entrar')").click()
            
            # Aguarda o token por até 10s
            for _ in range(10):
                if token_jwt: break
                await asyncio.sleep(1)

            await browser.close()

            if not token_jwt:
                raise Exception("Falha na captura do Token JWT.")

            print(f"[{ticket_id}] Autenticado. Iniciando cálculos via API...")
            banco_de_tickets[ticket_id] = {"status": "calculando"}

            # --- CÁLCULO DIRETO VIA API ---
            # Aqui usamos o 'httpx' para enviar o JSON que você capturou
            async with httpx.AsyncClient() as client:
                headers = {
                    "authorization": token_jwt,
                    "content-type": "application/json",
                    "origin": "https://aggilizador.com.br"
                }

                # Montamos o corpo da requisição baseado no seu cURL
                # Nota: Em um sistema real, automatizaremos a busca da FIPE antes deste passo
                payload = {
                    "cotacao": {
                        "segurado": {
                            "nome": dados_cliente['nome'],
                            "cpfCnpj": dados_cliente['cpf'],
                            "fone1": dados_cliente['telefone'],
                            "email": dados_cliente['email'],
                            "tipoPessoa": "F",
                            "sexo": "M" # Padrão para teste
                        },
                        "automoveis": [{
                            "placa": dados_cliente['placa'],
                            "fipe": "0242349", # Exemplo fixo da sua captura
                            "cepPernoite": "89703166"
                        }],
                        "tipo": 5,
                        "ramo": 31
                    }
                }

                response = await client.post(
                    "https://api-prod.aggilizador.com.br/calculo/calcularV2",
                    json=payload,
                    headers=headers,
                    timeout=60.0
                )

                if response.status_code == 200:
                    resultado = response.json()
                    print(f"[{ticket_id}] Cálculo concluído com sucesso!")
                    banco_de_tickets[ticket_id] = {
                        "status": "concluido",
                        "resultados": resultado,
                        "link_pdf": "GERADO_VIA_API"
                    }
                else:
                    print(f"[{ticket_id}] Erro no cálculo: {response.text}")
                    raise Exception(f"Erro API: {response.status_code}")

    except Exception as e:
        print(f"[{ticket_id}] ERRO: {e}")
        banco_de_tickets[ticket_id] = {"status": "erro", "erro": str(e)}

@app.post("/api/iniciar-cotacao")
async def iniciar_cotacao(dados: DadosCotacao, background_tasks: BackgroundTasks):
    ticket_id = str(uuid.uuid4())
    banco_de_tickets[ticket_id] = {"status": "processando"}
    background_tasks.add_task(tarefa_do_robo, ticket_id, dados.dict())
    return {"ticket": ticket_id}

@app.get("/api/status-cotacao/{ticket_id}")
async def checar_status(ticket_id: str):
    return banco_de_tickets.get(ticket_id, {"erro": "Não encontrado"})
