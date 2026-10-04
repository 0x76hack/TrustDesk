import re
from typing import Dict, Any, List
import urllib.parse

DELIMITER_PATTERNS = [
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"---+\s*(BEGIN|START)\s*(SYSTEM|DIRECTIVE|INSTRUCTION|OVERRIDE)",
    r"===+\s*(BEGIN|START|OVERRIDE)",
    r"```+\s*(system|instruction|override)",
]

INJECTION_REGEXES = [
    r"ignore\s+(all\s+)?(previous|prior|above|existing)\s+(instructions?|prompts?|directives?|rules?|constraints?)",
    r"disregard\s+(all\s+)?(previous|prior|above|existing)\s+(instructions?|prompts?|directives?|rules?)",
    r"forget\s+(all\s+)?(previous|prior|above|existing)\s+(instructions?|prompts?|directives?|rules?)",
    r"reset\s+(all\s+)?(system\s+)?(instructions?|state|prompts?|rules?)",
    r"you\s+are\s+now\s+(in\s+)?(developer\s+mode|dan|unrestricted|god\s+mode|jailbroken|unfiltered|maintenance\s+mode)",
    r"assume\s+(the\s+)?(role|identity)\s+of\s+(an?\s+)?(unrestricted|jailbroken|developer|evil|superadmin)",
    r"(system|command|security|policy|operational)\s+override",
    r"new\s+system\s+(directive|instruction|prompt)",
    r"act\s+as\s+(an?\s+)?(unrestricted|dan|jailbroken|developer|evil|uncensored)",
    r"in\s+an?\s+(academic|fictional|hypothetical|research)\s+(scenario|context|paper|exercise).*?(print|show|output|reveal|ignore|bypass)",
]

OBFUSCATED_PATTERNS = [
    r"i\s*g\s*n\s*o\s*r\s*e\s+p\s*r\s*e\s*v\s*i\s*o\s*u\s*s",
    r"d\s*i\s*s\s*r\s*e\s*g\s*a\s*r\s*d\s+a\s*l\s*l",
    r"s\s*y\s*s\s*t\s*e\s*m\s+p\s*r\s*o\s*m\s*p\s*t",
    r"j\s*a\s*i\s*l\s*b\s*r\s*e\s*a\s*k",
]

BYPASS_PATTERNS = [
    r"i\s+am\s+(the\s+|an?\s+)?([a-zA-Z\s]{0,25})?(admin|administrator|manager|developer|system\s+operator|ceo|security\s+auditor)",
    r"i('?m| am)\s+the\s+([a-zA-Z\s]{0,25})?(manager|admin|creator|boss|ceo)",
    r"override\s+(all\s+)?(security\s+|operational\s+)?polic(y|ies)",
    r"bypass\s+(all\s+)?(security|authentication|approval|policy)",
    r"grant\s+(me\s+)?([0-9]+\s+)?([a-zA-Z\s]{0,15})?(refund|admin|access|balance|credits?|promo)",
    r"without\s+(requiring\s+)?(any\s+)?approval",
    r"KB-ADVERSARIAL-[0-9]+",
]

SECRET_PATTERNS = [
    r"(print|reveal|output|show|display|dump|leak|tell\s+me)\s+(your\s+)?(system\s+prompt|initial\s+prompt|hidden\s+prompt|system\s+instructions?|developer\s+instructions?|api\s*key|environment|configuration|rules|passwords?)",
    r"what\s+(is|are)\s+your\s+(exact\s+)?(system\s+prompt|initial\s+instructions?|system\s+instructions?)",
    r"repeat\s+(everything|the\s+words)\s+above",
    r"output\s+everything\s+between\s+<system>\s+and",
]

TOOL_EXEC_PATTERNS = [
    r"<\s*tool_call\s*>",
    r"\{\s*[\"'](tool|function|tool_call|action)[\"']\s*:\s*[\"'][a-zA-Z0-9_]+[\"']",
    r"\b(eval|exec|os\.system|subprocess\.Popen)\s*\(",
    r";\s*(drop\s+table|grant\s+role|alter\s+user)",
]

EXFIL_PATTERNS = [
    r"!\[.*?\]\s*\(\s*https?://",
    r"<\s*img\s+[^>]*src\s*=\s*['\"]?https?://",
]


def fence_input(text: str) -> Dict[str, Any]:
    if not text:
        return {"is_safe": True, "threat_type": None, "details": None, "risk_level": "low"}

    cleaned = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]", "", text)
    unquoted = urllib.parse.unquote(cleaned)
    normalized_variants = [cleaned, unquoted, cleaned.lower(), unquoted.lower()]

    for variant in normalized_variants:
        for p in DELIMITER_PATTERNS:
            if re.search(p, variant, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "threat_type": "delimiter_breakout",
                    "details": "Protocol delimiter hijacking detected",
                    "risk_level": "critical",
                }

    for variant in normalized_variants:
        for p in INJECTION_REGEXES:
            if re.search(p, variant, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "threat_type": "prompt_injection",
                    "details": "Adversarial prompt injection pattern detected",
                    "risk_level": "critical",
                }

    collapsed = re.sub(r'[^a-zA-Z0-9]', '', cleaned.lower())
    collapsed_triggers = [
        "ignoreprevious",
        "ignoreallprevious",
        "disregardall",
        "systemprompt",
        "systemoverride",
        "jailbreak",
        "danmode",
        "developermode",
    ]
    for trigger in collapsed_triggers:
        if trigger in collapsed:
            return {
                "is_safe": False,
                "threat_type": "obfuscated_injection",
                "details": f"Obfuscated sequence '{trigger}' detected",
                "risk_level": "critical",
            }

    for variant in normalized_variants:
        for p in OBFUSCATED_PATTERNS:
            if re.search(p, variant, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "threat_type": "obfuscated_injection",
                    "details": "Obfuscated adversarial sequence detected",
                    "risk_level": "critical",
                }

    for variant in normalized_variants:
        for p in BYPASS_PATTERNS:
            if re.search(p, variant, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "threat_type": "identity_bypass",
                    "details": "Privilege usurpation or identity bypass detected",
                    "risk_level": "critical",
                }

    for variant in normalized_variants:
        for p in SECRET_PATTERNS:
            if re.search(p, variant, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "threat_type": "secret_disclosure",
                    "details": "Attempt to exfiltrate system prompt or secrets",
                    "risk_level": "critical",
                }

    for variant in normalized_variants:
        for p in TOOL_EXEC_PATTERNS:
            if re.search(p, variant, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "threat_type": "tool_hijack",
                    "details": "Unauthorized tool invocation or code injection syntax detected",
                    "risk_level": "critical",
                }

    for variant in normalized_variants:
        for p in EXFIL_PATTERNS:
            if re.search(p, variant, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "threat_type": "data_exfiltration_probe",
                    "details": "Out-of-band data exfiltration channel detected",
                    "risk_level": "critical",
                }

    return {
        "is_safe": True,
        "threat_type": None,
        "details": None,
        "risk_level": "low",
    }


def scrub_pii(text: str) -> str:
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', text)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
    return text


SENSITIVE_OUTPUT_PATTERNS = [
    (r"sk-[a-zA-Z0-9_\-]{20,}", "API Key Leak"),
    (r"Bearer\s+[a-zA-Z0-9_\-\.]{25,}", "Bearer Token Leak"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key Leak"),
    (r"postgresql(\+asyncpg)?://[^\s]+", "Database Connection String Leak"),
    (r"redis://[^\s]+", "Redis Connection String Leak"),
    (r"trustdesk_secret", "Database Password Leak"),
    (r"\$2[abxy]\$\d+\$[./A-Za-z0-9]{53}", "Bcrypt Password Hash Leak"),
    (r"You are TrustDesk's AI Customer Operations Specialist", "System Prompt Instructions Leak"),
    (r"Strict Refund Isolation: NEVER bring up", "Internal Operational Rule Leak"),
]


def validate_output(text: str) -> Dict[str, Any]:
    issues: List[str] = []
    is_safe = True

    for pattern, description in SENSITIVE_OUTPUT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append(description)
            is_safe = False

    return {
        "is_safe": is_safe,
        "issues": issues,
        "risk_level": "critical" if not is_safe else "low",
    }


def check_adversarial_document(doc_id: str, is_adversarial: bool) -> Dict[str, Any]:
    return {
        "is_safe": not is_adversarial,
        "issues": ["Adversarial document detected"] if is_adversarial else [],
        "risk_level": "critical" if is_adversarial else "low",
    }
