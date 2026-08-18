from dataclasses import replace
from io import BytesIO
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_pricing_import import build_patron_pricing_import_router
from app.modules.pricing.application.import_preview import PricingImportPreviewService
from app.platform.security.authorization import AuthorizationDecision, AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorKind
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from tests.application.test_financial_report_draft_lines import _seed_draft


class _DenyPolicy:
    def authorize(self, *, context, request):
        return AuthorizationDecision.denied(reason="test")


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_pricing_import_preview_parses_dpgf_rows_without_persisting_raw_file(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    payload = _xlsx(
        [
            ["Code", "Désignation", "Unité", "Quantité", "Prix unitaire", "Colonne ignorée"],
            ["A-01", "Terrassement", "m2", 10, 12.5],
            ["A-02", "Fondations", "m3", 2, 100],
        ]
    )
    preview = PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
        actor=actor,
        case_id=case_id,
        document_kind="DPGF",
        filename="bordereau.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        payload=payload,
    )
    assert preview.row_count == 2
    assert preview.valid_row_count == 2
    assert preview.error_count == 0
    assert preview.total_minor == 32_500
    assert preview.rows[0].total_minor == 12_500


def test_pricing_import_preview_reports_missing_designation_and_refuses_non_xlsx(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    payload = _xlsx([["Code", "Quantité", "Prix unitaire"], ["A-01", 1, 10]])
    with pytest.raises(ValueError, match="IMPORT_DESIGNATION_COLUMN_REQUIRED"):
        PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
            actor=actor,
            case_id=case_id,
            document_kind="BPU",
            filename="bordereau.xlsx",
            content_type=None,
            payload=payload,
        )
    with pytest.raises(ValueError, match="IMPORT_XLSX_REQUIRED"):
        PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsm",
            content_type=None,
            payload=payload,
        )


def test_pricing_import_preview_refuses_policy_denied_patron(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    with pytest.raises(PermissionError, match="AUTHORIZATION_DENIED"):
        PricingImportPreviewService(policy=_DenyPolicy()).preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type=None,
            payload=b"not-read",
        )


def test_pricing_import_preview_refuses_collaborator_before_reading_financial_rows(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    collaborator = replace(
        actor,
        actor_id=uuid4(),
        identity_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=capabilities_for(ActorKind.COLLABORATEUR),
    )
    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
            actor=collaborator,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type=None,
            payload=b"not-read",
        )


def test_pricing_import_preview_rejects_size_and_content_type_before_parsing(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    service = PricingImportPreviewService(policy=AuthorizationPolicy())
    with pytest.raises(ValueError, match="IMPORT_FILE_TOO_LARGE"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type=None,
            payload=b"x" * (10 * 1024 * 1024 + 1),
        )
    with pytest.raises(ValueError, match="IMPORT_CONTENT_TYPE_REJECTED"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type="text/plain",
            payload=b"x",
        )


def test_pricing_import_preview_rejects_invalid_empty_and_macro_workbooks(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    service = PricingImportPreviewService(policy=AuthorizationPolicy())
    with pytest.raises(ValueError, match="IMPORT_WORKBOOK_INVALID"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type=None,
            payload=b"not-an-xlsx",
        )
    empty_payload = _xlsx([])
    with pytest.raises(ValueError, match="IMPORT_EMPTY_WORKBOOK"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="empty.xlsx",
            content_type=None,
            payload=empty_payload,
        )
    import zipfile

    macro_payload = BytesIO()
    with zipfile.ZipFile(macro_payload, "w") as archive:
        archive.writestr("xl/vbaProject.bin", b"macro")
    with pytest.raises(ValueError, match="IMPORT_MACROS_REJECTED"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="macro.xlsx",
            content_type=None,
            payload=macro_payload.getvalue(),
        )


def test_pricing_import_preview_reports_invalid_row_values(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    preview = PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
        actor=actor,
        case_id=case_id,
        document_kind="BPU",
        filename="bordereau.xlsx",
        content_type=None,
        payload=_xlsx(
            [
                ["Désignation", "Quantité", "Prix unitaire"],
                ["Ligne invalide", "abc", None],
                ["Ligne négative", -2, -10],
            ]
        ),
    )
    assert preview.valid_row_count == 0
    assert preview.error_count >= 3
    assert {"QUANTITY_INVALID", "PRICE_REQUIRED"}.issubset(preview.rows[0].errors)


def test_pricing_import_preview_bounds_error_collection_and_bad_numbers(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    preview = PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
        actor=actor,
        case_id=case_id,
        document_kind="DPGF",
        filename="large-invalid.xlsx",
        content_type=None,
        payload=_xlsx(
            [["Désignation", "Quantité", "Prix unitaire"]]
            + [[" ", "not-a-number", "not-a-price"] for _ in range(50)]
        ),
    )
    assert preview.error_count == 102
    assert preview.valid_row_count == 0
    assert preview.row_count == 34


def test_pricing_import_preview_ignores_blank_rows_and_defaults_quantity(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    preview = PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
        actor=actor,
        case_id=case_id,
        document_kind="BPU",
        filename="defaults.xlsx",
        content_type=None,
        payload=_xlsx(
            [
                ["Désignation", "Quantité", "Prix unitaire"],
                [None, None, None],
                ["Sans quantité", None, 5],
            ]
        ),
    )
    assert preview.row_count == 1
    assert preview.rows[0].quantity_decimal == "1"
    assert preview.rows[0].total_minor == 500


def test_pricing_import_preview_http_contract(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)

    class _Resolver:
        def resolve(self, *, access_token):
            assert access_token == "test-token"
            return actor

    app = FastAPI()
    app.include_router(
        build_patron_pricing_import_router(
            service=PricingImportPreviewService(policy=AuthorizationPolicy()),
            security_runtime=ConsultationSecurityRuntime(
                context_resolver=_Resolver(), policy=AuthorizationPolicy()
            ),
        )
    )
    client = TestClient(app)
    payload = _xlsx(
        [["Désignation", "Quantité", "Prix unitaire"], ["Lot test", 2, 7.5]]
    )
    response = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview?document_kind=BPU",
        files={
            "upload": (
                "lot.xlsx",
                payload,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["valid_row_count"] == 1
    assert response.json()["rows"][0]["total_minor"] == 1500
    unauthenticated = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview",
        files={"upload": ("lot.xlsx", payload)},
    )
    assert unauthenticated.status_code == 401
    invalid = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview",
        files={"upload": ("broken.xlsx", b"broken")},
        headers={"Authorization": "Bearer test-token"},
    )
    assert invalid.status_code == 422

    denied_app = FastAPI()
    denied_app.include_router(
        build_patron_pricing_import_router(
            service=PricingImportPreviewService(policy=_DenyPolicy()),
            security_runtime=ConsultationSecurityRuntime(
                context_resolver=_Resolver(), policy=AuthorizationPolicy()
            ),
        )
    )
    denied = TestClient(denied_app).post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview",
        files={"upload": ("lot.xlsx", payload)},
        headers={"Authorization": "Bearer test-token"},
    )
    assert denied.status_code == 403


def test_pricing_import_preview_rejects_zip_bomb_metadata(session_factory, monkeypatch):
    actor, case_id, _, _ = _seed_draft(session_factory)

    class _HugeArchive:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def namelist(self):
            return []

        def infolist(self):
            return [type("Info", (), {"file_size": 50 * 1024 * 1024 + 1})()]

    monkeypatch.setattr(
        "app.modules.pricing.application.import_preview.ZipFile", _HugeArchive
    )
    with pytest.raises(ValueError, match="IMPORT_ARCHIVE_TOO_LARGE"):
        PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bomb.xlsx",
            content_type=None,
            payload=b"metadata-only",
        )
