# 11 — Ordem Recomendada de Desenvolvimento do MVP

## Objetivo

Organizar o desenvolvimento em baby steps para facilitar execução com IA e divisão entre pessoas do time.

---

## Fase 1 — Fundação

### 1. Subir infraestrutura local

Serviços:

- MongoDB;
- RabbitMQ;
- ChromaDB;
- Ollama;
- API;
- Web.

Tasks:

- criar `docker-compose.yml`;
- configurar `.env`;
- validar conexão entre serviços;
- criar `/health` na API;
- criar tela inicial da Web.

Pronto quando:

- todos os containers sobem;
- API conecta no MongoDB;
- RabbitMQ abre no painel;
- ChromaDB responde;
- Ollama responde.

---

## Fase 2 — Autenticação e layout

Tasks:

1. criar usuário único seedado;
2. criar login;
3. proteger rotas;
4. criar layout autenticado;
5. criar menu para Home, Dashboard, Projetos, Stakeholders e Importação.

Pronto quando:

- usuário loga;
- sem login não acessa telas;
- navegação básica funciona.

---

## Fase 3 — Modelagem e CRUDs principais

Tasks:

1. criar schemas MongoDB;
2. criar CRUD de stakeholders;
3. criar CRUD de projetos;
4. criar CRUD de protocolos;
5. implementar CNPJ obrigatório;
6. implementar regra de cartório/ofício;
7. implementar encerramento de protocolo;
8. implementar audit log de edição.

Pronto quando:

- usuário cria stakeholder;
- usuário cria projeto;
- usuário cria protocolo com CNPJ;
- cartório exige ofício quando necessário;
- edição gera audit log.

---

## Fase 4 — Carga inicial

Tasks:

1. criar endpoint upload;
2. ler XLSX;
3. normalizar cabeçalho;
4. validar CNPJ e campos obrigatórios;
5. criar stakeholders automaticamente quando possível;
6. criar projetos;
7. criar protocolos;
8. retornar resumo;
9. criar tela de upload;
10. mostrar erros por linha.

Pronto quando:

- planilha modelo popula o sistema;
- projetos aparecem em `/projetos`;
- protocolos aparecem dentro dos projetos.

---

## Fase 5 — Dashboard e visualizações

Tasks:

1. criar endpoint de resumo;
2. criar cards do dashboard;
3. criar listagem de projetos;
4. criar Kanban de projetos;
5. criar listagem de protocolos no projeto;
6. criar Kanban de protocolos;
7. separar protocolos não encontrados;
8. destacar divergências.

Pronto quando:

- dashboard mostra indicadores;
- projeto mostra protocolos;
- usuário alterna lista/Kanban.

---

## Fase 6 — RabbitMQ ponta a ponta fake

Tasks:

1. criar filas;
2. criar publicação de `scraping.jobs`;
3. criar scraper fake;
4. criar cleaner fake;
5. criar IA fake;
6. API recebe resultado fake;
7. API atualiza protocolo.

Pronto quando:

- clicar “consultar agora” muda dados do protocolo usando fluxo fake.

---

## Fase 7 — Scraping real

Tasks:

1. configurar stakeholder real;
2. montar URL de consulta;
3. fazer request via curl/requests;
4. salvar HTML bruto;
5. detectar não encontrado;
6. detectar erro técnico;
7. publicar para cleaner.

Pronto quando:

- pelo menos um site real é consultado;
- HTML aparece salvo no MongoDB.

---

## Fase 8 — Cleaner/Parser real

Tasks:

1. remover head/script/style/footer;
2. extrair texto;
3. preservar tabelas;
4. salvar `clean_text`;
5. validar suficiência básica;
6. publicar para IA.

Pronto quando:

- HTML bruto vira texto limpo útil.

---

## Fase 9 — IA extratora real

Tasks:

1. configurar Ollama + Qwen;
2. criar prompt de extração;
3. validar JSON com schema;
4. implementar retry de correção;
5. publicar resultado;
6. tratar protocolo não encontrado;
7. tratar JSON inválido.

Pronto quando:

- texto limpo vira JSON estruturado.

---

## Fase 10 — Persistência e divergência

Tasks:

1. API consome resultado da IA;
2. valida payload;
3. salva `consultation_results`;
4. atualiza `protocols.external_status`;
5. compara com `manual_status`;
6. marca `has_divergence`;
7. marca `found_in_last_search=false` quando não encontrado;
8. atualiza dashboard.

Pronto quando:

- divergência aparece no detalhe do protocolo;
- não encontrado aparece separado.

---

## Fase 11 — ChromaDB e RAG

Tasks:

1. criar coleção ChromaDB;
2. montar documento textual do protocolo;
3. indexar após importação;
4. atualizar após resultado de scraping;
5. implementar busca semântica;
6. implementar BM25;
7. combinar resultados;
8. criar endpoint `/rag/query`;
9. criar tela `/home` com chat;
10. retornar fontes clicáveis.

Pronto quando:

- usuário pergunta sobre projeto e recebe resposta;
- pergunta sobre Copel retorna protocolos da Copel;
- fontes abrem telas internas.

---

## Fase 12 — Polimento para demo

Tasks:

1. criar dados de exemplo;
2. preparar roteiro de apresentação;
3. criar estados visuais claros:
   - divergência;
   - não encontrado;
   - encerrado;
   - monitorando;
4. garantir que botão “consultar agora” funciona;
5. testar fluxo completo;
6. ajustar mensagens de erro;
7. preparar pitch.

Pronto quando:

- demo mostra carga inicial;
- mostra CRUD;
- mostra scraping;
- mostra IA extraindo;
- mostra divergência;
- mostra RAG.

---

## Divisão sugerida por pessoas

### Pessoa 1 — Backend/API

- autenticação;
- CRUDs;
- importação;
- regras de negócio;
- endpoints RAG.

### Pessoa 2 — Web

- telas;
- formulários;
- listagem/Kanban;
- chat RAG;
- dashboard.

### Pessoa 3 — Scraping/Cleaner

- scraper;
- cleaner/parser;
- RabbitMQ;
- tratamento de erro.

### Pessoa 4 — IA/RAG

- Ollama/Qwen;
- prompt extraction;
- validação JSON;
- ChromaDB;
- hybrid search.

---

## Roteiro de demo sugerido

1. Fazer login.
2. Importar planilha modelo.
3. Mostrar projetos criados.
4. Abrir projeto e mostrar protocolos.
5. Criar/editar protocolo com CNPJ.
6. Criar stakeholder Copel com URL.
7. Clicar “consultar agora”.
8. Mostrar HTML bruto salvo ou log do scraping.
9. Mostrar status externo extraído pela IA.
10. Mostrar divergência entre status manual e externo.
11. Mostrar protocolo não encontrado separado, se houver.
12. Ir para `/home` e perguntar: “Quais protocolos estão com divergência?”
13. Mostrar resposta com fontes clicáveis.
