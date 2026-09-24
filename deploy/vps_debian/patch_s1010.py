import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
old1 = "    items.value = res.rubrics ?? res.rubricas ?? res.data ?? [];"
new1 = """    const raw: any[] = (res.rubrics ?? res.rubricas ?? res.data ?? []) as any[];
    // Backend devolve os campos do V1 (codigoevento, nome_evento, natureza_atual...)
    items.value = raw.map((r: any) => ({
      ...r,
      codigo: r.codigo ?? r.codigoevento,
      descricao: r.descricao ?? r.nome_evento,
      natureza_codigo: r.natureza_codigo ?? r.natureza_codigo_atual,
      natureza_nome: r.natureza_nome ?? r.natureza_atual,
      problema: r.problema ?? r.observacao ?? r.sugestao_col_f,
      status: r.status ?? (r.natureza_nova ? `corrigida: ${r.natureza_nova}` : "pending"),
    }));"""
old2 = "    if (prog) progress.value = prog;"
new2 = """    if (prog) {
      const p: any = prog;
      progress.value = {
        total: p.total ?? p.total_verificar,
        corrigidas: p.corrigidas ?? p.total_corrigidas,
        pendentes: p.pendentes ?? p.total_pendentes,
        pct: p.pct ?? p.percentual,
      };
    }"""
if "raw.map((r: any)" in s:
    print("ja aplicado"); sys.exit(0)
assert s.count(old1) == 1 and s.count(old2) == 1, "trecho nao encontrado"
s = s.replace(old1, new1).replace(old2, new2)
open(p, "w", encoding="utf-8").write(s)
print("S1010View.vue ajustado")
