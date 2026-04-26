import os
import uuid
import asyncio
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI(title="API Corretora - Motor de Scraping Híbrido")

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
    print(f"[{ticket_id}] Iniciando motor de scraping para: {dados_cliente['nome']}")
    
    USUARIO_AGG = os.getenv("AGG_USUARIO")
    SENHA_AGG = os.getenv("AGG_SENHA")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            token_jwt = None

            # --- MONITOR DE TRÁFEGO ---
            # Esta função intercepta as conversas do navegador e rouba o Token de Autorização
            async def interceptar_token(request):
                nonlocal token_jwt
                headers = request.headers
                if "authorization" in headers and "eyJ" in headers["authorization"]:
                    token_jwt = headers["authorization"]

            page.on("request", interceptar_token)

            # --- LOGIN PARA GERAR TOKEN ---
            print(f"[{ticket_id}] Gerando sessão no Aggilizador...")
            await page.goto("https://aggilizador.com.br/login")
            await page.locator("input[type='email']").fill(USUARIO_AGG)
            await page.locator("input[type='password']").fill(SENHA_AGG)
            await page.locator("button:has-text('Entrar')").click()
            
            # Aguardamos o token aparecer na rede (geralmente ocorre logo após o login)
            for _ in range(10): 
                if token_jwt: break
                await asyncio.sleep(1)

            if not token_jwt:
                raise Exception("Não foi possível capturar o token de acesso.")

            print(f"[{ticket_id}] Token capturado com sucesso!")
            banco_de_tickets[ticket_id] = {"status": "consultando_api"}

            # --- SCRAPING DIRETO (API) ---
            # Agora não precisamos mais clicar em nada! Enviamos o CPF direto para a API.
            print(f"[{ticket_id}] Consultando dados do CPF via API interna...")
            
            # Simulamos a chamada que você me mandou no cURL
            # Em produção, usaremos 'httpx' ou o próprio 'page.request' do Playwright
            url_api = f"https://api-prod.aggilizador.com.br/cadastros/cliente?cpfCnpj={dados_cliente['cpf']}&simplificado=true"
            
            headers_api = {
                "authorization": token_jwt,
                "accept": "application/json",
                "content-type": "application/json",
                "origin": "https://aggilizador.com.br",
                "referer": "https://aggilizador.com.br/"
            }

            api_context = page.request
            response = await api_context.get(url_api, headers=headers_api)
            
            if response.ok:
                dados_retorno = await response.json()
                print(f"[{ticket_id}] Dados recuperados da API: {dados_retorno.get('nome', 'N/A')}")
                
                # --- PRÓXIMO PASSO: REPLICAR O CÁLCULO ---
                # Aqui o robô enviará o POST de cálculo usando o mesmo Token
                print(f"[{ticket_id}] Iniciando processamento de cálculo...")
                
                # Simulação de finalização com sucesso
                await asyncio.sleep(2)
                banco_de_tickets[ticket_id] = {
                    "status": "concluido",
                    "mensagem": f"Cotação processada via API para {dados_cliente['nome']}",
                    "link_pdf": "PENDENTE_MAPEAR_POST_CALCULO"
                }
            else:
                raise Exception(f"Erro na API do Aggilizador: {response.status}")

            await browser.close()

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
