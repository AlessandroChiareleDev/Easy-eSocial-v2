# CICLO100 — Técnica de Envio Massivo S-1210 ao eSocial em Levas de 100 CPFs

> Documento auto-contido. Leia do início ao fim — assume **zero conhecimento prévio** do projeto.

---

## 1. O que é o CICLO100

**CICLO100** é uma técnica operacional de envio massivo de eventos `S-1210` (Pagamentos a Trabalhadores) ao Web Service do eSocial em **levas controladas de 100 CPFs por execução**, agrupadas em **rodadas de 20 levas (= 2.000 CPFs por "leva grande")**, com:

- **Validação contínua da taxa de erro a cada 100 CPFs** (regra de parada se >20%);
- **Idempotência total** entre execuções (`--pular-ja-tentados` evita reenviar quem já foi tentado);
- **Auditoria persistente** em `timeline_envio` / `timeline_envio_item` para reconciliação posterior;
- **Reportagem mínima entre rodadas** ("**N/20** (envio M): X✅/Y❌ (Z%). Segue.") para não poluir contexto.

A técnica foi forjada validando o fix do `_gerar_id` (atomic global counter) sobre **13.646 CPFs reais** em produção (`per_apur=2025-08`, empresa SOLUCOES SERVIÇOS TERCEIRIZADOS, CNPJ 09445502000109) com **taxa de erro final de 2,79%** e **zero ocorrências de erro 543/1089** (que era o bug original).

---

## 2. Por que 100 CPFs por leva (e não 500 ou 1000)

| Tamanho | Risco | Tempo médio | Granularidade de stop |
|---|---|---|---|
| 50 | desperdício de overhead | ~30s | excessiva |
| **100** | **ótimo** | **~50–70s** | **boa (≤1 min de prejuízo se algo der errado)** |
| 200–500 | janela longa sob falha | 2–5 min | ruim — descobre tarde |
| 1000+ | timeline_envio gigante, difícil reconciliar | 10+ min | péssima |

**100 é o sweet spot**: dá pra **abortar em 1 minuto** se uma leva passar de 20% de erro, sem desperdiçar muito processamento. O eSocial impõe `batch_size ≤ 50`, então 100 vira **2 batches paralelos × 50 CPFs**, casando perfeitamente com `workers=5`.

---

## 3. Pré-requisitos de ambiente

### 3.1. Banco de dados PostgreSQL
- Host: `localhost:5432`
- Database: `easy_social_solucoes`
- User/Pass: `postgres`/`postgres`
- Tabelas usadas:
  - `explorador_eventos` — XMLs S-1210 originais (HEAD = `retificado_por_id IS NULL`).
  - `empresa_zips_brutos` — vínculo `zip_id ↔ empresa_id`.
  - `timeline_envio` — uma linha **por execução** (= 1 leva de 100). Campos chave: `id`, `total_tentados`, `total_sucesso`, `total_erro`, `histograma_erros` (JSONB), `status`.
  - `timeline_envio_item` — uma linha **por CPF** dentro do envio. Campos chave: `cpf`, `tipo_evento`, `status` (`sucesso` / `erro_esocial` / `pendente_consulta`), `erro_codigo`.
  - `timeline_mes` — agrupador por `(empresa_id, per_apur)`.

### 3.2. Backend Python
- Caminho: `C:\Users\xandao\Documents\GitHub\Easy-eSocial-v2\backend`
- venv ativado: `c:\Users\xandao\Documents\GitHub\Easy-Social\.venv\Scripts\Activate.ps1`
- Módulo: `app.envio_paralelo_v2`

### 3.3. Certificado digital eSocial (A1, .pfx)
- Path: `c:\Users\xandao\Documents\GitHub\Easy-Social\_certificados_locais\SOLUCOES_SERVICOS_TERCEIRIZADOS_09445502000109.pfx`
- Senha: `Sol500424`
- CNPJ titular: `09445502000109`

### 3.4. Limite eSocial — REGRA DE OURO
- **EnviarLoteEventos** (envio de eventos): **NÃO tem cota diária** — pode rodar à vontade.
- **WsConsultarIdentificadores / WsSolicitarDownload**: cota de **10 chamadas/dia compartilhada** entre TODAS as APIs de download. Não usar durante o CICLO100.
- HTTP 500 com `ServiceActivationException` = limite diário atingido (não é serviço fora).

---

## 4. Comando canônico de uma rodada CICLO100

```powershell
cd 'C:\Users\xandao\Documents\GitHub\Easy-eSocial-v2\backend'
python -m app.envio_paralelo_v2 `
  --per-apur 2025-08 `
  --limite 100 `
  --workers 5 `
  --batch 50 `
  --progress-every 50 `
  --cert 'c:\Users\xandao\Documents\GitHub\Easy-Social\_certificados_locais\SOLUCOES_SERVICOS_TERCEIRIZADOS_09445502000109.pfx' `
  --senha 'Sol500424' `
  --cnpj '09445502000109' `
  --ambiente producao `
  --pular-ja-tentados `
  2>&1 | Tee-Object -FilePath '_envio_loteNN.log'
```

### 4.1. Anatomia das flags

| Flag | Valor | Por quê |
|---|---|---|
| `--per-apur` | `2025-08` | competência (YYYY-MM). Trocar para a próxima per_apur ao migrar de mês. |
| `--limite` | `100` | **NÃO mudar** — é a essência do CICLO100. |
| `--workers` | `5` | máximo seguro do pool DB (hard-cap no código `envio_paralelo_v2.py`). |
| `--batch` | `50` | limite hard do eSocial (50 eventos por lote). 100 ÷ 50 = 2 batches. |
| `--progress-every` | `50` | imprime linha de progresso a cada 50 CPFs (= meio da leva e final). |
| `--cert` | path .pfx | certificado A1 da empresa titular do envio. |
| `--senha` | string | senha do PFX. |
| `--cnpj` | 14 dígitos | CNPJ do empregador (deve casar com o cert). |
| `--ambiente` | `producao` | use `homologacao` para testes; `producao` para envio real. |
| `--pular-ja-tentados` | flag | **CRÍTICO** — exclui CPFs que já têm linha em `timeline_envio_item` para a mesma `(empresa_id, per_apur, tipo_evento, cpf)`. Garante idempotência. |
| `Tee-Object` | `_envio_loteNN.log` | salva log incrementando NN por rodada (115, 116, 117…). Permite reauditoria offline. |

### 4.2. O que o programa faz internamente

1. **Carrega 100 eventos HEAD** com `DISTINCT ON (cpf)` em `explorador_eventos`, ordenados por `dt_processamento DESC` (= versão mais recente do XML por CPF), pulando os já tentados.
2. **Cria `timeline_envio`** com `id` autoincrement (envio_id) e marca `total_tentados=100`.
3. **Cria 100 linhas em `timeline_envio_item`** com status inicial `pendente`.
4. **Divide em 2 batches de 50**, distribui entre `workers=5` (sobra capacidade — limite real é o eSocial).
5. Cada worker:
   - Lê XML do `lobject` (Postgres LO).
   - Assina com o PFX (XMLDSig).
   - Monta `eSocial.EnviarLoteEventos` (SOAP) com `idEvento` único usando `_gerar_id` (atomic counter — fix do bug).
   - POST → recebe `cd=201` (lote aceito) + `nrProtocolo`.
   - **Polling** a cada 8s até `cd_lote=201` (processado, max 12 tentativas = ~96s).
   - Para cada CPF: parsea retorno e atualiza `timeline_envio_item.status` + `erro_codigo`.
6. **Histograma final**: `SELECT erro_codigo, COUNT(*) FROM timeline_envio_item WHERE timeline_envio_id=X GROUP BY erro_codigo`.
7. Imprime bloco `=== RESUMO PARALELO ===` com `sucesso`, `erro`, `pendente_consulta`, `elapsed`, `histograma`.

### 4.3. Códigos de retorno mais comuns

| Código | O que é | Tratamento CICLO100 |
|---|---|---|
| `201` | sucesso (recibo emitido) | conta como ✅ |
| `202` | advertência (recibo emitido **com aviso** — ex.: cadastro inconsistente) | conta como ❌ no resumo, **mas o evento foi recebido**. Esperado em ~0,7% dos casos. |
| `401` | trabalhador sem cadastro / sem vínculo / S-2200 ausente | conta como ❌. Maior volume de erro real (~2% médio). |
| `543` | id duplicado | **NUNCA mais** após o fix do `_gerar_id` (zero em 13.646 CPFs). Se aparecer = regressão. |
| `1089` | id já recebido anteriormente | **NUNCA mais** após o fix. Se aparecer = regressão. |
| `pendente_consulta` | polling estourou 12 tentativas sem `cd=201` | rodar reconsulta antes de declarar erro. |

---

## 5. O ciclo completo — passo a passo operacional

### 5.1. Antes de começar

1. **Conferir quantos CPFs faltam** para a per_apur:

   Crie/use `backend/_count_pendentes.py`:
   ```python
   import psycopg2, psycopg2.extras
   conn = psycopg2.connect(host='localhost', port=5432, dbname='easy_social_solucoes', user='postgres', password='postgres')
   c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
   c.execute("SELECT DISTINCT empresa_id FROM empresa_zips_brutos ORDER BY 1")
   empresa_id = c.fetchall()[0]['empresa_id']
   PER = '2025-08'  # <-- TROCAR aqui ao mudar de mês
   c.execute(f"""
   SELECT COUNT(*) AS pendentes FROM (
     SELECT DISTINCT ON (ev.cpf) ev.id
       FROM explorador_eventos ev
       JOIN empresa_zips_brutos z ON z.id=ev.zip_id
      WHERE z.empresa_id=%s AND ev.tipo_evento='S-1210' AND ev.per_apur=%s
        AND ev.retificado_por_id IS NULL AND ev.xml_oid IS NOT NULL
        AND NOT EXISTS (
              SELECT 1 FROM timeline_envio_item it
                JOIN timeline_envio te ON te.id=it.timeline_envio_id
                JOIN timeline_mes  tm ON tm.id=te.timeline_mes_id
               WHERE tm.empresa_id=%s AND tm.per_apur=%s
                 AND it.tipo_evento='S-1210' AND it.cpf=ev.cpf
            )
      ORDER BY ev.cpf ASC, ev.dt_processamento DESC NULLS LAST, ev.id DESC
   ) sub
   """, (empresa_id, PER, empresa_id, PER))
   print(c.fetchone())
   ```

2. Calcule o número de levas: `pendentes / 100` (arredonde pra cima). Última leva pode ter <100.

### 5.2. Execução: 1 leva grande = 20 rodadas de 100

Para cada rodada N (1 a 20):

1. Executar o **comando canônico** trocando apenas o nome do log: `_envio_lote115.log`, `_envio_lote116.log`, …
2. Aguardar o `=== RESUMO PARALELO ===`.
3. Reportar **uma única linha curta**:
   ```
   **N/20** (envio M): X✅ / Y❌ (Z%). Segue.
   ```
   - `N` = índice da rodada (1 a 20)
   - `M` = `envio_id` (autoincrement do banco)
   - `X` = sucesso, `Y` = erro
   - `Z%` = `Y/100*100`
4. **REGRA DE PARADA**: se `Z > 20%` → **PARAR** imediatamente, **não** iniciar próxima rodada, e pedir análise humana antes de prosseguir.
5. Se `Z ≤ 20%` → ir para rodada N+1.

### 5.3. Após as 20 rodadas

Gerar consolidado da leva grande (envios consecutivos `K` até `K+19`):

```python
# backend/_count_levaN.py (substituir os IDs)
import psycopg2
c = psycopg2.connect(host='localhost', port=5432, dbname='easy_social_solucoes',
                    user='postgres', password='postgres').cursor()
ID_INI, ID_FIM = 142, 161  # <-- ajustar
c.execute("SELECT COALESCE(SUM(total_tentados),0), COALESCE(SUM(total_sucesso),0), "
          "COALESCE(SUM(total_erro),0) FROM timeline_envio WHERE id BETWEEN %s AND %s",
          (ID_INI, ID_FIM))
t,s,e = c.fetchone()
print(f'Leva ({ID_INI}-{ID_FIM}): tentados={t} sucesso={s} erro={e} taxa={100*e/t:.2f}%')
c.execute("SELECT erro_codigo, COUNT(*) FROM timeline_envio_item "
          "WHERE timeline_envio_id BETWEEN %s AND %s AND status='erro_esocial' "
          "GROUP BY erro_codigo ORDER BY 2 DESC", (ID_INI, ID_FIM))
print('Histograma:', c.fetchall())
```

### 5.4. Repetir levas grandes até `pendentes = 0`

A última leva grande pode não fechar 20 rodadas — apenas o necessário para zerar pendentes. A última rodada da última leva pode ter `--limite < 100` automaticamente (o programa seleciona o que sobrar; mostra `selecionados N eventos` com `N` real).

---

## 6. Como replicar para outros meses (per_apur)

### Passos exatos

1. **Trocar `--per-apur`** no comando canônico para a competência alvo (ex.: `2025-09`, `2025-10`).
2. **Trocar `PER` em `_count_pendentes.py`** para a mesma competência.
3. **Rodar `_count_pendentes.py`** para descobrir quantos CPFs pendentes a per_apur tem.
4. **Calcular total de rodadas** = `ceil(pendentes / 100)`.
5. **Executar levas grandes de 20 rodadas** seguindo §5.2.
6. **`--pular-ja-tentados` é por per_apur** — então CPFs tentados em 2025-08 **não bloqueiam** envios em 2025-09 (cada per_apur tem sua própria contagem).
7. **NUNCA reutilizar log filenames** — incrementar `_envio_loteNN.log` continuamente entre per_apur (ex.: 2025-08 terminou em lote137, 2025-09 começa em lote138).

### Cuidados ao mudar de per_apur

- **Verificar se há eventos S-1210 carregados** para a per_apur em `explorador_eventos`. Se `_count_pendentes.py` retornar `total_head=0`, a per_apur não tem dados — precisa baixar/extrair primeiro (fora do escopo do CICLO100).
- **Ambiente**: continuar `producao` (homologação não tem dados reais para validar S-1210).
- **Mesmo certificado/CNPJ** se for a mesma empresa empregadora.

### Tabela de planejamento (modelo)

| per_apur | total_head | pendentes | levas grandes (20) | rodadas extras | log inicial |
|---|---|---|---|---|---|
| 2025-08 | 15.495 | 0 (concluído) | 7 + parcial | — | _envio_lote28.log |
| 2025-09 | ? | ? | ? | ? | _envio_lote138.log |
| 2025-10 | ? | ? | ? | ? | … |

---

## 7. Templates prontos

### 7.1. Loop bash/PowerShell de 20 rodadas (semi-automatizado)

> **Não recomendado para uso cego** — a regra de parada >20% exige análise humana. Use só se você for monitorar.

```powershell
cd 'C:\Users\xandao\Documents\GitHub\Easy-eSocial-v2\backend'
$LOTE_INICIAL = 138  # ajustar
$PER = '2025-09'      # ajustar
for ($i = 0; $i -lt 20; $i++) {
    $lote = $LOTE_INICIAL + $i
    $log = "_envio_lote$lote.log"
    Write-Host "=== Rodada $($i+1)/20 (log=$log) ==="
    python -m app.envio_paralelo_v2 `
      --per-apur $PER --limite 100 --workers 5 --batch 50 --progress-every 50 `
      --cert 'c:\Users\xandao\Documents\GitHub\Easy-Social\_certificados_locais\SOLUCOES_SERVICOS_TERCEIRIZADOS_09445502000109.pfx' `
      --senha 'Sol500424' --cnpj '09445502000109' --ambiente producao --pular-ja-tentados `
      2>&1 | Tee-Object -FilePath $log
    if ($LASTEXITCODE -ne 0) { Write-Host "!! Falha — abortando"; break }
}
```

### 7.2. Linha de relatório padrão (manual, recomendado)

Após cada rodada, copiar exatamente:
```
**N/20** (envio M): X✅ / Y❌ (Z%). Segue.
```

Exemplo real (8ª leva, rodada 14):
```
**14/20** (envio 155): 100✅ / 0❌ (0%). Segue.
```

---

## 8. Histórico de validação (referência)

CICLO100 foi validado de 28/04 a 07/05/2026 sobre `per_apur=2025-08`:

| Leva grande | Envios | CPFs | Erro | Taxa |
|---|---|---|---|---|
| 1ª (parcial) | 28-37 | 1.000 | — | 3,10% |
| 2ª (parcial) | 38-41 | 400 | — | 3,50% |
| 3ª | 42-61 | 2.000 | — | 3,55% |
| 4ª | 62-81 | 2.000 | — | 3,45% |
| 5ª | 82-101 | 2.000 | 75 | 3,75% |
| 6ª | 102-121 | 2.000 | 59 | 2,95% |
| 7ª | 122-141 | 2.000 | 24 | 1,20% |
| 8ª | 142-161 | 2.000 | 30 | 1,50% |
| Final (3 rodadas) | 162-164 | 246 | 8 | 3,25% |
| **TOTAL** | **28-164** | **13.646** | **381** | **2,79%** |

**Histograma final**: `401×280` (sem cadastro) + `202×101` (advertência). **Zero `543`/`1089`** — fix do `_gerar_id` 100% estável.

---

## 9. Troubleshooting rápido

| Sintoma | Causa provável | Ação |
|---|---|---|
| `selecionados 0 eventos` | per_apur sem dados ou todos já tentados | rodar `_count_pendentes.py`; se `total_head=0`, faltam dados |
| HTTP 500 + `ServiceActivationException` em **EnviarLote** | indisponibilidade real do eSocial | aguardar; **não confundir** com cota de download |
| Taxa de erro >20% em uma leva | regressão ou problema cadastral massivo | **PARAR**, ler logs, conferir histograma |
| `pendente_consulta > 0` no resumo | polling estourou 12 tentativas | rodar reconsulta com `WsConsultarLote` antes de declarar erro |
| `543` ou `1089` no histograma | regressão do `_gerar_id` | **STOP TUDO** — abrir investigação no atomic counter |

---

## 10. Comandos rápidos de auditoria pós-CICLO

```sql
-- Total da per_apur
SELECT COALESCE(SUM(total_tentados),0) AS tentados,
       COALESCE(SUM(total_sucesso),0)  AS sucesso,
       COALESCE(SUM(total_erro),0)     AS erro
  FROM timeline_envio te
  JOIN timeline_mes tm ON tm.id=te.timeline_mes_id
 WHERE tm.per_apur='2025-08';

-- Histograma de erros por per_apur
SELECT erro_codigo, COUNT(*)
  FROM timeline_envio_item it
  JOIN timeline_envio te ON te.id=it.timeline_envio_id
  JOIN timeline_mes tm   ON tm.id=te.timeline_mes_id
 WHERE tm.per_apur='2025-08' AND it.status='erro_esocial'
 GROUP BY erro_codigo ORDER BY 2 DESC;

-- CPFs com erro 401 (sem cadastro) — candidatos a investigar S-2200
SELECT DISTINCT cpf FROM timeline_envio_item it
  JOIN timeline_envio te ON te.id=it.timeline_envio_id
  JOIN timeline_mes tm   ON tm.id=te.timeline_mes_id
 WHERE tm.per_apur='2025-08' AND it.erro_codigo='401';
```

---

## 11. Resumo executivo (TL;DR para nova IA)

1. **Comando**: rodar `app.envio_paralelo_v2` com `--limite 100 --workers 5 --batch 50 --pular-ja-tentados`.
2. **Padrão**: 20 rodadas de 100 = 1 "leva grande" de 2.000 CPFs.
3. **Reportagem**: 1 linha curta por rodada (`**N/20** (envio M): X✅ / Y❌ (Z%). Segue.`).
4. **Stop rule**: `Z > 20%` → parar imediatamente.
5. **Idempotência**: `--pular-ja-tentados` garante que reexecutar é seguro.
6. **Replicar p/ outro mês**: trocar `--per-apur`; tudo o mais idêntico.
7. **Após zerar pendentes**: rodar consolidado SQL e histograma para fechar a per_apur.

CICLO100 = simples, auditável, idempotente, com circuit-breaker humano. Pronto para qualquer per_apur.
