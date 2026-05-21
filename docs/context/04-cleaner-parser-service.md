# 04 — Serviço Cleaner / Parser

## Objetivo

Receber o HTML bruto salvo pelo scraper, remover conteúdo inútil e gerar um texto limpo e mais relevante para a IA extratora.

Esse serviço melhora a qualidade da extração e reduz o risco da IA se perder com menus, scripts, CSS, rodapés e conteúdo irrelevante.

---

## Entrada

Consome mensagens da fila `cleaner.jobs`:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "scraped_content_id": "content_123"
}
```

---

## Saída

Atualiza `scraped_contents` com `clean_text`:

```json
{
  "clean_text": "Protocolo 12345 Status: Em análise Última movimentação: 20/05/2026...",
  "cleaned_at": "2026-05-20T12:03:00Z",
  "cleaning_strategy": "generic_html_text_extractor"
}
```

Depois publica em `ai.extraction.jobs`:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "scraped_content_id": "content_123"
}
```

---

## O que remover

- `<head>`;
- `<script>`;
- `<style>`;
- menus;
- navbars;
- footers;
- comentários HTML;
- SVGs;
- conteúdo duplicado;
- textos muito repetitivos;
- termos de cookies;
- banners;
- espaços excessivos;
- quebras de linha repetidas.

---

## O que preservar

- número do protocolo;
- CNPJ;
- nome do órgão/stakeholder;
- status;
- situação;
- movimentações;
- datas;
- observações;
- mensagens de erro;
- mensagens de não encontrado;
- tabelas de andamento;
- links relevantes de comprovante ou consulta.

---

## Regras de negócio

### RB-CLEANER-001 — Cleaner não interpreta regra de negócio

O cleaner apenas limpa e estrutura texto. Ele não decide status final.

### RB-CLEANER-002 — Texto limpo deve manter rastreabilidade

O texto limpo deve permanecer vinculado ao HTML bruto por `scraped_content_id`.

### RB-CLEANER-003 — HTML bruto nunca deve ser apagado

Mesmo se o texto limpo for ruim, manter HTML bruto para auditoria.

### RB-CLEANER-004 — Se o cleaner remover demais, deve marcar erro

Se o texto final ficar vazio ou pequeno demais, marcar `cleaning_failed`.

### RB-CLEANER-005 — Pode existir estratégia por stakeholder

Para stakeholders conhecidos, pode haver parsers específicos.

Exemplo:

```text
CopelParser
PrefeituraParser
CartorioParser
GenericParser
```

---

## Loop com IA avaliadora

O usuário propôs um fluxo onde a IA analisa se o conteúdo limpo está bom. Para MVP, recomenda-se uma versão simples:

```text
Cleaner gera texto limpo
        ↓
IA Avaliadora recebe objetivo + texto limpo
        ↓
IA responde se o texto é suficiente
        ↓
Se suficiente: segue para extração
Se insuficiente: tentar limpeza alternativa uma vez
Se ainda insuficiente: marcar erro de limpeza
```

### Saída da IA avaliadora

```json
{
  "is_sufficient": true,
  "reason": "O texto contém protocolo, status e última movimentação",
  "suggested_action": "continue"
}
```

Para evitar loop infinito, permitir no máximo 1 ou 2 tentativas.

---

## Baby steps de desenvolvimento

### Task CLEANER-001 — Criar serviço consumidor

Descrição:

- criar serviço separado;
- conectar no RabbitMQ;
- consumir `cleaner.jobs`;
- buscar `scraped_content_id` no MongoDB.

Critérios de aceite:

- recebe mensagem e carrega HTML bruto.

---

### Task CLEANER-002 — Implementar limpeza genérica

Descrição:

- usar parser HTML;
- remover tags inúteis;
- extrair texto;
- normalizar espaços;
- remover linhas duplicadas.

Critérios de aceite:

- HTML com script/style gera texto sem JS/CSS;
- texto final é legível.

---

### Task CLEANER-003 — Preservar tabelas

Descrição:

- converter tabelas HTML em texto estruturado;
- manter cabeçalho e linhas;
- preservar datas e status.

Critérios de aceite:

- tabela de movimentações aparece no texto limpo.

---

### Task CLEANER-004 — Detectar texto insuficiente

Descrição:

- criar regra simples:
  - mínimo de caracteres;
  - presença de protocolo ou CNPJ;
  - presença de palavras-chave como status, situação, andamento, protocolo.

Critérios de aceite:

- texto vazio gera erro;
- texto útil segue para IA.

---

### Task CLEANER-005 — Salvar clean_text

Descrição:

- atualizar documento `scraped_contents`;
- salvar `clean_text`;
- salvar estratégia usada;
- salvar data de limpeza.

Critérios de aceite:

- HTML e texto limpo ficam no mesmo documento ou relacionados.

---

### Task CLEANER-006 — Publicar para IA

Descrição:

- publicar mensagem em `ai.extraction.jobs`;
- atualizar job para estágio `ai_pending`.

Critérios de aceite:

- IA recebe apenas ID, não texto gigante.

---

### Task CLEANER-007 — Implementar avaliador de suficiência com IA

Descrição:

- criar prompt específico para avaliar se o texto limpo tem informação suficiente;
- resposta deve ser JSON;
- limitar tentativas;
- se insuficiente, aplicar estratégia alternativa.

Critérios de aceite:

- IA consegue dizer se o texto está bom;
- loop não é infinito;
- se falhar, erro é registrado.

---

### Task CLEANER-008 — Criar parsers específicos por stakeholder

Descrição:

- criar interface comum `BaseParser`;
- criar `GenericParser`;
- permitir registrar parser específico por tipo/nome do stakeholder.

Critérios de aceite:

- se stakeholder tiver parser específico, usar ele;
- se não tiver, usar genérico.
