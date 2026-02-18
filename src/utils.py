import hmac
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature:
        return False
    
    if signature.startswith("sha256="):
        signature = signature[7:]
    
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


def parse_repo_name(full_name: str) -> str:
    return full_name.split("/")[-1] if "/" in full_name else full_name


def should_notify_branch(branch_filter: Optional[str], branch: str) -> bool:
    if not branch_filter:
        return True
    
    filters = [f.strip() for f in branch_filter.split(",")]
    return branch in filters or "*" in filters


def should_notify_label(label_filter: Optional[str], labels: list) -> bool:
    if not label_filter:
        return True
    
    if not labels:
        return False
    
    filter_labels = [f.strip() for f in label_filter.split(",")]
    label_names = [label.get("name", "") if isinstance(label, dict) else str(label) for label in labels]
    
    return any(label in filter_labels for label in label_names) or "*" in filter_labels


def should_notify_author(author_filter: Optional[str], author: str) -> bool:
    if not author_filter:
        return True
    
    filters = [f.strip() for f in author_filter.split(",")]
    return author in filters or "*" in filters
