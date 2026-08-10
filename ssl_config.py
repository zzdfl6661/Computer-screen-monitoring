import os
import subprocess
import platform
from datetime import datetime, timedelta

SSL_DIR = 'ssl'
CERT_FILE = 'cert.pem'
KEY_FILE = 'key.pem'

def generate_self_signed_cert(cert_path: str = None, key_path: str = None, days: int = 365):
    if cert_path is None:
        cert_path = os.path.join(SSL_DIR, CERT_FILE)
    if key_path is None:
        key_path = os.path.join(SSL_DIR, KEY_FILE)
    
    if not os.path.exists(SSL_DIR):
        os.makedirs(SSL_DIR)
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        print(f"证书文件已存在: {cert_path}, {key_path}")
        return cert_path, key_path
    
    if platform.system() == 'Windows':
        _generate_cert_windows(cert_path, key_path, days)
    else:
        _generate_cert_openssl(cert_path, key_path, days)
    
    print(f"自签名证书生成成功: {cert_path}, {key_path}")
    return cert_path, key_path

def _generate_cert_openssl(cert_path: str, key_path: str, days: int):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    with open(key_path, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'CN'),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Beijing'),
        x509.NameAttribute(NameOID.LOCALITY_NAME, 'Beijing'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'LearningApp'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=days)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName('localhost')]),
        critical=False,
    ).sign(key, hashes.SHA256(), default_backend())
    
    with open(cert_path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

def _generate_cert_windows(cert_path: str, key_path: str, days: int):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    with open(key_path, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'CN'),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Beijing'),
        x509.NameAttribute(NameOID.LOCALITY_NAME, 'Beijing'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'LearningApp'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=days)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName('localhost')]),
        critical=False,
    ).sign(key, hashes.SHA256(), default_backend())
    
    with open(cert_path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

def get_ssl_context(cert_path: str = None, key_path: str = None):
    import ssl
    
    if cert_path is None:
        cert_path = os.path.join(SSL_DIR, CERT_FILE)
    if key_path is None:
        key_path = os.path.join(SSL_DIR, KEY_FILE)
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        generate_self_signed_cert(cert_path, key_path)
    
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    
    return ssl_context

if __name__ == '__main__':
    generate_self_signed_cert()
    print("SSL 证书生成完成")