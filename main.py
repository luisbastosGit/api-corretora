**from fastapi import FastAPI, BackgroundTasks**

**from pydantic import BaseModel**

**from fastapi.middleware.cors import CORSMiddleware**

**import uuid**

**import time**

**import asyncio**



**app = FastAPI(title="API Corretora - Motor de Multicálculo")**



**# REGRA DE SEGURANÇA: Configurar o CORS.**

**# Isso permite que a sua página no Wix consiga conversar com este servidor.**

**app.add\_middleware(**

&#x20;   **CORSMiddleware,**

&#x20;   **allow\_origins=\["\*"], # No futuro, trocaremos o "\*" pelo domínio exato do seu Wix**

&#x20;   **allow\_credentials=True,**

&#x20;   **allow\_methods=\["\*"],**

&#x20;   **allow\_headers=\["\*"],**

**)**



**# Nosso "banco de dados" temporário na memória para controlar as filas**

**banco\_de\_tickets = {}**



**# Mapeamento do que o Wix vai nos enviar**

**class DadosCotacao(BaseModel):**

&#x20;   **nome: str**

&#x20;   **cpf: str**

&#x20;   **placa: str**

&#x20;   **pacote\_escolhido: str**



**# Função que simula o trabalho do robô (A Fase 3 entrará exatamente aqui)**

**async def tarefa\_do\_robo(ticket\_id: str):**

&#x20;   **# Simulamos que o robô está abrindo o Aggilizador e calculando por 15 segundos**

&#x20;   **await asyncio.sleep(15)**

&#x20;

&#x20;   **# Quando o robô termina, ele atualiza o status do ticket**

&#x20;   **banco\_de\_tickets\[ticket\_id] = {**

&#x20;       **"status": "concluido",**

&#x20;       **"link\_pdf": "https://seu-drive.com/arquivo-simulado.pdf"**

&#x20;   **}**



**# ---------------------------------------------------------**

**# PORTA 1: Onde o Wix bate para entregar os dados**

**# ---------------------------------------------------------**

**@app.post("/api/iniciar-cotacao")**

**async def iniciar\_cotacao(dados: DadosCotacao, background\_tasks: BackgroundTasks):**

&#x20;   **# 1. Gera o código único de atendimento**

&#x20;   **ticket\_id = str(uuid.uuid4())**

&#x20;

&#x20;   **# 2. Registra no sistema que este ticket começou a ser processado**

&#x20;   **banco\_de\_tickets\[ticket\_id] = {"status": "processando"}**

&#x20;

&#x20;   **# 3. Manda o robô trabalhar em segundo plano (na fila)**

&#x20;   **background\_tasks.add\_task(tarefa\_do\_robo, ticket\_id)**

&#x20;

&#x20;   **# 4. Devolve o ticket para o Wix imediatamente, sem deixar o cliente esperando**

&#x20;   **return {"ticket": ticket\_id, "mensagem": "Dados recebidos, robô acionado!"}**



**# ---------------------------------------------------------**

**# PORTA 2: Onde o Wix bate para perguntar "Já acabou?"**

**# ---------------------------------------------------------**

**@app.get("/api/status-cotacao/{ticket\_id}")**

**async def checar\_status(ticket\_id: str):**

&#x20;   **# Procura o ticket na memória**

&#x20;   **resultado = banco\_de\_tickets.get(ticket\_id)**

&#x20;

&#x20;   **if not resultado:**

&#x20;       **return {"erro": "Ticket não encontrado."}**

&#x20;

&#x20;   **return resultado**

