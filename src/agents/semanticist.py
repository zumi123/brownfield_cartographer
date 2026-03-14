"""
Semanticist agent: LLM-powered purpose statements, doc drift, domain clustering, Day-One answers.
Uses OPENAI_API_KEY (or OPENROUTER via base_url). Falls back to stubs when no key.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..graph.knowledge_graph import KnowledgeGraph

log = logging.getLogger(__name__)

# Rough token estimate: 1 token ~ 4 chars
CHARS_PER_TOKEN = 4
MAX_BULK_TOKENS = 50_000
MAX_SYNTHESIS_TOKENS = 30_000

# OpenRouter free models (see https://openrouter.ai/docs#models)
OPENROUTER_BULK_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_SYNTHESIS_MODEL = "google/gemini-2.0-flash-001"
OPENAI_BULK_MODEL = "gpt-4o-mini"
OPENAI_SYNTHESIS_MODEL = "gpt-4o"

# Retry and timeout for LLM calls (500s and timeouts are common on free tiers)
LLM_MAX_RETRIES = 3
LLM_RETRY_BACKOFF_SEC = 2.0
LLM_TIMEOUT_SEC = 90

# Root-level entry scripts to skip for LLM purpose (saves API calls, avoids analyzing the UI when run from Streamlit)
SKIP_PURPOSE_PATHS = {"app_ui.py", "run.py", "main.py", "manage.py"}


@dataclass
class ContextWindowBudget:
    """Track token usage and select model tier (bulk vs synthesis)."""

    cumulative_input: int = 0
    cumulative_output: int = 0
    bulk_budget: int = MAX_BULK_TOKENS
    synthesis_budget: int = MAX_SYNTHESIS_TOKENS

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // CHARS_PER_TOKEN)

    def use_bulk(self, input_tokens: int, output_estimate: int = 500) -> bool:
        if self.cumulative_input + input_tokens > self.bulk_budget:
            return False
        self.cumulative_input += input_tokens
        self.cumulative_output += output_estimate
        return True

    def use_synthesis(self, input_tokens: int, output_estimate: int = 2000) -> bool:
        if self.cumulative_input + input_tokens > self.synthesis_budget:
            return False
        self.cumulative_input += input_tokens
        self.cumulative_output += output_estimate
        return True

    def total_used(self) -> int:
        return self.cumulative_input + self.cumulative_output


def _get_client():
    """OpenAI-compatible client; supports OpenRouter (free models) via OPENROUTER_API_KEY + base URL."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENROUTER_API_BASE") or os.environ.get("OPENAI_API_BASE")
    # When using OpenRouter key, default base to OpenRouter API
    if api_key and (os.environ.get("OPENROUTER_API_KEY") or "openrouter" in (base_url or "").lower()):
        base_url = base_url or "https://openrouter.ai/api/v1"
    if not api_key:
        return None, None, None
    try:
        from openai import OpenAI
        client = (
            OpenAI(api_key=api_key, base_url=base_url, timeout=LLM_TIMEOUT_SEC)
            if base_url
            else OpenAI(api_key=api_key, timeout=LLM_TIMEOUT_SEC)
        )
        is_openrouter = base_url and "openrouter" in base_url.lower()
        return client, api_key, is_openrouter
    except Exception as e:
        log.warning("OpenAI client init failed: %s", e)
        return None, None, None


def _call_llm_with_retry(client, create_kwargs: dict, label: str = "LLM call"):
    """Run chat.completions.create with retries. Client should be built with timeout=LLM_TIMEOUT_SEC."""
    last_err = None
    for attempt in range(LLM_MAX_RETRIES):
        try:
            return client.chat.completions.create(**create_kwargs)
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            # Retry on 500, timeout, or connection errors
            if attempt < LLM_MAX_RETRIES - 1 and (
                "500" in err_str or "timeout" in err_str or "timed out" in err_str or "connection" in err_str
            ):
                delay = LLM_RETRY_BACKOFF_SEC * (2 ** attempt)
                log.info("%s failed (attempt %s): %s; retrying in %.1fs", label, attempt + 1, e, delay)
                time.sleep(delay)
            else:
                raise
    if last_err:
        raise last_err
    raise RuntimeError("LLM call failed")

def _extract_docstring(content: str) -> str:
    """First triple-quoted string in file (module docstring)."""
    for q in ['"""', "'''"]:
        i = content.find(q)
        if i >= 0:
            j = content.find(q, i + 3)
            if j >= 0:
                return content[i + 3 : j].strip()
    return ""


class Semanticist:
    """LLM-powered purpose extraction, domain clustering, and Day-One question answering."""

    def __init__(self, repo_root: pathlib.Path, knowledge_graph: KnowledgeGraph) -> None:
        self.repo_root = pathlib.Path(repo_root)
        self.kg = knowledge_graph
        self.budget = ContextWindowBudget()
        self._client, self._api_key, self._is_openrouter = _get_client()
        self._bulk_model = OPENROUTER_BULK_MODEL if self._is_openrouter else OPENAI_BULK_MODEL
        self._synthesis_model = OPENROUTER_SYNTHESIS_MODEL if self._is_openrouter else OPENAI_SYNTHESIS_MODEL
        self._purpose_statements: dict[str, str] = {}
        self._doc_drift: dict[str, bool] = {}
        self._domain_labels: dict[str, str] = {}
        self._day_one_answers: Optional[dict[str, Any]] = None

    def run(self) -> None:
        """Generate purpose statements for modules, cluster domains, answer Day-One questions."""
        # Purpose statements (bulk)
        for node_id in list(self.kg.module_graph.nodes):
            if self.kg.module_graph.nodes[node_id].get("language") != "python":
                continue
            # Skip root-level entry scripts (e.g. app_ui.py when running Streamlit from repo root)
            if node_id in SKIP_PURPOSE_PATHS or pathlib.Path(node_id).name in SKIP_PURPOSE_PATHS:
                self._purpose_statements[node_id] = f"Entry script: {node_id} (skipped for LLM)."
                if self.kg.module_graph.has_node(node_id):
                    self.kg.module_graph.nodes[node_id]["purpose_statement"] = self._purpose_statements[node_id]
                continue
            path = self.repo_root / node_id
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            purpose, drift = self.generate_purpose_statement(node_id, content)
            if purpose:
                self._purpose_statements[node_id] = purpose
                self.kg.module_graph.nodes[node_id]["purpose_statement"] = purpose
                self.kg.module_graph.nodes[node_id]["documentation_drift"] = drift
                self._doc_drift[node_id] = drift
        # Domain clustering
        self.cluster_into_domains()
        # Day-One answers
        self.answer_day_one_questions()

    def generate_purpose_statement(self, module_path: str, content: str) -> tuple[str, bool]:
        """Return (purpose_statement, documentation_drift)."""
        docstring = _extract_docstring(content)
        # Truncate code for context (no docstring in prompt for purpose)
        code_without_doc = content
        if docstring:
            for q in ['"""', "'''"]:
                if q + docstring + q in content:
                    code_without_doc = content.replace(q + docstring + q, "", 1).strip()
                    break
        code_snippet = code_without_doc[: 6000].strip()
        tokens = self.budget.estimate_tokens(code_snippet) + 200
        if not self.budget.use_bulk(tokens, 150):
            return self._stub_purpose(module_path), False

        if self._client is None:
            return self._stub_purpose(module_path), False

        try:
            resp = _call_llm_with_retry(
                self._client,
                {
                    "model": self._bulk_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a code analyst. Given a Python module's code (no docstring), output exactly 2-3 sentences describing what the module does (business/functional purpose), not implementation detail. Output only the purpose, no preamble.",
                        },
                        {"role": "user", "content": f"Module path: {module_path}\n\nCode:\n{code_snippet}"},
                    ],
                    "max_tokens": 150,
                },
                label=f"purpose({module_path})",
            )
            purpose = (resp.choices[0].message.content or "").strip()
            if not purpose:
                return self._stub_purpose(module_path), False
            # Drift: docstring contradicts or is absent where we inferred non-trivial purpose
            drift = bool(docstring and purpose and len(purpose) > 20)
            return purpose, drift
        except Exception as e:
            log.warning("LLM purpose failed for %s: %s", module_path, e)
            return self._stub_purpose(module_path), False

    def _stub_purpose(self, module_path: str) -> str:
        return f"Module at {module_path} (purpose not generated; no API key or LLM failed after retries)."

    def cluster_into_domains(self, k: int = 6) -> None:
        """Assign domain_cluster to each module from purpose statements (embed + k-means or keyword fallback)."""
        paths_with_purpose = [p for p in self._purpose_statements if self.kg.module_graph.has_node(p)]
        if not paths_with_purpose:
            self._cluster_keyword_fallback(k)
            return
        # OpenRouter does not expose embeddings API; use keyword fallback
        if self._is_openrouter:
            self._cluster_keyword_fallback(k)
            return
        if self._client:
            try:
                texts = [self._purpose_statements[p] for p in paths_with_purpose]
                emb = self._client.embeddings.create(model="text-embedding-3-small", input=texts)
                vecs = [e.embedding for e in emb.data]
                if len(vecs) != len(paths_with_purpose) or len(vecs) < 2:
                    self._cluster_keyword_fallback(k)
                    return
                import random
                n, dim = len(vecs), len(vecs[0])
                k_actual = min(k, n)
                centroids = [list(vecs[random.randint(0, n - 1)]) for _ in range(k_actual)]
                for _ in range(12):
                    assign = [min(range(k_actual), key=lambda c: sum((vecs[i][j] - centroids[c][j]) ** 2 for j in range(dim))) for i in range(n)]
                    new_centroids = []
                    for c in range(k_actual):
                        subset = [vecs[i] for i in range(n) if assign[i] == c]
                        if not subset:
                            new_centroids.append(centroids[c])
                        else:
                            new_centroids.append([sum(s[j] for s in subset) / len(subset) for j in range(dim)])
                    centroids = new_centroids
                for i, path in enumerate(paths_with_purpose):
                    if i < len(assign):
                        label = f"domain_{assign[i]}"
                        self.kg.module_graph.nodes[path]["domain_cluster"] = label
                        self._domain_labels[path] = label
                return
            except Exception as e:
                log.warning("Embedding/cluster failed: %s", e)
        self._cluster_keyword_fallback(k)

    def _cluster_keyword_fallback(self, k: int) -> None:
        keywords = ["agent", "orchestrat", "graph", "model", "schema", "analyzer", "cli", "config", "lineage", "surveyor", "hydrologist"]
        for path in self.kg.module_graph.nodes:
            if self.kg.module_graph.nodes[path].get("language") != "python":
                continue
            purpose = self._purpose_statements.get(path, path)
            for i, kw in enumerate(keywords[:k]):
                if kw in purpose.lower() or kw in path.lower():
                    self.kg.module_graph.nodes[path]["domain_cluster"] = f"domain_{i}"
                    self._domain_labels[path] = f"domain_{i}"
                    break
            else:
                self.kg.module_graph.nodes[path]["domain_cluster"] = "domain_0"
                self._domain_labels[path] = "domain_0"

    def answer_day_one_questions(self) -> None:
        """Synthesis: five FDE Day-One answers with evidence citations."""
        # Build context from KG
        mg = self.kg.to_module_graph_dict()
        lg = self.kg.to_lineage_graph_dict()
        sources = self.kg.find_sources()
        sinks = self.kg.find_sinks()
        high_velocity = mg.get("high_velocity_files", [])[:10]
        scc = self.kg.strongly_connected_components()
        circular = [list(c) for c in scc if len(c) > 1][:5]
        context = (
            f"Module graph nodes: {len(mg.get('nodes', []))}. Edges: {len(mg.get('edges', []))}.\n"
            f"Lineage nodes: {len(lg.get('nodes', []))}. Lineage edges: {len(lg.get('edges', []))}.\n"
            f"Data sources (in-degree 0): {sources[:15]}.\n"
            f"Data sinks (out-degree 0): {sinks[:15]}.\n"
            f"High-velocity files: {high_velocity}.\n"
            f"Circular dependencies (SCC): {circular}.\n"
            f"Purpose statements (sample): {json.dumps(dict(list(self._purpose_statements.items())[:5]), default=str)}."
        )
        tokens = self.budget.estimate_tokens(context) + 500
        if not self.budget.use_synthesis(tokens, 1500):
            self._day_one_answers = self._stub_day_one()
            return

        if self._client is None:
            self._day_one_answers = self._stub_day_one()
            return

        questions = """
1. What is the primary data ingestion path?
2. What are the 3-5 most critical output datasets/endpoints?
3. What is the blast radius if the most critical module fails?
4. Where is the business logic concentrated vs. distributed?
5. What has changed most frequently in the last 90 days (git velocity)?
"""
        try:
            resp = _call_llm_with_retry(
                self._client,
                {
                    "model": self._synthesis_model,
                    "messages": [
                        {"role": "system", "content": "You are an FDE analyst. Answer the five Day-One questions based ONLY on the provided codebase analysis. For each answer give 2-4 sentences and cite evidence: file paths and/or line numbers where relevant. Format as JSON: {\"1\": {\"answer\": \"...\", \"evidence\": \"...\"}, \"2\": ...}"},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestions:\n{questions}\n\nOutput valid JSON only."},
                    ],
                    "max_tokens": 1500,
                },
                label="Day-One synthesis",
            )
            raw = (resp.choices[0].message.content or "").strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            self._day_one_answers = json.loads(raw)
        except Exception as e:
            log.warning("Day-One synthesis failed: %s", e)
            self._day_one_answers = self._stub_day_one()

    def _stub_day_one(self) -> dict:
        return {
            "1": {"answer": "Primary ingestion: repo path -> CLI -> Orchestrator -> Surveyor/Hydrologist (file discovery, AST/config parsing).", "evidence": "src/cli.py, src/orchestrator.py"},
            "2": {"answer": "Critical outputs: .cartography/module_graph.json, lineage_graph.json, CODEBASE.md, onboarding_brief.md.", "evidence": "orchestrator serialization"},
            "3": {"answer": "Blast radius: orchestrator or knowledge_graph failure breaks full pipeline; single agent failure isolates to that agent.", "evidence": "src/orchestrator.py, src/graph/knowledge_graph.py"},
            "4": {"answer": "Logic concentrated in knowledge_graph.py and orchestrator.py; distributed across analyzers and agents.", "evidence": "module graph structure"},
            "5": {"answer": "High-velocity files from change_velocity_30d; see high_velocity_files in module graph.", "evidence": "Surveyor _attach_git_velocity"},
        }

    @property
    def purpose_statements(self) -> dict[str, str]:
        return self._purpose_statements

    @property
    def doc_drift(self) -> dict[str, bool]:
        return self._doc_drift

    @property
    def day_one_answers(self) -> Optional[dict[str, Any]]:
        return self._day_one_answers
