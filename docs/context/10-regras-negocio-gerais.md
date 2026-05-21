# 10 — Regras de Negócio Gerais

## Objetivo

Centralizar as regras de negócio que todos os serviços devem respeitar.

---

## Projetos

### RN-PROJ-001 — Projeto é o agrupador principal

Todo protocolo deve estar vinculado a um projeto.

### RN-PROJ-002 — Projeto pode ser visualizado em lista ou Kanban

A tela de projetos deve permitir alternar entre visualização em lista e Kanban.

### RN-PROJ-003 — Projeto inativo não apaga protocolos

Inativar um projeto não deve apagar seus protocolos ou histórico.

---

## Protocolos

### RN-PROT-001 — Protocolo pertence a um projeto

Não existe protocolo solto no sistema.

### RN-PROT-002 — Protocolo deve ter CNPJ

O CNPJ deve estar no protocolo, não apenas no projeto.

### RN-PROT-003 — Protocolo deve estar vinculado a stakeholder

Sem stakeholder, o sistema não sabe onde consultar.

### RN-PROT-004 — Usuário pode alterar status manual

O status editado pelo usuário é permitido e deve ser mantido.

### RN-PROT-005 — Status externo diferente gera divergência

Se o scraping encontrar status diferente do status manual, o sistema deve marcar divergência.

Não sobrescrever automaticamente o status manual sem evidenciar a diferença.

### RN-PROT-006 — Encerramento manual para monitoramento

Se o usuário encerrar o protocolo, o sistema deve parar de monitorar.

Campos sugeridos:

```json
{
  "closed_manually": true,
  "monitoring_enabled": false,
  "situation": "Finalizado pelo usuário"
}
```

### RN-PROT-007 — Protocolo não encontrado aparece separado

Se o site não encontrar o protocolo, marcar `found_in_last_search=false` e exibir separado dentro do projeto.

### RN-PROT-008 — Histórico exigido é de edição

O sistema precisa mostrar a última vez editado por X e o que mudou. Não é obrigatório manter histórico completo de status.

### RN-PROT-009 — Protocolos podem ser visualizados em lista ou Kanban

Dentro do projeto, o usuário escolhe visualização em lista ou Kanban.

---

## Stakeholders

### RN-STAKE-001 — Stakeholder é origem de dados

Stakeholder representa órgão/site onde o protocolo será consultado.

Exemplos:

- Copel;
- Prefeitura;
- Cartório;
- Tabelionato.

### RN-STAKE-002 — Stakeholder deve ter URL

Para scraping, o stakeholder deve possuir URL base ou template de consulta.

### RN-STAKE-003 — Cartório pode exigir ofício/serventia

Se o stakeholder for cartório, o sistema deve permitir e possivelmente exigir campo `oficio`/`serventia` no protocolo.

### RN-STAKE-004 — Stakeholder inativo não gera scraping

Protocolos vinculados a stakeholder inativo não devem gerar novos jobs automáticos.

---

## Carga inicial

### RN-CARGA-001 — Carga inicial é onboarding

Usada para iniciar a base com a planilha modelo.

### RN-CARGA-002 — Após carga, sistema vira fonte principal

Alterações futuras devem ser feitas pelo sistema.

### RN-CARGA-003 — CNPJ ausente deve ser erro

Como a regra exige CNPJ no protocolo, linhas sem CNPJ devem ser rejeitadas ou reportadas.

---

## Scraping

### RN-SCRAP-001 — Scraping consulta apenas protocolos monitoráveis

Não consultar protocolos encerrados, inativos ou com monitoramento desligado.

### RN-SCRAP-002 — Salvar HTML bruto

Todo HTML bruto deve ser salvo no MongoDB antes de limpeza.

### RN-SCRAP-003 — Não encontrado não é igual a erro técnico

Não encontrado é um resultado esperado. Timeout/site fora do ar é erro técnico.

---

## IA

### RN-IA-001 — IA extratora retorna JSON

A IA deve retornar dados estruturados em JSON.

### RN-IA-002 — IA não aplica regra de negócio

Ela não decide divergência, encerramento ou atualização final. A API faz isso.

### RN-IA-003 — IA não deve inventar

Se não encontrar informação, retornar `null`.

---

## RAG

### RN-RAG-001 — RAG usa dados do sistema

A IA da `/home` deve responder com base no MongoDB/ChromaDB.

### RN-RAG-002 — Cálculos usam MongoDB

Perguntas de quantidade, média e contagem devem consultar dados estruturados no MongoDB.

### RN-RAG-003 — Resposta deve citar fontes internas

A resposta deve retornar links ou referências para projeto/protocolo usado.

---

## Dashboard

### RN-DASH-001 — Dashboard mostra visão geral

Deve mostrar totais e alertas principais.

### RN-DASH-002 — Divergências são importantes

Protocolos com divergência devem ter destaque.

### RN-DASH-003 — Não encontrados são separados

Protocolos não encontrados não devem se misturar com “sem mudança”.

---

## Autenticação

### RN-AUTH-001 — Apenas um usuário no MVP

Não precisa de gestão de múltiplos usuários.

### RN-AUTH-002 — Todas as telas internas exigem login

Sem autenticação, redirecionar para `/login`.
