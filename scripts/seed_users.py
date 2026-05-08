"""F8.6 — Seed de usuarios + vinculo empresas (sistema schema).

Uso:
    # Seed default (4 usuarios padrao + vinculos APPA/SOLUCOES)
    python scripts/seed_users.py --default

    # Interativo (prompts)
    python scripts/seed_users.py --interactive

    # Listar atual
    python scripts/seed_users.py --list

    # Mudar senha
    python scripts/seed_users.py --reset-password email@x.com

Idempotente: usa ON CONFLICT DO UPDATE em users e ON CONFLICT DO NOTHING em user_empresas.
Senhas dos defaults sao trocadas quando o usuario fizer primeiro login (TODO: flag must_change_password).
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import string
import sys
from pathlib import Path

# Garante que `app` e importavel mesmo rodando do root do repo
_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

from app import config  # noqa: E402
from app.auth import hash_password  # noqa: E402


# -------------------------------------------------------------------- defaults

DEFAULT_USERS: list[dict] = [
    {
        "email": "admin@easyesocial.com.br",
        "nome": "Admin Easy eSocial",
        "super_admin": True,
        "empresas": [],  # super_admin acessa tudo
    },
    {
        "email": "rafa@appa.com.br",
        "nome": "Rafa (APPA)",
        "super_admin": False,
        "empresas": [("05969071000110", "admin")],
    },
    {
        "email": "ana@appa.com.br",
        "nome": "Ana (APPA)",
        "super_admin": False,
        "empresas": [("05969071000110", "operador")],
    },
    {
        "email": "alessandro@solucoes.com.br",
        "nome": "Alessandro (Solucoes)",
        "super_admin": False,
        "empresas": [("09445502000109", "admin")],
    },
]


# -------------------------------------------------------------------- helpers


def _connect():
    if not config.SISTEMA_DB_URL:
        print("[ERRO] SISTEMA_DB_URL ausente no .env do backend.", file=sys.stderr)
        sys.exit(2)
    conn = psycopg2.connect(config.SISTEMA_DB_URL, options="-c search_path=sistema,public")
    conn.autocommit = False
    return conn


def _gen_password(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _upsert_user(cur, email: str, nome: str, password: str, super_admin: bool) -> str:
    """Insere ou atualiza usuario. Retorna user_id (UUID)."""
    cur.execute(
        """
        INSERT INTO users (email, password_hash, nome, super_admin, ativo)
        VALUES (%s, %s, %s, %s, TRUE)
        ON CONFLICT (email) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                nome          = EXCLUDED.nome,
                super_admin   = EXCLUDED.super_admin,
                ativo         = TRUE
        RETURNING id
        """,
        (email, hash_password(password), nome, super_admin),
    )
    return str(cur.fetchone()[0])


def _link_empresa(cur, user_id: str, cnpj: str, papel: str) -> bool:
    """Vincula user a empresa. Retorna True se criou, False se ja existia."""
    cur.execute("SELECT 1 FROM empresas_routing WHERE cnpj=%s", (cnpj,))
    if cur.fetchone() is None:
        print(f"  [WARN] empresa cnpj={cnpj} nao existe em empresas_routing — pulando.")
        return False
    cur.execute(
        """
        INSERT INTO user_empresas (user_id, cnpj, papel)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, cnpj) DO UPDATE SET papel = EXCLUDED.papel
        RETURNING (xmax = 0) AS inserted
        """,
        (user_id, cnpj, papel),
    )
    row = cur.fetchone()
    return bool(row[0]) if row else False


# -------------------------------------------------------------------- commands


def cmd_default(args: argparse.Namespace) -> int:
    print("[seed-default] Seed de 4 usuarios padrao.\n")
    creds: list[tuple[str, str]] = []
    with _connect() as conn:
        with conn.cursor() as cur:
            for u in DEFAULT_USERS:
                pwd = args.password or _gen_password()
                uid = _upsert_user(cur, u["email"], u["nome"], pwd, u["super_admin"])
                creds.append((u["email"], pwd))
                created_links = 0
                for cnpj, papel in u["empresas"]:
                    if _link_empresa(cur, uid, cnpj, papel):
                        created_links += 1
                marker = "*" if u["super_admin"] else " "
                print(
                    f"  {marker} {u['email']:35s} -> id={uid[:8]}... "
                    f"empresas={len(u['empresas'])} (criadas={created_links})"
                )
        conn.commit()

    print("\n=== CREDENCIAIS GERADAS (anote AGORA) ===")
    for email, pwd in creds:
        print(f"  {email:35s}  senha={pwd}")
    print("==========================================")
    print("\nDica: re-rodar este comando rotaciona TODAS as senhas.")
    return 0


def cmd_interactive(args: argparse.Namespace) -> int:
    print("[seed-interactive] novo usuario.\n")
    email = input("email: ").strip().lower()
    if not email or "@" not in email:
        print("email invalido."); return 1
    nome = input("nome (opcional): ").strip() or email.split("@")[0]
    pwd = getpass.getpass("senha (vazio = gerar): ").strip() or _gen_password()
    super_admin_in = input("super_admin? [s/N]: ").strip().lower()
    super_admin = super_admin_in in ("s", "y", "sim", "yes")

    pairs: list[tuple[str, str]] = []
    if not super_admin:
        print("\nVincule a empresas (Enter vazio termina).")
        while True:
            cnpj = input("  cnpj: ").strip().replace(".", "").replace("/", "").replace("-", "")
            if not cnpj:
                break
            papel = input("  papel [admin/operador/leitor]: ").strip().lower() or "operador"
            if papel not in ("admin", "operador", "leitor"):
                print("  papel invalido — pulando.")
                continue
            pairs.append((cnpj, papel))

    with _connect() as conn:
        with conn.cursor() as cur:
            uid = _upsert_user(cur, email, nome, pwd, super_admin)
            for cnpj, papel in pairs:
                _link_empresa(cur, uid, cnpj, papel)
        conn.commit()

    print(f"\nOK. user_id={uid}")
    print(f"     senha={pwd}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.nome, u.super_admin, u.ativo, u.ultimo_login,
                       COALESCE(json_agg(json_build_object('cnpj', ue.cnpj, 'papel', ue.papel))
                                FILTER (WHERE ue.cnpj IS NOT NULL), '[]'::json) AS empresas
                  FROM users u
                  LEFT JOIN user_empresas ue ON ue.user_id = u.id
              GROUP BY u.id
              ORDER BY u.criado_em
                """
            )
            rows = cur.fetchall()

    if not rows:
        print("(nenhum usuario)")
        return 0

    print(f"{'EMAIL':35s} {'NOME':25s} {'SA':3s} {'ATV':4s} EMPRESAS")
    for r in rows:
        empresas = r["empresas"] or []
        emp_str = ", ".join(f"{e['cnpj'][:8]}..({e['papel']})" for e in empresas) or "-"
        sa = "*" if r["super_admin"] else " "
        atv = "ON" if r["ativo"] else "off"
        print(f"{r['email']:35s} {(r['nome'] or '')[:25]:25s} {sa:3s} {atv:4s} {emp_str}")
    return 0


def cmd_reset_password(args: argparse.Namespace) -> int:
    pwd = args.password or _gen_password()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE email=%s RETURNING id",
                (hash_password(pwd), args.email),
            )
            row = cur.fetchone()
            if not row:
                print(f"[ERRO] usuario {args.email} nao encontrado")
                return 1
        conn.commit()
    print(f"OK. nova senha de {args.email}: {pwd}")
    return 0


# -------------------------------------------------------------------- main


def main() -> int:
    p = argparse.ArgumentParser(description="Seed de usuarios sistema.users")
    sub = p.add_subparsers(dest="cmd", required=False)

    p_def = sub.add_parser("default", help="seed dos 4 usuarios padrao")
    p_def.add_argument("--password", help="forca senha unica para todos (default: gerada)")
    p_def.set_defaults(func=cmd_default)

    p_int = sub.add_parser("interactive", help="cadastra um usuario via prompts")
    p_int.set_defaults(func=cmd_interactive)

    p_list = sub.add_parser("list", help="lista usuarios + vinculos")
    p_list.set_defaults(func=cmd_list)

    p_reset = sub.add_parser("reset-password", help="reseta senha de um usuario")
    p_reset.add_argument("email")
    p_reset.add_argument("--password", help="senha explicita (default: gerada)")
    p_reset.set_defaults(func=cmd_reset_password)

    # alias antigos
    p.add_argument("--default", action="store_true", help="atalho para 'default'")
    p.add_argument("--interactive", action="store_true", help="atalho para 'interactive'")
    p.add_argument("--list", action="store_true", help="atalho para 'list'")
    p.add_argument("--reset-password", metavar="EMAIL", help="atalho para 'reset-password EMAIL'")
    p.add_argument("--password", help="senha (com --default ou --reset-password)")

    args = p.parse_args()

    if args.default:
        return cmd_default(args)
    if args.interactive:
        return cmd_interactive(args)
    if args.list:
        return cmd_list(args)
    if args.reset_password:
        args.email = args.reset_password
        return cmd_reset_password(args)
    if hasattr(args, "func"):
        return args.func(args)

    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
