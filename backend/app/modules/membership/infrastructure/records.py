"""Membership-owned ORM record boundary.

The physical declarations remain in the shared SQLAlchemy registry for now so
Alembic table identities and historical imports stay stable. Application and
membership infrastructure code must import assignment/task records from this
module; a later physical move can then be performed independently.
"""

from app.platform.security.models import (
    AssignmentClarificationRequestRecord,
    AssignmentInteractionPatronValidationRecord,
    CaseAssignmentAcknowledgementRecord,
    CaseAssignmentChangeEventRecord,
    CaseAssignmentRecord,
    CaseAssignmentUnavailabilityRecord,
    CollaboratorInformationRequestRecord,
    CollaboratorInformationResponseRecord,
    CollaboratorTaskBlockerRecord,
    CollaboratorTaskRecord,
    CollaboratorTaskResultRecord,
    TenantMembershipRecord,
)

__all__ = [
    "AssignmentClarificationRequestRecord",
    "AssignmentInteractionPatronValidationRecord",
    "CaseAssignmentAcknowledgementRecord",
    "CaseAssignmentChangeEventRecord",
    "CaseAssignmentRecord",
    "CaseAssignmentUnavailabilityRecord",
    "CollaboratorInformationRequestRecord",
    "CollaboratorInformationResponseRecord",
    "CollaboratorTaskBlockerRecord",
    "CollaboratorTaskRecord",
    "CollaboratorTaskResultRecord",
    "TenantMembershipRecord",
]
