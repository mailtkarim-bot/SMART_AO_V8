"""Add closed CCAP/CCTP contract-risk taxonomy signals.

Revision ID: 20260826_0066
Revises: 20260826_0065
Create Date: 2026-08-26
"""

from collections.abc import Sequence

from alembic import op

revision = "20260826_0066"
down_revision = "20260826_0065"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_OBSERVATION_KIND_CONSTRAINT = (
    "requirement_kind IN ("
    "'RC_DOCUMENT_CANDIDATURE', 'RC_CONTENT_OFFER', 'RC_SUBMISSION_DEADLINE', "
    "'RC_RESPONSE_CHANNEL', 'RC_FILE_CONSTRAINT', 'RC_SITE_VISIT', "
    "'RC_AWARD_CRITERION', 'RC_NEGOTIATION', 'RC_OFFER_VALIDITY', "
    "'CCAP_PENALTIES', 'CCAP_RETENTION_GUARANTEE', 'CCAP_GUARANTEE', "
    "'CCAP_INSURANCE', 'CCTP_VARIANTS', 'CCAP_SUBCONTRACTING', "
    "'CCAP_QUALIFICATIONS'"
    ")"
)
_REQUIREMENT_TYPE_CONSTRAINT = (
    "requirement_type IN ('CANDIDATURE_DOCUMENT', 'OFFER_DOCUMENT', "
    "'SUBMISSION_DEADLINE_SIGNAL', 'SUBMISSION_CHANNEL', 'FILE_CONSTRAINT', "
    "'SITE_VISIT', 'AWARD_CRITERION_SIGNAL', 'NEGOTIATION_SIGNAL', "
    "'OFFER_VALIDITY_SIGNAL', 'CONTRACT_RISK_SIGNAL')"
)
_OLD_OBSERVATION_KIND_CONSTRAINT = (
    "requirement_kind IN ("
    "'RC_DOCUMENT_CANDIDATURE', 'RC_CONTENT_OFFER', 'RC_SUBMISSION_DEADLINE', "
    "'RC_RESPONSE_CHANNEL', 'RC_FILE_CONSTRAINT', 'RC_SITE_VISIT', "
    "'RC_AWARD_CRITERION', 'RC_NEGOTIATION', 'RC_OFFER_VALIDITY'"
    ")"
)
_OLD_REQUIREMENT_TYPE_CONSTRAINT = (
    "requirement_type IN ('CANDIDATURE_DOCUMENT', 'OFFER_DOCUMENT', "
    "'SUBMISSION_DEADLINE_SIGNAL', 'SUBMISSION_CHANNEL', 'FILE_CONSTRAINT', "
    "'SITE_VISIT', 'AWARD_CRITERION_SIGNAL', 'NEGOTIATION_SIGNAL', "
    "'OFFER_VALIDITY_SIGNAL')"
)


def upgrade() -> None:
    op.drop_constraint("requirement_kind", "dce_rc_requirement_observations", type_="check")
    op.create_check_constraint(
        "requirement_kind",
        "dce_rc_requirement_observations",
        _OBSERVATION_KIND_CONSTRAINT,
    )
    op.drop_constraint("requirement_type", "dce_requirements", type_="check")
    op.create_check_constraint(
        "requirement_type",
        "dce_requirements",
        _REQUIREMENT_TYPE_CONSTRAINT,
    )


def downgrade() -> None:
    op.drop_constraint("requirement_type", "dce_requirements", type_="check")
    op.create_check_constraint(
        "requirement_type",
        "dce_requirements",
        _OLD_REQUIREMENT_TYPE_CONSTRAINT,
    )
    op.drop_constraint("requirement_kind", "dce_rc_requirement_observations", type_="check")
    op.create_check_constraint(
        "requirement_kind",
        "dce_rc_requirement_observations",
        _OLD_OBSERVATION_KIND_CONSTRAINT,
    )
