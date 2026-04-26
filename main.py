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
            # Criamos um contexto com um User-Agent comum para evitar bloqueios
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = await context.new_page()

            token_jwt = None

            # Captura o token de forma mais agressiva em qualquer requisição de saída
            async def interceptar_token(request):
                nonlocal token_jwt
                # Procuramos o cabeçalho de autorização em requisições para a API
                if "api-prod" in request.url:
                    auth = request.headers.get("authorization")
                    if auth and "eyJ" in auth:
                        token_jwt = auth
                        print(f"[{ticket_id}] TOKEN CAPTURADO via: {request.url}")

            page.on("request", interceptar_token)

            # --- LOGIN ---
            print(f"[{ticket_id}] Fazendo login para capturar sessão...")
            await page.goto("https://aggilizador.com.br/login")
            await page.locator("input[type='email']").fill(USUARIO_AGG)
            await page.locator("input[type='password']").fill(SENHA_AGG)
            await page.locator("button:has-text('Entrar')").click()
            
            # ESPERA ATIVA: Aguarda o token por até 30 segundos ou até a página mudar
            for _ in range(30):
                if token_jwt: break
                await asyncio.sleep(1)

            if not token_jwt:
                # Se falhar, tentamos esperar o carregamento final da rede
                await page.wait_for_load_state("networkidle")
                if not token_jwt:
                    raise Exception("O Token JWT não apareceu no tráfego de rede.")

            print(f"[{ticket_id}] Autenticado com sucesso. Iniciando API...")
            await browser.close() # Já temos o token, não precisamos mais do navegador

            # --- CÁLCULO VIA API (HTTPX) ---
            banco_de_tickets[ticket_id] = {"status": "calculando"}
            async with httpx.AsyncClient() as client:
                headers = {
                    "authorization": token_jwt,
                    "content-type": "application/json",
                    "origin": "https://aggilizador.com.br",
                    "referer": "https://aggilizador.com.br/"
                }

                # Payload baseado no seu cURL anterior
                payload = {
                    "cotacao": {
                        "segurado": {
                            "nome": dados_cliente['nome'],
                            "cpfCnpj": dados_cliente['cpf'],
                            "fone1": dados_cliente['telefone'],
                            "email": dados_cliente['email'],
                            "tipoPessoa": "F",
                            "sexo": "M"
                        },
                        "automoveis": [{
                            "placa": dados_cliente['placa'],
                            "fipe": "0242349", # Valor temporário
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

                if response.status_code in [200, 201]:
                    banco_de_tickets[ticket_id] = {
                        "status": "concluido",
                        "resultados": response.json(),
                        "link_pdf": "OK"
                    }
                    print(f"[{ticket_id}] Sucesso total via API!")
                else:
                    raise Exception(f"Erro no cálculo: {response.status_code} - {response.text}")

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
