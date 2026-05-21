# Tasks baby steps — Integração entre os 3 repositórios e demo

Este arquivo pode ser copiado para os três repos em:

```txt
/docs/tasks/04-tasks-integracao-e-demo.md
```

Use estas tasks quando os serviços básicos já existirem.

---

## INT-001 — Padronizar variáveis de ambiente entre serviços

### Objetivo

Garantir que API, Web e Scraping conversem entre si.

### Variáveis principais

API:

```env
PORT=3000
MONGODB_URI=mongodb://localhost:27017/caminhoes_bpk
RABBITMQ_URL=amqp://localhost:5672
CHROMA_URL=http://localhost:8000
OLLAMA_URL=http://localhost:11434
JWT_SECRET=change-me
```

WEB:

```env
NEXT_PUBLIC_API_URL=http://localhost:3000
```

SCRAPING:

```env
MONGODB_URI=mongodb://localhost:27017/caminhoes_bpk
RABBITMQ_URL=amqp://localhost:5672
API_BASE_URL=http://localhost:3000
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

### Critério de aceite

- `.env.example` dos 3 repos estão coerentes.
- README de cada repo mostra como configurar.

---

## INT-002 — Criar docker-compose opcional para infraestrutura

### Objetivo

Subir dependências locais facilmente.

### Serviços

```txt
mongodb
rabbitmq
chromadb
```

### Opcional

Ollama pode ser documentado fora do compose se ficar pesado.

### Critério de aceite

- `docker compose up -d` sobe MongoDB, RabbitMQ e ChromaDB.
- Portas documentadas.

---

## INT-003 — Testar fluxo completo de carga inicial

### Fluxo

1. Subir API.
2. Subir Web.
3. Login.
4. Abrir tela de importação.
5. Enviar planilha modelo.
6. Confirmar criação de projetos e protocolos.
7. Abrir dashboard.
8. Abrir projeto e protocolo importado.

### Critério de aceite

- Planilha entra pelo Web.
- API salva no MongoDB.
- Web mostra dados salvos.

---

## INT-004 — Testar fluxo completo de scraping manual

### Fluxo

1. Criar stakeholder com URL de teste real.
2. Criar protocolo com CNPJ.
3. Clicar em “consultar agora”.
4. API publica em `scraping.jobs`.
5. Scraping consome.
6. Scraping salva raw HTML no MongoDB.
7. Cleaner gera texto limpo.
8. IA extrai JSON.
9. Scraping envia resultado para API.
10. API atualiza protocolo.
11. Web mostra status externo e divergência, se houver.

### Critério de aceite

- Fluxo completo roda pelo menos uma vez.
- Nenhum HTML bruto trafega pela fila.
- Resultado aparece na tela do protocolo.

---

## INT-005 — Testar protocolo não encontrado

### Fluxo

1. Usar protocolo inválido.
2. Rodar consulta.
3. Scraping/IA identifica não encontrado.
4. API marca `not_found_on_source=true`.
5. Web mostra separado.

### Critério de aceite

- Protocolo não encontrado não é confundido com erro genérico.
- Fica visível no projeto.

---

## INT-006 — Testar divergência entre status manual e externo

### Fluxo

1. Criar protocolo com `manual_status="Em análise"`.
2. Fazer resultado externo retornar `Aguardando documentação`.
3. API marca divergência.
4. Web mostra alerta.

### Critério de aceite

- Status manual não é sobrescrito.
- Divergência fica clara.

---

## INT-007 — Testar finalização manual de protocolo

### Fluxo

1. Abrir protocolo.
2. Clicar em finalizar.
3. API define `monitoring_enabled=false`.
4. Tentar consultar agora.
5. API rejeita ou informa que não monitora finalizados.

### Critério de aceite

- Protocolo finalizado não entra no scraping.

---

## INT-008 — Testar RAG na Home IA

### Fluxo

1. Garantir que há projetos/protocolos indexados no ChromaDB.
2. Abrir `/home`.
3. Perguntar: “Quais protocolos estão com divergência?”
4. API busca contexto no ChromaDB.
5. IA responde com base no contexto.
6. Web mostra resposta e fontes.

### Critério de aceite

- IA não inventa quando não há dados.
- Resposta cita informações existentes.

---

## INT-009 — Preparar roteiro final de pitch

### Roteiro sugerido

1. Mostrar problema: acompanhamento manual em planilha e sites.
2. Fazer login.
3. Importar planilha inicial.
4. Mostrar dashboard.
5. Abrir projeto.
6. Abrir protocolo com CNPJ.
7. Mostrar stakeholder/origem de dados.
8. Rodar consulta agora.
9. Mostrar extração da IA.
10. Mostrar divergência de status.
11. Mostrar protocolo não encontrado separado.
12. Perguntar algo na Home IA.
13. Fechar com visão futura: WhatsApp, Telegram, Teams e alertas.

### Critério de aceite

- Time consegue demonstrar em menos de 5 minutos.
