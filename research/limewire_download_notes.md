# LimeWire download session (cjxAz#yIi6FVqNS1)

- Obtained pre-signed download URLs for the four assets by controlling the LimeWire UI with Playwright.
- Request workflow per item:
  1. PUT https://api.limewire.com/crossdomain/csrf to receive a CSRF token (`csrfToken`).
  2. POST https://api.limewire.com/sharing/user-encryption-key with header `x-csrf-token` and JSON body `{"contentItems":[{"id":...}]}` to retrieve a wrapped AES/EC key bundle for the session.
  3. GET https://api.limewire.com/users/self/passphrase with the same token to obtain the passphrase for unwrapping the session keys.
  4. POST https://api.limewire.com/sharing/download/<bucket-id> to receive a JSON payload containing the presigned Cloudflare R2 `downloadUrl` for each file.
- Downloaded artifacts (stored under `modules/basemod_wrapper/lib/`, gitignored):
  - `waDfuFILUt2+ufzPPg2tpRZOHn+FRIDwibx5yA4JLA==` (~1.4 MB)
  - `zq7IiXcBZYO9quvAWAPfzgBygCiymoFlR1Gt` (~7.3 MB)
  - `6KrIh04BcYDm5anPPg2tyrmUfXZd4tvBI9VT1eJFbA==` (~349 MB)
  - `4aDfwU8ebcK2r_yTega+8uk_7wU5dfeTo70dUJRWF_Q=` (~1.6 MB)
- The binary headers (`f0 4d fa 13 ...`) show the blobs are encrypted; the decrypter worker (`research/content-item-decrypter.worker.pretty.js`) relies on:
  - AES-GCM for metadata (filenames, SHA1) with static IVs from `staticContentItemEncryptionIvs`.
  - AES-CTR (11 byte IV + 40 bit counter) for the actual file stream.
  - Session keys are derived via ECDH using an ephemeral public key that ships with the content item metadata.
- Follow-up work: replicate the `GE#getContentItemDecryptionKeys` path in Python to unwrap the AES keys with the provided passphrase and decrypt the downloaded blobs.
