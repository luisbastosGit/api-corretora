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
    banco_de_tickets[ticket_id] = {"status": "iniciando navegador"}
    print(f"[{ticket_id}] Iniciando robô para o cliente: {dados_cliente['nome']}")
    
    USUARIO_AGG = os.getenv("AGG_USUARIO")
    SENHA_AGG = os.getenv("AGG_SENHA")

    if not USUARIO_AGG or not SENHA_AGG:
        banco_de_tickets[ticket_id] = {"status": "erro", "erro": "Credenciais ausentes."}
        return

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = await context.new_page()

            # --- LOGIN ---
            await page.goto("https://aggilizador.com.br/login")
            await page.locator("input[type='email']").fill(USUARIO_AGG)
            await page.locator("input[type='password']").fill(SENHA_AGG)
            await page.locator("button:has-text('Entrar')").click()
            
            # Aguarda a transição do login
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3) # Delay de segurança pós-login

            # --- O SALTO ---
            print(f"[{ticket_id}] Saltando para o formulário...")
            await page.goto("https://aggilizador.com.br/cotacao/auto/formulario")
            
            # Delay estratégico para o Angular "tentar" carregar
            await asyncio.sleep(4) 
            
            print(f"[{ticket_id}] Aplicando Refresh (F5) para destravar componentes...")
            await page.reload(wait_until="networkidle")
            
            # --- PREENCHIMENTO COM ESPERA ATIVA ---
            try:
                print(f"[{ticket_id}] Aguardando campo CPF (máx 20s)...")
                cpf_locator = page.locator('[data-testid="input_cpf-cnpj"]')
                
                # Espera o campo ficar visível e estável
                await cpf_locator.wait_for(state="visible", timeout=20000)
                await asyncio.sleep(1) # Pequena pausa para garantir que o JS anexou os eventos ao campo
                
                print(f"[{ticket_id}] SUCESSO! Inserindo dados...")
                await cpf_locator.click() # Clicar antes de preencher ajuda em campos Angular
                await cpf_locator.fill(dados_cliente['cpf'])
                await page.keyboard.press("Tab") 
                
                # Aguarda o processamento do CPF pelo sistema
                nome_locator = page.locator('[data-testid="input_nome-segurado"]')
                tentativas = 0
                while tentativas < 20:
                    nome_atual = await nome_locator.input_value()
                    if nome_atual and len(nome_atual) > 2:
                        print(f"[{ticket_id}] Dados do cliente recuperados: {nome_atual}")
                        break
                    await asyncio.sleep(1)
                    tentativas += 1
                
                if tentativas == 20:
                    await nome_locator.fill(dados_cliente['nome'])

                # Demais campos com pequenas esperas entre eles
                await page.get_by_label("Telefone").fill(dados_cliente['telefone'])
                await asyncio.sleep(0.5)
                await page.get_by_label("Email").fill(dados_cliente['email'])
                await asyncio.sleep(0.5)
                await page.get_by_label("Placa").fill(dados_cliente['placa'])
                await page.keyboard.press("Tab")
                
                print(f"[{ticket_id}] Preenchimento concluído com sucesso.")

            except Exception as loc_erro:
                print(f"[{ticket_id}] Erro de carregamento/delay: {loc_erro}")

            await asyncio.sleep(5)
            await browser.close()
            banco_de_tickets[ticket_id] = {"status": "concluido", "link_pdf": "OK"}

    except Exception as e:
        print(f"[{ticket_id}] ERRO: {e}")
        banco_de_tickets[ticket_id] = {"status": "erro", "erro": str(e)}

@app.post("/api/iniciar-cotacao")
async def iniciar_cotacao(dados: DadosCotacao, background_tasks: BackgroundTasks):
    ticket_id = str(uuid.uuid4())
    banco_de_tickets[ticket_id] = {"status": "processando"}
    background_tasks.add_task(tarefa_do_robo, ticket_id, dados.dict())
    return {"ticket": ticket_id, "mensagem": "Processo iniciado!"}

@app.get("/api/status-cotacao/{ticket_id}")
async def checar_status(ticket_id: str):
    return banco_de_tickets.get(ticket_id, {"erro": "Não encontrado."})
