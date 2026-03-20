# Trading Automation Startup — Planning Hub

> **Vision**: Build a company that designs configurable automated trading system apps for customers, across any broker platform, with a professional GUI/CLI.

---

## Company & Founder

| Item | Detail |
|------|--------|
| **Entity** | NODEBLE Limited Partnership |
| **UEN** | T22LP0146G |
| **Type** | LLP (Limited Liability Partnership) |
| **Jurisdiction** | Singapore |
| **Founder** | Ma Yongtao |
| **Status** | Active (currently dormant) |
| **Address** | 99 Robertson Quay #40-11, Singapore 238258 |

### Founder Background
- Retired — previously in tech/finance
- Running 4 automated trading systems in production ($300K+ real money)
- 20+ milestones of iterative development with AI-assisted coding
- Currently studying SUSS (Accountancy → considering CS/AI pivot)
### Infrastructure

| Machine | Specs | Role | IP |
|---------|-------|------|----|
| **Mac Mini (M-series)** | Apple Silicon, 228GB disk | Production trading server — runs all 4 trading systems, OpenClaw gateway, cron jobs 24/7 | localhost |
| **Desktop Server** | i7-8700, 32GB DDR4, **RTX 5060 Ti 16GB + RTX 4080**, 512GB NVMe, Ubuntu Server 24.04 | GPU compute — local LLM inference (Qwen2.5-14B), future ML/backtesting workloads | 192.168.1.5 |
| **Synology DS1821+** | 8-bay NAS, 3× 10TB SATA (SHR ~20TB usable) | Storage — backups, data archival | LAN |

> [!note] The desktop server alone has more GPU power than most small hedge fund setups. Two GPUs means we can run inference + training simultaneously, or serve multiple users' backtests in parallel.

### Assets Available
- **Existing codebase**: ~9,000+ lines of battle-tested trading automation code
- **Live track record**: real money results across Tiger, IBKR, Longport, Moomoo
- **Company entity**: ready to invoice, sign contracts, hold IP
- **Hardware**: 3 servers (trading, GPU compute, storage) — enough to host MVP for 50+ users
- **AI tooling**: Claude Code, OpenClaw — rapid development capability

---

## Navigation

### Foundation
- [[01 - Existing Systems Audit]] — What we've already built and proven
- [[02 - Cross-Platform Comparison]] — Feature matrix across all 4 systems
- [[03 - Core IP & Reusable Components]] — What can be extracted into a product

### Product
- [[04 - Product Vision]] — What we're building and for whom
- [[05 - Architecture Draft]] — Technical architecture for the product
- [[06 - MVP Definition]] — Minimum viable product scope
- [[07 - Technology Stack]] — Web (FastAPI + React)

### Business
- [[08 - Target Market]] — Chinese-speaking Tiger Brokers traders
- [[09 - Business Model]] — Pure software tool (no advisory license needed)
- [[10 - Competitive Landscape]] — Tiger automation is a near-vacuum
- [[11 - Regulatory Considerations]] — ⚠️ MUST READ before commercial launch

### Execution
- [[12 - Roadmap]] — Friends (free) → Software Tool → Platform
- [[13 - Team & Hiring]] — Solo founder + AI tools
- [[14 - Funding Strategy]] — 100% self-funded / bootstrapped
- [[15 - Implementation Sessions]] — Step-by-step session guide (30+ sessions)

---

**Created**: 2026-03-19
**Status**: Discovery Phase → v2 (contradictions resolved after audit review)
**Audit**: [2026-03-19 Vault Review](~/workspace/results/2026-03-19-vault-review.md)
