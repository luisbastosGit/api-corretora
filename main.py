import os
import uuid
import asyncio
import httpx
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Corretora - Motor de Scraping Puro")

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
    banco_de_tickets[ticket_id] = {"status": "autenticando_api"}
    
    USUARIO_AGG = os.getenv("AGG_USUARIO")
    SENHA_AGG = os.getenv("AGG_SENHA")

    # Cabeçalhos que imitam o seu navegador Edge/Chrome para evitar o erro 403
    HEADERS_BASE = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Origin": "https://aggilizador.com.br",
        "Referer": "https://aggilizador.com.br/",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # --- PASSO 1: LOGIN ---
            print(f"[{ticket_id}] Solicitando Token via API com Headers Reais...")
            
            payload_login = {
                "email": USUARIO_AGG,
                "password": SENHA_AGG,
                "aplicacaoId": 4
            }
            
            res_login = await client.post(
                "https://api-prod.aggilizador.com.br/auth/login", 
                json=payload_login,
                headers=HEADERS_BASE
            )
            
            if res_login.status_code != 200:
                print(f"[{ticket_id}] Detalhe do Erro {res_login.status_code}: {res_login.text}")
                raise Exception(f"Bloqueio de Segurança (403) ou Credenciais Inválidas.")
            
            token_jwt = res_login.json().get("token")
            print(f"[{ticket_id}] Token obtido com sucesso!")

            # --- PASSO 2: CÁLCULO ---
            banco_de_tickets[ticket_id] = {"status": "calculando"}
            
            headers_auth = HEADERS_BASE.copy()
            headers_auth["Authorization"] = f"Bearer {token_jwt}"

            payload_calc = {
                "cotacao": {
                    "segurado": {
                        "nome": dados_cliente['nome'],
                        "cpfCnpj": dados_cliente['cpf'],
                        "fone1": dados_cliente['telefone'],
                        "email": dados_cliente['email'],
                        "tipoPessoa": "F", "sexo": "M", "cep": "89703166"
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

            res_calc = await client.post(
                "https://api-prod.aggilizador.com.br/calculo/calcularV2",
                json=payload_calc,
                headers=headers_auth
            )

            if res_calc.status_code in [200, 201]:
                banco_de_tickets[ticket_id] = {
                    "status": "concluido",
                    "resultados": res_calc.json()
                }
                print(f"[{ticket_id}] Sucesso!")
            else:
                raise Exception(f"Erro no cálculo: {res_calc.status_code}")

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
