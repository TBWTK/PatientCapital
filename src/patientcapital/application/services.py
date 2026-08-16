"""Transactional use cases; no transport owns portfolio logic."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, func, select, text
from sqlalchemy.orm import Session

from patientcapital.application.errors import ApplicationError
from patientcapital.contracts import (
    AnalyticsMoneyMetricResponse,
    AnalyticsOverviewResponse,
    AssetListResponse,
    AssetPut,
    AssetResponse,
    DiscoveryCandidateResponse,
    DiscoveryRecommendationCreate,
    DividendResearchResponse,
    MarketResearchStatusResponse,
    MarketSearchResponse,
    PortfolioAssetResponse,
    PortfolioResponse,
    PriceCreate,
    PriceFreshnessAssetResponse,
    PriceFreshnessResponse,
    PriceResponse,
    ProfilePut,
    ProfileResponse,
    ProposalSetCreate,
    ProposalSetResponse,
    RecommendationCreate,
    RecommendationLineResponse,
    RecommendationResponse,
    RejectedDiscoveryCandidateResponse,
    ResearchCitationResponse,
    StrategyProposalResponse,
    TransactionCreate,
    TransactionDraftDecisionCreate,
    TransactionDraftDecisionResponse,
    TransactionDraftFields,
    TransactionDraftManualCreate,
    TransactionDraftResponse,
    TransactionDraftTextCreate,
    TransactionResponse,
)
from patientcapital.domain.discovery import MarketSelection, select_market_candidates
from patientcapital.domain.models import (
    AllocationInput,
    Asset,
    FeePolicy,
    Position,
    PriceSnapshot,
    TargetAllocation,
)
from patientcapital.domain.money import Money, quantize_minor
from patientcapital.domain.planner import build_contribution_plan
from patientcapital.domain.strategies import StrategyDefinition, admitted_strategies
from patientcapital.domain.transaction_intake import (
    PARSER_VERSION,
    KnownAsset,
    ParsedTransaction,
    parse_transaction_text,
)
from patientcapital.market_intelligence.service import (
    AcquiredMarketResearch,
    acquire_market_research,
    latest_market_research,
    serialize_candidate,
)
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import MarketCandidate, MarketDataProvider
from patientcapital.persistence.models import (
    AssetIdentity,
    AssetVersion,
    PriceRecord,
    ProfileVersion,
    ProposalSetRecord,
    RecommendationRunRecord,
    TransactionDraftDecisionRecord,
    TransactionDraftRecord,
    TransactionRecord,
)
from patientcapital.transaction_intake.image import ImageTextExtractor

_PROFILE_LOCK = 7_421_001
_ASSET_LOCK = 7_421_002
_LEDGER_LOCK = 7_421_003


def _lock(session: Session, key: int) -> None:
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _profile_query() -> Select[tuple[ProfileVersion]]:
    return select(ProfileVersion).order_by(ProfileVersion.version.desc()).limit(1)


def _latest_profile_record(session: Session) -> ProfileVersion | None:
    return session.scalar(_profile_query())


def _profile_response(record: ProfileVersion) -> ProfileResponse:
    return ProfileResponse(
        version=record.version,
        base_currency=record.base_currency,
        investment_horizon_years=record.investment_horizon_years,
        risk_level=record.risk_level,
        cash_buffer=record.cash_buffer,
        broker_name=record.broker_name,
        fee_rate=record.fee_rate,
        minimum_fee=record.minimum_fee,
        created_at=record.created_at,
    )


def get_profile(session: Session) -> ProfileResponse:
    record = _latest_profile_record(session)
    if record is None:
        raise ApplicationError(404, "PROFILE_NOT_CONFIGURED", "investor profile is not configured")
    return _profile_response(record)


def put_profile(session: Session, payload: ProfilePut) -> ProfileResponse:
    with session.begin():
        _lock(session, _PROFILE_LOCK)
        current = _latest_profile_record(session)
        current_version = current.version if current is not None else None
        if payload.expected_version != current_version:
            raise ApplicationError(
                409,
                "VERSION_CONFLICT",
                (
                    f"expected profile version {payload.expected_version}, "
                    f"current is {current_version}"
                ),
            )
        record = ProfileVersion(
            version=1 if current is None else current.version + 1,
            base_currency=payload.base_currency,
            investment_horizon_years=payload.investment_horizon_years,
            risk_level=payload.risk_level,
            cash_buffer=payload.cash_buffer,
            broker_name=payload.broker_name,
            fee_rate=payload.fee_rate,
            minimum_fee=payload.minimum_fee,
        )
        session.add(record)
        session.flush()
        return _profile_response(record)


def _latest_asset_query(asset_id: str | None = None) -> Select[tuple[AssetVersion]]:
    latest = (
        select(AssetVersion.asset_id, func.max(AssetVersion.version).label("version"))
        .group_by(AssetVersion.asset_id)
        .subquery()
    )
    query = select(AssetVersion).join(
        latest,
        and_(
            AssetVersion.asset_id == latest.c.asset_id,
            AssetVersion.version == latest.c.version,
        ),
    )
    if asset_id is not None:
        query = query.where(AssetVersion.asset_id == asset_id)
    return query.order_by(AssetVersion.asset_id)


def _latest_assets(session: Session) -> list[AssetVersion]:
    return list(session.scalars(_latest_asset_query()).all())


def _latest_asset(session: Session, asset_id: str) -> AssetVersion | None:
    return session.scalar(_latest_asset_query(asset_id))


def _asset_response(record: AssetVersion) -> AssetResponse:
    return AssetResponse(
        asset_id=record.asset_id,
        version=record.version,
        name=record.name,
        currency=record.currency,
        lot_size=record.lot_size,
        target_weight=record.target_weight,
        is_active=record.is_active,
        created_at=record.created_at,
    )


def list_assets(session: Session) -> AssetListResponse:
    return AssetListResponse(assets=[_asset_response(item) for item in _latest_assets(session)])


def put_asset(session: Session, asset_id: str, payload: AssetPut) -> AssetResponse:
    with session.begin():
        _lock(session, _ASSET_LOCK)
        current = _latest_asset(session, asset_id)
        current_version = current.version if current is not None else None
        if payload.expected_version != current_version:
            raise ApplicationError(
                409,
                "VERSION_CONFLICT",
                f"expected asset version {payload.expected_version}, current is {current_version}",
            )
        if current is None:
            session.add(AssetIdentity(id=asset_id))
            version = 1
        else:
            version = current.version + 1
        record = AssetVersion(
            asset_id=asset_id,
            version=version,
            name=payload.name,
            currency=payload.currency,
            lot_size=payload.lot_size,
            target_weight=payload.target_weight,
            is_active=payload.is_active,
        )
        session.add(record)
        session.flush()
        return _asset_response(record)


def _price_response(record: PriceRecord) -> PriceResponse:
    return PriceResponse(
        id=record.id,
        asset_id=record.asset_id,
        price=record.price,
        currency=record.currency,
        as_of=record.as_of,
        max_age_seconds=record.max_age_seconds,
        source=record.source,
        created_at=record.created_at,
    )


def create_price(session: Session, asset_id: str, payload: PriceCreate) -> PriceResponse:
    with session.begin():
        asset = _latest_asset(session, asset_id)
        if asset is None:
            raise ApplicationError(404, "ASSET_NOT_FOUND", f"asset {asset_id} does not exist")
        if asset.currency != payload.currency:
            raise ApplicationError(
                422,
                "CURRENCY_MISMATCH",
                f"price currency differs from asset {asset_id}",
            )
        if payload.as_of.tzinfo is None or payload.as_of.utcoffset() is None:
            raise ApplicationError(422, "INVALID_PRICE_TIME", "price time must include a timezone")
        record = PriceRecord(
            id=uuid4(),
            asset_id=asset_id,
            price=payload.price,
            currency=payload.currency,
            as_of=payload.as_of,
            max_age_seconds=payload.max_age_seconds,
            source=payload.source,
        )
        session.add(record)
        session.flush()
        return _price_response(record)


def _transaction_hash(payload: TransactionCreate) -> str:
    encoded = json.dumps(
        payload.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _transaction_response(record: TransactionRecord) -> TransactionResponse:
    return TransactionResponse(
        id=record.id,
        idempotency_key=record.idempotency_key,
        asset_id=record.asset_id,
        side=record.side,
        quantity=record.quantity,
        unit_price=record.unit_price.quantize(Decimal("0.00000001")),
        accrued_interest_total=quantize_minor(record.accrued_interest_total),
        fee=quantize_minor(record.fee),
        currency=record.currency,
        occurred_at=record.occurred_at,
        note=record.note,
        created_at=record.created_at,
    )


def _transactions(session: Session) -> list[TransactionRecord]:
    return list(
        session.scalars(
            select(TransactionRecord).order_by(
                TransactionRecord.occurred_at, TransactionRecord.created_at, TransactionRecord.id
            )
        ).all()
    )


def _quantities(events: list[TransactionRecord]) -> dict[str, int]:
    quantities: dict[str, int] = {}
    for event in events:
        direction = 1 if event.side == "BUY" else -1
        quantities[event.asset_id] = quantities.get(event.asset_id, 0) + direction * event.quantity
    return quantities


def create_transaction(
    session: Session, payload: TransactionCreate
) -> tuple[TransactionResponse, bool]:
    with session.begin():
        _lock(session, _LEDGER_LOCK)
        return _create_transaction_in_transaction(session, payload)


def _create_transaction_in_transaction(
    session: Session, payload: TransactionCreate
) -> tuple[TransactionResponse, bool]:
    request_hash = _transaction_hash(payload)
    existing = session.scalar(
        select(TransactionRecord).where(
            TransactionRecord.idempotency_key == payload.idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ApplicationError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "idempotency key was already used for a different transaction",
            )
        return _transaction_response(existing), False

    asset = _latest_asset(session, payload.asset_id)
    if asset is None:
        raise ApplicationError(404, "ASSET_NOT_FOUND", f"asset {payload.asset_id} does not exist")
    if asset.currency != payload.currency:
        raise ApplicationError(422, "CURRENCY_MISMATCH", "transaction currency differs from asset")
    quantities = _quantities(_transactions(session))
    if payload.side == "SELL" and quantities.get(payload.asset_id, 0) < payload.quantity:
        raise ApplicationError(
            422,
            "INSUFFICIENT_POSITION",
            f"cannot sell {payload.quantity} units of {payload.asset_id}",
        )
    record = TransactionRecord(
        id=uuid4(),
        idempotency_key=payload.idempotency_key,
        request_hash=request_hash,
        asset_id=payload.asset_id,
        side=payload.side,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        accrued_interest_total=payload.accrued_interest_total,
        fee=payload.fee,
        currency=payload.currency,
        occurred_at=payload.occurred_at,
        note=payload.note,
    )
    session.add(record)
    session.flush()
    return _transaction_response(record), True


def _draft_fields(parsed: ParsedTransaction) -> TransactionDraftFields:
    return TransactionDraftFields(
        side=parsed.side,  # type: ignore[arg-type]
        asset_id=parsed.asset_id,
        asset_name=parsed.asset_name,
        quantity=parsed.quantity,
        unit_price=parsed.unit_price,
        accrued_interest_total=parsed.accrued_interest_total,
        fee=parsed.fee,
        currency=parsed.currency,
        occurred_at=parsed.occurred_at,
    )


def _draft_decision(
    session: Session, record: TransactionDraftDecisionRecord | None
) -> TransactionDraftDecisionResponse | None:
    if record is None:
        return None
    transaction = (
        session.get(TransactionRecord, record.transaction_id)
        if record.transaction_id is not None
        else None
    )
    if record.decision == "confirm" and transaction is None:
        raise ApplicationError(
            500,
            "DRAFT_DECISION_INVARIANT_BROKEN",
            "confirmed draft has no transaction",
        )
    return TransactionDraftDecisionResponse(
        decision=record.decision,  # type: ignore[arg-type]
        transaction=_transaction_response(transaction) if transaction is not None else None,
        decided_at=record.created_at,
    )


def _draft_response(session: Session, record: TransactionDraftRecord) -> TransactionDraftResponse:
    decision_record = session.scalar(
        select(TransactionDraftDecisionRecord).where(
            TransactionDraftDecisionRecord.draft_id == record.id
        )
    )
    decision = _draft_decision(session, decision_record)
    status = (
        "unconfirmed"
        if decision is None
        else ("confirmed" if decision.decision == "confirm" else "rejected")
    )
    return TransactionDraftResponse(
        id=record.id,
        version=record.version,
        status=status,  # type: ignore[arg-type]
        source_kind=record.source_kind,  # type: ignore[arg-type]
        source_sha256=record.source_sha256,
        source_metadata=record.source_metadata,  # type: ignore[arg-type]
        extractor_version=record.extractor_version,
        fields=TransactionDraftFields.model_validate(record.extracted_fields),
        unknown_fields=record.unknown_fields,
        conflicts=record.conflicts,
        field_confidence={
            key: Decimal(str(value)) for key, value in record.field_confidence.items()
        },
        created_at=record.created_at,
        expires_at=record.expires_at,
        decision=decision,
    )


def _known_assets(session: Session) -> tuple[KnownAsset, ...]:
    return tuple(
        KnownAsset(item.asset_id, item.name, item.currency) for item in _latest_assets(session)
    )


def _persist_parsed_draft(
    session: Session,
    *,
    source_kind: str,
    source_sha256: str,
    source_metadata: dict[str, object],
    extractor_version: str,
    parsed: ParsedTransaction,
) -> TransactionDraftResponse:
    now = datetime.now(UTC)
    fields = _draft_fields(parsed)
    record = TransactionDraftRecord(
        id=uuid4(),
        version=1,
        source_kind=source_kind,
        source_sha256=source_sha256,
        source_metadata=source_metadata,
        extractor_version=extractor_version,
        extracted_fields=fields.model_dump(mode="json"),
        unknown_fields=list(parsed.unknown_fields),
        conflicts=list(parsed.conflicts),
        field_confidence={key: str(value) for key, value in parsed.field_confidence.items()},
        expires_at=now + timedelta(hours=24),
    )
    session.add(record)
    session.flush()
    return _draft_response(session, record)


def create_transaction_draft_from_text(
    session: Session, payload: TransactionDraftTextCreate
) -> TransactionDraftResponse:
    with session.begin():
        parsed = parse_transaction_text(
            payload.text,
            _known_assets(session),
            timezone=ZoneInfo("Europe/Moscow"),
        )
        return _persist_parsed_draft(
            session,
            source_kind="text",
            source_sha256=hashlib.sha256(payload.text.encode()).hexdigest(),
            source_metadata={},
            extractor_version=PARSER_VERSION,
            parsed=parsed,
        )


def create_transaction_draft_from_image(
    session: Session,
    *,
    content: bytes,
    declared_content_type: str,
    extractor: ImageTextExtractor,
) -> TransactionDraftResponse:
    extracted = extractor.extract(content, declared_content_type=declared_content_type)
    with session.begin():
        parsed = parse_transaction_text(
            extracted.text,
            _known_assets(session),
            timezone=ZoneInfo("Europe/Moscow"),
        )
        return _persist_parsed_draft(
            session,
            source_kind="image",
            source_sha256=hashlib.sha256(content).hexdigest(),
            source_metadata={
                "media_type": extracted.media_type,
                "width": extracted.width,
                "height": extracted.height,
            },
            extractor_version=extracted.extractor_version,
            parsed=parsed,
        )


def create_transaction_draft_manual(
    session: Session, payload: TransactionDraftManualCreate
) -> TransactionDraftResponse:
    with session.begin():
        asset = _latest_asset(session, payload.asset_id)
        if asset is None:
            raise ApplicationError(
                404, "ASSET_NOT_FOUND", f"asset {payload.asset_id} does not exist"
            )
        if asset.currency != payload.currency:
            raise ApplicationError(422, "CURRENCY_MISMATCH", "draft currency differs from asset")
        confidence = {field: Decimal("1.00") for field in (
            "side",
            "asset_id",
            "quantity",
            "unit_price",
            "accrued_interest_total",
            "fee",
            "currency",
            "occurred_at",
        )}
        parsed = ParsedTransaction(
            side=payload.side,
            asset_id=payload.asset_id,
            asset_name=asset.name,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            accrued_interest_total=payload.accrued_interest_total,
            fee=payload.fee,
            currency=payload.currency,
            occurred_at=payload.occurred_at,
            unknown_fields=(),
            conflicts=(),
            field_confidence=confidence,
        )
        encoded = json.dumps(
            payload.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return _persist_parsed_draft(
            session,
            source_kind="manual",
            source_sha256=hashlib.sha256(encoded).hexdigest(),
            source_metadata={},
            extractor_version="manual-exact-v1",
            parsed=parsed,
        )


def get_transaction_draft(session: Session, draft_id: UUID) -> TransactionDraftResponse:
    record = session.get(TransactionDraftRecord, draft_id)
    if record is None:
        raise ApplicationError(
            404, "TRANSACTION_DRAFT_NOT_FOUND", "transaction draft was not found"
        )
    return _draft_response(session, record)


def decide_transaction_draft(
    session: Session,
    draft_id: UUID,
    payload: TransactionDraftDecisionCreate,
) -> tuple[TransactionDraftResponse, bool]:
    request_hash = hashlib.sha256(
        json.dumps(
            payload.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with session.begin():
        _lock(session, _LEDGER_LOCK)
        draft = session.get(TransactionDraftRecord, draft_id)
        if draft is None:
            raise ApplicationError(
                404, "TRANSACTION_DRAFT_NOT_FOUND", "transaction draft was not found"
            )
        if payload.expected_version != draft.version:
            raise ApplicationError(409, "VERSION_CONFLICT", "transaction draft version changed")
        existing = session.scalar(
            select(TransactionDraftDecisionRecord).where(
                TransactionDraftDecisionRecord.draft_id == draft_id
            )
        )
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ApplicationError(409, "DRAFT_ALREADY_DECIDED", "draft already has a decision")
            return _draft_response(session, draft), False

        transaction_response: TransactionResponse | None = None
        if payload.decision == "confirm":
            if payload.transaction is None:  # guarded by contract validation
                raise ApplicationError(422, "INCOMPLETE_CONFIRMATION", "transaction is required")
            transaction_response, created = _create_transaction_in_transaction(
                session, payload.transaction
            )
            if not created:
                raise ApplicationError(
                    409,
                    "DRAFT_TRANSACTION_ALREADY_RECORDED",
                    "confirmed transaction idempotency key already exists",
                )
        decision = TransactionDraftDecisionRecord(
            id=uuid4(),
            draft_id=draft_id,
            request_hash=request_hash,
            decision=payload.decision,
            confirmed_payload=(
                payload.transaction.model_dump(mode="json")
                if payload.transaction is not None
                else None
            ),
            transaction_id=transaction_response.id if transaction_response is not None else None,
        )
        session.add(decision)
        session.flush()
        return _draft_response(session, draft), True


def _latest_prices(session: Session, asset_ids: set[str]) -> dict[str, PriceRecord]:
    if not asset_ids:
        return {}
    records = session.scalars(
        select(PriceRecord)
        .where(PriceRecord.asset_id.in_(asset_ids))
        .order_by(PriceRecord.created_at.desc(), PriceRecord.id.desc())
    )
    result: dict[str, PriceRecord] = {}
    for record in records:
        result.setdefault(record.asset_id, record)
    return result


def _ledger_state(
    events: list[TransactionRecord],
) -> tuple[dict[str, int], dict[str, Decimal]]:
    quantities, cost_basis, _realized = _ledger_projection(events)
    return quantities, cost_basis


def _ledger_projection(
    events: list[TransactionRecord],
) -> tuple[dict[str, int], dict[str, Decimal], Decimal]:
    quantities: dict[str, int] = {}
    cost_basis: dict[str, Decimal] = {}
    realized = Decimal("0.00")
    for event in events:
        quantity = quantities.get(event.asset_id, 0)
        cost = cost_basis.get(event.asset_id, Decimal("0.00"))
        if event.side == "BUY":
            quantity += event.quantity
            cost += event.unit_price * event.quantity + event.accrued_interest_total + event.fee
        else:
            if quantity < event.quantity:
                raise ApplicationError(
                    500,
                    "LEDGER_INVARIANT_BROKEN",
                    f"negative historical position for {event.asset_id}",
                )
            average_cost = cost / quantity
            removed_cost = average_cost * event.quantity
            proceeds = (
                event.unit_price * event.quantity
                + event.accrued_interest_total
                - event.fee
            )
            realized = quantize_minor(realized + proceeds - removed_cost)
            cost -= removed_cost
            quantity -= event.quantity
        quantities[event.asset_id] = quantity
        cost_basis[event.asset_id] = quantize_minor(cost)
    return quantities, cost_basis, realized


def get_portfolio(session: Session) -> PortfolioResponse:
    profile = _latest_profile_record(session)
    if profile is None:
        raise ApplicationError(404, "PROFILE_NOT_CONFIGURED", "investor profile is not configured")
    assets = _latest_assets(session)
    quantities, costs = _ledger_state(_transactions(session))
    relevant = [item for item in assets if item.is_active or quantities.get(item.asset_id, 0) > 0]
    prices = _latest_prices(session, {item.asset_id for item in relevant})
    missing = [item.asset_id for item in relevant if item.asset_id not in prices]
    if missing:
        raise ApplicationError(422, "MISSING_PRICE", f"missing prices for {', '.join(missing)}")

    market_values = {
        item.asset_id: quantize_minor(
            prices[item.asset_id].price * quantities.get(item.asset_id, 0)
        )
        for item in relevant
    }
    total_market = sum(market_values.values(), Decimal("0.00"))
    total_cost = sum((costs.get(item.asset_id, Decimal("0.00")) for item in relevant), Decimal())
    response_assets: list[PortfolioAssetResponse] = []
    for item in relevant:
        market = market_values[item.asset_id]
        cost = costs.get(item.asset_id, Decimal("0.00"))
        actual_weight = (
            (market / total_market).quantize(Decimal("0.00000001"))
            if total_market > 0
            else Decimal("0.00000000")
        )
        response_assets.append(
            PortfolioAssetResponse(
                asset_id=item.asset_id,
                name=item.name,
                quantity=quantities.get(item.asset_id, 0),
                currency=item.currency,
                latest_price=prices[item.asset_id].price,
                price_as_of=prices[item.asset_id].as_of,
                market_value=market,
                cost_basis=cost,
                unrealized_pnl=quantize_minor(market - cost),
                target_weight=item.target_weight,
                actual_weight=actual_weight,
                drift=(actual_weight - item.target_weight).quantize(Decimal("0.00000001")),
            )
        )
    return PortfolioResponse(
        currency=profile.base_currency,
        total_market_value=quantize_minor(total_market),
        total_cost_basis=quantize_minor(total_cost),
        total_unrealized_pnl=quantize_minor(total_market - total_cost),
        assets=response_assets,
    )


def _available_metric(value: Decimal) -> AnalyticsMoneyMetricResponse:
    return AnalyticsMoneyMetricResponse(
        status="available",
        value=quantize_minor(value),
        reason=None,
    )


def _not_configured_metric(reason: str) -> AnalyticsMoneyMetricResponse:
    return AnalyticsMoneyMetricResponse(status="not_configured", value=None, reason=reason)


def get_analytics_overview(session: Session) -> AnalyticsOverviewResponse:
    portfolio = get_portfolio(session)
    events = _transactions(session)
    _quantities_by_asset, _costs_by_asset, realized = _ledger_projection(events)
    prices = _latest_prices(session, {asset.asset_id for asset in portfolio.assets})
    now = datetime.now(UTC)
    freshness_assets: list[PriceFreshnessAssetResponse] = []
    for asset in portfolio.assets:
        price = prices.get(asset.asset_id)
        if price is None:  # guarded by get_portfolio, kept explicit for invariant drift
            raise ApplicationError(
                500,
                "ANALYTICS_PRICE_INVARIANT_BROKEN",
                f"portfolio asset {asset.asset_id} has no price snapshot",
            )
        expires_at = price.as_of + timedelta(seconds=price.max_age_seconds)
        freshness_assets.append(
            PriceFreshnessAssetResponse(
                asset_id=asset.asset_id,
                status="fresh" if now <= expires_at else "stale",
                as_of=price.as_of,
                max_age_seconds=price.max_age_seconds,
                source=price.source,
            )
        )
    if not freshness_assets:
        freshness = PriceFreshnessResponse(
            status="unknown",
            oldest_as_of=None,
            reason="portfolio has no priced assets",
            assets=[],
        )
    else:
        has_stale = any(item.status == "stale" for item in freshness_assets)
        freshness = PriceFreshnessResponse(
            status="stale" if has_stale else "fresh",
            oldest_as_of=min(item.as_of for item in freshness_assets),
            reason="one or more portfolio prices are stale" if has_stale else None,
            assets=freshness_assets,
        )
    recent = [_transaction_response(event) for event in reversed(events[-10:])]
    return AnalyticsOverviewResponse(
        currency=portfolio.currency,
        calculated_at=now,
        algorithm_version="analytics-ledger-v1",
        market_value=_available_metric(portfolio.total_market_value),
        cost_basis=_available_metric(portfolio.total_cost_basis),
        net_contributions=_not_configured_metric(
            "DEPOSIT/WITHDRAWAL events are not configured in the ledger"
        ),
        realized_result=_available_metric(realized),
        unrealized_result=_available_metric(portfolio.total_unrealized_pnl),
        income=_not_configured_metric(
            "COUPON/DIVIDEND events are not configured in the ledger"
        ),
        price_freshness=freshness,
        allocation=portfolio.assets,
        recent_activity=recent,
    )


def _recommendation_response(
    run_id: UUID,
    contribution: Decimal,
    request: AllocationInput,
) -> RecommendationResponse:
    plan = build_contribution_plan(request)
    return RecommendationResponse(
        id=run_id,
        algorithm_version=plan.algorithm_version,
        input_hash=plan.input_hash,
        calculated_at=plan.calculated_at,
        currency=plan.investable.currency,
        contribution=contribution,
        cash_buffer=request.cash_buffer.amount,
        investable=plan.investable.amount,
        gross=plan.gross.amount,
        fees=plan.fees.amount,
        spent=plan.spent.amount,
        leftover=plan.leftover.amount,
        reason=plan.reason.value,
        lines=[
            RecommendationLineResponse(
                asset_id=line.asset_id,
                lots=line.lots,
                lot_size=line.lot_size,
                quantity=line.quantity,
                unit_price=line.unit_price,
                current_value=line.current_value.amount,
                target_value=line.target_value.amount,
                pre_drift=line.pre_drift.amount,
                post_drift=line.post_drift.amount,
                gross=line.gross.amount,
                fee=line.fee.amount,
                total=line.total.amount,
            )
            for line in plan.lines
        ],
    )


def _discovery_candidate_response(
    item: MarketCandidate,
    *,
    target_weight: Decimal,
    rationale: str,
    score: Decimal,
    rank_factors: dict[str, str],
) -> DiscoveryCandidateResponse:
    return DiscoveryCandidateResponse(
        asset_id=item.asset_id,
        name=item.name,
        instrument_type=item.kind.value,
        target_weight=target_weight,
        rationale=rationale,
        unit_price=item.unit_price,
        lot_size=item.lot_size,
        lot_cost=quantize_minor(item.unit_price * item.lot_size),
        price_as_of=item.price_as_of,
        quote_kind=item.quote_kind,
        turnover=item.turnover,
        maturity_date=item.maturity_date,
        yield_percent=item.yield_percent,
        next_coupon_date=item.next_coupon_date,
        coupon_percent=item.coupon_percent,
        coupon_value=item.coupon_value,
        score=score,
        rank_factors=rank_factors,
        source_url=item.source_url,
        classification_url=item.classification_url,
        research=(
            DividendResearchResponse(
                schema_version=item.research.schema_version,
                policy_version=item.research.policy_version,
                scope=item.research.scope.value,
                observed_at=item.research.observed_at,
                max_age_seconds=int(item.research.max_age.total_seconds()),
                reporting_period_end=item.research.reporting_period_end,
                profitable_years=item.research.profitable_years,
                dividend_years=item.research.dividend_years,
                payout_ratio_percent=item.research.payout_ratio_percent,
                balance_sheet_status=item.research.balance_sheet_status.value,
                governance_program_member=item.research.governance_program_member,
                corporate_action_status=item.research.corporate_action_status.value,
                summary=item.research.summary,
                citations=[
                    ResearchCitationResponse(
                        kind=citation.kind.value,
                        title=citation.title,
                        url=citation.url,
                    )
                    for citation in item.research.citations
                ],
                annual_dividend_per_share=item.research.annual_dividend_per_share,
                historical_dividend_yield_percent=(
                    item.research.historical_dividend_yield_percent
                ),
                last_registry_close_date=item.research.last_registry_close_date,
                listing_level=item.research.listing_level,
                unknown_facts=list(item.research.unknown_facts),
            )
            if item.research is not None
            else None
        ),
    )


def _rejected_discovery_candidate_response(
    item: MarketCandidate,
    *,
    reason: str,
    score: Decimal | None,
    rank_factors: dict[str, str],
) -> RejectedDiscoveryCandidateResponse:
    return RejectedDiscoveryCandidateResponse(
        asset_id=item.asset_id,
        name=item.name,
        instrument_type=item.kind.value,
        reason=reason,
        unit_price=item.unit_price,
        lot_size=item.lot_size,
        lot_cost=quantize_minor(item.unit_price * item.lot_size),
        price_as_of=item.price_as_of,
        source_url=item.source_url,
        score=score,
        rank_factors=rank_factors,
    )


def _market_search_response(acquired: AcquiredMarketResearch) -> MarketSearchResponse:
    record = acquired.record
    return MarketSearchResponse(
        snapshot_id=record.id,
        mode=acquired.mode,
        scan_policy_version=record.scan_policy_version,
        provider=record.provider,
        observed_at=record.observed_at,
        expires_at=record.expires_at,
        universe_size=record.universe_size,
        candidate_count=record.candidate_count,
        enriched_count=record.enriched_count,
        kind_counts={key: int(value) for key, value in record.kind_counts.items()},
    )


def get_latest_market_research(session: Session) -> MarketResearchStatusResponse:
    record = latest_market_research(session)
    if record is None:
        raise ApplicationError(
            404, "MARKET_RESEARCH_NOT_FOUND", "no market research snapshot is available"
        )
    return MarketResearchStatusResponse(
        id=record.id,
        status=record.status,  # type: ignore[arg-type]
        scan_policy_version=record.scan_policy_version,
        provider=record.provider,
        error_code=record.error_code,
        observed_at=record.observed_at,
        expires_at=record.expires_at,
        universe_size=record.universe_size,
        candidate_count=record.candidate_count,
        enriched_count=record.enriched_count,
        kind_counts={key: int(value) for key, value in record.kind_counts.items()},
        created_at=record.created_at,
    )


def _materialize_discovery_universe(
    session: Session,
    *,
    candidates: dict[str, MarketCandidate],
    selection: MarketSelection,
    quantities: dict[str, int],
) -> dict[str, PriceRecord]:
    selected_targets = {item.candidate.asset_id: item.target_weight for item in selection.items}
    universe_ids = set(selected_targets) | {
        asset_id for asset_id, quantity in quantities.items() if quantity > 0
    }
    latest = {item.asset_id: item for item in _latest_assets(session)}

    for asset_id, current in latest.items():
        if asset_id in universe_ids:
            continue
        if current.is_active or current.target_weight != 0:
            session.add(
                AssetVersion(
                    asset_id=asset_id,
                    version=current.version + 1,
                    name=current.name,
                    currency=current.currency,
                    lot_size=current.lot_size,
                    target_weight=Decimal("0.00000000"),
                    is_active=False,
                )
            )

    price_records: dict[str, PriceRecord] = {}
    for asset_id in sorted(universe_ids):
        candidate = candidates[asset_id]
        target = selected_targets.get(asset_id, Decimal("0.00000000"))
        existing = latest.get(asset_id)
        if existing is None:
            session.add(AssetIdentity(id=asset_id))
            version = 1
        else:
            version = existing.version + 1
        if existing is None or (
            existing.name != candidate.name
            or existing.currency != candidate.currency
            or existing.lot_size != candidate.lot_size
            or existing.target_weight != target
            or not existing.is_active
        ):
            session.add(
                AssetVersion(
                    asset_id=asset_id,
                    version=version,
                    name=candidate.name,
                    currency=candidate.currency,
                    lot_size=candidate.lot_size,
                    target_weight=target,
                    is_active=True,
                )
            )
        price = PriceRecord(
            id=uuid4(),
            asset_id=asset_id,
            price=candidate.unit_price,
            currency=candidate.currency,
            as_of=candidate.price_as_of,
            max_age_seconds=int(candidate.max_age.total_seconds()),
            source=candidate.source_url,
        )
        session.add(price)
        price_records[asset_id] = price
    return price_records


def create_discovery_recommendation(
    session: Session,
    payload: DiscoveryRecommendationCreate,
    provider: MarketDataProvider,
    *,
    market_research_cache_seconds: int = 14_400,
) -> RecommendationResponse:
    calculated_at = datetime.now(UTC)
    try:
        acquired = acquire_market_research(
            session,
            provider,
            observed_at=calculated_at,
            cache_seconds=market_research_cache_seconds,
        )
    except MarketDataError as error:
        status = 503 if error.code == "MOEX_UNAVAILABLE" else 502
        raise ApplicationError(status, error.code, error.detail) from error
    discovered = acquired.candidates
    discovered_by_id: dict[str, MarketCandidate] = {}
    for candidate in discovered:
        if candidate.asset_id in discovered_by_id:
            raise ApplicationError(
                502,
                "MOEX_INVALID_RESPONSE",
                f"duplicate market candidate {candidate.asset_id}",
            )
        discovered_by_id[candidate.asset_id] = candidate

    with session.begin():
        _lock(session, _PROFILE_LOCK)
        _lock(session, _ASSET_LOCK)
        _lock(session, _LEDGER_LOCK)
        profile = _latest_profile_record(session)
        if profile is None:
            raise ApplicationError(
                404, "PROFILE_NOT_CONFIGURED", "investor profile is not configured"
            )
        if profile.base_currency != "RUB":
            raise ApplicationError(
                422,
                "UNSUPPORTED_DISCOVERY_CURRENCY",
                "automatic MOEX discovery currently supports RUB profiles only",
            )
        events = _transactions(session)
        quantities, _ = _ledger_state(events)
        unsupported = sorted(
            asset_id
            for asset_id, quantity in quantities.items()
            if quantity > 0 and asset_id not in discovered_by_id
        )
        if unsupported:
            raise ApplicationError(
                422,
                "UNSUPPORTED_MARKET_HOLDING",
                "automatic discovery cannot refresh held instruments: " + ", ".join(unsupported),
            )

        selection = select_market_candidates(
            discovered,
            contribution=payload.contribution,
            horizon_years=profile.investment_horizon_years,
            risk_level=profile.risk_level,
            calculated_at=calculated_at,
        )
        selected_ids = {item.candidate.asset_id for item in selection.items}
        universe_ids = selected_ids | {
            asset_id for asset_id, quantity in quantities.items() if quantity > 0
        }
        universe = tuple(discovered_by_id[asset_id] for asset_id in sorted(universe_ids))
        targets = {item.candidate.asset_id: item.target_weight for item in selection.items}
        price_records = _materialize_discovery_universe(
            session,
            candidates=discovered_by_id,
            selection=selection,
            quantities=quantities,
        )
        domain_request = AllocationInput(
            contribution=Money(payload.contribution, profile.base_currency),
            cash_buffer=Money(profile.cash_buffer, profile.base_currency),
            assets=tuple(
                Asset(item.asset_id, item.name, item.currency, item.lot_size) for item in universe
            ),
            prices=tuple(
                PriceSnapshot(
                    asset_id=item.asset_id,
                    price=item.unit_price,
                    currency=item.currency,
                    as_of=item.price_as_of,
                    max_age=item.max_age,
                    source=item.source_url,
                )
                for item in universe
            ),
            positions=tuple(
                Position(item.asset_id, quantities.get(item.asset_id, 0)) for item in universe
            ),
            targets=tuple(
                TargetAllocation(item.asset_id, targets.get(item.asset_id, Decimal("0")))
                for item in universe
            ),
            fee_policy=FeePolicy(
                rate=profile.fee_rate,
                minimum=Money(profile.minimum_fee, profile.base_currency),
            ),
            calculated_at=calculated_at,
        )
        run_id = uuid4()
        base_response = _recommendation_response(run_id, payload.contribution, domain_request)
        response = base_response.model_copy(
            update={
                "mode": "automatic",
                "policy_version": selection.policy_version,
                "horizon_years": profile.investment_horizon_years,
                "risk_level": profile.risk_level,
                "candidates": [
                    _discovery_candidate_response(
                        item.candidate,
                        target_weight=item.target_weight,
                        rationale=item.rationale,
                        score=item.score,
                        rank_factors=dict(item.rank_factors),
                    )
                    for item in selection.items
                ],
                "rejected_candidates": [
                    _rejected_discovery_candidate_response(
                        item.candidate,
                        reason=item.reason,
                        score=item.score,
                        rank_factors=dict(item.rank_factors or {}),
                    )
                    for item in selection.rejected
                ],
                "profile_version": profile.version,
                "search": _market_search_response(acquired),
            }
        )
        input_snapshot: dict[str, object] = {
            "mode": "automatic",
            "profile_version": profile.version,
            "provider": provider.name,
            "policy_version": selection.policy_version,
            "horizon_years": profile.investment_horizon_years,
            "risk_level": profile.risk_level,
            "fee_rate": str(profile.fee_rate),
            "minimum_fee": str(profile.minimum_fee),
            "market_research": response.search.model_dump(mode="json") if response.search else None,
            "assets": [
                {
                    **serialize_candidate(item),
                    "asset_id": item.asset_id,
                    "kind": item.kind.value,
                    "target_weight": str(targets.get(item.asset_id, Decimal("0"))),
                    "quantity": quantities.get(item.asset_id, 0),
                    "price_snapshot_id": str(price_records[item.asset_id].id),
                }
                for item in universe
            ],
        }
        session.add(
            RecommendationRunRecord(
                id=run_id,
                input_hash=response.input_hash,
                algorithm_version=response.algorithm_version,
                calculated_at=response.calculated_at,
                currency=response.currency,
                contribution=response.contribution,
                cash_buffer=response.cash_buffer,
                gross=response.gross,
                fees=response.fees,
                spent=response.spent,
                leftover=response.leftover,
                reason=response.reason,
                input_snapshot=input_snapshot,
                output_snapshot=response.model_dump(mode="json"),
            )
        )
        session.flush()
        return response


def create_recommendation(
    session: Session, payload: RecommendationCreate
) -> RecommendationResponse:
    with session.begin():
        profile = _latest_profile_record(session)
        if profile is None:
            raise ApplicationError(
                404, "PROFILE_NOT_CONFIGURED", "investor profile is not configured"
            )
        all_assets = _latest_assets(session)
        quantities, _ = _ledger_state(_transactions(session))
        assets = [
            item for item in all_assets if item.is_active or quantities.get(item.asset_id, 0) > 0
        ]
        if not assets:
            raise ApplicationError(422, "EMPTY_ASSET_SET", "no portfolio assets are configured")
        prices = _latest_prices(session, {item.asset_id for item in assets})
        missing = [item.asset_id for item in assets if item.asset_id not in prices]
        if missing:
            raise ApplicationError(422, "MISSING_PRICE", f"missing prices for {', '.join(missing)}")

        calculated_at = datetime.now(UTC)
        domain_request = AllocationInput(
            contribution=Money(payload.contribution, profile.base_currency),
            cash_buffer=Money(profile.cash_buffer, profile.base_currency),
            assets=tuple(
                Asset(item.asset_id, item.name, item.currency, item.lot_size) for item in assets
            ),
            prices=tuple(
                PriceSnapshot(
                    asset_id=item.asset_id,
                    price=prices[item.asset_id].price,
                    currency=prices[item.asset_id].currency,
                    as_of=prices[item.asset_id].as_of,
                    max_age=timedelta(seconds=prices[item.asset_id].max_age_seconds),
                    source=prices[item.asset_id].source,
                )
                for item in assets
            ),
            positions=tuple(
                Position(item.asset_id, quantities.get(item.asset_id, 0)) for item in assets
            ),
            targets=tuple(TargetAllocation(item.asset_id, item.target_weight) for item in assets),
            fee_policy=FeePolicy(
                rate=profile.fee_rate,
                minimum=Money(profile.minimum_fee, profile.base_currency),
            ),
            calculated_at=calculated_at,
        )
        run_id = uuid4()
        base_response = _recommendation_response(run_id, payload.contribution, domain_request)
        response = base_response.model_copy(update={"profile_version": profile.version})
        input_snapshot: dict[str, object] = {
            "profile_version": profile.version,
            "base_currency": profile.base_currency,
            "fee_rate": str(profile.fee_rate),
            "minimum_fee": str(profile.minimum_fee),
            "assets": [
                {
                    "asset_id": item.asset_id,
                    "asset_version": item.version,
                    "target_weight": str(item.target_weight),
                    "price_snapshot_id": str(prices[item.asset_id].id),
                    "quantity": quantities.get(item.asset_id, 0),
                }
                for item in assets
            ],
        }
        record = RecommendationRunRecord(
            id=run_id,
            input_hash=response.input_hash,
            algorithm_version=response.algorithm_version,
            calculated_at=response.calculated_at,
            currency=response.currency,
            contribution=response.contribution,
            cash_buffer=response.cash_buffer,
            gross=response.gross,
            fees=response.fees,
            spent=response.spent,
            leftover=response.leftover,
            reason=response.reason,
            input_snapshot=input_snapshot,
            output_snapshot=response.model_dump(mode="json"),
        )
        session.add(record)
        session.flush()
        return response


def get_recommendation(session: Session, run_id: UUID) -> RecommendationResponse:
    record = session.get(RecommendationRunRecord, run_id)
    if record is None:
        raise ApplicationError(404, "RECOMMENDATION_NOT_FOUND", "recommendation run was not found")
    return RecommendationResponse.model_validate(record.output_snapshot)


def _strategy_response(
    definition: StrategyDefinition,
    recommendation: RecommendationResponse,
    *,
    recommended: bool,
) -> StrategyProposalResponse:
    return StrategyProposalResponse(
        strategy_id=definition.strategy_id,
        name=definition.name,
        summary=definition.summary,
        why=definition.why,
        risk_note=definition.risk_note,
        tradeoffs=list(definition.tradeoffs),
        recommended=recommended,
        recommendation=recommendation,
    )


def _proposal_set_response(session: Session, record: ProposalSetRecord) -> ProposalSetResponse:
    strategies: list[StrategyProposalResponse] = []
    for snapshot in record.strategies:
        run_id_value = snapshot.get("run_id")
        if not isinstance(run_id_value, str):
            raise ApplicationError(
                500, "PROPOSAL_SET_INVARIANT_BROKEN", "proposal strategy has no run id"
            )
        run = session.get(RecommendationRunRecord, UUID(run_id_value))
        if run is None:
            raise ApplicationError(
                500,
                "PROPOSAL_SET_INVARIANT_BROKEN",
                f"recommendation run {run_id_value} is missing",
            )
        strategy_payload = dict(snapshot)
        strategy_payload.pop("run_id", None)
        strategy_payload["recommendation"] = RecommendationResponse.model_validate(
            run.output_snapshot
        )
        strategies.append(StrategyProposalResponse.model_validate(strategy_payload))
    if not 1 <= len(strategies) <= 3:
        raise ApplicationError(
            500,
            "PROPOSAL_SET_INVARIANT_BROKEN",
            "proposal set must contain between one and three strategies",
        )
    return ProposalSetResponse(
        id=record.id,
        contribution=record.contribution,
        currency=record.currency,
        profile_version=record.profile_version,
        recommended_strategy_id=record.recommended_strategy_id,
        strategies=strategies,
        created_at=record.created_at,
    )


def create_proposal_set(
    session: Session,
    payload: ProposalSetCreate,
    provider: MarketDataProvider,
    *,
    market_research_cache_seconds: int = 14_400,
) -> ProposalSetResponse:
    definitions = tuple(sorted(admitted_strategies(), key=lambda item: -item.priority))
    if not 1 <= len(definitions) <= 3:
        raise ApplicationError(
            500,
            "STRATEGY_REGISTRY_INVALID",
            "strategy registry must admit between one and three strategies",
        )

    responses: list[tuple[StrategyDefinition, RecommendationResponse]] = []
    for definition in definitions:
        recommendation = create_discovery_recommendation(
            session,
            DiscoveryRecommendationCreate(contribution=payload.contribution),
            provider,
            market_research_cache_seconds=market_research_cache_seconds,
        )
        responses.append((definition, recommendation))

    recommended_id = definitions[0].strategy_id
    stored_strategies: list[dict[str, object]] = []
    for definition, recommendation in responses:
        strategy = _strategy_response(
            definition,
            recommendation,
            recommended=definition.strategy_id == recommended_id,
        )
        stored = strategy.model_dump(mode="json", exclude={"recommendation"})
        stored["run_id"] = str(recommendation.id)
        stored_strategies.append(stored)

    profile_version_value = responses[0][1].profile_version
    if profile_version_value is None:
        raise ApplicationError(
            500, "PROPOSAL_SET_INVARIANT_BROKEN", "recommendation has no profile version"
        )

    with session.begin():
        record = ProposalSetRecord(
            id=uuid4(),
            contribution=payload.contribution,
            currency=responses[0][1].currency,
            profile_version=profile_version_value,
            recommended_strategy_id=recommended_id,
            strategies=stored_strategies,
        )
        session.add(record)
        session.flush()
        return _proposal_set_response(session, record)


def get_proposal_set(session: Session, proposal_set_id: UUID) -> ProposalSetResponse:
    record = session.get(ProposalSetRecord, proposal_set_id)
    if record is None:
        raise ApplicationError(404, "PROPOSAL_SET_NOT_FOUND", "proposal set was not found")
    return _proposal_set_response(session, record)
