"""Web Push sender: RFC 8291 message encryption (aes128gcm) + RFC 8292 VAPID.

Small and dependency-light on purpose (only `cryptography`), so it builds anywhere.
"""
import base64
import json
import os
import struct
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RECORD_SIZE = 4096


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hkdf(salt, ikm, info, length):
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def _public_bytes(key) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def encrypt(plaintext: bytes, ua_public_b64: str, auth_b64: str, *, salt=None, sender_private=None) -> bytes:
    """Encrypt one push message body (RFC 8291 section 3.4, single record)."""
    ua_public = unb64u(ua_public_b64)
    auth = unb64u(auth_b64)
    salt = salt or os.urandom(16)
    as_key = sender_private or ec.generate_private_key(ec.SECP256R1())
    as_public = _public_bytes(as_key)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    ecdh = as_key.exchange(ec.ECDH(), ua_key)
    ikm = _hkdf(auth, ecdh, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    if len(plaintext) + 1 + 16 > RECORD_SIZE - 86:
        raise ValueError("push payload too large")
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    header = salt + struct.pack("!IB", RECORD_SIZE, len(as_public)) + as_public
    return header + ciphertext


def decrypt(body: bytes, ua_private, auth_b64: str) -> bytes:
    """Inverse of encrypt (used by tests, mirrors what a browser does)."""
    salt, rs, idlen = body[:16], *struct.unpack("!IB", body[16:21])
    as_public = body[21:21 + idlen]
    ciphertext = body[21 + idlen:]
    ua_public = _public_bytes(ua_private)
    as_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
    ecdh = ua_private.exchange(ec.ECDH(), as_key)
    ikm = _hkdf(unb64u(auth_b64), ecdh, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    padded = AESGCM(cek).decrypt(nonce, ciphertext, None)
    return padded.rstrip(b"\x00")[:-1]


# ---------------- VAPID ----------------

def load_vapid_key(private_b64: str):
    """VAPID private key as the raw 32-byte scalar, base64url (the common format)."""
    return ec.derive_private_key(int.from_bytes(unb64u(private_b64), "big"), ec.SECP256R1())


def vapid_public_b64(key) -> str:
    return b64u(_public_bytes(key))


def generate_vapid_keys():
    key = ec.generate_private_key(ec.SECP256R1())
    return b64u(key.private_numbers().private_value.to_bytes(32, "big")), vapid_public_b64(key)


def vapid_header(endpoint: str, key, subject: str, ttl_seconds=12 * 3600) -> str:
    parts = urlsplit(endpoint)
    claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int(time.time()) + ttl_seconds, "sub": subject}
    signing_input = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode()) + "." + \
        b64u(json.dumps(claims, separators=(",", ":")).encode())
    der = key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    jwt = signing_input + "." + b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={jwt}, k={vapid_public_b64(key)}"


def send(http, subscription: dict, payload: dict, key, subject: str, ttl=12 * 3600):
    """POST one notification. Returns the HTTP status (201/200 ok, 404/410 = subscription gone)."""
    body = encrypt(json.dumps(payload, separators=(",", ":")).encode(), subscription["p256dh"], subscription["auth"])
    r = http.post(subscription["endpoint"], data=body, timeout=20, headers={
        "Authorization": vapid_header(subscription["endpoint"], key, subject),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Urgency": "normal",
    })
    return r.status_code
