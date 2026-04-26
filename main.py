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

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # --- PASSO 1: SCRAPING DE LOGIN (DIRETO NA API) ---
            print(f"[{ticket_id}] Solicitando Token de Acesso via API...")
            
            payload_login = {
                "email": USUARIO_AGG,
                "password": SENHA_AGG,
                "aplicacaoId": 4 # ID padrão do Aggilizador Web
            }
            
            # O Aggilizador usa este endpoint para validar logins
            res_login = await client.post(
                "https://api-prod.aggilizador.com.br/auth/login", 
                json=payload_login
            )
            
            if res_login.status_code != 200:
                raise Exception(f"Falha na autenticação API: {res_login.status_code}")
            
            token_jwt = res_login.json().get("token")
            print(f"[{ticket_id}] Autenticação via Scraping de API bem-sucedida!")

            # --- PASSO 2: SCRAPING DE CÁLCULO ---
            banco_de_tickets[ticket_id] = {"status": "calculando"}
            
            headers = {
                "authorization": f"Bearer {token_jwt}",
                "content-type": "application/json",
                "origin": "https://aggilizador.com.br"
            }

            # Payload estruturado com base no seu cURL anterior
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
                        "fipe": "0242349", # Valor de referência do seu teste
                        "cepPernoite": "89703166",
                        "anoFabricacao": 2018, "anoModelo": 2019
                    }],
                    "tipo": 5, "ramo": 31
                }
            }

            print(f"[{ticket_id}] Disparando multicalculo...")
            res_calc = await client.post(
                "https://api-prod.aggilizador.com.br/calculo/calcularV2",
                json=payload_calc,
                headers=headers
            )

            if res_calc.status_code in [200, 201]:
                print(f"[{ticket_id}] Cálculo finalizado com sucesso!")
                banco_de_tickets[ticket_id] = {
                    "status": "concluido",
                    "resultados": res_calc.json(),
                    "mensagem": "Cotação processada em tempo recorde."
                }
            else:
                raise Exception(f"Erro no cálculo API: {res_calc.status_code} - {res_calc.text}")

    except Exception as e:
        print(f"[{ticket_id}] ERRO NO SCRAPING: {e}")
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
