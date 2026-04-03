---
layout: default
title: Evidence-Bound Documentation
---

# Evidence-Bound Documentation

Enterprise Document Q&A with Verified Citations. Every answer cites source documents — or the system refuses.

---

## Getting Started

- [Getting Started](GETTING_STARTED.md) — Clone to running in 10 minutes

## Architecture

- [Architecture Diagrams](ARCHITECTURE_DIAGRAM.md) — System overview, RAG pipeline, data model, deployment, auth flow
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md) — Stack, security, providers, deployment tiers
- [Architecture Review](ARCHITECTURE_REVIEW.md) — Honest gaps, competitive analysis, roadmap

## Technical Reference

- [Technical Deep Dive](TECHNICAL_DEEP_DIVE.md) — RAG pipeline internals, caching, cost tracking, PII, testing
- [LLM Providers](LLM_PROVIDERS.md) — Configure Azure OpenAI, Anthropic, Gemini, Ollama
- [Data Model](architecture/data-model.md) — Full database schema (11 tables)
- [Provider Interfaces](architecture/interfaces.md) — LLM, Search, Embedding, Parser abstractions
- [Migrations](architecture/migrations.md) — Schema migration patterns

## Operations

- [Operations Runbook](OPERATIONS.md) — Deploy, monitor, diagnose, rollback
- [Development Workflow](WORKFLOW.md) — TDD, skills, hooks, review gates

## Strategic

- [RAG Harness Spec](RAG_HARNESS_SPEC.md) — Extracting a reusable RAG framework
- [Multi-Tenant Readiness](planning/MULTI_TENANT_READINESS.md) — SaaS gap analysis
