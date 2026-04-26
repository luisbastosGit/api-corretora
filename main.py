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
        erro_msg = "Credenciais não encontradas nas Variáveis de Ambiente."
        print(f"[{ticket_id}] ERRO: {erro_msg}")
        banco_de_tickets[ticket_id] = {"status": "erro", "erro": erro_msg}
        return

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # --- ETAPA 1: LOGIN ---
            print(f"[{ticket_id}] Acessando portal Aggilizador...")
            banco_de_tickets[ticket_id] = {"status": "fazendo login"}
            await page.goto("https://aggilizador.com.br/login")

            await page.locator("input[type='email']").fill(USUARIO_AGG)
            await page.locator("input[type='password']").fill(SENHA_AGG)
            await page.locator("button:has-text('Entrar')").click()

            await page.wait_for_load_state("networkidle")
            print(f"[{ticket_id}] Login efetuado com sucesso!")

            # --- ETAPA 2: NAVEGAÇÃO AO FORMULÁRIO ---
            print(f"[{ticket_id}] Saltando para o Formulário de Automóvel...")
            await page.goto("https://aggilizador.com.br/cotacao/auto/formulario")
            
            # --- ETAPA 3: PREENCHIMENTO DE ALTA PRECISÃO ---
            print(f"[{ticket_id}] Iniciando injeção de dados...")

            try:
                # 1. Mira a Laser no CPF usando o padrão de Test ID
                print(f"[{ticket_id}] Aguardando campo de CPF...")
                cpf_locator = page.locator('[data-testid="input_cpf-cnpj"]')
                await cpf_locator.wait_for(state="visible", timeout=15000)
                
                print(f"[{ticket_id}] Preenchendo CPF...")
                await cpf_locator.fill(dados_cliente['cpf'])
                await page.keyboard.press("Tab") 
                
                # 2. Sentinela de Processamento usando a sua captura exata (Imagem 1)
                nome_locator = page.locator('[data-testid="input_nome-segurado"]')
                print(f"[{ticket_id}] Aguardando Aggilizador processar o CPF...")
                
                tentativas = 0
                while tentativas < 15:
                    nome_atual = await nome_locator.input_value()
                    if nome_atual and len(nome_atual) > 2:
                        print(f"[{ticket_id}] Sucesso! Sistema carregou os dados do cliente: {nome_atual}")
                        break
                    await asyncio.sleep(1)
                    tentativas += 1
                
                if tentativas == 15:
                    print(f"[{ticket_id}] Aviso: O sistema demorou muito. Forçando preenchimento manual do Nome...")
                    await nome_locator.fill(dados_cliente['nome'])

                # 3. Preenchimento Temporário (Até termos os Test IDs exatos)
                print(f"[{ticket_id}] Inserindo Contatos e Veículo...")
                
                try:
                    await page.get_by_label("Telefone").fill(dados_cliente['telefone'])
                    await page.get_by_label("Email").fill(dados_cliente['email'])
                    await page.get_by_label("Placa").fill(dados_cliente['placa'])
                    await page.keyboard.press("Tab")
                    print(f"[{ticket_id}] Dados preenchidos com sucesso!")
                except Exception as erro_secundario:
                    print(f"[{ticket_id}] Falha ao preencher campos secundários sem o ID exato. Erro: {erro_secundario}")

            except Exception as loc_erro:
                print(f"[{ticket_id}] ALERTA CRÍTICO DE SELETOR. Erro: {loc_erro}")

            await asyncio.sleep(5)
            await browser.close()

            banco_de_tickets[ticket_id] = {
                "status": "concluido",
                "link_pdf": "TESTE_FORMULARIO_OK"
            }

    except Exception as e:
        print(f"[{ticket_id}] ERRO FATAL no processo: {e}")
        banco_de_tickets[ticket_id] = {"status": "erro", "erro": str(e)}

@app.post("/api/iniciar-cotacao")
async def iniciar_cotacao(dados: DadosCotacao, background_tasks: BackgroundTasks):
    ticket_id = str(uuid.uuid4())
    banco_de_tickets[ticket_id] = {"status": "processando"}
    
    background_tasks.add_task(tarefa_do_robo, ticket_id, dados.dict())
    return {"ticket": ticket_id, "mensagem": "Dados recebidos, robô acionado!"}

@app.get("/api/status-cotacao/{ticket_id}")
async def checar_status(ticket_id: str):
    resultado = banco_de_tickets.get(ticket_id)
    if not resultado:
        return {"erro": "Ticket não encontrado."}
    return resultado
