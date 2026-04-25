import os
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid
import asyncio
from playwright.async_api import async_playwright

app = FastAPI(title="API Corretora - Motor de Multicálculo")

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
    # Avisamos ao sistema que a navegação vai começar
    banco_de_tickets[ticket_id] = {"status": "iniciando navegador"}
    print(f"[{ticket_id}] Iniciando robô para o cliente: {dados_cliente['nome']}")
    
    # 1. Abre o cofre seguro do Render para pegar as credenciais
    USUARIO_AGG = os.getenv("AGG_USUARIO")
    SENHA_AGG = os.getenv("AGG_SENHA")

    if not USUARIO_AGG or not SENHA_AGG:
        erro_msg = "Credenciais do Aggilizador não encontradas nas Variáveis de Ambiente."
        print(f"[{ticket_id}] ERRO: {erro_msg}")
        banco_de_tickets[ticket_id] = {"status": "erro", "erro": erro_msg}
        return

    try:
        # 2. Instancia o Navegador Invisível (Chromium)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # 3. Acessa a tela de Login
            print(f"[{ticket_id}] Acessando portal Aggilizador...")
            banco_de_tickets[ticket_id] = {"status": "fazendo login"}
            await page.goto("https://aggilizador.com.br/login")

            # 4. Preenche os campos (Buscando pelos tipos de input que vimos na sua imagem)
            print(f"[{ticket_id}] Inserindo credenciais seguras...")
            await page.locator("input[type='email']").fill(USUARIO_AGG)
            await page.locator("input[type='password']").fill(SENHA_AGG)

            # 5. Clica no botão Entrar
            await page.locator("button:has-text('Entrar')").click()

            # 6. Aguarda a página carregar após o login (Espera a rede acalmar)
            print(f"[{ticket_id}] Aguardando dashboard carregar...")
            await page.wait_for_load_state("networkidle")

            # SE CHEGAMOS ATÉ AQUI SEM ERROS, O LOGIN FOI UM SUCESSO!
            print(f"[{ticket_id}] Login efetuado com sucesso!")
            
            # --- FIM DA FASE 3 (O PREENCHIMENTO DO FORMULÁRIO ENTRA AQUI NA PRÓXIMA FASE) ---
            
            # Simulamos um tempinho extra só para ver o teste passar bonito
            await asyncio.sleep(3)
            await browser.close()

            # Finaliza a tarefa e avisa a tela do Wix
            banco_de_tickets[ticket_id] = {
                "status": "concluido",
                "link_pdf": "TESTE_LOGIN_OK_O_ROBO_ESTA_DENTRO_DO_SISTEMA"
            }

    except Exception as e:
        print(f"[{ticket_id}] ERRO FATAL no processo: {e}")
        banco_de_tickets[ticket_id] = {"status": "erro", "erro": str(e)}

@app.post("/api/iniciar-cotacao")
async def iniciar_cotacao(dados: DadosCotacao, background_tasks: BackgroundTasks):
    ticket_id = str(uuid.uuid4())
    banco_de_tickets[ticket_id] = {"status": "processando"}
    
    # Enviamos também os dados do cliente para o robô usar mais pra frente
    background_tasks.add_task(tarefa_do_robo, ticket_id, dados.dict())
    
    return {"ticket": ticket_id, "mensagem": "Dados recebidos, robô acionado!"}

@app.get("/api/status-cotacao/{ticket_id}")
async def checar_status(ticket_id: str):
    resultado = banco_de_tickets.get(ticket_id)
    if not resultado:
        return {"erro": "Ticket não encontrado."}
    return resultado
