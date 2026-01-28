#!/usr/bin/env python3

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timedelta
import os

# 生成 CA 私钥
ca_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# 生成 CA 证书
ca_subject = ca_issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "NY"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, "Syracuse"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SEED Labs"),
    x509.NameAttribute(NameOID.COMMON_NAME, "vpn-ca.example.com"),
])

ca_cert = x509.CertificateBuilder().subject_name(
    ca_subject
).issuer_name(
    ca_issuer
).public_key(
    ca_private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=365)
).add_extension(
    x509.BasicConstraints(ca=True, path_length=None), critical=True,
).sign(ca_private_key, hashes.SHA256(), default_backend())

# 生成服务器私钥
server_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# 生成服务器证书
server_subject = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "NY"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, "Syracuse"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SEED Labs"),
    x509.NameAttribute(NameOID.COMMON_NAME, "vpnserver-Ken.com"),
])

server_cert = x509.CertificateBuilder().subject_name(
    server_subject
).issuer_name(
    ca_issuer
).public_key(
    server_private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=365)
).sign(ca_private_key, hashes.SHA256(), default_backend())

# 生成客户端私钥
client_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# 生成客户端证书
client_subject = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "NY"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, "Syracuse"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SEED Labs"),
    x509.NameAttribute(NameOID.COMMON_NAME, "vpnclient.example.com"),
])

client_cert = x509.CertificateBuilder().subject_name(
    client_subject
).issuer_name(
    ca_issuer
).public_key(
    client_private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=365)
).sign(ca_private_key, hashes.SHA256(), default_backend())

# 写入 CA 证书
with open("ca-cert.pem", "wb") as f:
    f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

# 写入服务器证书
with open("server-cert.pem", "wb") as f:
    f.write(server_cert.public_bytes(serialization.Encoding.PEM))

# 写入服务器私钥
with open("server-key.pem", "wb") as f:
    f.write(server_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))

# 写入客户端证书
with open("client-cert.pem", "wb") as f:
    f.write(client_cert.public_bytes(serialization.Encoding.PEM))

# 写入客户端私钥
with open("client-key.pem", "wb") as f:
    f.write(client_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))

print("Certificates generated successfully")