# CHAIN WALK v2 — Explorador de Eventos

> Linha do tempo **mensal** de envios em massa de **S-1210**, com cadeia de
> retificações por CPF, XMLs preservados (sucesso e fracasso), download
> individual ou em pacote e limpeza anual com confirmação rígida.

> 📎 **Documentos relacionados**:
>
> - [COMO_ENVIAR_SOLUCOES.md](COMO_ENVIAR_SOLUCOES.md) — primeiro envio teste
>   prático (100 CPFs de agosto/2025) usando o pipeline do Chain Walk.
> - [CLIENTE_ESOCIAL_REAL_PREV.md](CLIENTE_ESOCIAL_REAL_PREV.md) — como portar
>   o cliente SOAP do eSocial (envio + consulta de lote) a partir do projeto
>   Real Prev.

---

## 1. Visão geral

O eSocial é um sistema **incremental**: cada `(CPF, perApur, tipo_evento)`
tem uma cadeia de versões — `nrReciboAnterior` aponta da versão nova para a
anterior. O Chain Walk **expõe essa cadeia visualmente** mês a mês.

- **Régua é POR MÊS** (`perApur`). Trocar de mês = trocar de régua.
- Cada **bolinha** da régua é uma **rodada de envio em massa** daquele mês.
- A **bolinha v0** é o estado vindo do **zip do retorno do eSocial** (raiz).
- Bolinhas seguintes nascem **só de envios em massa de S-1210** disparados
  pelo Easy-eSocial-v2.
- Caminhar = clicar em bolinhas ou usar `◀ ▶`. O grid de eventos abaixo
  re-renderiza no estado daquele instante.
- **Apenas S-1210** participa do chain walk. Outros tipos (S-2200, S-2299,
  S-1010 etc.) ficam como referência no Explorador, sem timeline.

## 2. Modelo de dados

### 2.1 Tabelas novas

```
timeline_mes
├─ id                BIGSERIAL PK
├─ empresa_id        INT NOT NULL
├─ per_apur          TEXT NOT NULL  -- 'YYYY-MM'
├─ head_envio_id     BIGINT NULL    -- aponta para timeline_envio mais recente
├─ criado_em         TIMESTAMP DEFAULT NOW()
└─ UNIQUE (empresa_id, per_apur)

timeline_envio                       -- cada bolinha da régua
├─ id                BIGSERIAL PK
├─ timeline_mes_id   BIGINT NOT NULL FK
├─ sequencia         INT NOT NULL    -- 0 = zip_inicial, 1, 2, 3...
├─ tipo              TEXT NOT NULL   -- 'zip_inicial' | 'envio_massa'
│                                    -- futuro: 'envio_individual'
├─ iniciado_em       TIMESTAMP DEFAULT NOW()
├─ finalizado_em     TIMESTAMP NULL
├─ status            TEXT NOT NULL   -- 'em_andamento' | 'concluido' | 'falhou'
├─ total_tentados    INT DEFAULT 0
├─ total_sucesso     INT DEFAULT 0
├─ total_erro        INT DEFAULT 0
├─ resumo            JSONB NULL      -- contadores extras, filtros usados
└─ UNIQUE (timeline_mes_id, sequencia)

timeline_envio_item                  -- granular por CPF dentro do envio
├─ id                BIGSERIAL PK
├─ timeline_envio_id BIGINT NOT NULL FK
├─ cpf               TEXT NOT NULL
├─ tipo_evento       TEXT NOT NULL DEFAULT 'S-1210'
├─ status            TEXT NOT NULL   -- 'sucesso' | 'erro_esocial'
│                                    -- | 'rejeitado_local' | 'falha_rede'
├─ versao_anterior_id BIGINT NULL FK explorador_eventos
├─ versao_nova_id     BIGINT NULL FK explorador_eventos
├─ xml_enviado_oid   OID NULL        -- SEMPRE preenchido se chegou a montar XML
├─ xml_retorno_oid   OID NULL        -- preenchido quando eSocial respondeu
├─ erro_codigo       TEXT NULL
├─ erro_mensagem     TEXT NULL
├─ duracao_ms        INT NULL
└─ criado_em         TIMESTAMP DEFAULT NOW()
```

### 2.2 Colunas adicionadas em `explorador_eventos`

```sql
ALTER TABLE explorador_eventos
  ADD COLUMN retificado_por_id BIGINT NULL
    REFERENCES explorador_eventos(id) ON DELETE SET NULL,
  ADD COLUMN origem_envio_id   BIGINT NULL
    REFERENCES timeline_envio(id) ON DELETE SET NULL;

CREATE INDEX idx_explorador_eventos_cadeia
  ON explorador_eventos (cpf, per_apur, tipo_evento)
  WHERE tipo_evento = 'S-1210';

CREATE INDEX idx_explorador_eventos_head
  ON explorador_eventos (cpf, per_apur, tipo_evento)
  WHERE tipo_evento = 'S-1210' AND retificado_por_id IS NULL;
```

### 2.3 Regra de imutabilidade

- Versão com `retificado_por_id IS NOT NULL` é **imutável**.
- Reenvio só age sobre a versão **HEAD** (`retificado_por_id IS NULL`).
- Tentar reenviar uma versão não-HEAD = `409 Conflict`.

## 3. Backfill na migration

Para cada `(empresa_id, perApur)` distinto já presente em
`explorador_eventos`:

1. Cria `timeline_mes` (UPSERT)
2. Cria `timeline_envio` com `sequencia=0`, `tipo='zip_inicial'`,
   `status='concluido'`, contadores baseados nos eventos S-1210 daquele mês
3. Marca `origem_envio_id` de todos os eventos S-1210 daquele mês com o id
   dessa bolinha v0
4. Atualiza `head_envio_id = id_da_bolinha_v0`

### 3.1 Detecção automática de cadeias no próprio zip

Após criar v0, varre eventos S-1210 do mês procurando `nrReciboAnterior`
preenchido. Se existe outro evento no mesmo `(cpf, per_apur)` cujo
`nr_recibo` bate, conecta:

```sql
UPDATE explorador_eventos AS antigo
   SET retificado_por_id = novo.id
  FROM explorador_eventos AS novo
 WHERE novo.tipo_evento = 'S-1210'
   AND novo.cpf = antigo.cpf
   AND novo.per_apur = antigo.per_apur
   AND novo.nr_recibo_anterior = antigo.nr_recibo
   AND antigo.retificado_por_id IS NULL
   AND novo.id <> antigo.id;
```

Isso resolve cadeias que o eSocial já entregou prontas no zip.

## 4. Endpoints

### 4.1 Régua mensal

```
GET /api/explorador/timeline?empresa_id=1&per_apur=2025-08
→ {
    "timeline_mes": { id, per_apur, head_envio_id },
    "envios": [
      { id, sequencia, tipo, status, iniciado_em, finalizado_em,
        total_tentados, total_sucesso, total_erro }
    ]
  }
```

### 4.2 Estado em uma bolinha (CPFs e status)

```
GET /api/explorador/timeline/envio/{envio_id}/estado
→ {
    "envio": {...},
    "items": [
      { cpf, status, versao_anterior_id, versao_nova_id,
        nr_recibo_anterior, nr_recibo_novo, erro_codigo, erro_mensagem }
    ],
    "totais": { sucesso, erro_esocial, falha_rede, rejeitado_local }
  }
```

### 4.3 Cadeia de um CPF/perApur

```
GET /api/explorador/cadeia?empresa_id=1&cpf=08132588983&per_apur=2025-08&tipo_evento=S-1210
→ {
    "cpf": "...", "per_apur": "...",
    "versoes": [
      { id, nr_recibo, nr_recibo_anterior, origem_envio_id,
        is_head: bool, tem_xml: bool }
    ],
    "tentativas": [   // tudo, sucesso e erro, ordenado cronologicamente
      { envio_id, sequencia, status, criado_em,
        xml_enviado_disponivel, xml_retorno_disponivel,
        erro_codigo, erro_mensagem }
    ]
  }
```

### 4.4 Download de XML por tentativa

```
GET /api/explorador/tentativa/{item_id}/xml-enviado    → application/xml
GET /api/explorador/tentativa/{item_id}/xml-retorno    → application/xml
```

### 4.5 Download empacotado da cadeia

```
GET /api/explorador/cadeia/zip?empresa_id=1&cpf=...&per_apur=...&tipo_evento=S-1210
→ application/zip
   ├─ enviado_t1_sucesso.xml
   ├─ retorno_t1_sucesso.xml
   ├─ enviado_t2_erro.xml
   ├─ retorno_t2_erro.xml
   └─ ...
```

### 4.6 Limpeza anual

```
POST /api/explorador/limpeza-anual
{
  "empresa_id": 1,
  "ano": 2024,
  "confirmacao": "DELETAR TUDO DE 2024 DA SOLUCOES SERVICOS TERCEIRIZ"
}
→ 200 { ok, registros_apagados, bytes_liberados }
→ 422 { erro: "frase de confirmação não bate", esperado: "..." }
```

Regras:

- Frase montada server-side: `f"DELETAR TUDO DE {ano} DA {nome_empresa.upper().strip()}"`.
- Comparação byte-a-byte; whitespace excedente devolve 422.
- Bloqueia se houver `timeline_envio` em `em_andamento` em qualquer mês do
  ano.
- Apaga: `timeline_envio_item` + LOs de XML + `timeline_envio` + versões
  não-HEAD do ano + zips do ano. Mantém: `explorador_atividade` (registra
  `acao='limpeza_anual'` com contadores).

### 4.7 Reenvio em massa (futuro — fora deste MD, mas espaço já reservado)

```
POST /api/explorador/timeline/{timeline_mes_id}/envio-massa
{ "filtro": "todos" | "somente_erro" | "somente_pendente",
  "cpfs"?: ["08132...", ...] }
→ inicia novo timeline_envio (sequencia = head+1) e abre SSE
GET /api/explorador/timeline/envio/{envio_id}/log    (SSE)
```

## 5. Frontend (Vue 3)

### 5.1 Componentes novos

```
src/components/explorador/timeline/
├─ TimelineMes.vue          // seletor de mês (perApur disponíveis)
├─ TimelineRegua.vue        // bolinhas + setas ◀ ▶
├─ EstadoEnvio.vue          // grid de CPFs no estado da bolinha selecionada
├─ DrawerCadeiaCpf.vue      // mini-cadeia + tentativas + downloads
└─ ModalLimpezaAnual.vue    // confirmação rígida
```

### 5.2 Roteamento dentro de `ExploradorView`

Quando usuário clica numa pasta `S-1210` num mês X:

1. Lê régua de X (`GET /timeline`)
2. Renderiza `TimelineRegua` no topo
3. Aponta para HEAD por padrão. Estado vem de `EstadoEnvio` no envio HEAD
4. Click em bolinha → muda `envioSelecionadoId`. `EstadoEnvio` recarrega
5. Click num CPF → abre `DrawerCadeiaCpf`

### 5.3 Sinalização visual

- HEAD: fundo normal, ações habilitadas
- Visualizando bolinha não-HEAD: banner amarelo no topo
  `📅 Olhando estado de t2 (3 envios atrás) — [voltar pro AGORA]`
  - leve tinta azul no fundo
- Linha de CPF cuja versão visível é não-HEAD: ícone 🔒 + tooltip
  `Esta versão foi retificada em t3 → [ir para t3]`

## 6. Regras de armazenamento de XML

| Cenário                                   | xml_enviado | xml_retorno          | versão criada |
| ----------------------------------------- | ----------- | -------------------- | ------------- |
| Sucesso eSocial                           | ✅ salvo    | ✅ salvo             | ✅ HEAD nova  |
| Erro de validação eSocial                 | ✅ salvo    | ✅ salvo (com erros) | ❌            |
| Timeout / falha rede                      | ✅ salvo    | ⚠ vazio              | ❌            |
| Rejeitado localmente (assinatura, schema) | ✅ salvo    | —                    | ❌            |

XMLs vão para `pg_largeobject` (mesma técnica dos zips). Tamanho típico:
~3 KB enviado + ~2 KB retorno → ~5 KB por tentativa. 1 mês com 1500 CPFs e
média de 1.3 tentativas ≈ 10 MB. Insignificante.

## 7. Limpeza anual — UI

Card vermelho em **Configurações → Manutenção** (ou no próprio Explorador,
seção "Zona de perigo"):

```
┌─ ZONA DE PERIGO ────────────────────────────────────┐
│ Limpeza anual de XMLs e cadeias                     │
│                                                      │
│ Selecione o ano fechado:  [▼ 2024]                  │
│                                                      │
│ ⚠ Vai apagar:                                       │
│   • 12.480 versões de S-1210                        │
│   • 8.234 XMLs (340 MB)                             │
│   • 12 envios da timeline                           │
│   • Mantém estatísticas agregadas no histórico      │
│                                                      │
│ Para confirmar, digite EXATAMENTE:                  │
│   DELETAR TUDO DE 2024 DA SOLUCOES SERVICOS TERCEIRIZ │
│                                                      │
│ [____________________________________________]      │
│                                                      │
│  [ APAGAR DEFINITIVAMENTE ]    (só ativa se bater)  │
└──────────────────────────────────────────────────────┘
```

## 8. Ordem de implementação

1. ✅ MD (este arquivo)
2. Migration `003_chain_walk.sql` — tabelas + colunas + índices
3. Backfill — script Python `app/backfill_chain.py` chamado também ao
   subir um zip novo (ao final da extração)
4. Endpoints `GET /timeline`, `/timeline/envio/{id}/estado`, `/cadeia`
5. Componentes `TimelineMes`, `TimelineRegua`, `EstadoEnvio`
6. Endpoints `/cadeia/zip` (download empacotado) + `tentativa/{id}/xml-*`
7. `DrawerCadeiaCpf` com lista de tentativas e downloads
8. Endpoint `/limpeza-anual` + `ModalLimpezaAnual`
9. _(futuro)_ Reenvio em massa + SSE log

## 9. Não-objetivos (escopo fora desta versão)

- Reenvio individual ou em massa (item 9 do roadmap)
- Cross-month timeline (decididamente NÃO)
- Eventos diferentes de S-1210 no chain walk
- Reverter operação (rollback) — preservar histórico já é suficiente
- Multi-usuário e travas pessimistas — MVP single-user

## 10. Riscos e mitigações

| Risco                                              | Mitigação                                                         |
| -------------------------------------------------- | ----------------------------------------------------------------- |
| `nrReciboAnterior` aponta pra recibo fora do banco | Cadeia órfã — flag e ainda funcional                              |
| Concorrência entre 2 envios no mesmo mês           | UNIQUE `(timeline_mes_id, sequencia)` + lock advisory na criação  |
| LO órfão se delete falhar no meio                  | TX atômica + `lo_unlink` em finally                               |
| Confirmação digitada com BOM/U+00A0 invisível      | Normalizar `unicodedata.normalize('NFKC', ...)` antes de comparar |
