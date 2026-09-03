"""
Approval system for RANN Agent.
As required by MASTER PROMPT Section 20.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import uuid
import structlog

logger = structlog.get_logger()


class ApprovalType(Enum):
    PRODUCTION_DEPLOYMENT = "production_deployment"
    DESTRUCTIVE = "destructive"
    CREDENTIALS = "credentials"
    PRIVILEGE = "privilege"
    PROTECTED_BRANCH = "protected_branch"
    EXTERNAL_FINANCIAL = "external_financial"
    SECURITY_POLICY = "security_policy"
    LARGE_DELETION = "large_deletion"


@dataclass
class ApprovalRequest:
    request_id: str
    approval_type: ApprovalType
    description: str
    requested_by: str
    timestamp: str
    status: str  # pending, approved, rejected
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApprovalSystem:
    """Manages approval requests for dangerous operations."""

    def __init__(self, storage: Optional["Database"] = None) -> None:
        self.storage = storage
        self._pending: Dict[str, ApprovalRequest] = {}

    def request(
        self,
        approval_type: ApprovalType,
        description: str,
        requested_by: str = "agent",
    ) -> str:
        """Submit an approval request."""
        request_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        req = ApprovalRequest(
            request_id=request_id,
            approval_type=approval_type,
            description=description,
            requested_by=requested_by,
            timestamp=now,
            status="pending",
        )

        self._pending[request_id] = req

        if self.storage:
            self.storage.save_approval_request(
                request_id,
                {
                    "approval_type": approval_type.value,
                    "description": description,
                    "requested_by": requested_by,
                    "timestamp": now,
                    "status": "pending",
                },
            )

        logger.info(
            "approval_requested",
            request_id=request_id,
            type=approval_type.value,
        )
        return request_id

    def approve(self, request_id: str, reviewed_by: str = "user") -> bool:
        """Approve a pending request."""
        if request_id not in self._pending:
            if self.storage:
                stored = self.storage.get_approval_request(request_id)
                if stored and stored["status"] == "approved":
                    return True
            return False

        req = self._pending[request_id]
        req.status = "approved"
        req.reviewed_by = reviewed_by
        req.reviewed_at = datetime.now().isoformat()

        if self.storage:
            self.storage.update_approval_status(request_id, "approved", reviewed_by)

        logger.info("approval_approved", request_id=request_id, by=reviewed_by)
        return True

    def reject(self, request_id: str, reason: str, reviewed_by: str = "user") -> bool:
        """Reject a pending request."""
        if request_id not in self._pending:
            return False

        req = self._pending[request_id]
        req.status = "rejected"
        req.reviewed_by = reviewed_by
        req.reviewed_at = datetime.now().isoformat()
        req.rejection_reason = reason

        if self.storage:
            self.storage.update_approval_status(
                request_id, "rejected", reviewed_by, reason
            )

        logger.info("approval_rejected", request_id=request_id, by=reviewed_by, reason=reason)
        return True

    def requires_approval(self, action: str) -> bool:
        """Check if an action requires approval before execution."""
        approval_required = {
            "deploy": ApprovalType.PRODUCTION_DEPLOYMENT,
            "delete": ApprovalType.DESTRUCTIVE,
            "rm": ApprovalType.DESTRUCTIVE,
            "sudo": ApprovalType.PRIVILEGE,
            "chmod": ApprovalType.DESTRUCTIVE,
            "chown": ApprovalType.DESTRUCTIVE,
            "kubectl": ApprovalType.PRODUCTION_DEPLOYMENT,
            "docker_push": ApprovalType.PRODUCTION_DEPLOYMENT,
            "terraform_destroy": ApprovalType.PRODUCTION_DEPLOYMENT,
        }
        return action.lower() in approval_required

    def get_pending(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        pending = list(self._pending.values())
        if self.storage:
            stored = self.storage.list_pending_approvals()
            for s in stored:
                req_id = s["request_id"]
                if req_id not in self._pending:
                    self._pending[req_id] = ApprovalRequest(
                        request_id=req_id,
                        approval_type=ApprovalType(s["approval_type"]),
                        description=s["description"],
                        requested_by=s.get("requested_by", ""),
                        timestamp=s["timestamp"],
                        status=s["status"],
                    )
            pending = [r for r in self._pending.values() if r.status == "pending"]
        return pending