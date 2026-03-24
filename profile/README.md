# ChittyApps

**End-user applications built on the ChittyOS platform.**

ChittyApps delivers the products people actually use -- financial management, document signing, evidence processing, and AI agent interfaces -- all backed by ChittyOS trust infrastructure.

## Projects

| Project | What It Does | Stack |
|---------|-------------|-------|
| [**ChittyFinance**](https://github.com/chittyapps/chittyfinance) | Multi-entity financial management with Plaid banking integration | Express + React + Vite |
| [**DocuMint**](https://github.com/chittyapps/documint) | Document signing with ChittyProof 11-pillar proof standard | Cloudflare Workers |
| [**ChittyProof**](https://github.com/chittyapps/chittyproof) | Evidence-grade document transformation and proof minting | Cloudflare Workers |
| [**ChittyContextual**](https://github.com/chittyapps/chittycontextual) | Timeline analysis and contextual topic extraction with iMessage integration | Cloudflare Workers |
| [**ChittyAgent Studio**](https://github.com/chittyapps/chittyagent-studio) | Visual AI agent builder and management interface | React |

## How It Fits

```
ChittyFoundation  -->  Trust anchors (ID, Chain, DNA)
ChittyOS          -->  Platform services (Auth, Connect, Router)
ChittyApps        -->  User-facing products  <-- you are here
```

Every app authenticates through ChittyAuth, resolves identity via ChittyID, and logs events to ChittyChronicle.

## Contributing

Each repo has a `CLAUDE.md` with dev commands and patterns. Most apps deploy to Cloudflare Workers via `npx wrangler deploy`.

---

Part of the [ChittyOS ecosystem](https://github.com/chittyos)
