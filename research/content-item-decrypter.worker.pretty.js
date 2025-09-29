(function() {
    "use strict";
    const _ = t => {
            const {
                baseDelay: e = 250,
                minDelay: r = 0,
                maxDelay: n = 1 / 0,
                maxRetryCount: a = 1 / 0
            } = t || {};
            return s => {
                if (!(s > a - 1)) return Math.max(r, Math.min(n, s && e * Math.pow(2, s - 1)))
            }
        },
        g = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
        A = typeof Uint8Array > "u" ? [] : new Uint8Array(256);
    for (let t = 0; t < g.length; t++) A[g.charCodeAt(t)] = t;
    const b = t => {
            let e = t.length * .75,
                r = 0,
                n, a, s, o;
            t[t.length - 1] === "=" && (e--, t[t.length - 2] === "=" && e--);
            const c = new ArrayBuffer(e),
                y = new Uint8Array(c);
            for (let p = 0; p < t.length; p += 4) n = A[t.charCodeAt(p)], a = A[t.charCodeAt(p + 1)], s = A[t.charCodeAt(p + 2)], o = A[t.charCodeAt(p + 3)], y[r++] = n << 2 | a >> 4, y[r++] = (a & 15) << 4 | s >> 2, y[r++] = (s & 3) << 6 | o & 63;
            return c
        },
        C = t => {
            const e = new Uint8Array(t),
                r = e.length;
            let n = "";
            for (let a = 0; a < r; a += 3) n += g[e[a] >> 2], n += g[(e[a] & 3) << 4 | e[a + 1] >> 4], n += g[(e[a + 1] & 15) << 2 | e[a + 2] >> 6], n += g[e[a + 2] & 63];
            return r % 3 === 2 ? n = n.substring(0, n.length - 1) + "=" : r % 3 === 1 && (n = n.substring(0, n.length - 2) + "=="), n
        },
        V = t => {
            if (!t) return "";
            let e = t.replace(/-/g, "+").replace(/_/g, "/");
            const r = 4 - e.length % 4;
            return r !== 4 && (e += "=".repeat(r)), e
        },
        P = () => {
            let t, e;
            const r = new Promise((n, a) => {
                t = n, e = a
            });
            if (!t || !e) throw new Error("Missing Resolvers");
            return {
                promise: r,
                resolve: t,
                reject: e
            }
        },
        H = t => ({
            ok: !0,
            value: t
        }),
        K = t => ({
            ok: !1,
            error: t
        }),
        S = (t, e) => t instanceof Error ? t : typeof DOMException == "function" && t instanceof DOMException ? new Error(`DOMException: ${t.name} ${t.message}`) : (typeof e == "function" ? e(t) : e) || new Error(`${t}`),
        D = new WeakMap,
        J = (t, ...e) => {
            const r = e.filter(a => a instanceof AbortSignal);
            if (!r.length) return;
            const n = D.get(t) || new WeakSet;
            D.set(t, n);
            for (const a of r) {
                if (t.signal.aborted) break;
                if (n.has(a)) continue;
                const s = () => {
                    t.abort(a.reason), a.removeEventListener("abort", s), D.delete(t), n.delete(a)
                };
                a.aborted ? s() : (n.add(a), a.addEventListener("abort", s))
            }
        };
    class E extends Error {
        constructor(e, r) {
            super(e.message), this.underlyingError = e, this.response = r
        }
    }
    const q = async (t, e) => typeof t == "function" ? t(e) : t, Q = async (t, e, r) => {
        if (typeof t == "number") return t;
        if (typeof t == "function") return t == null ? void 0 : t(e, r);
        if (Array.isArray(t)) return t[e]
    }, O = (t, e) => {
        const {
            init: r,
            inspect: n,
            retry: a,
            timeout: s
        } = e || {}, {
            promise: o,
            resolve: c
        } = P(), y = new AbortController, p = i => {
            c(i), d !== null && clearTimeout(d), y.signal.aborted || y.abort(i)
        }, w = async i => {
            const l = i && !i.ok && i.error || null,
                h = await q(r, l) || {};
            J(y, h.signal);
            const f = await fetch(t, {
                ...h
            }).then(H);
            return await (n == null ? void 0 : n(f.value, l)) || f
        };
        let d = null,
            m = 0;
        return s && (d = setTimeout(() => p(K(new E(new Error(`The extended-fetch timeout of ${s}ms has been exceeded`)))), s)), y.signal.addEventListener("abort", () => {
            const {
                reason: i
            } = y.signal;
            p(K(new E(S(i, new Error(`Extended-fetch aborted: ${i}`)))))
        }), (async () => {
            let i = null;
            try {
                for (; !y.signal.aborted && (i = await w(i).catch(f => K(new E(S(f, new Error(`Extended-fetch fetch error: ${f}`))))), !i.ok);) {
                    const l = await Q(a, m, i.error).catch(() => null);
                    if (typeof l != "number") break;
                    const h = Math.max(0, l);
                    h && await new Promise(f => setTimeout(f, h)), m++
                }
                p(i || K(new E(new Error("No extended-fetch result"))))
            } catch (l) {
                p(K(new E(new Error(`Extended-fetch error: ${l}`))))
            }
        })(), o
    }, v = 256, M = ["encrypt", "decrypt"], Z = {
        ASYMMETRIC_PRIVATE_KEY: {
            keyFormat: "jwk",
            keyProperties: {
                name: "ECDH",
                namedCurve: "P-256"
            },
            keyUsages: ["deriveBits", "deriveKey"]
        },
        "SYMMETRIC_AES-GCM_KEY": {
            keyFormat: "raw",
            keyProperties: {
                name: "AES-GCM",
                length: v
            },
            keyUsages: M
        },
        "SYMMETRIC_AES-CTR_KEY": {
            keyFormat: "raw",
            keyProperties: {
                name: "AES-CTR",
                length: v
            },
            keyUsages: M
        },
        WRAPPING_KEY: {
            keyFormat: "raw",
            keyProperties: {
                name: "AES-KW",
                length: v
            },
            keyUsages: ["wrapKey", "unwrapKey"]
        },
        WRAPPED_ASYMMETRIC_PRIVATE_KEY: {
            keyFormat: "raw",
            keyProperties: {
                name: "AES-CTR"
            },
            keyUsages: ["wrapKey"]
        }
    }, R = new Map, N = new Map;
    class u {
        static getKeyProperties(e) {
            return Z[e]
        }
        async createKeyWrappingKey() {
            const e = u.getKeyProperties("WRAPPING_KEY");
            return crypto.subtle.generateKey(e.keyProperties, !0, e.keyUsages)
        }
        async createEncryptionAesCryptoKey(e) {
            const r = u.getKeyProperties(e);
            return {
                aesKeyType: e,
                cryptoKey: await crypto.subtle.generateKey(r.keyProperties, !0, r.keyUsages)
            }
        }
        async deriveEncryptionKeyFromAesKey(e, r) {
            const n = u.getKeyProperties(e.aesKeyType),
                a = await crypto.subtle.exportKey("raw", e.cryptoKey),
                s = await crypto.subtle.importKey("raw", a, "HKDF", !1, ["deriveKey"]),
                o = new TextEncoder;
            return {
                aesKeyType: e.aesKeyType,
                cryptoKey: await crypto.subtle.deriveKey({
                    name: "HKDF",
                    hash: "SHA-256",
                    info: o.encode(r),
                    salt: o.encode("no-salt-because-it-needs-to-be-deterministic")
                }, s, n.keyProperties, !0, n.keyUsages)
            }
        }
        async serializeEncryptionAesCryptoKey({
            aesKeyType: e,
            cryptoKey: r
        }) {
            return {
                aesKeyType: e,
                jwk: await crypto.subtle.exportKey("jwk", r)
            }
        }
        async deserializeEncryptionAesCryptoKey({
            aesKeyType: e,
            jwk: r
        }) {
            const n = u.getKeyProperties(e);
            return {
                aesKeyType: e,
                cryptoKey: await crypto.subtle.importKey("jwk", r, n.keyProperties, !0, n.keyUsages)
            }
        }
        randomSalt() {
            return crypto.getRandomValues(new Uint8Array(16))
        }
        async wrapWithPassphrase(e, r, n) {
            const a = await this.generateWrappingKeyFromPassphrase(e, r),
                s = this.getWrappingFormat(n);
            return crypto.subtle.wrapKey(s, n, a, "AES-KW")
        }
        async extractPrivateKeyAndWrapWithPassphrase(e, r, n) {
            const a = await this.generateWrappingKeyFromPassphrase(e, r);
            return this.extractPrivateKeyAndWrapWithWrappingKey(a, n)
        }
        async unwrapKeyWithPassphrase(e, r, n, a) {
            const s = `${a}_${e}_${C(r)}_${C(n)}`,
                o = N.get(s);
            if (o) return o;
            const c = await this.generateWrappingKeyFromPassphrase(e, r),
                {
                    keyFormat: y,
                    keyProperties: p,
                    keyUsages: w
                } = u.getKeyProperties(a),
                d = await crypto.subtle.unwrapKey(y, n, c, "AES-KW", p, !0, w);
            return N.set(s, d), d
        }
        async unwrapKeyWithWrappingKey(e, r, n) {
            const {
                keyFormat: a,
                keyProperties: s,
                keyUsages: o
            } = u.getKeyProperties(n);
            return crypto.subtle.unwrapKey(a, r, e, "AES-KW", s, !0, o)
        }
        wrapWithWrappingKey(e, r) {
            return crypto.subtle.wrapKey(this.getWrappingFormat(r), r, e, "AES-KW")
        }
        async extractPrivateKeyAndWrapWithWrappingKey(e, r) {
            const n = await this.extractPrivateKey(r),
                a = await crypto.subtle.importKey("raw", b(n), {
                    name: "AES-CTR"
                }, !0, ["wrapKey"]);
            return crypto.subtle.wrapKey("raw", a, e, "AES-KW")
        }
        async encryptAesGcm(e, r, n) {
            const a = await crypto.subtle.encrypt({
                name: "AES-GCM",
                iv: n
            }, e.cryptoKey, r);
            return {
                iv: n,
                encryptedData: a
            }
        }
        async encryptAesCtr(e, r, n, a) {
            const s = this.getAesCtrNonce(n, a),
                o = await crypto.subtle.encrypt({
                    name: "AES-CTR",
                    counter: s,
                    length: 40
                }, e.cryptoKey, r),
                c = a + Math.ceil(r.byteLength / 16);
            return {
                iv: n,
                encryptedData: o,
                newCounter: c
            }
        }
        getAesCtrNonce(e, r) {
            if (e.byteLength !== 11) throw new Error("IV must be 11 bytes");
            if (r < 0 || r > 0xffffffffff || !Number.isInteger(r)) throw new Error("Counter must be a non-negative integer not exceeding 40 bits");
            const n = new ArrayBuffer(16);
            new Uint8Array(n).set(new Uint8Array(e), 0);
            const s = new DataView(n, 11, 5);
            return s.setUint32(0, Math.floor(r / 256), !1), s.setUint8(4, r % 256), n
        }
        decryptAesGcm(e, r, n) {
            return n.byteLength === 0 ? new ArrayBuffer(0) : crypto.subtle.decrypt({
                name: "AES-GCM",
                iv: r
            }, e.cryptoKey, n)
        }
        async decryptAesCtr(e, r, n, a) {
            if (a.byteLength == 0) return {
                decryptedData: new ArrayBuffer(0),
                newCounter: n
            };
            const o = {
                    name: "AES-CTR",
                    counter: this.getAesCtrNonce(r, n),
                    length: 40
                },
                c = await crypto.subtle.decrypt(o, e.cryptoKey, a),
                y = n + Math.ceil(a.byteLength / 16);
            return {
                decryptedData: c,
                newCounter: y
            }
        }
        async exportPrivateKey(e) {
            return JSON.stringify(await crypto.subtle.exportKey("jwk", e))
        }
        async importPrivateKey(e) {
            const {
                keyProperties: r
            } = u.getKeyProperties("ASYMMETRIC_PRIVATE_KEY");
            return await crypto.subtle.importKey("jwk", e, r, !0, ["deriveKey", "deriveBits"])
        }
        async generateWrappingKeyFromPassphrase(e, r) {
            const n = `${e}_${C(r)}`,
                a = R.get(n);
            if (a) return a;
            const s = await crypto.subtle.importKey("raw", new TextEncoder().encode(e), {
                    name: "PBKDF2"
                }, !1, ["deriveBits", "deriveKey"]),
                o = u.getKeyProperties("WRAPPING_KEY"),
                c = await crypto.subtle.deriveKey({
                    name: "PBKDF2",
                    iterations: 1e5,
                    hash: "SHA-256",
                    salt: r
                }, s, o.keyProperties, !0, o.keyUsages);
            return R.set(n, c), c
        }
        getWrappingFormat(e) {
            switch (e.type) {
                case "private":
                    return "jwk";
                case "public":
                case "secret":
                    return "raw";
                default:
                    throw new Error("Unsupported")
            }
        }
        async extractPrivateKey(e) {
            if (e.type === "secret") return C(await crypto.subtle.exportKey("raw", e));
            const n = (await crypto.subtle.exportKey("jwk", e)).d;
            if (!n) throw Error("Could not extract private-key part");
            return V(n)
        }
    }
    const T = async t => {
        const e = new u,
            [r, n] = await Promise.all([e.deserializeEncryptionAesCryptoKey(t.aesGcmJwk), e.deserializeEncryptionAesCryptoKey(t.aesCtrJwk)]);
        return {
            aesGcmCryptoKey: r,
            aesCtrCryptoKey: n
        }
    };
    var k = {
        staticContentItemEncryptionIvs: {
            mainFileNameBase64: "EtrUFVLIRAW8aUCd",
            mainFileBase64: "C8aZG384/qPpBzg=",
            mainFileSha1Base64: "6Q+YlJkg8RFR/FHN",
            previewFileBase64: "i3iv8Nv2xEje9VE="
        }
    };
    class U {
        constructor(e) {
            this.decryptionKeys = e, this.utf8TextDecoder = new TextDecoder, this.symmetricKeyService = new u
        }
        async decryptContentItemFileName(e) {
            return this.utf8TextDecoder.decode(await this.decryptAesGcm(b(e.nameEncrypted), k.staticContentItemEncryptionIvs.mainFileNameBase64))
        }
        async decryptContentItemSha1(e) {
            return this.decryptAesGcm(b(e.sha1Encrypted), k.staticContentItemEncryptionIvs.mainFileSha1Base64)
        }
        async decryptContentItemFileStream(e, r) {
            return this.decryptAesCtr(e, k.staticContentItemEncryptionIvs.mainFileBase64, r)
        }
        async decryptPreviewFileContents(e) {
            return this.decryptAesCtr(e, k.staticContentItemEncryptionIvs.previewFileBase64)
        }
        async decryptAesGcm(e, r) {
            return this.symmetricKeyService.decryptAesGcm(this.decryptionKeys.aesGcmCryptoKey, b(r), e)
        }
        async decryptAesCtr(e, r, n = 0) {
            if (n % 16) throw new Error("decryptAesCtr: byteOffset must be aligned to block size (multiple of 16)");
            const a = this.symmetricKeyService,
                s = b(r);
            let o = n / 16,
                c = new Uint8Array(0);
            const y = new TransformStream({
                transform: async (p, w) => {
                    const d = new Uint8Array(c.byteLength + p.byteLength);
                    d.set(c, 0), d.set(new Uint8Array(p), c.byteLength);
                    const m = Math.floor(d.byteLength / 16) * 16,
                        i = d.slice(0, m),
                        {
                            decryptedData: l,
                            newCounter: h
                        } = await a.decryptAesCtr(this.decryptionKeys.aesCtrCryptoKey, s, o, i);
                    w.enqueue(new Uint8Array(l)), c = d.slice(m), o = h
                },
                flush: async p => {
                    if (c.byteLength > 0) {
                        const {
                            decryptedData: w,
                            newCounter: d
                        } = await a.decryptAesCtr(this.decryptionKeys.aesCtrCryptoKey, s, o, c);
                        p.enqueue(new Uint8Array(w)), o = d
                    }
                }
            });
            return e.pipeThrough(y)
        }
    }
    const B = typeof WorkerGlobalScope < "u" && self instanceof WorkerGlobalScope,
        G = typeof SharedWorkerGlobalScope < "u" && self instanceof SharedWorkerGlobalScope,
        X = _({
            maxDelay: 45e3
        }),
        F = new Map,
        I = new Map,
        L = t => `${t.id}${t.nameEncrypted}`,
        $ = (t, e) => `${t.id}${e==null?void 0:e.id}`,
        W = new Set,
        x = new Set,
        ee = 6,
        Y = () => {
            const t = Array.from(W)[0];
            t && (x.add(t), W.delete(t), t().then(() => {
                x.delete(t), Y()
            }))
        },
        j = t => {
            W.add(t), x.size < ee && Y()
        },
        z = t => async e => {
            const {
                data: r
            } = e;
            switch (r.type) {
                case "decryptName": {
                    t({
                        type: "decryptName",
                        contentItem: r.contentItem,
                        decryptedName: await te(await T(r.decryptionKeysSerialized), r.contentItem)
                    });
                    break
                }
                case "downloadAndDecryptData": {
                    const {
                        contentItem: n,
                        previewItem: a,
                        downloadUrl: s,
                        decryptionKeysSerialized: o
                    } = r;
                    t({
                        type: "downloadAndDecryptData",
                        contentItem: n,
                        previewItem: a,
                        downloadUrl: s,
                        decryptedData: await re(s, await T(o), n, a)
                    });
                    break
                }
                case "cachedDecryptedName": {
                    t({
                        type: "cachedDecryptedName",
                        contentItem: r.contentItem,
                        decryptedName: await F.get(L(r.contentItem))
                    });
                    break
                }
                case "cachedDecryptedData": {
                    t({
                        type: "cachedDecryptedData",
                        contentItem: r.contentItem,
                        previewItem: r.previewItem,
                        decryptedData: await I.get($(r.contentItem, r.previewItem))
                    });
                    break
                }
            }
        };
    (B || G) && (addEventListener("error", ({
        error: t
    }) => {
        throw t instanceof Error ? t : typeof t == "string" ? new Error(t) : new Error(`[Content Item Decrypter worker] error: ${t}`)
    }), addEventListener("unhandledrejection", ({
        reason: t
    }) => {
        throw t instanceof Error ? t : typeof t == "string" ? new Error(t) : new Error(`[Content Item Decrypter worker] unhandledrejection: ${t}`)
    })), B && addEventListener("message", z(t => postMessage(t))), G && self.addEventListener("connect", e => {
        e.ports.forEach(r => {
            r.addEventListener("message", z(n => r.postMessage(n))), r.start()
        })
    });
    async function te(t, e) {
        const r = L(e),
            n = F.get(r);
        if (n) return n;
        const a = new U(t),
            {
                promise: s,
                resolve: o
            } = P();
        return F.set(r, s), j(async () => {
            const y = await a.decryptContentItemFileName(e);
            o(y)
        }), s
    }
    async function re(t, e, r, n) {
        const a = $(r, n),
            s = I.get(a);
        if (s) return s;
        const o = new U(e),
            {
                promise: c,
                resolve: y
            } = P();
        return I.set(a, c), j(async () => {
            const w = await O(t, {
                retry: X,
                inspect: l => l.status !== 200 && K(new E(new Error(`Could not download from "${t}"`), l))
            });
            if (!w.ok || !w.value.body) throw new Error(`Download failed from "${t}"`);
            const m = (await (n ? o.decryptPreviewFileContents(w.value.body) : o.decryptContentItemFileStream(w.value.body))).getReader();
            let i = new Blob;
            for (;;) {
                const {
                    value: l,
                    done: h
                } = await m.read();
                if (h) break;
                i = new Blob([i, l], {
                    type: (n == null ? void 0 : n.mediaType) ?? r.mediaType
                })
            }
            y(i)
        }), c
    }
})();
! function() {
    try {
        var e = "undefined" != typeof window ? window : "undefined" != typeof global ? global : "undefined" != typeof self ? self : {},
            n = (new Error).stack;
        n && (e._sentryDebugIds = e._sentryDebugIds || {}, e._sentryDebugIds[n] = "31a72b9e-aa34-5d58-a662-e9d1205350d5")
    } catch (e) {}
}()
//# debugId=31a72b9e-aa34-5d58-a662-e9d1205350d5
//# sourceMappingURL=content-item-decrypter.worker-BkKaelkV.js.map