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
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
            context = await browser.new_context()
            page = await context.new_page()

            # Bloqueia lixo visual para salvar RAM
            await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,pdf,css}", lambda route: route.abort())

            # --- LOGIN ---
            print(f"[{ticket_id}] Acessando página de login...")
            await page.goto("https://aggilizador.com.br/login", wait_until="domcontentloaded")
            
            # Preenche usando type (mais lento/humano) em vez de fill
            await page.locator("input[type='email']").type(USUARIO_AGG, delay=50)
            await page.locator("input[type='password']").type(SENHA_AGG, delay=50)
            
            print(f"[{ticket_id}] Disparando login via teclado...")
            await page.keyboard.press("Enter")
            
            # Tenta capturar o token por 20 segundos
            token_jwt = None
            for i in range(20):
                token_jwt = await page.evaluate("""() => {
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        const val = localStorage.getItem(key);
                        if (val && val.includes('eyJ')) return val;
                    }
                    return null;
                }""")
                if token_jwt: break
                await asyncio.sleep(1)

            if not token_jwt:
                # Se falhar, vamos ver se há mensagem de erro na tela
                msg_erro = await page.locator(".mat-error, .alert").text_content() if await page.locator(".mat-error, .alert").count() > 0 else "Nenhuma msg visível"
                raise Exception(f"Token não capturado. Erro na tela: {msg_erro}")

            # Limpa o token se ele vier como objeto JSON
            if '"token":"' in token_jwt:
                import json
                try: token_jwt = json.loads(token_jwt)['token']
                except: pass
            
            token_jwt = token_jwt.replace('"', '')
            print(f"[{ticket_id}] Autenticado! Iniciando API de cálculo...")
            await browser.close()

            # --- CÁLCULO VIA API ---
            banco_de_tickets[ticket_id] = {"status": "calculando"}
            async with httpx.AsyncClient() as client:
                headers = {
                    "authorization": f"Bearer {token_jwt}" if "eyJ" in token_jwt else token_jwt,
                    "content-type": "application/json",
                    "origin": "https://aggilizador.com.br"
                }

                payload = {
                    "cotacao": {
                        "segurado": {
                            "nome": dados_cliente['nome'],
                            "cpfCnpj": dados_cliente['cpf'],
                            "fone1": dados_cliente['telefone'],
                            "email": dados_cliente['email'],
                            "tipoPessoa": "F", "sexo": "M"
                        },
                        "automoveis": [{
                            "placa": dados_cliente['placa'],
                            "fipe": "0242349",
                            "cepPernoite": "89703166",
                            "anoFabricacao": 2018, "anoModelo": 2019
                        }],
                        "tipo": 5, "ramo": 31
                    }
                }

                response = await client.post(
                    "https://api-prod.aggilizador.com.br/calculo/calcularV2",
                    json=payload, headers=headers, timeout=60.0
                )

                if response.status_code in [200, 201]:
                    banco_de_tickets[ticket_id] = {"status": "concluido", "resultados": response.json()}
                    print(f"[{ticket_id}] Sucesso!")
                else:
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
