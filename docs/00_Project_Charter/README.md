# Project Charter

## Project name

ChatBotWeb / Yoranix AI Platform

## Purpose

Create a reusable multi-tenant AI knowledge platform that allows Verizon Group to deliver client-specific chatbots and future AI agents without rebuilding each solution from scratch.

## Business problem

Verizon Group receives repeated requests from small and medium organisations for chatbots that can answer questions from a specific knowledge base. Each request currently risks becoming a custom implementation project. This does not scale operationally or commercially.

## Product objective

Build one platform where a new client can be onboarded by creating a tenant workspace, uploading or connecting knowledge sources, configuring branding, and deploying a chatbot widget.

## Target outcome

A production-ready SaaS platform capable of supporting thousands of organisations, each with isolated data, knowledge bases, users, analytics, and deployment channels.

## Initial scope

The MVP includes:

- Organisation and workspace management
- Client admin dashboard
- Document upload and knowledge management
- RAG ingestion pipeline
- Tenant-aware retrieval
- Chatbot API
- Embeddable website widget
- Chat history
- Source citations
- Basic analytics
- Basic role-based access control

## Out of scope for MVP

- Voice agents
- WhatsApp integration
- Microsoft Teams integration
- Billing engine
- Marketplace
- Autonomous multi-agent workflows
- Custom model training
- Fine-tuning
- Multi-region deployment

## Success criteria

- A client can be onboarded without custom engineering.
- A client can upload knowledge and receive chatbot answers from it.
- Chatbot answers include source grounding.
- Tenant data is isolated.
- The platform can support multiple organisations from the same codebase.
- The MVP can be deployed using Docker.

## Key risks

- Poor retrieval quality from messy documents
- Cross-tenant data leakage
- Outdated knowledge being used in answers
- High LLM cost per conversation
- Hallucinated responses
- Unclear client ownership of knowledge updates

## Guiding principle

This project is not a chatbot demo. It is a commercial AI platform designed for repeatable delivery and long-term scale.
