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
            context = await browser.new_context()
            page = await context.new_page()

            # --- LOGIN ---
            print(f"[{ticket_id}] Fazendo login...")
            await page.goto("https://aggilizador.com.br/login")
            await page.locator("input[type='email']").fill(USUARIO_AGG)
            await page.locator("input[type='password']").fill(SENHA_AGG)
            await page.locator("button:has-text('Entrar')").click()
            
            # Aguarda o redirecionamento pós-login para o Dashboard
            await page.wait_for_url("**/cotacoes", timeout=30000)
            print(f"[{ticket_id}] Dashboard alcançado. Extraindo credenciais da memória...")

            # --- EXTRAÇÃO ATIVA DO TOKEN ---
            # Este script busca o token no LocalStorage do navegador
            token_jwt = await page.evaluate("""() => {
                const authData = localStorage.getItem('auth-storage'); // Nome comum em apps Angular
                if (authData) return JSON.parse(authData).token;
                
                // Plano B: Tentar todas as chaves do LocalStorage que pareçam JWT
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    const val = localStorage.getItem(key);
                    if (val && val.includes('eyJ')) return val.replace(/\"/g, "");
                }
                return null;
            }""")

            if not token_jwt:
                raise Exception("Token JWT não encontrado no LocalStorage após login.")

            # Limpeza do token (garante que não tenha 'Bearer ' duplicado)
            if not token_jwt.startswith("eyJ"):
                 token_jwt = token_jwt.split(" ")[-1]

            print(f"[{ticket_id}] Token extraído com sucesso!")
            await browser.close()

            # --- CÁLCULO VIA API ---
            banco_de_tickets[ticket_id] = {"status": "calculando"}
            async with httpx.AsyncClient() as client:
                headers = {
                    "authorization": f"{token_jwt}",
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
                            "tipoPessoa": "F",
                            "sexo": "M"
                        },
                        "automoveis": [{
                            "placa": dados_cliente['placa'],
                            "fipe": "0242349",
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
                    print(f"[{ticket_id}] Cálculo finalizado via API!")
                else:
                    raise Exception(f"Erro API: {response.status_code} - {response.text}")

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
