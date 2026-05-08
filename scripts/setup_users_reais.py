"""Limpa os usuarios de teste e cria os usuarios reais.

Uso (local, sem precisar de VPS):
    python scripts/setup_users_reais.py

Apaga: admin@easyesocial.com.br, rafa@appa.com.br
Cria: xandeadmin (super_admin), Ana (operador em TODAS empresas ativas)
"""
from __future__ import annotations

import os
import sys

import bcrypt
import psycopg2

DSN = os.environ.get(
    "SISTEMA_DB_URL",
    "postgresql://postgres:EsoV2_CoxRHWQ1z6iucG7ZyvdqFIbN"
    "@db.kjbgiwnlvqnrfdozjvhq.supabase.co:5432/postgres?sslmode=require",
)


def hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def main() -> int:
    conn = psycopg2.connect(DSN, options="-c search_path=sistema,public")
    conn.autocommit = False
    cur = conn.cursor()

    # 1) Apaga os usuarios de teste (cascade vai limpar user_empresas)
    print("=== Apagando usuarios de teste ===")
    cur.execute(
        "DELETE FROM users WHERE lower(email) IN (%s, %s) RETURNING email",
        ("admin@easyesocial.com.br", "rafa@appa.com.br"),
    )
    apagados = [r[0] for r in cur.fetchall()]
    print(f"Apagados: {apagados or '(nenhum)'}")

    # 2) Cria/atualiza xandeadmin (super_admin)
    print("\n=== Criando xandeadmin (super_admin) ===")
    cur.execute(
        """
        INSERT INTO users (email, password_hash, nome, ativo, super_admin)
        VALUES (%s, %s, %s, TRUE, TRUE)
        ON CONFLICT (email) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                nome          = EXCLUDED.nome,
                ativo         = TRUE,
                super_admin   = TRUE
        RETURNING id, email
        """,
        ("xandeadmin", hash_pw("xandaos2@"), "Xande (admin)"),
    )
    xande_id, xande_email = cur.fetchone()
    print(f"OK  id={xande_id}  email={xande_email}")

    # 3) Cria/atualiza Ana (usuario comum)
    print("\n=== Criando Ana ===")
    cur.execute(
        """
        INSERT INTO users (email, password_hash, nome, ativo, super_admin)
        VALUES (%s, %s, %s, TRUE, FALSE)
        ON CONFLICT (email) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                nome          = EXCLUDED.nome,
                ativo         = TRUE,
                super_admin   = FALSE
        RETURNING id, email
        """,
        ("Ana", hash_pw("123321"), "Ana"),
    )
    ana_id, ana_email = cur.fetchone()
    print(f"OK  id={ana_id}  email={ana_email}")

    # 4) Vincula Ana a TODAS as empresas ativas como 'operador'
    cur.execute(
        "SELECT cnpj, razao_social FROM empresas_routing WHERE ativo = TRUE ORDER BY razao_social"
    )
    empresas = cur.fetchall()
    print(f"\n=== Vinculando Ana a {len(empresas)} empresa(s) ativas ===")

    # Limpa vinculos antigos da Ana antes de recriar (idempotente)
    cur.execute("DELETE FROM user_empresas WHERE user_id = %s", (ana_id,))

    for cnpj, rs in empresas:
        cur.execute(
            """
            INSERT INTO user_empresas (user_id, cnpj, papel)
            VALUES (%s, %s, 'operador')
            ON CONFLICT (user_id, cnpj) DO UPDATE SET papel = EXCLUDED.papel
            """,
            (ana_id, cnpj),
        )
        print(f"  - {cnpj}  {rs}")

    if not empresas:
        print("  (nenhuma empresa ativa cadastrada ainda)")

    conn.commit()

    # 5) Resumo final
    print("\n=== Estado final em sistema.users ===")
    cur.execute(
        "SELECT email, nome, super_admin, ativo FROM users ORDER BY super_admin DESC, email"
    )
    for row in cur.fetchall():
        print(" ", row)

    cur.close()
    conn.close()
    print("\nOK. Login pelo frontend:")
    print("  xandeadmin / xandaos2@   (super_admin, ve tudo)")
    print("  Ana        / 123321       (operador nas empresas ativas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
