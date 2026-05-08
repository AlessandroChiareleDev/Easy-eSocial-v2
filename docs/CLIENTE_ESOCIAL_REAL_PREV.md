# Cliente eSocial — adaptação a partir do projeto Real Prev

> Documento operacional para implementar o **cliente SOAP do eSocial** dentro
> do `Easy-eSocial-v2/backend` (FastAPI). Toda a base já foi implementada e
> validada no projeto **Real Prev** (`C:\Users\xandao\Documents\GitHub\Projeto`).
> Este MD descreve **o quê copiar, o quê adaptar e por quê**.

---

## 1. Onde está o código fonte de referência (Real Prev)

```
C:\Users\xandao\Documents\GitHub\Projeto\python-backend\esocial\
├── esocial_client.py          ← cliente SOAP: enviar_lote / consultar_lote
├── xml_signer.py              ← assinatura XMLDSig (signxml)
├── xml_validator.py           ← validação estrutural pré-envio
├── xsd_validator.py           ← validação contra XSD oficial
├── xml_generator.py           ← (não precisa para reenvio — só para gerar do zero)
├── certificate_manager.py     ← carrega .pfx, decifra senha
├── certificate_extractor.py
├── comparador_dados.py
└── schemas/                   ← XSDs oficiais do eSocial S-1.2 / S-1.3
```

URLs oficiais (já no `esocial_client.py`):

| Ambiente            | Envio                                                    | Consulta                         |
| ------------------- | -------------------------------------------------------- | -------------------------------- |
| `producao`          | `webservices.esocial.gov.br/.../WsEnviarLoteEventos.svc` | `.../WsConsultarLoteEventos.svc` |
| `producao_restrita` | `webservices.producaorestrita.esocial.gov.br/...`        | idem                             |
| `homologacao`       | (mesmo da `producao_restrita`)                           | idem                             |

Endpoints **download cirúrgico** (consulta identificadores / solicitar /
download eventos) **não estão** nesse cliente — são limitados a 10/dia e ficam
fora deste módulo. Aqui só usamos `EnviarLoteEventos` e
`ConsultarLoteEventos`.

---

## 2. O que precisamos no Easy-eSocial-v2

Para o **envio teste de 100 CPFs S-1210** (vide
[COMO_ENVIAR_SOLUCOES.md](COMO_ENVIAR_SOLUCOES.md)) o módulo precisa:

| #   | Função                                                                                                        | Origem (Real Prev)                    | Destino (v2)            |
| --- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ----------------------- |
| 1   | `ESocialClient.enviar_lote(xmls_assinados, cert_path, senha, ...)`                                            | `esocial_client.py:120-260`           | `app/esocial_client.py` |
| 2   | `ESocialClient._montar_lote_envio(xmls, ...)`                                                                 | `esocial_client.py:285-450`           | mesmo arquivo           |
| 3   | `ESocialClient.consultar_lote(protocolo, ...)`                                                                | `esocial_client.py:_consultar_lote*`  | mesmo arquivo           |
| 4   | `parsear_resposta_envio(xml)` / `parsear_resposta_consulta(xml)`                                              | idem                                  | mesmo arquivo           |
| 5   | Carga do certificado .pfx → PEM temporário                                                                    | `_create_soap_client` + `enviar_lote` | helper `app/cert.py`    |
| 6   | (NÃO copiar `xml_signer.py`) — os XMLs do reenvio **já estão assinados**, vieram do ZIP do retorno do eSocial | —                                     | —                       |

> 🔑 Diferença crítica vs. Real Prev: lá, o fluxo é "gera XML → assina →
> envia". Aqui é **"pega XML que já vem assinado do ZIP do retorno do
> eSocial → envia"**. Pulamos `xml_generator` e `xml_signer`. A assinatura
> existente no XML é válida e o `Id` do evento já está fixado.

---

## 3. Como o lote é montado

Resumo do que `_montar_lote_envio` faz (transcrição comentada):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/v1_1_0">
  <envioLoteEventos grupo="2">
    <ideEmpregador>
      <tpInsc>1</tpInsc>           <!-- 1=CNPJ -->
      <nrInsc>05969071</nrInsc>    <!-- raiz CNPJ SOLUCOES -->
    </ideEmpregador>
    <ideTransmissor>
      <tpInsc>1</tpInsc>
      <nrInsc>{cnpj_do_certificado}</nrInsc>
    </ideTransmissor>
    <eventos>
      <evento Id="ID1...">          <!-- mesmo Id do evento interno -->
        <eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtRemun/v_S_01_02_00">
          <evtRemun Id="ID1...">...</evtRemun>
          <Signature>...</Signature>  <!-- assinatura ORIGINAL preservada -->
        </eSocial>
      </evento>
      <evento Id="ID1...">...</evento>
      ... (até 40 por lote no Simplificado)
    </eventos>
  </envioLoteEventos>
</eSocial>
```

Pontos críticos extraídos do código da Real Prev:

1. **Manter o `<eSocial>` wrapper** dentro de `<evento>` — sem ele o SERPRO
   responde 402 "evtProcTrab/evtRemun element is not declared".
2. **Remover só o `<?xml ?>`** do XML do evento (não pode haver declaração
   aninhada dentro do envelope SOAP).
3. **`<evento Id="...">` precisa ser igual ao `Id` do `evtRemun`** dentro —
   senão erro SERPRO 555.
4. **`grupo`**: para S-1210 reenvio o valor é `2` (eventos periódicos).
5. **Limite Simplificado** = 40 eventos por lote.

---

## 4. Envelope SOAP

```http
POST .../WsEnviarLoteEventos.svc HTTP/1.1
Content-Type: text/xml; charset=utf-8
SOAPAction: http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_1_0/ServicoEnviarLoteEventos/EnviarLoteEventos

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:v1="http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_1_0">
  <soapenv:Header/>
  <soapenv:Body>
    <v1:EnviarLoteEventos>
      <v1:loteEventos>{lote_xml_sem_xml_decl}</v1:loteEventos>
    </v1:EnviarLoteEventos>
  </soapenv:Body>
</soapenv:Envelope>
```

> Real Prev abandonou `zeep` para o envio (zeep tem bugs de namespace com WCF
> da SERPRO) e foi para **`requests` puro com SOAP montado à mão** — vamos
> fazer igual no v2.

Autenticação: **mTLS com o .pfx** convertido para PEM temporário (cert + key
separados). Preserva privacidade do .pfx — nunca persiste em disco fora de
`tempfile.NamedTemporaryFile(delete=False)` que é apagado no `finally`.

---

## 5. Resposta do eSocial

`enviar_lote` devolve algo do tipo:

```json
{
  "sucesso": true,
  "protocolo": "1.2.202508.0000000123456789",
  "dh_recebimento": "2026-05-07T14:32:11-03:00",
  "status_lote": "201",
  "descricao": "Lote sendo processado"
}
```

E **o protocolo precisa ser consultado** depois (assíncrono):

```python
client.consultar_lote(protocolo, cert_path, cert_password)
# devolve dict com lista de eventos: nrRecibo, status, ocorrencias[]
```

No v2 o orquestrador do envio teste vai:

1. POST `EnviarLoteEventos` → salva `protocolo` em
   `timeline_envio.resumo.protocolos[]`
2. Polling a cada N segundos em `ConsultarLoteEventos` (limite generoso, sem
   abusar — o serviço de consulta de lote não conta no quota de 10/dia da API
   de download)
3. Quando status_lote = `202` (processado) → distribui resultado por CPF nos
   `timeline_envio_item`

---

## 6. Erros conhecidos (catálogo curto)

Extraído da experiência Real Prev:

| Código          | Significado                             | Tratamento sugerido                   |
| --------------- | --------------------------------------- | ------------------------------------- |
| `201`           | Lote em processamento                   | normal — consultar depois             |
| `202`           | Lote processado                         | distribuir status por evento          |
| `301`           | Erro estrutural do lote                 | revisar montagem (provável bug nosso) |
| `402`           | Elemento não declarado                  | manter wrapper `<eSocial>`            |
| `555`           | Id do evento ≠ Id do `<evento>` no lote | mesmo Id                              |
| `627`           | Assinatura inválida                     | XML foi modificado após assinatura    |
| `1042`          | XSD inválido                            | rodar validador local antes           |
| `MS5XX/timeout` | Indisponibilidade ou cota               | retry com backoff                     |

Para **reenvio do mesmo XML que veio do download**, esperamos receber em
massa um código de "evento já processado" / duplicado — exatamente o que
sinaliza que o pipeline funcionou.

---

## 7. Plano de adaptação (passos)

### 7.1 Copiar e simplificar

```
copy Projeto/python-backend/esocial/esocial_client.py
   ->  Easy-eSocial-v2/backend/app/esocial_client.py
```

Remover do arquivo:

- toda menção a `xml_signer` (não usamos);
- helpers de "geração" de evento (já temos XML pronto);
- prints/`logging.info` decorativos;
- código específico de S-2500/S-2501 (foco aqui é S-1210).

Manter / portar:

- `URLS` dict;
- `enviar_lote(xmls_bytes_list, cert_path, cert_password, ...)` — adaptar para
  receber **lista de bytes de XML já assinados** e empacotar em UM lote por
  chamada;
- `_montar_lote_envio` ajustado para múltiplos eventos no mesmo `<eventos>`;
- `consultar_lote(protocolo, cert_path, cert_password, ...)`;
- `_parsear_resposta_envio`, `_parsear_resposta_consulta`.

### 7.2 Configuração

Adicionar em `app/config.py`:

```python
ESOCIAL_AMBIENTE      = _env("ESOCIAL_AMBIENTE", "homologacao")
ESOCIAL_CERT_PATH     = _env("ESOCIAL_CERT_PATH", "")
ESOCIAL_CERT_PASSWORD = _env("ESOCIAL_CERT_PASSWORD", "")
ESOCIAL_CNPJ_RAIZ     = _env("ESOCIAL_CNPJ_RAIZ", "05969071")
ESOCIAL_GRUPO         = int(_env("ESOCIAL_GRUPO", "2"))
ESOCIAL_LOTE_MAX      = int(_env("ESOCIAL_LOTE_MAX", "40"))
```

`.env` real de produção fica fora do git (já tem `.gitignore`); os
certificados ficam em `_certificados_locais/` (já existe no Easy-Social).

### 7.3 Engine de envio

`app/envio_engine.py` (novo):

```python
def enviar_em_modo_real(envio_id: int) -> None:
    """Pega timeline_envio_item pendentes, monta lotes <=40,
    chama esocial_client.enviar_lote, persiste protocolo,
    depois faz polling consultar_lote e atualiza items."""
```

E o stub `enviar_em_modo_simulado(envio_id)` (já útil pra UI sem cliente real
disponível). O endpoint `POST /timeline/envio-teste/{id}/processar?modo=real`
roteia entre os dois.

### 7.4 Persistência do retorno

Para cada item do lote, gravar:

- `xml_retorno_oid` = LO com o XML de retorno do `consultar_lote` recortado
  pro evento (use XPath por `Id`);
- `nr_recibo_novo` = `nrRecibo` do retorno;
- `erro_codigo` / `erro_mensagem` = `status.cdResposta` + `descricao` da
  primeira ocorrência erro (se houver).

### 7.5 Testes mínimos antes de apertar "real"

1. Modo `simulado` rodando ponta-a-ponta na UI (sem chamar eSocial).
2. Validar XSD localmente (xsd_validator do Real Prev — opcional, defensivo).
3. Em `homologacao` (= produção restrita SERPRO) com 1 CPF antes dos 100.
4. Quando ok: `producao` com os 100 CPFs.

---

## 8. Diferenças sutis a NÃO esquecer

1. **Encoding**: tudo UTF-8, sem BOM. Real Prev teve falha em produção quando
   `xml_evento.decode("utf-8-sig")` deixou BOM no meio do envelope.
2. **`Signature` element**: NÃO mexer no XML do evento (não reformatar, não
   prettify, não strip()). Reescrita altera o digest e quebra a assinatura.
3. **`grupo`**: S-1210 = `2`, não `1`. (`1` é totalizadores e tabelas; `3`
   simplificado, `4` doméstico.)
4. **Timezone do timestamp**: `pytz.timezone("America/Sao_Paulo")`
   obrigatório (eSocial rejeita UTC puro em alguns campos auxiliares).
5. **`session.verify = False`** _somente_ em homologação. Em produção,
   manter validação SSL.

---

## 9. Pontos de contato

- Implementação inteira do Real Prev: `Projeto/python-backend/esocial/`
- A IA do projeto Real Prev já validou esses pontos em produção real (eSocial
  S-1.2 / S-1.3, eventos S-2500/S-2501, S-1000, S-1005, S-2200).
- Para reenvio S-1210 (foco do v2 agora), o caminho mais curto: copiar
  `enviar_lote` + `_montar_lote_envio` + `consultar_lote` e instrumentar.

---

## 10. TODO

- [ ] Copiar e simplificar `esocial_client.py` para `app/esocial_client.py`
- [ ] Adicionar variáveis de ambiente em `config.py`
- [ ] Criar `app/envio_engine.py` (modos `simulado` e `real`)
- [ ] Endpoint `POST /api/explorador/timeline/envio-teste/{id}/processar`
- [ ] Endpoint `GET /api/explorador/tentativa/{item_id}/xml-enviado` e
      `xml-retorno`
- [ ] UI: botão "🚀 disparar envio teste 100 CPFs" + modal confirmação +
      visualização v1 com histograma de erros

---

**Documento criado em 07/05/2026** — referência para portar o cliente
SOAP eSocial do projeto Real Prev para o Easy-eSocial-v2.
