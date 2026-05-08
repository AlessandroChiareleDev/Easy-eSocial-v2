# Como Enviar Soluções — primeiro envio teste (100 CPFs de agosto/2025)

> **Documento operacional** do primeiro envio teste do Easy-eSocial-v2 / módulo Chain Walk.
> Linkado a partir de [CHAIN_WALK_V2.md](CHAIN_WALK_V2.md).

---

## Parte 1 — O que é esse envio teste e como ele é feito

### 1.1 Objetivo

Pegar **100 CPFs HEAD do `perApur=2025-08`** (mês de agosto da empresa Soluções) e
**reenviar para o eSocial os mesmos S-1210 que já estão em base** — exatamente os
mesmos XMLs originais que vieram do ZIP do Download Cirúrgico.

A ideia **não** é gerar XML novo nem retificar nada de propósito: é só validar a
ponta-a-ponta do nosso pipeline (extração → empacotamento em lote → envio →
recebimento de retorno) usando dados reais de produção.

### 1.2 Por que é seguro reenviar o mesmo XML?

- Os XMLs em base **já foram processados pelo eSocial uma vez** (vieram do
  download de retorno). Cada um carrega `Id` único, `nrRecibo` original e
  assinatura válida.
- Reenviar **o mesmo `Id`** ao eSocial **não cria evento novo** — o ambiente
  responde com erro de evento duplicado / já processado.
  É exatamente o comportamento que queremos para esse teste de fumaça:
  - quem **rejeita por duplicidade** = ✅ pipeline funciona, o eSocial reconheceu
    o evento;
  - quem **rejeita por outro motivo** (assinatura inválida, namespace errado,
    rede caiu) = 🔴 problema do nosso lado, vamos ver o erro exato.

> Não é retificação. Não é evento novo. Não vai alterar a folha. É um
> "ping" de fim-a-fim usando o material que já temos. O HEAD continua intocado
> em base — quem é HEAD agora continua HEAD depois.

### 1.3 Quais são os 100 CPFs

```
SELECT ev.id, ev.cpf, ev.nr_recibo, ev.xml_entry_name, ev.zip_id
  FROM explorador_eventos ev
  JOIN empresa_zips_brutos z ON z.id = ev.zip_id
 WHERE z.empresa_id = 1                  -- SOLUCOES
   AND ev.tipo_evento = 'S-1210'
   AND ev.per_apur = '2025-08'
   AND ev.retificado_por_id IS NULL      -- só HEAD
 ORDER BY ev.cpf ASC
 LIMIT 100;
```

Critério é determinístico (ordem por CPF) — toda execução pega os mesmos 100,
até subir versão nova ou alguém rodar limpeza.

### 1.4 Onde ficam os XMLs

`explorador_eventos` **não tem coluna OID** de XML por evento. Os XMLs ficam
dentro do **ZIP cru** em `empresa_zips_brutos.conteudo_oid`, e a coluna
`explorador_eventos.xml_entry_name` aponta para o caminho do arquivo dentro do
ZIP. Para reenviar:

1. Abrir o `pg_largeobject` do ZIP em modo streaming.
2. `zipfile.read(xml_entry_name)` → bytes do XML original (com assinatura
   eSocial intacta).
3. **Copiar esses bytes** para um novo `pg_largeobject` dedicado (OID novo) e
   guardar em `timeline_envio_item.xml_enviado_oid` — assim cada tentativa tem o
   próprio XML congelado para download independente, e o ZIP original nunca é
   tocado.

> Os bytes em `xml_enviado_oid` são **idênticos byte-a-byte** ao XML que está
> dentro do ZIP. Quando o usuário baixar a v0 (zip original) e a v1 (envio
> teste) para o mesmo CPF, o conteúdo é o mesmo arquivo.

### 1.5 Como o envio é montado

1. Ler os 100 XMLs como bytes.
2. Particionar em **lotes de até 40 eventos** (limite do Simplificado eSocial).
   Para 100 CPFs = 3 lotes (40 + 40 + 20).
3. Para cada lote: gerar o envelope `EnviarLoteEventos` colando os XMLs
   exatamente como foram extraídos.
4. POST no WebService de produção do eSocial Simplificado.
5. Para cada CPF, registrar:
   - `status` = `sucesso` / `erro_esocial` / `falha_rede` / `pendente`
   - `erro_codigo` + `erro_mensagem` (do XML de retorno do eSocial)
   - `xml_retorno_oid` (Large Object com a porção de retorno daquele evento)
   - `duracao_ms`

### 1.6 Topologia da timeline depois do teste

Antes:

```
●  ← v0 (zip_inicial, agosto)
HEAD
```

Depois do envio teste:

```
●━━━━━━━●  ← v1 (envio_massa "envio teste 100", agosto)
v0      HEAD?
```

> **Importante:** _como nada foi retificado_, o `head_envio_id` continua
> apontando para **v0**. A v1 é apenas uma _tentativa de reenvio_ registrada na
> régua. Cada `timeline_envio_item.versao_anterior_id` aponta para o evento
> original em `explorador_eventos`, mas **`retificado_por_id` continua NULL** em
> todos os 100.
>
> O usuário disse explicitamente: _"eles são o mesmo arquivo, eles não foram
> reposicionados, só foram apontados pra frente"_. É exatamente isso: a
> tentativa fica registrada (v1), mas o estado oficial da base não muda.

### 1.7 Modos de execução do motor

O backend v2/explorador hoje **não tem cliente SOAP do eSocial** (só parser).
Para destravar este teste imediatamente, o motor é plugável em dois modos:

| Modo       | Descrição                                                                                         | Quando usar                                                   |
| ---------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `simulado` | adapter local que registra "sucesso" para todos com `nrRecibo` reaproveitado, sem POST real       | UI/preview do fluxo, testes de regressão sem bater no eSocial |
| `real`     | importa `app.esocial_client.enviar_lote(xmls)` (a ser plugado do V1) e usa o retorno SOAP genuíno | quando o usuário autorizar o disparo                          |

> Conforme as **regras de uso de cota do eSocial**: este endpoint usa
> `EnviarLoteEventos` (não conta no limite de 10 consultas/dia da API de
> download). Mas mesmo assim **só é executado em modo `real` por ação explícita
> do usuário** (botão dedicado na UI).

### 1.8 Idempotência

- Se o usuário clicar duas vezes em "criar envio teste" para o mesmo
  `(empresa, perApur, "envio teste")` enquanto o anterior ainda estiver
  `em_andamento` ou `concluido`, retornamos 409 com o `envio_id` existente.
- Para "rodar de novo" o mesmo lote, é necessário criar nova sequência (v2, v3…)
  via parâmetro explícito `forcar_nova_sequencia=true`.

---

## Parte 2 — O que o usuário vê no front

### 2.1 Régua antes vs. depois

A régua mensal de agosto/2025 ganha um segundo ponto:

```
●━━━━━━━━━━━●
v0          v1
zip         envio teste (100/100)
inicial
```

Cada bolinha clicável abre o **Estado do Envio**.

### 2.2 Estado do Envio teste (v1)

Painel com **contadores agregados**:

- 🟢 sucesso: N (com `nrRecibo` retornado)
- 🔴 erro_esocial: N (rejeição com `erro_codigo` + mensagem)
- 🟡 falha_rede: N (timeout, conexão recusada, 5xx)
- ⚪ pendente: N (ainda não tentado pelo motor)
- ⚫ não_tentado: N (ficou de fora dos 100, mas seria HEAD do mês — informativo)

E, abaixo, **lista/grid de CPFs do envio**, cada um com:

- ícone de status
- `nrRecibo` se sucesso (igual ao recibo original — confirma que o eSocial
  reconheceu o `Id`)
- `erro_codigo` + mensagem se erro
- 📤 botão **baixar XML enviado** (do `xml_enviado_oid` da tentativa)
- 📥 botão **baixar XML de retorno** (do `xml_retorno_oid` da tentativa)

### 2.3 Tipos de erro agrupados

Topo do painel de erro mostra um histograma:

```
erro 201 (Id duplicado/evento já processado)  ▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆▆ 87
erro 1042 (assinatura inválida)               ▆▆ 8
falha_rede (timeout)                          ▆ 4
desconhecido                                  ▏ 1
```

Esse histograma é a primeira "métrica de saúde" do pipeline.

### 2.4 Drawer de Cadeia do CPF

Continua mostrando:

- v0 (zip inicial) — 🔒 imutável, com `nr_recibo` original
- v1 (envio teste) — registrado como **tentativa**, NÃO como nova versão de
  `explorador_eventos`. Aparece na seção "Tentativas registradas":
  - status (🟢🔴🟡)
  - link para baixar XML enviado/retorno
- HEAD continua apontando para v0 (carimbo "🔒 HEAD" na v0).

### 2.5 Banner "estado de t1"

Quando o usuário clica em v1 na régua, o banner amarelo aparece:

```
📅 Você está olhando o estado de v1 — [voltar pro AGORA]
```

Reforça que **v1 é fotografia do envio teste**, não é o estado oficial da base.

### 2.6 Download em massa

Botão **"📦 baixar todos XMLs (zip)"** no painel de v1 → empacota
on-the-fly num zip:

```
envio_teste_2025-08_v1.zip
├── enviados/
│   ├── 00111122233.xml
│   ├── 00222333444.xml
│   └── ...
└── retornos/
    ├── 00111122233.xml
    └── ...
```

Os XMLs em `enviados/` são **idênticos** aos que estão no ZIP original do mês —
só que organizados por CPF/tentativa para facilitar a comparação.

---

## Parte 3 — Modelo de dados (o que muda)

Não precisa de migration nova. Reaproveita o que já existe no Chain Walk v2:

### `timeline_envio` (linha nova)

```
id           : 2
timeline_mes : 1 (agosto/2025/SOLUCOES)
sequencia    : 1
tipo         : 'envio_massa'
status       : 'em_andamento' → 'concluido'
iniciado_em  : NOW()
total_tentados : 100
total_sucesso  : NN
total_erro     : NN
resumo       : {
  "modo": "simulado" | "real",
  "rotulo": "envio teste 100",
  "criterio": "100 primeiros CPFs HEAD ordem alfabética",
  "lotes": 3,
  "histograma_erros": { "201": 87, "1042": 8, ... }
}
```

### `timeline_envio_item` (100 linhas)

```
timeline_envio_id : 2
cpf               : '00111122233'
tipo_evento       : 'S-1210'
status            : 'sucesso' | 'erro_esocial' | 'falha_rede' | 'pendente'
versao_anterior_id: id em explorador_eventos do HEAD original
versao_nova_id    : NULL  (nada virou versão nova)
nr_recibo_anterior: nr_recibo do original
nr_recibo_novo    : nr_recibo do retorno (se sucesso, será o mesmo do anterior)
xml_enviado_oid   : OID do LO com bytes idênticos ao XML do ZIP
xml_retorno_oid   : OID do LO com a porção do XML de retorno do eSocial
erro_codigo       : '201' / '1042' / 'TIMEOUT' / NULL
erro_mensagem     : texto do erro
duracao_ms        : tempo de envio + resposta
```

### `explorador_eventos` (sem alteração)

`retificado_por_id` continua NULL para todos os 100. Nada virou versão antiga.

---

## Parte 4 — Endpoints novos no backend (resumo)

| Método | Path                                                        | Função                                                                                                  |
| ------ | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| POST   | `/api/explorador/timeline/envio-teste/criar`                | cria `timeline_envio` v1 + 100 `timeline_envio_item` com `xml_enviado_oid` populado e `status=pendente` |
| POST   | `/api/explorador/timeline/envio-teste/{envio_id}/processar` | dispara o motor (modo `simulado` ou `real`) sobre os items pendentes                                    |
| GET    | `/api/explorador/tentativa/{item_id}/xml-enviado`           | stream do LO (bytes idênticos ao XML do ZIP)                                                            |
| GET    | `/api/explorador/tentativa/{item_id}/xml-retorno`           | stream do LO de retorno                                                                                 |
| GET    | `/api/explorador/timeline/envio/{envio_id}/zip-tentativas`  | empacota tudo on-the-fly                                                                                |

Os primeiros dois são **mutáveis** (POST) e exigem confirmação no front.

---

## Parte 5 — Sequência de ações para o operador

1. Subir/extrair o ZIP de agosto/2025 (já feito).
2. Acessar **Explorador → Chain Walk → mês 2025-08**.
3. Clicar em **"➕ criar envio teste (100 CPFs HEAD)"** — modal de confirmação.
4. v1 aparece como bolinha 🟡 (em_andamento) na régua, com 100 itens `pendente`.
5. Clicar **"▶ processar (modo simulado)"** ou **"▶ processar (modo real)"**.
6. Bolinha vira 🟢/🟠 conforme distribuição de status.
7. Abrir o painel de v1, ver contadores + histograma + lista de CPFs.
8. Baixar XMLs individuais ou em zip, comparar com os do ZIP original — devem
   bater byte-a-byte.

---

## Parte 6 — Não-objetivos

Esta etapa **não inclui**:

- alterar `head_envio_id` (continua apontando para v0);
- gerar XML novo / retificação (`indRetif=2`) — isso é função do "montador de
  S-1210", outro módulo;
- consultar download cirúrgico do eSocial (limite de 10/dia — vide
  `/memories/esocial-critical-rules.md`);
- limpar zips antigos.

---

## Parte 7 — Mitigações

- Antes de processar em modo `real`: alertar usuário sobre cota e pedir
  confirmação digitada (frase fixa) — análogo ao modal de limpeza anual.
- Se o motor não estiver disponível (`app.esocial_client` ausente), o endpoint
  `/processar?modo=real` retorna 503 com instrução clara.
- Idempotência: bloqueia criação de novo envio teste se já existe um
  `em_andamento` para o mesmo (mês, rótulo).
- Logs em `explorador_atividade` para cada criação/processamento.

---

**Documento criado em 07/05/2026** — primeira aplicação prática do Chain Walk
v2. Próximo módulo natural: **montador de S-1210** (vide
[../../Easy-Social/docs/GUIA_MONTAGEM_S1210.md](../../Easy-Social/docs/GUIA_MONTAGEM_S1210.md)
no projeto V1).
