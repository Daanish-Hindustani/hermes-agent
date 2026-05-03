# Protein Design Agent

A focused agent for protein design, forked from [Nous Research's Hermes Agent](https://github.com/NousResearch/hermes-agent).
The fork strips Hermes down to its core runtime (CLI, planning/memory, tool registry, browser, terminal, code execution, RL scaffolding) and adds a custom **protein-design plugin** plus protein-design-specific skills.

## What it does

The agent gives you a conversational interface over a curated set of protein-design tools:

- **Sequence + literature search** — PubMed, UniProt, RCSB
- **Structure prediction** — ESMFold, AlphaFold2-Multimer
- **Design** — RFdiffusion3, ProteinMPNN, binder design
- **Analysis** — Rosetta interface analyzer, structure inspection

All wired through Hermes' tool-calling runtime, so the agent can plan multi-step pipelines (search → design → predict → analyze) and run them with persistent memory across sessions.

## Quick start

```bash
# Install dependencies (uv recommended)
uv sync

# Run the CLI
python cli.py
# or use the wrapper
./proteinclaw
```

## Repo layout

```
plugins/protein-design/      # Custom protein-design plugin (tools, runtime, schemas)
skills/protein-design/       # Protein-design skill documents
plugins/                     # Kept: context_engine, memory, observability
tools/                       # Core Hermes tools (web, terminal, browser, file, mcp, etc.)
agent/                       # LLM adapters, prompt builders, memory manager
gateway/                     # Local CLI gateway (platform integrations stripped)
environments/                # Tool execution environments
hermes_cli/                  # CLI wiring (auth, config, commands)
```

## What's been removed from upstream Hermes

To focus on protein design, this fork drops:

- All messaging-platform integrations (Telegram, Discord, Slack, WhatsApp, Signal, Feishu, etc.)
- Voice mode, TTS, transcription, and image generation tools
- Vision tools (LLM image analysis)
- Smart-home (Home Assistant), Spotify, and other consumer integrations
- The Docusaurus website and dashboard UIs
- All non-protein skills

See `git log backup/pre-protein-prune..HEAD` for the full prune history; checkout `backup/pre-protein-prune` for full rollback.

## License

MIT, inherited from upstream Hermes Agent. See `LICENSE`.
