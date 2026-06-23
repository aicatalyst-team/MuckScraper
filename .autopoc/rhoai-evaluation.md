# RHOAI Fitness Evaluation: MuckScraper

## Project Summary
Self-hosted news aggregator with AI-powered summarization, bias scoring, and story clustering using Ollama LLMs and pgvector embeddings. Flask web UI with edition publishing.

## Strategy Area
- **Category:** agentic-ai (LLM-powered content processing pipeline)
- **Relationship:** validates-platform-story

## Impact Dimensions (0-20 scale)
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| audience_value | 14 | Content processing teams needing AI-powered news aggregation |
| strategic_alignment | 12 | Uses LLM inference but not directly an RHOAI product feature |
| strategy_fit | 12 | Agentic AI adjacent: multi-step AI pipeline with tool integration |
| platform_leverage | 14 | Multi-container deployment leverages OpenShift orchestration |
| demo_potential | 16 | Polished web UI with dark mode, bias visualization, real-time AI summaries |

**Impact Score:** (14 + 12 + 12 + 14 + 16) / 5 = **13.6 / 20**

## Feasibility Dimensions (0-10 scale)
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| container_readiness | 7 | Existing Dockerfiles, but need UBI conversion and Playwright deps |
| dependency_profile | 3 | Heavy deps: PostgreSQL+pgvector, Meilisearch, Ollama, News APIs |
| reproduction_confidence | 4 | Complex multi-service orchestration with migration requirements |
| complexity_sweet_spot | 5 | Interesting demo but complex for 1-3 day PoC |

**Feasibility Score:** (7 + 3 + 4 + 5) / 4 = **4.75 / 10**

## Recommendation
Challenging but rewarding PoC candidate. Focus on web + scheduler components with PostgreSQL sidecar. Skip Meilisearch initially, use stub mode for Ollama if available, or connect to LLM proxy.
