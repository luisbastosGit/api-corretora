from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time
import asyncio

app = FastAPI(title="API Corretora - Motor de Multicálculo")

# REGRA DE SEGURANÇA: Configurar o CORS. 
# Isso permite que a sua página no Wix consiga conversar com este servidor.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nosso "banco de dados" temporário na memória para controlar as filas
banco_de_tickets = {}

# Mapeamento do que o Wix vai nos enviar
class DadosCotacao(BaseModel):
    nome: str
    cpf: str
    placa: str
    pacote_escolhido: str

# Função que simula o trabalho do robô (A Fase 3 entrará exatamente aqui)
async def tarefa_do_robo(ticket_id: str):
    # Simulamos que o robô está abrindo o Aggilizador e calculando por 15 segundos
    await asyncio.sleep(15)
    
    # Quando o robô termina, ele atualiza o status do ticket
    banco_de_tickets[ticket_id] = {
        "status": "concluido",
        "link_pdf": "https://seu-drive.com/arquivo-simulado.pdf"
    }

# ---------------------------------------------------------
# PORTA 1: Onde o Wix bate para entregar os dados
# ---------------------------------------------------------
@app.post("/api/iniciar-cotacao")
async def iniciar_cotacao(dados: DadosCotacao, background_tasks: BackgroundTasks):
    # 1. Gera o código único de atendimento
    ticket_id = str(uuid.uuid4())
    
    # 2. Registra no sistema que este ticket começou a ser processado
    banco_de_tickets[ticket_id] = {"status": "processando"}
    
    # 3. Manda o robô trabalhar em segundo plano (na fila)
    background_tasks.add_task(tarefa_do_robo, ticket_id)
    
    # 4. Devolve o ticket para o Wix imediatamente, sem deixar o cliente esperando
    return {"ticket": ticket_id, "mensagem": "Dados recebidos, robô acionado!"}

# ---------------------------------------------------------
# PORTA 2: Onde o Wix bate para perguntar "Já acabou?"
# ---------------------------------------------------------
@app.get("/api/status-cotacao/{ticket_id}")
async def checar_status(ticket_id: str):
    # Procura o ticket na memória
    resultado = banco_de_tickets.get(ticket_id)
    
    if not resultado:
        return {"erro": "Ticket não encontrado."}
    
    return resultado
