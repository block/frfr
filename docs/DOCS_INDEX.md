# Frfr Documentation Index

Quick reference to find the right documentation for your needs.

## Getting Started

| Document | Purpose | Audience |
|----------|---------|----------|
| **[QUICKSTART.md](QUICKSTART.md)** | Get up and running in 5 minutes | Everyone |
| **[README.md](../README.md)** | Full project overview and usage | Users & Developers |
| **[README.docker.md](README.docker.md)** | Docker setup and troubleshooting | Docker users |
| **[AUTHENTICATION.md](AUTHENTICATION.md)** | API key setup and auth configuration | Everyone |

## Architecture & Design

| Document | Purpose | Audience |
|----------|---------|----------|
| **[DESIGN.md](DESIGN.md)** | System architecture and design decisions | Developers & Contributors |
| **[STATUS.md](../STATUS.md)** | Current V5 production status and features | Everyone |

## Features & Implementation

| Document | Purpose | Audience |
|----------|---------|----------|
| **[ENHANCED_EXTRACTION.md](ENHANCED_EXTRACTION.md)** | Enhanced extraction guide with metadata | Developers |
| **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** | V4 implementation summary | Developers |
| **[MAXIMUM_DEPTH_MODE.md](MAXIMUM_DEPTH_MODE.md)** | Maximum depth extraction philosophy | Developers |
| **[PARALLEL_AND_RECOVERY.md](PARALLEL_AND_RECOVERY.md)** | Parallel processing and recovery | Developers |
| Resume capability: see [PARALLEL_AND_RECOVERY.md](PARALLEL_AND_RECOVERY.md) | Resume interrupted extractions | Users |
| **[STRUCTURAL_EXTRACTION.md](STRUCTURAL_EXTRACTION.md)** | Structure-aware extraction | Developers |
| **[TEST_SUITE_SUMMARY.md](TEST_SUITE_SUMMARY.md)** | Component test suite | Developers |

## V5 - Multiple Evidence Quotes (Current)

| Document | Purpose | Audience |
|----------|---------|----------|
| **[V5_DESIGN.md](V5_DESIGN.md)** | V5 design and architecture | Developers |
| **[V5_IMPLEMENTATION_COMPLETE.md](V5_IMPLEMENTATION_COMPLETE.md)** | V5 implementation details | Developers |
| **[V5_FINAL_RESULTS.md](V5_FINAL_RESULTS.md)** | V5 production results (35% QV coverage) | Everyone |

## Quick Navigation

### "I want to..."

- **...get started quickly** → [QUICKSTART.md](QUICKSTART.md)
- **...understand the architecture** → [DESIGN.md](DESIGN.md) or [README.md](../README.md)
- **...set up Docker** → [README.docker.md](README.docker.md)
- **...set up authentication** → [AUTHENTICATION.md](AUTHENTICATION.md)
- **...see current production status** → [STATUS.md](../STATUS.md)
- **...understand V5 features** → [V5_FINAL_RESULTS.md](V5_FINAL_RESULTS.md)
- **...learn about extraction features** → [ENHANCED_EXTRACTION.md](ENHANCED_EXTRACTION.md)
- **...resume an interrupted extraction** → [PARALLEL_AND_RECOVERY.md](PARALLEL_AND_RECOVERY.md)
- **...troubleshoot Docker** → [README.docker.md](README.docker.md#troubleshooting)
- **...run Makefile commands** → Run `make help`

## Documentation Structure

```
frfr/
├── README.md                          # Main documentation (at repo root)
├── QUICKSTART.md                      # 5-minute setup
├── DESIGN.md                          # Architecture & philosophy
├── STATUS.md                          # Current V5 production status (at repo root)
├── README.docker.md                   # Docker guide
├── AUTHENTICATION.md                  # API key setup
├── DOCS_INDEX.md                      # This file
├── ENHANCED_EXTRACTION.md             # Enhanced extraction guide
├── IMPLEMENTATION_SUMMARY.md          # Implementation summary
├── MAXIMUM_DEPTH_MODE.md              # Maximum depth philosophy
├── PARALLEL_AND_RECOVERY.md           # Parallel processing
├── STRUCTURAL_EXTRACTION.md           # Structure-aware extraction
├── TEST_SUITE_SUMMARY.md              # Test suite
├── V5_DESIGN.md                       # V5 design
├── V5_IMPLEMENTATION_COMPLETE.md      # V5 implementation
├── V5_FINAL_RESULTS.md                # V5 production results
├── .env.example                       # Configuration template
└── Makefile                           # Docker commands
```

## Key Concepts by Document

### Core Documentation

**README.md** - Project overview, installation, usage, CLI options, fact schema, use cases

**DESIGN.md** - Problem statement, solution approach, core components, design decisions

**STATUS.md** - V5 production status, current features, performance metrics, next steps

**QUICKSTART.md** - 3-command quick start for PDF extraction

**README.docker.md** - Docker setup, services, commands, troubleshooting

**AUTHENTICATION.md** - API key setup, Claude CLI auth, troubleshooting

### Feature Documentation

**V5_FINAL_RESULTS.md** - V5 production results, 35% QV coverage achieved, feature adoption

**ENHANCED_EXTRACTION.md** - Enhanced schema, metadata fields, specificity scoring

**MAXIMUM_DEPTH_MODE.md** - Maximum depth philosophy, extraction strategy

**PARALLEL_AND_RECOVERY.md** - Parallel processing, fact recovery, performance

**PARALLEL_AND_RECOVERY.md** - Resume interrupted extractions, session management

**STRUCTURAL_EXTRACTION.md** - Section-aware extraction, table structure parsing

**TEST_SUITE_SUMMARY.md** - Component test suite, validation scripts

## For Different Roles

### End Users
1. [QUICKSTART.md](QUICKSTART.md) - Get started in 3 commands
2. [README.md](../README.md) - Full usage guide
3. [AUTHENTICATION.md](AUTHENTICATION.md) - Set up API access
4. [PARALLEL_AND_RECOVERY.md](PARALLEL_AND_RECOVERY.md) - Resume interrupted work

### Developers (New)
1. [README.md](README.md) - Project overview
2. [DESIGN.md](DESIGN.md) - Architecture and philosophy
3. [README.docker.md](README.docker.md) - Development setup
4. [STATUS.md](../STATUS.md) - Current production status
5. [V5_FINAL_RESULTS.md](V5_FINAL_RESULTS.md) - Latest achievements

### Contributors
1. [STATUS.md](../STATUS.md) - Current V5 production status
2. [ENHANCED_EXTRACTION.md](ENHANCED_EXTRACTION.md) - Extraction features
3. [V5_DESIGN.md](V5_DESIGN.md) - V5 architecture
4. [DESIGN.md](DESIGN.md) - Core philosophy

### Production Users
1. [V5_FINAL_RESULTS.md](V5_FINAL_RESULTS.md) - V5 performance metrics
1. [STATUS.md](../STATUS.md) - Production features and status
3. [AUTHENTICATION.md](AUTHENTICATION.md) - Deployment auth setup

## Documentation Standards

All documentation follows these principles:
- **Clarity**: Clear, concise language
- **Examples**: Practical code examples
- **Context**: Explains "why" not just "how"
- **Up-to-date**: Reflects current implementation
- **Cross-referenced**: Links to related docs

## Need More Help?

- Check `make help` for Docker commands
- See [README.docker.md](README.docker.md#troubleshooting) for troubleshooting
- Review [STATUS.md](../STATUS.md) for current production status
- Check [V5_FINAL_RESULTS.md](V5_FINAL_RESULTS.md) for performance metrics
- Review module-specific docstrings in source code

---

**Last updated**: 2025-10-17 - V5 production-ready with 35% QV coverage, 17 active docs
