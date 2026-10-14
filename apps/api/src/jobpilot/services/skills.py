"""Skill name normalisation shared by extraction and matching."""

import re

# Lowercase variant -> canonical lowercase key.
ALIASES = {
    "postgres": "postgresql", "psql": "postgresql",
    "js": "javascript", "ecmascript": "javascript",
    "ts": "typescript",
    "golang": "go",
    "k8s": "kubernetes",
    "node": "node.js", "nodejs": "node.js",
    "reactjs": "react", "react.js": "react",
    "nextjs": "next.js", "vuejs": "vue", "vue.js": "vue",
    "amazon web services": "aws", "google cloud": "gcp", "google cloud platform": "gcp",
    "microsoft azure": "azure",
    "ml": "machine learning",
    "sklearn": "scikit-learn",
    "ci/cd": "ci/cd", "cicd": "ci/cd", "continuous integration": "ci/cd",
    "restful": "rest", "rest api": "rest", "rest apis": "rest",
    "dotnet": ".net",
    "ms excel": "excel", "microsoft excel": "excel",
}


def skill_key(name: str) -> str:
    """Comparable key for a skill name: lowercase, single spaces, aliases resolved."""
    key = re.sub(r"\s+", " ", name.strip().lower())
    return ALIASES.get(key, key)


def dedupe_skills(names: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for name in names:
        key = skill_key(name)
        if key and key not in seen:
            seen.add(key)
            result.append(name.strip())
    return result
