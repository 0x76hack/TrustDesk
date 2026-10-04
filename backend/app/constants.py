import enum


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    TRIAGED = "triaged"
    AUTOMATED = "automated"
    ASSISTED = "assisted"
    WORKING = "working"
    ESCALATED = "escalated"
    DRAFT_READY = "draft_ready"
    ACTION_PROPOSED = "action_proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED_EXECUTED = "approved_executed"
    REJECTED = "rejected"
    RESOLVED = "resolved"
    CLOSED = "closed"

    @classmethod
    def all_values(cls) -> set[str]:
        return {item.value for item in cls}


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    @classmethod
    def all_values(cls) -> set[str]:
        return {item.value for item in cls}


class TicketCategory(str, enum.Enum):
    SHIPPING = "shipping"
    REFUND = "refund"
    WARRANTY = "warranty"
    BILLING = "billing"
    ACCOUNT_SECURITY = "account_security"
    GENERAL = "general"

    @classmethod
    def all_values(cls) -> set[str]:
        return {item.value for item in cls}


class UserRole(str, enum.Enum):
    AGENT = "agent"
    SENIOR_AGENT = "senior_agent"
    ADMIN = "admin"

    @classmethod
    def all_values(cls) -> set[str]:
        return {item.value for item in cls}


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def all_values(cls) -> set[str]:
        return {item.value for item in cls}


KB_CHUNK_WORD_SIZE: int = 300
KB_CHUNK_OVERLAP: int = 50
RETRIEVAL_MAX_CHARS: int = 8000
DRAFT_POLL_ATTEMPTS: int = 15
DRAFT_POLL_INTERVAL_S: float = 0.3
DEFAULT_PAGE_LIMIT: int = 50
MAX_PAGE_LIMIT: int = 100
PASSWORD_MIN_LENGTH: int = 8
LOGIN_RATE_LIMIT_PER_MINUTE: int = 5
OTP_EXPIRY_SECONDS: int = 120
