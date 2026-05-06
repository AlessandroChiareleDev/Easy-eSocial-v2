# Explicação: como funciona ENVIO de S-1210 por CPF (1 CPF pode ter VÁRIOS XMLs no mesmo mês)

> Documento companheiro do `explicacao todos eventos que vem mes a mes do esocial.md`.
> Aquele explica **DOWNLOAD** (o que vem do eSocial dentro dos zips).
> Este aqui explica **ENVIO** (o que a gente MANDA pro eSocial).
> Foco: por que um CPF tem mais de um S-1210 no mesmo mês e como o sistema lida com isso.

---

## 1. REGRA FUNDAMENTAL EM 1 LINHA

**1 pagamento = 1 XML S-1210.** Se o trabalhador recebeu 3 pagamentos no mês, são 3 S-1210 enviados. Sem regra fixa de quantos.

---

## 2. EVIDÊNCIA REAL — APPA, ano 2025

Consulta na tabela `s1210_cpf_envios` da APPA (Supabase, empresa_id=1):

| Mês     | CPFs únicos | Envios c/ sucesso | Média/CPF | Pico observado          |
|---------|------------:|------------------:|----------:|-------------------------|
| 2025-01 |     11.290  |           11.280  |   1,00    | 1 envio/CPF             |
| 2025-02 |     11.600  |           18.623  |   1,61    | misto                   |
| 2025-03 |     11.185  |           20.756  |   1,86    | quase 2/CPF             |
| 2025-06 |      9.475  |           11.872  |   1,25    | 6.988 com 1, 2.442 com 2 |
| **2025-08** | **7.477** |  **16.088**   | **2,15** | 142 com 1, 6.647 com 2, **588 com 4, 50 com 6** |
| 2025-12 |      7.423  |           14.188  |   1,91    | 6.989 com 2, 70 com 3   |

> **Conclusão:** TEM CPF que recebeu **6 S-1210 num mês só** (agosto/2025). Isso é normal e legal — cada um é um pagamento real diferente.

---

## 3. POR QUE UM CPF TEM MÚLTIPLOS S-1210?

Cada **NATUREZA** de pagamento gera um S-1210 separado:

| Natureza             | Exemplo                                 | Quando vira XML |
|----------------------|-----------------------------------------|-----------------|
| **Folha mensal**     | salário do mês                          | Sempre          |
| **Adiantamento**     | vale do dia 20                          | Empresa que paga vale |
| **Plano de saúde**   | titular + dependentes (cnpjOper, regANS, vlrSaudeTit) | Quando empresa banca plano |
| **Férias**           | quando o cara sai de férias             | No mês das férias |
| **13º salário**      | parcelas 1 e 2                          | Nov + dez (ou jan ano seguinte) |
| **Rescisão**         | TRCT — verbas rescisórias               | No mês do desligamento |
| **Complemento IRRF** | ajuste de IR retido                     | Quando contabilidade descobre erro |
| **Processo trabalhista** | pagamento por sentença              | Quando juiz manda pagar |

> Cada uma dessas vira **1 XML S-1210 com `tpPgto` diferente** (ou mesma `tpPgto` mas blocos `<infoPgto>` separados).

---

## 4. OS 3 LOTES DA APPA — NOSSA ORGANIZAÇÃO

A APPA **divide os pagamentos em 3 grupos** (`lote_num` 1, 2, 3) por motivo operacional:

| Lote | Conteúdo típico                            | Por que separado |
|------|--------------------------------------------|------------------|
| **1** | Folha mensal + adiantamento                | Maior volume — primeira a transmitir |
| **2** | Pagamentos com **plano de saúde**          | Precisa do XLSX `aba_operadoras` (cnpjOper, regANS, vlrSaudeTit) |
| **3** | Complementos: férias, rescisão, ajustes IR | Menor volume, casos específicos |

> Importante: **dentro do MESMO lote um CPF pode aparecer mais de uma vez** se ele recebeu 2 pagamentos da mesma natureza. O lote é só um agrupamento operacional nosso, não regra do eSocial.

---

## 5. DE ONDE VEM A INFORMAÇÃO DOS PAGAMENTOS?

A contabilidade da empresa manda uma **planilha XLSX** por mês. Estrutura:

```
xlsx upload → s1210_xlsx (1 linha por arquivo)
            → s1210_cpf_scope (N linhas: 1 por LINHA da planilha)
            → s1210_cpf_envios (N linhas: 1 por TENTATIVA de envio)
```

- **`s1210_xlsx`**: o arquivo em si (sha256, totais)
- **`s1210_cpf_scope`**: cada linha da planilha vira aqui. Se o CPF X tem 2 pagamentos no XLSX (folha + adiantamento), são 2 linhas no scope.
- **`s1210_cpf_envios`**: cada vez que tentamos enviar um pagamento, vira 1 linha. **Múltiplas tentativas do mesmo pagamento criam várias linhas** (status pode ser `ok`, `erro`, `erro_rede`, `enviando`, `na`, `ok_recuperado`).

> **Cuidado quando contar "quantos S-1210 enviei":** filtra `status IN ('ok','ok_recuperado')` pra não contar tentativas falhadas.

---

## 6. RETIFICAÇÃO — REENVIANDO UM CPF

> **Pergunta:** "se o cara tem 2 S-1210 no mês e eu quero corrigir, eu mando 1 ou os 2?"

**Resposta:** Mando os 2, ou 1, depende do que mudou.

### Regra prática

- Cada S-1210 enviado tem um **`nrRecibo`** próprio devolvido pelo eSocial.
- Pra retificar UM pagamento específico:
  - Gera novo XML com `<indRetif>2</indRetif>` + `<nrRecibo>NRRECIBO_ORIGINAL_DAQUELE_PAGAMENTO</nrRecibo>`
  - Os OUTROS pagamentos do mesmo CPF/mês **não precisam reenviar** se estiverem certos
- Pra excluir UM pagamento que foi mandado errado:
  - Manda S-3000 apontando o `nrRecibo` daquele S-1210 específico
  - Os outros ficam de boa

### Caso comum: erro 459 (recibo não encontrado)

> Se o eSocial diz que não acha o `nrRecibo`, você precisa primeiro **descobrir qual é o recibo certo** daquele pagamento. Por isso temos `s1210_cpf_recibo` com 3 fontes:
> - `nr_recibo_zip`: tirado do XML que baixamos do eSocial
> - `nr_recibo_usado`: o que tentamos usar
> - `nr_recibo_esocial`: o que o eSocial confirmou via consulta

---

## 7. COMO O CÓDIGO MONTA O LOTE PRO eSOCIAL

`python-scripts/esocial/s1210_repo_routes.py` — endpoint `POST /api/s1210-repo/enviar-lote-cpfs`:

```
Input:  {empresa_id, per_apur, lote_num, cpfs:[CPF1,CPF2,...]}

Pra cada CPF:
  1. Lê os pagamentos daquele CPF/per_apur do scope (s1210_cpf_scope)
  2. Se for lote 2, junta info de plano de saúde (cnpjOper, regANS, vlrSaudeTit)
  3. Gera 1 XML S-1210 contendo TODOS os pagamentos do CPF naquele lote
  4. Assina o XML com cert A1

Junta TODOS os XMLs num SOAP único (até 50 CPFs por lote eSocial)
Envia → recebe protocolo
Polla consulta → distribui resposta CPF a CPF
Salva 1 linha por CPF em s1210_cpf_envios
```

> **Detalhe importante:** **1 XML S-1210 pode conter VÁRIOS `<infoPgto>` do mesmo CPF**. O eSocial aceita agregar pagamentos do mesmo trabalhador num XML só, desde que sejam da mesma `tpPgto` e `perRef`. Por isso a média na tabela não é "1 XML por pagamento" exato — pode ser "1 XML por GRUPO de pagamentos da mesma natureza".

---

## 8. DIFERENÇA ENVIO (APPA) vs DOWNLOAD (zip do eSocial)

| Aspecto              | s1210_cpf_envios (nosso banco)        | Zip baixado do eSocial          |
|----------------------|---------------------------------------|---------------------------------|
| O que tem            | Tudo que **NÓS** enviamos             | Tudo que **EMPRESA** transmitiu (nós + outros sistemas) |
| Cobertura APPA       | Desde quando viraram cliente nosso    | Histórico inteiro da empresa    |
| Cobertura SOLUCOES   | **ZERO** (nunca enviamos pra SOLUCOES) | Tudo que a contabilidade mandou |
| Granularidade        | 1 linha por tentativa de envio        | 1 XML por evento aceito         |
| Status               | ok, erro, erro_rede, enviando, na, ok_recuperado | sempre "aceito" (se tá no zip, foi aceito) |

### Exemplo concreto: APPA junho/2025

- **Nosso banco**: 11.872 envios com sucesso (9.475 CPFs)
- **Zip baixado**: 19.234 S-1210 (9.616 CPFs)
- **Diferença de 7.362 XMLs**: foram enviados antes da gente assumir a APPA (provavelmente TI Solutions ou contabilidade antiga). Eles existem no eSocial mas a gente não tem registro.

---

## 9. TABELAS DO SCHEMA APPA RELACIONADAS A S-1210

```
s1210_xlsx              — arquivos XLSX da contabilidade (1 por per_apur normalmente)
s1210_cpf_scope         — linha-a-linha da planilha (CPF + pagamentos crus)
s1210_cpf_envios        — tentativas de envio (status, nr_recibo, xml, resposta)
s1210_cpf_recibo        — recibos confirmados (3 fontes: zip, usado, eSocial)
s1210_cpf_blocklist     — CPFs que NÃO devem ser enviados (motivos manuais)
s1210_lote1_codfunc_scope — escopo específico do lote 1 por código de função
s1210_operadoras        — cadastro de operadoras de plano de saúde (cnpjOper, regANS)
v_s1210_contadores      — view de contadores agregados pra dashboard
```

---

## 10. RESUMÃO DE BOLSO

| Pergunta                                          | Resposta curta                                      |
|---------------------------------------------------|-----------------------------------------------------|
| Quantos XMLs por CPF por mês?                     | Depende de quantos pagamentos. 1 a 6 é normal.      |
| Tem regra fixa?                                   | Não. 1 XML por natureza de pagamento.               |
| Pra reenviar, mando todos?                        | Não. Só os que mudaram, com `indRetif=2` + `nrRecibo` original de cada um. |
| O que é lote_num 1, 2, 3?                         | Organização NOSSA (folha/plano/complemento). eSocial não sabe disso. |
| Por que SOLUCOES não tem nada em s1210_cpf_envios? | Nunca enviamos pra SOLUCOES — esses XMLs vieram de outro sistema. |
| Por que tem mais XML no zip do que enviei?        | Empresa enviou por outros sistemas antes (ou paralelamente). |
| Por que tem menos XML no zip do que enviei?       | Zip incompleto, ou exclusões S-3000 já aplicadas.   |

---

> **Próximo passo (futuro):** Construir **Explorador de Eventos** no V2 que mostra, por CPF, TIMELINE de TODOS os S-1210 (enviados + recebidos), com chain walk completo: S-2200 (admissão) → S-1200 (folha) → S-1210 (pagamento) → S-5001/2/3 (totalizadores) → S-2299 (desligamento). Documentado no roadmap do README do V2.
