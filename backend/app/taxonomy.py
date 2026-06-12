"""Canonical skill vocabulary + synonym/alias map.

Why this exists (from the research): Taleo/iCIMS do EXACT-string matching ("JS" != "JavaScript"),
while Workday/Greenhouse do semantic matching. To score honestly we canonicalize both the JD and the
resume to the same keys, but we ALSO keep the JD's exact surface form so the renderer can use the
literal string the JD used (which matters for the strict parsers)."""
from __future__ import annotations
import re

# canonical_key -> list of aliases (all lowercase). The canonical key is also a valid alias.
ALIASES = {
    "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript", "ts"],
    "python": ["python"],
    "java": ["java"],
    "c++": ["c++", "cpp"],
    "c#": ["c#", "c sharp", "csharp", ".net", "dotnet"],
    "go": ["go", "golang"],
    "rust": ["rust"],
    "sql": ["sql"],
    "kotlin": ["kotlin"], "swift": ["swift"], "scala": ["scala"], "ruby": ["ruby"], "php": ["php"],
    "react": ["react", "react.js", "reactjs"],
    "node.js": ["node.js", "node", "nodejs"],
    "spring boot": ["spring boot", "springboot", "spring"],
    "django": ["django"], "flask": ["flask"], "fastapi": ["fastapi"],
    "express": ["express", "express.js"],
    "graphql": ["graphql"], "grpc": ["grpc"], "rest": ["rest", "rest api", "rest apis", "restful"],
    "kafka": ["kafka", "apache kafka"], "rabbitmq": ["rabbitmq"], "spark": ["spark", "apache spark"],
    "airflow": ["airflow", "apache airflow"], "hadoop": ["hadoop"],
    "microservices": ["microservices", "microservice"],
    "aws": ["aws", "amazon web services"], "gcp": ["gcp", "google cloud"], "azure": ["azure"],
    "kubernetes": ["kubernetes", "k8s"], "docker": ["docker"], "terraform": ["terraform"],
    "helm": ["helm"], "linux": ["linux"], "ci/cd": ["ci/cd", "cicd", "ci cd", "continuous integration"],
    "jenkins": ["jenkins"], "gitlab": ["gitlab", "gitlab ci"], "github actions": ["github actions"],
    "postgresql": ["postgresql", "postgres"], "mysql": ["mysql"], "redis": ["redis"],
    "mongodb": ["mongodb", "mongo"], "dynamodb": ["dynamodb"], "cassandra": ["cassandra"],
    "elasticsearch": ["elasticsearch", "elastic search"], "snowflake": ["snowflake"],
    "prometheus": ["prometheus"], "grafana": ["grafana"], "opentelemetry": ["opentelemetry", "otel"],
    "datadog": ["datadog"], "kibana": ["kibana"],
    "machine learning": ["machine learning", "ml"], "deep learning": ["deep learning"],
    "pytorch": ["pytorch"], "tensorflow": ["tensorflow"], "scikit-learn": ["scikit-learn", "sklearn"],
    "pandas": ["pandas"], "numpy": ["numpy"], "nlp": ["nlp", "natural language processing"],
    "llm": ["llm", "large language model", "large language models"], "rag": ["rag"],
    "xgboost": ["xgboost"], "bert": ["bert"], "langchain": ["langchain"], "langgraph": ["langgraph"],
    "git": ["git"], "graphql": ["graphql"], "websocket": ["websocket", "websockets"],
    "distributed systems": ["distributed systems", "distributed system"],
    "data structures": ["data structures", "data structures and algorithms", "dsa", "algorithms"],
}

# build reverse lookup: alias -> canonical
_ALIAS_TO_CANON = {}
for canon, al in ALIASES.items():
    for a in al:
        _ALIAS_TO_CANON[a] = canon

# concept/process words that are NOT hard skills (never count as skills-section items)
NON_SKILL_CONCEPTS = {
    "idempotency", "fault tolerance", "scalability", "code review", "on-call", "on call",
    "software architecture", "communication", "leadership", "teamwork", "agile", "scrum",
    "problem solving", "stakeholder management", "ownership", "collaboration",
}


def canon(term: str) -> str:
    """Map a surface term to its canonical key (or a cleaned lowercase form if unknown)."""
    t = re.sub(r"\s+", " ", (term or "").strip().lower())
    return _ALIAS_TO_CANON.get(t, t)


def term_present(term: str, text_low: str) -> bool:
    """Tolerant presence check for a term (or any of its aliases) in lowercased text.
    Word-bounded on alphanumeric edges so 'go' won't match 'good'; spaces flexible."""
    c = canon(term)
    candidates = ALIASES.get(c, [c])
    for cand in candidates:
        esc = re.escape(cand).replace(r"\ ", r"\s*")
        pat = (r"\b" if cand[:1].isalnum() else "") + esc + (r"\b" if cand[-1:].isalnum() else "")
        try:
            if re.search(pat, text_low):
                return True
        except re.error:
            if cand in text_low:
                return True
    return False


# ── Skill families (for TRUTHFUL adjacency) ───────────────────────────────────
# Key = honest umbrella label; value = canonical members. Used to surface the umbrella
# skill the candidate genuinely holds when a JD asks for a sibling — NEVER to claim the
# sibling tool itself. (Per research: present "relational databases (PostgreSQL)", not "MySQL".)
SKILL_FAMILIES = {
    "relational databases": ["postgresql", "mysql", "oracle", "sql server", "sqlite", "mariadb", "sql"],
    "nosql / key-value stores": ["redis", "dynamodb", "cassandra", "mongodb", "memcached"],
    "cloud platforms": ["aws", "gcp", "azure"],
    "message queues / streaming": ["kafka", "rabbitmq", "sqs", "sns", "kinesis", "pub/sub", "activemq"],
    "container orchestration": ["kubernetes", "ecs", "nomad", "openshift", "docker"],
    "ci/cd pipelines": ["jenkins", "gitlab", "github actions", "circleci", "travis", "ci/cd"],
    "frontend frameworks": ["react", "angular", "vue", "svelte"],
    "observability": ["prometheus", "grafana", "opentelemetry", "datadog", "kibana"],
}


def adjacent_held(jd_skill: str, resume_low: str):
    """If the JD wants `jd_skill` which the resume does NOT contain, but the resume DOES contain a
    same-family sibling, return (umbrella_label, held_sibling_canonical). Else None.
    This is the honest basis for surfacing 'relational databases (PostgreSQL)' when a JD asks MySQL."""
    if term_present(jd_skill, resume_low):
        return None
    target = canon(jd_skill)
    for label, members in SKILL_FAMILIES.items():
        if target in members:
            for held in members:
                if held != target and term_present(held, resume_low):
                    return (label, held)
    return None
