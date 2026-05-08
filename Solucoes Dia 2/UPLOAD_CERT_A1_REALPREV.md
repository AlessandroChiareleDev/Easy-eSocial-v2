# UPLOAD A1 — Pattern Real Prev (PORTAR PRO V2)

> Decisão **08/05/2026**: V2 vai herdar o fluxo de upload + assinatura A1 do **Real Prev** (`C:\Users\xandao\Documents\GitHub\Projeto`), não do V1 do Easy-Social. Real Prev é mais maduro, multi-tenant por design, suporta e-CPF e procuração eletrônica.

---

## 1. Por que Real Prev e não V1?

| Aspecto | V1 Easy-Social | Real Prev | Vencedor |
|---|---|---|---|
| Validação PFX | Fernet + cryptography ✅ | Fernet + cryptography ✅ | empate |
| Multi-tenant | nenhum (cert global) | `tenant_token` SHA-256 do CNPJ ✅ | **Real Prev** |
| Suporte e-CPF | só e-CNPJ | e-CPF + e-CNPJ ✅ | **Real Prev** |
| Procuração eletrônica | não | sim — cert pode ser de contador para múltiplos empregadores ✅ | **Real Prev** |
| Status visual (vencido/expirando/válido) | não | sim, com `dias_restantes` ✅ | **Real Prev** |
| Lock anti-duplicata | não | sim (`numero_serie` único) ✅ | **Real Prev** |
| Endpoint listar por empregador | não | sim (`/por-empregador`) ✅ | **Real Prev** |
| Senha senha-salva temporária | sim (24h) | só `senha_encrypted` permanente | empate funcional |
| Assinatura XML | `XMLSigner` custom | `signxml.XMLSigner` + URI vazio (regra eSocial) ✅ | **Real Prev** |
| Bibliotecas | cryptography, lxml, custom | `signxml`, `cryptography`, `lxml` ✅ | **Real Prev** |

---

## 2. Arquivos a copiar do Real Prev

### 2.1. Lift-and-shift (sem mudança lógica)

```
Projeto/python-backend/esocial/certificate_manager.py
Projeto/python-backend/esocial/certificate_extractor.py
Projeto/python-backend/esocial/xml_signer.py
```
→ destino:
```
Easy-eSocial-v2/backend/app/certificate_manager.py
Easy-eSocial-v2/backend/app/certificate_extractor.py
Easy-eSocial-v2/backend/app/xml_signer.py
```

> ⚠️ **Substituir** o `xml_signer.py` atual do V2 pelo do Real Prev (o do V2 é home-baked; o do Real Prev é `signxml` + URI vazio comprovado em homologação).

### 2.2. Endpoints a recriar (extrair de `Projeto/python-backend/main.py` linhas 9465-9831)

| Endpoint Real Prev | Função | V2 destino |
|---|---|---|
| `POST /api/certificado/upload` | upload + valida + persiste | `backend/app/cert_routes.py` |
| `GET /api/certificado/ativo` | retorna cert ativo do tenant (com fallback) | `cert_routes.py` |
| `GET /api/certificados/listar-ativos` | lista todos do tenant | `cert_routes.py` |
| `GET /api/certificados/por-empregador` | dropdown UI: empregador + status cert | `cert_routes.py` |
| `GET /api/certificado/info-completa` | detalhe completo cert ativo | `cert_routes.py` |
| `DELETE /api/certificado/{id}` | remove (com `check_tenant_access`) | `cert_routes.py` |

---

## 3. Schema de banco — tabela `certificados`

Inferido dos campos usados em `models.Certificado` no Real Prev:

```sql
CREATE TABLE certificados (
  id SERIAL PRIMARY KEY,
  tenant_token VARCHAR(16),                 -- SHA-256(cnpj)[:16] — multi-tenant
  cnpj VARCHAR(14),                         -- pode ser NULL se e-CPF puro
  cpf_titular VARCHAR(11),                  -- só preenchido em e-CPF
  tipo_titular VARCHAR(2) DEFAULT 'PJ',     -- 'PF' (e-CPF) ou 'PJ' (e-CNPJ)
  nome_titular VARCHAR(255) NOT NULL,
  emissor VARCHAR(255),
  numero_serie VARCHAR(100) UNIQUE NOT NULL,  -- lock anti-duplicata
  validade TIMESTAMP NOT NULL,
  arquivo_path VARCHAR(500) NOT NULL,
  senha_hash VARCHAR(64),                   -- SHA256 (compat — pode descartar no V2)
  senha_encrypted TEXT NOT NULL,            -- Fernet (preferencial)
  ativo BOOLEAN DEFAULT TRUE,
  upload_em TIMESTAMP DEFAULT NOW(),
  upload_por VARCHAR(100),                  -- username
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_cert_tenant ON certificados(tenant_token);
CREATE INDEX idx_cert_cnpj_ativo ON certificados(cnpj, ativo);
```

> Na arquitetura V2 (1 banco por empresa) o `tenant_token` deixa de ser strictly necessário **dentro** de cada banco — porque o banco já é exclusivo da empresa. Mas mantemos o campo por consistência e pra suportar o caso "contador com cert único para múltiplas empresas" via procuração.

---

## 4. Fluxo end-to-end (Real Prev)

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. UI / Frontend                                                    │
│     <input type=file accept=".pfx,.p12">  +  <input type=password>   │
│     FormData: { file, senha }                                        │
└──────────────┬───────────────────────────────────────────────────────┘
               │ POST multipart/form-data
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  2. POST /api/certificado/upload  (FastAPI, autenticado JWT)         │
│     await file.read() → pfx_data                                     │
│     CertificateManager.validate_pfx(pfx_data, senha)                 │
│       → cnpj, nome_titular, emissor, numero_serie, validade          │
│       → raise se senha errada / cert vencido                         │
│     CertificateExtractor.extract_certificate_info() → cpf/cnpj+tipo  │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  3. Lock anti-duplicata                                              │
│     SELECT * FROM certificados WHERE numero_serie = ?  → 400 se já   │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  4. Persistência                                                     │
│     CertificateManager.save_certificate(...) → arquivo_path          │
│     UPDATE ativo=FALSE WHERE cnpj=? AND ativo=TRUE                   │
│     INSERT INTO certificados (tenant_token, cnpj, ..., ativo=TRUE)   │
│       senha_encrypted = Fernet.encrypt(senha)                        │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  5. Resposta JSON com metadados (sem senha)                          │
└──────────────────────────────────────────────────────────────────────┘

────────────────────  na hora de assinar  ────────────────────────────

┌──────────────────────────────────────────────────────────────────────┐
│  6. select_active_certificate(db, current_user, certificado_id?)     │
│     - filtra por tenant (super-admin tenant_token=NULL vê tudo)      │
│     - se id explícito, valida + retorna                              │
│     - else retorna mais recente ativo                                │
│     - 403/404 se fora do escopo                                      │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  7. CertificateManager.decrypt_password(senha_encrypted)             │
│     XMLSignatureManager.sign_xml(xml_path, cert_path, senha)         │
│       - signxml.XMLSigner(method=enveloped, rsa-sha256, sha256,      │
│                            c14n)                                     │
│       - Id maiúsculo no evento (eSocial obriga)                      │
│       - URI vazio na referência (eSocial erro 142 se não)            │
│       - retorna {nome}_ASSINADO.xml                                  │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  8. Envio SOAP via requests + cert SSL                               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. Trechos críticos para copiar (referência)

### 5.1. `CertificateManager.validate_pfx` — Real Prev

```python
@staticmethod
def validate_pfx(pfx_data: bytes, password: str) -> dict:
    private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
        pfx_data, password.encode(), backend=default_backend()
    )
    if certificate is None:
        raise ValueError("Certificado não encontrado no arquivo PFX")
    # extrair CNPJ via OID 2.5.4.5 (serialNumber)
    cnpj = next((a.value.split(":")[-1] for a in certificate.subject
                 if a.oid.dotted_string == "2.5.4.5"), None)
    nome_titular = next((a.value for a in certificate.subject
                         if a.oid == x509.oid.NameOID.COMMON_NAME), None)
    emissor = next((a.value for a in certificate.issuer
                    if a.oid == x509.oid.NameOID.COMMON_NAME), None)
    numero_serie = format(certificate.serial_number, "x").upper()
    validade = certificate.not_valid_after_utc.replace(tzinfo=None)
    if validade < datetime.now():
        raise ValueError("Certificado vencido")
    return {"cnpj": cnpj, "nome_titular": nome_titular, "emissor": emissor,
            "numero_serie": numero_serie, "validade": validade, "valido": True}
```

### 5.2. Endpoint `POST /api/certificado/upload` — Real Prev

```python
@app.post("/api/certificado/upload")
async def upload_certificado(
    file: UploadFile = File(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    pfx_data = await file.read()
    cert_info = CertificateManager.validate_pfx(pfx_data, senha)
    extra_info = CertificateExtractor.extract_certificate_info(pfx_data, senha)

    if db.query(models.Certificado).filter(
        models.Certificado.numero_serie == cert_info["numero_serie"]
    ).first():
        raise HTTPException(409, "Certificado já cadastrado")

    filepath = CertificateManager.save_certificate(
        pfx_data, cert_info["cnpj"] or extra_info["cpf_titular"], cert_info["numero_serie"]
    )
    db.query(models.Certificado).filter(
        models.Certificado.cnpj == cert_info["cnpj"],
        models.Certificado.ativo == True,
    ).update({"ativo": False})

    cert = models.Certificado(
        tenant_token=current_user.tenant_token,
        cnpj=cert_info["cnpj"],
        cpf_titular=extra_info.get("cpf_titular"),
        tipo_titular=extra_info.get("tipo_titular", "PJ"),
        nome_titular=cert_info["nome_titular"],
        emissor=cert_info["emissor"],
        numero_serie=cert_info["numero_serie"],
        validade=cert_info["validade"],
        arquivo_path=filepath,
        senha_encrypted=CertificateManager.encrypt_password(senha),
        ativo=True,
        upload_por=current_user.username,
    )
    db.add(cert); db.commit(); db.refresh(cert)
    return {"success": True, "certificado": {...}}
```

### 5.3. `XMLSignatureManager.sign_xml` — regra crítica eSocial

```python
# eSocial exige Id maiúsculo
if evento_element.get("id"): del evento_element.attrib["id"]
evento_element.set("Id", evento_id)

signer = XMLSigner(
    method=signxml.methods.enveloped,
    signature_algorithm="rsa-sha256",
    digest_algorithm="sha256",
    c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
)
cert_pem = certificate.public_bytes(Encoding.PEM)
signed_root = signer.sign(root, key=private_key, cert=cert_pem)
# IMPORTANTE: URI vazio (assinatura sobre todo o documento)
# Sem isso → SERPRO erro 142
```

### 5.4. `tenant_filter` (helper)

```python
def tenant_filter(query, model, current_user):
    """Super-admin (tenant_token=None) vê tudo; demais só do próprio tenant."""
    if current_user.tenant_token is None:
        return query
    return query.filter(model.tenant_token == current_user.tenant_token)

def select_active_certificate(db, current_user, certificado_id=None):
    cq = db.query(models.Certificado).filter(models.Certificado.ativo == True)
    cq = tenant_filter(cq, models.Certificado, current_user)
    if certificado_id is not None:
        cq = cq.filter(models.Certificado.id == certificado_id)
    cert = cq.order_by(models.Certificado.id.desc()).first()
    if not cert:
        raise HTTPException(404, "Nenhum certificado ativo encontrado.")
    if cert.validade < datetime.now():
        raise HTTPException(400, f"Certificado vencido em {cert.validade:%d/%m/%Y}")
    return cert
```

---

## 6. Frontend Vue 3 (V2) — componente `CertificadoUpload.vue`

> O Real Prev usa React + axios. No V2 vamos refazer em Vue 3 + Composition API + Pinia store.

```vue
<script setup lang="ts">
import { ref } from 'vue'
import api from '@/api'
import { useCertStore } from '@/stores/cert'

const file = ref<File | null>(null)
const senha = ref('')
const erro = ref('')
const enviando = ref(false)
const store = useCertStore()

async function enviar() {
  if (!file.value || !senha.value) return
  erro.value = ''
  enviando.value = true
  const fd = new FormData()
  fd.append('file', file.value)
  fd.append('senha', senha.value)
  try {
    const { data } = await api.post('/api/certificado/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    store.setAtivo(data.certificado)
    senha.value = ''  // nunca persiste no client
    file.value = null
  } catch (e: any) {
    erro.value = e?.response?.data?.detail ?? 'Erro no upload'
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <div class="cert-upload">
    <input type="file" accept=".pfx,.p12"
           @change="e => file = (e.target as HTMLInputElement).files?.[0] ?? null">
    <input type="password" v-model="senha" placeholder="Senha do certificado" autocomplete="off">
    <button :disabled="!file || !senha || enviando" @click="enviar">
      {{ enviando ? 'Enviando…' : 'Enviar certificado' }}
    </button>
    <p v-if="erro" class="erro">{{ erro }}</p>
  </div>
</template>
```

**Política client-side**:
- Senha **nunca** vai pra localStorage / sessionStorage
- `autocomplete="off"` no input password
- Limpar `senha.value` após sucesso ou falha
- Token JWT já é enviado pelo interceptor axios padrão

---

## 7. Plano de port (ordem de execução)

```
[ ] 1. Criar tabela certificados no banco V2 (DDL §3) em migration nova
[ ] 2. Copiar 3 arquivos: certificate_manager.py, certificate_extractor.py, xml_signer.py
[ ] 3. Criar backend/app/cert_routes.py com 6 endpoints (extrair de main.py linhas 9465-9831)
[ ] 4. Adicionar models.Certificado no V2 (SQLAlchemy ou raw psycopg2)
[ ] 5. Criar tenant_filter() + select_active_certificate() em backend/app/auth.py
[ ] 6. Frontend: CertificadoUpload.vue + CertificadoAtivo.vue + store cert
[ ] 7. Integrar com envio_paralelo_v2.py — substituir leitura de PFX do filesystem por:
       cert = select_active_certificate(db, user); senha = decrypt_password(cert.senha_encrypted)
[ ] 8. Testar com PFX da Soluções (homologação primeiro, depois produção)
[ ] 9. Repetir teste com PFX do APPA (depois de centralizar em _certificados_locais/)
[ ] 10. Validar erro 142 ausente (URI vazio)
[ ] 11. Smoke: upload + listar + ativo + delete
```

---

## 8. Bibliotecas Python a adicionar em `backend/requirements.txt`

```
cryptography>=42.0
signxml>=3.2.2          # ← falta no V2 hoje (provável)
lxml>=5.1
```

(`Fernet` vem do `cryptography`, não precisa pacote extra.)

---

## 9. Riscos / gotchas conhecidos

| # | Problema | Mitigação |
|---|---|---|
| 1 | Hardcoded `_ENCRYPTION_KEY = b'VeO-WGEJAv51ZXFdGO0MV06Bl2lI1XkYMiqV_WOpy_g='` | mover pra env `SECRET_KEY` em produção, mas **manter compat** pra descriptografar senhas antigas |
| 2 | `arquivo_path` salva path absoluto Windows no Real Prev | em produção (Linux VPS) normalizar com `ntpath.basename()` + path relativo (Real Prev já faz isso nas linhas 7823-7831) |
| 3 | Validação de senha NÃO inclui re-assinar test → senha pode "abrir" o PFX mas falhar na hora de assinar | adicionar mini-test de assinatura sobre XML dummy no momento do upload |
| 4 | Sem rate-limit no `/upload` | adicionar nginx `limit_req_zone` (5/min/IP) |
| 5 | Cert salvo no filesystem do servidor — não Supabase Storage | OK pra V1 mas considerar S3-compat com server-side encryption no futuro |
| 6 | `signxml` é grande (puxa pyOpenSSL etc.) | aceitar — é o único maduro pra XMLDSig BR |
| 7 | Procuração eletrônica adiciona complexidade — V2 começa SEM ela, depois importa do Real Prev | feature deferred para Phase 2+ |

---

## 10. O que NÃO portar do Real Prev (por ora)

- Procuração eletrônica (`procuracao_service.py`, `procuracao_lista_service.py`) → V2 fase posterior
- ECac scraper (`ecac_scraper_service.py`) → fora do escopo
- Cache enquadramento CAEPF → não relacionado
- S-2500/S-5501 (eSocial **trabalhista**, Real Prev é sindical) → V2 já tem S-1210 próprio
- `senha_hash` (SHA256) → manter coluna por compat mas não usar pra novos uploads (só `senha_encrypted` Fernet)

---

## 11. Resumo executivo

1. Real Prev tem o pattern certo: cert via UI, banco multi-tenant, signxml + URI vazio.
2. Copiar 3 arquivos da pasta `Projeto/python-backend/esocial/`.
3. Recriar 6 endpoints `/api/certificado/*` no V2.
4. Criar tabela `certificados` no banco padrão de cada empresa.
5. Frontend: 1 componente Vue de upload + 1 store Pinia.
6. Integrar `envio_paralelo_v2.py` pra resolver cert via DB (não mais via flag CLI `--cert`).
7. Adicionar `signxml` em requirements.

> Próxima ação prática: quando autorizar Phase 0 da migração, este pattern entra como parte da Phase 2 (setup schema padrão Supabase).

---

## Apêndice — referências exatas no Real Prev

| Caminho | Linhas |
|---|---|
| `Projeto/python-backend/esocial/certificate_manager.py` | 1-185 |
| `Projeto/python-backend/esocial/certificate_extractor.py` | 1-220 |
| `Projeto/python-backend/esocial/xml_signer.py` | 1-260 |
| `Projeto/python-backend/main.py` | 9465-9831 (endpoints) |
| `Projeto/python-backend/main.py` | 747-771 (`select_active_certificate`) |
| `Projeto/python-backend/migrations/migrate_tenancy.py` | 1-150 (`tenant_token` SHA-256) |
