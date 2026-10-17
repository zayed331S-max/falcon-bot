import base64, hashlib
PUB = "6293d7639a49dc5bb17d77c1c7f606815065fe7994c8554fea56c3fa8cd5e275"
b = 256
q = 2**255 - 19
l = 2**252 + 27742317777372353535851937790883648493
def H(m): return hashlib.sha512(m).digest()
def inv(x): return pow(x, q - 2, q)
d = -121665 * inv(121666) % q
I = pow(2, (q - 1) // 4, q)
def xrec(y):
    xx = (y * y - 1) * inv(d * y * y + 1)
    x = pow(xx, (q + 3) // 8, q)
    if (x * x - xx) % q: x = x * I % q
    return q - x if x % 2 else x
By = 4 * inv(5)
B = (xrec(By) % q, By % q)
def add(P, Q):
    x1, y1 = P; x2, y2 = Q
    t = d * x1 * x2 * y1 * y2
    return (x1 * y2 + x2 * y1) * inv(1 + t) % q, (y1 * y2 + x1 * x2) * inv(1 - t) % q
def mul(P, e):
    R = (0, 1)
    while e:
        if e & 1: R = add(R, P)
        P = add(P, P); e >>= 1
    return R
def enc(P):
    x, y = P
    return ((y & ((1 << 255) - 1)) | ((x & 1) << 255)).to_bytes(32, "little")
def bit(h, i): return (h[i // 8] >> (i % 8)) & 1
def secret_scalar(h): return 2**(b - 2) + sum(2**i * bit(h, i) for i in range(3, b - 2))
def publickey(sk): return enc(mul(B, secret_scalar(H(sk))))
def Hint(m): return int.from_bytes(H(m), "little")
def sign(m, sk):
    h = H(sk); a = secret_scalar(h); pk = enc(mul(B, a))
    r = Hint(h[32:] + m); R = enc(mul(B, r))
    return R + ((r + Hint(R + pk + m) * a) % l).to_bytes(32, "little")
def dec(s):
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    x = xrec(y)
    if x & 1 != (s[31] >> 7): x = q - x
    if (-x * x + y * y - 1 - d * x * x * y * y) % q: raise ValueError
    return x, y
def verify(sig, m, pk):
    try:
        if len(sig) != 64 or len(pk) != 32: return False
        R = dec(sig[:32]); A = dec(pk)
        S = int.from_bytes(sig[32:], "little")
        return mul(B, S) == add(R, mul(A, Hint(enc(R) + pk + m)))
    except Exception:
        return False
def msg(uid): return b"zxfalcon:" + str(uid).encode()
def make(uid, sk): return "ZX-" + base64.urlsafe_b64encode(sign(msg(uid), sk)).decode().rstrip("=")
def valid(uid, code):
    try:
        c = (code or "").strip()
        if not c.startswith("ZX-"): return False
        c = c[3:]
        return verify(base64.urlsafe_b64decode(c + "=" * (-len(c) % 4)), msg(uid), bytes.fromhex(PUB))
    except Exception:
        return False
