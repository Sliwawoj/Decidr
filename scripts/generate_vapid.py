"""Print Web Push applicationServerKey and a pywebpush-compatible private key."""

import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

key = ec.generate_private_key(ec.SECP256R1())
private = key.private_numbers().private_value.to_bytes(32, "big")
public = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
print("VAPID_PRIVATE_KEY=" + encode(private))
print("VAPID_PUBLIC_KEY=" + encode(public))
