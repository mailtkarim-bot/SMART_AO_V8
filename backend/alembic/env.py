from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from app.modules.case.infrastructure.models import case  # noqa: F401
from app.modules.dce.infrastructure.models import (  # noqa: F401
    case_dce_impact,
    consultation,
    dce_classification,
    dce_extraction,
    dce_rc_analysis,
    dce_requirement_confirmations,
    dce_requirements,
    dce_staging,
    dce_version,
)
from app.modules.decision.infrastructure.models import (  # noqa: F401
    decision,
    risk,
    risk_requirement,
)
from app.modules.knowledge.infrastructure import models as knowledge_models  # noqa: F401
from app.modules.opportunity.infrastructure import models as opportunity_models  # noqa: F401
from app.modules.opportunity.infrastructure import (
    observation_models as opportunity_observation_models,  # noqa: F401
)
from app.modules.optimization.infrastructure import models as optimization_models  # noqa: F401
from app.modules.patron_action.infrastructure.models import patron_action  # noqa: F401
from app.modules.preparation.infrastructure.models import preparation  # noqa: F401
from app.modules.pricing.infrastructure.models import financial  # noqa: F401
from app.modules.submission.infrastructure.models import submission  # noqa: F401
from app.platform.persistence import models  # noqa: F401
from app.platform.persistence.alembic_runtime import resolve_database_url
from app.platform.persistence.base import Base
from app.platform.security import models as security_models  # noqa: F401
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    return resolve_database_url(config.get_main_option("sqlalchemy.url"))


def _database_config() -> dict[str, str]:
    section = dict(config.get_section(config.config_ini_section) or {})
    section["sqlalchemy.url"] = _database_url()
    return section


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        _database_config(),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
