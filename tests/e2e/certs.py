"""Generate a throwaway CA and server certificates for the TLS origins."""

from __future__ import annotations

import datetime as dt
import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

if TYPE_CHECKING:
    from pathlib import Path

IDN_ALABEL = "xn--bcher-kva.example"
IDN_ULABEL = "bücher.example"
TEST_NAME = "e2e.test"
WRONG_NAME = "wrong.example"


@dataclass(frozen=True)
class CertPair:
    cert: Path
    key: Path


@dataclass(frozen=True)
class CertSet:
    ca: Path
    valid: CertPair
    self_signed: CertPair
    expired: CertPair
    wrong_host: CertPair
    ip_only: CertPair


def _key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def _san(names: list[str]) -> x509.SubjectAlternativeName:
    entries: list[x509.GeneralName] = []
    for name in names:
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            entries.append(x509.DNSName(name))
    return x509.SubjectAlternativeName(entries)


def _write(directory: Path, stem: str, cert: x509.Certificate, key: ec.EllipticCurvePrivateKey) -> CertPair:
    cert_path = directory / f"{stem}.pem"
    key_path = directory / f"{stem}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return CertPair(cert_path, key_path)


def _leaf(
    *,
    common_name: str,
    names: list[str],
    issuer_name: x509.Name | None,
    issuer_key: ec.EllipticCurvePrivateKey | None,
    validity: tuple[dt.datetime, dt.datetime],
) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = _key()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_name or subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(validity[0])
        .not_valid_after(validity[1])
        .add_extension(_san(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    )
    if issuer_key is not None:
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), critical=False
        )
    return builder.sign(issuer_key or key, hashes.SHA256()), key


def generate(directory: Path, extra_names: list[str]) -> CertSet:
    """Write all certificates into ``directory``.

    ``extra_names`` adds names/IPs (e.g. ``host.docker.internal``) to the valid cert.
    """
    directory.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.UTC)
    ca_key = _key()
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "httptap e2e test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    ca_path = directory / "ca.pem"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    good_names = [TEST_NAME, "localhost", "127.0.0.1", "::1", IDN_ALABEL, *extra_names]
    window = (now - dt.timedelta(days=1), now + dt.timedelta(days=20))

    valid = _write(
        directory,
        "valid",
        *_leaf(
            common_name=TEST_NAME,
            names=good_names,
            issuer_name=ca_name,
            issuer_key=ca_key,
            validity=window,
        ),
    )
    self_signed = _write(
        directory,
        "self-signed",
        *_leaf(
            common_name=TEST_NAME,
            names=good_names,
            issuer_name=None,
            issuer_key=None,
            validity=window,
        ),
    )
    expired = _write(
        directory,
        "expired",
        *_leaf(
            common_name=TEST_NAME,
            names=good_names,
            issuer_name=ca_name,
            issuer_key=ca_key,
            validity=(now - dt.timedelta(days=30), now - dt.timedelta(days=2)),
        ),
    )
    wrong_host = _write(
        directory,
        "wrong-host",
        *_leaf(
            common_name=WRONG_NAME,
            names=[WRONG_NAME],
            issuer_name=ca_name,
            issuer_key=ca_key,
            validity=window,
        ),
    )
    ip_only = _write(
        directory,
        "ip-only",
        *_leaf(
            common_name="127.0.0.1",
            names=["127.0.0.1", "::1"],
            issuer_name=ca_name,
            issuer_key=ca_key,
            validity=window,
        ),
    )
    return CertSet(ca_path, valid, self_signed, expired, wrong_host, ip_only)
