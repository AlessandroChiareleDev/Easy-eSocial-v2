"""Certificate Manager — A1 (.pfx) — adaptado do V1/Real Prev.

Validacao, leitura, persistencia. FERNET_KEY vem de config.FERNET_KEY (.env).
Sem fallback hardcoded por seguranca: se nao tiver FERNET_KEY, encrypt levanta.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import pkcs12

from . import config


def _fernet() -> Fernet:
    if not config.FERNET_KEY:
        raise RuntimeError(
            "FERNET_KEY nao configurado no .env. "
            "Gere com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(config.FERNET_KEY.encode())


class CertificateManager:
    """Gerencia certificados digitais A1 para eSocial."""

    @staticmethod
    def encrypt_password(password: str) -> str:
        return _fernet().encrypt(password.encode()).decode()

    @staticmethod
    def decrypt_password(encrypted_password: str) -> str:
        return _fernet().decrypt(encrypted_password.encode()).decode()

    @staticmethod
    def validate_pfx(pfx_data: bytes, password: str) -> dict:
        try:
            _, certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data, password.encode(), backend=default_backend()
            )
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if "password" in msg or "decrypt" in msg or "mac" in msg:
                raise ValueError("Senha do certificado incorreta")
            raise ValueError(f"Erro ao validar certificado: {e}")

        if certificate is None:
            raise ValueError("Certificado nao encontrado no arquivo PFX")

        subject = certificate.subject
        issuer = certificate.issuer

        cnpj = None
        for attr in subject:
            if attr.oid.dotted_string == "2.5.4.5":  # serialNumber
                val = attr.value
                cnpj = val.split(":")[-1] if ":" in val else val
                break

        nome_titular = None
        for attr in subject:
            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                nome_titular = attr.value
                break

        # Fallback: extrai CNPJ do CN se nao achou no serialNumber
        if not cnpj and nome_titular and ":" in nome_titular:
            candidate = nome_titular.split(":")[-1].strip()
            if candidate.isdigit() and len(candidate) in (11, 14):
                cnpj = candidate

        emissor = None
        for attr in issuer:
            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                emissor = attr.value
                break

        numero_serie = format(certificate.serial_number, "x").upper()
        validade = certificate.not_valid_after_utc.replace(tzinfo=None)
        if validade < datetime.now():
            raise ValueError("Certificado vencido")

        return {
            "cnpj": cnpj,
            "nome_titular": nome_titular or "Nao identificado",
            "emissor": emissor or "Nao identificado",
            "numero_serie": numero_serie,
            "validade": validade,
            "valido": True,
        }

    @staticmethod
    def save_certificate(
        pfx_data: bytes, cnpj: str, numero_serie: str, base_dir: str | None = None
    ) -> str:
        if base_dir is None:
            base_dir = str(Path(__file__).resolve().parent.parent / "_certificados")
        os.makedirs(base_dir, exist_ok=True)
        filename = f"cert_{cnpj}_{numero_serie}.pfx"
        filepath = os.path.join(base_dir, filename)
        with open(filepath, "wb") as f:
            f.write(pfx_data)
        return filepath
