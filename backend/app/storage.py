"""Helpers para Postgres Large Objects (pg_largeobject).

Usado para guardar zips do eSocial (até 3 GB cada) em streaming sem
carregar tudo em memória.
"""
from __future__ import annotations

import hashlib
from typing import BinaryIO, Iterator

import psycopg2

CHUNK_BYTES = 4 * 1024 * 1024  # 4 MB


def write_lo_streaming(conn, source: BinaryIO) -> tuple[int, int, str]:
    """Escreve `source` num novo Large Object no banco.

    Retorna (oid, total_bytes, sha256_hex). A conexão NÃO é commitada
    aqui — caller decide.
    """
    sha = hashlib.sha256()
    total = 0
    lo = conn.lobject(0, mode="wb")  # cria novo LO
    oid = lo.oid
    try:
        while True:
            chunk = source.read(CHUNK_BYTES)
            if not chunk:
                break
            lo.write(chunk)
            sha.update(chunk)
            total += len(chunk)
    finally:
        lo.close()
    return oid, total, sha.hexdigest()


def open_lo(conn, oid: int):
    """Abre um Large Object existente em modo leitura. Caller fecha."""
    return conn.lobject(oid, mode="rb")


def iter_lo_bytes(conn, oid: int) -> Iterator[bytes]:
    """Itera bytes do LO em chunks (para download streaming)."""
    lo = conn.lobject(oid, mode="rb")
    try:
        while True:
            chunk = lo.read(CHUNK_BYTES)
            if not chunk:
                break
            yield chunk
    finally:
        lo.close()


def unlink_lo(conn, oid: int) -> None:
    """Apaga o Large Object."""
    try:
        lo = conn.lobject(oid, mode="rb")
        lo.unlink()
    except psycopg2.Error:
        pass


class LargeObjectReader:
    """File-like read-only sobre um Large Object — para passar pro zipfile.

    Suporta read/seek/tell, que é o mínimo que `zipfile.ZipFile` exige.
    """

    def __init__(self, conn, oid: int, size: int):
        self._lo = conn.lobject(oid, mode="rb")
        self._size = size
        self._pos = 0

    # API mínima file-like
    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            data = self._lo.read()
        else:
            data = self._lo.read(n)
        self._pos += len(data)
        return data

    def seek(self, offset: int, whence: int = 0) -> int:
        # psycopg2 lobject.seek aceita whence 0/1/2
        new_pos = self._lo.seek(offset, whence)
        self._pos = new_pos
        return new_pos

    def tell(self) -> int:
        return self._pos

    def close(self) -> None:
        try:
            self._lo.close()
        except Exception:  # noqa: BLE001
            pass

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    @property
    def closed(self) -> bool:
        return getattr(self._lo, "closed", False)

    @property
    def size(self) -> int:
        return self._size

    # Context manager
    def __enter__(self) -> "LargeObjectReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
