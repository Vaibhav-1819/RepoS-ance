"""
Secret redaction and sensitive file exclusion for RepoSéance.
Ensures private keys, tokens, and credentials never enter indexing or prompts.
"""

import re
from typing import Tuple, List

SECRET_PATTERNS = [
    # AWS Access Key
    (r"(?i)AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]"),
    # Generic API Keys and Bearer Tokens
    (r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]{20,})", "Bearer [REDACTED_TOKEN]"),
    (r"(?i)(api[_\-]?key\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-]{16,})(['\"]?)", r"\1[REDACTED_API_KEY]\3"),
    # OpenAI and Anthropic Keys
    (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_AI_KEY]"),
    (r"sk-ant-[a-zA-Z0-9\-]{20,}", "[REDACTED_AI_KEY]"),
    # GitHub Personal Access Tokens
    (r"gh[pousr]_[a-zA-Z0-9]{36,}", "[REDACTED_GITHUB_TOKEN]"),
    # Database Connection Strings with Passwords
    (r"(postgres(?:ql)?|mysql|mongodb(?:\+srv)?):\/\/[^:\/\s]+:([^@\/\s]+)@", r"\1://user:[REDACTED_PWD]@"),
    # Private Key Headers
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
]

EXCLUDED_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.stage",
    "id_rsa", "id_ed25519", "id_dsa",
    "credentials.json", "service-account.json", "secrets.yaml", "secrets.json",
    ".git", ".svn", ".hg"
}

EXCLUDED_EXTENSIONS = {
    ".pem", ".key", ".p12", ".pfx", ".cert", ".crt",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pyc", ".pyo", ".class", ".o"
}

EXCLUDED_DIRECTORIES = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    "target", "dist", "build", ".next", ".nuxt", "vendor", ".idea", ".vscode"
}


def mask_secrets(text: str) -> str:
    """Replaces recognizable credentials, keys, and tokens with safe redactions."""
    if not text:
        return ""
    masked = text
    for pattern, replacement in SECRET_PATTERNS:
        masked = re.sub(pattern, replacement, masked)
    return masked


def is_sensitive_file(filename: str) -> bool:
    """Checks whether a file should be completely omitted from AI indexing for privacy."""
    name_lower = filename.lower()
    if name_lower in EXCLUDED_FILENAMES:
        return True
    for ext in EXCLUDED_EXTENSIONS:
        if name_lower.endswith(ext):
            return True
    return False
