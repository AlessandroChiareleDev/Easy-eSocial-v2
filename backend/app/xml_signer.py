"""
Assinatura Digital XMLDSig para eSocial S-1010
Padrão: Enveloped, RSA-SHA256, SHA-256, C14N, URI=""

Baseado no código de referência do repositório Projeto (comprovado em homologação).
"""

from lxml import etree
import signxml
from signxml import XMLSigner
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding
from cryptography.hazmat.backends import default_backend


class S1010XMLSigner:
    """Assina XML S-1010 com certificado digital A1"""

    @staticmethod
    def assinar(xml_bytes: bytes, pfx_data: bytes, password: str) -> bytes:
        """
        Assina XML com certificado digital A1.

        Args:
            xml_bytes: XML gerado por S1010XMLGenerator (bytes)
            pfx_data: Conteúdo do arquivo .pfx
            password: Senha do certificado

        Returns:
            bytes do XML assinado

        Raises:
            ValueError: senha incorreta, XML inválido, PFX inválido
        """
        # 1. Carregar certificado
        try:
            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data,
                password.encode(),
                backend=default_backend(),
            )
        except Exception as e:
            msg = str(e).lower()
            if "password" in msg or "decrypt" in msg or "mac" in msg:
                raise ValueError("Senha do certificado incorreta")
            raise ValueError(f"Erro ao carregar certificado: {e}")

        if certificate is None:
            raise ValueError("Certificado não encontrado no PFX")

        # 2. Parse XML
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as e:
            raise ValueError(f"XML inválido: {e}")

        # 3. Garantir Id maiúsculo no elemento evento
        evento = None
        for child in root:
            if "evt" in child.tag.lower():
                evento = child
                break

        if evento is not None:
            evt_id = evento.get("Id") or evento.get("id")
            if evt_id and evento.get("id") and not evento.get("Id"):
                del evento.attrib["id"]
                evento.set("Id", evt_id)

        # 4. Assinar
        cert_pem = certificate.public_bytes(Encoding.PEM)

        signer = XMLSigner(
            method=signxml.methods.enveloped,
            signature_algorithm="rsa-sha256",
            digest_algorithm="sha256",
            c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        )

        try:
            signed_root = signer.sign(
                root,
                key=private_key,
                cert=cert_pem,
            )
        except Exception as e:
            raise ValueError(f"Erro ao assinar XML: {e}")

        # 5. Retornar bytes
        return etree.tostring(signed_root, xml_declaration=True, encoding="UTF-8")
