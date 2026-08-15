"""Transactional use cases; no transport owns portfolio logic."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Select, and_, func, select, text
from sqlalchemy.orm import Session

from patientcapital.application.errors import ApplicationError
from patientcapital.contracts import (
    AssetListResponse,
    AssetPut,
    AssetResponse,
    PortfolioAssetResponse,
    PortfolioResponse,
    PriceCreate,
    PriceResponse,
    ProfilePut,
    ProfileResponse,
    RecommendationCreate,
    RecommendationLineResponse,
    RecommendationResponse,
    TransactionCreate,
    TransactionResponse,
)
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
from patientcapital.persistence.models import (
    AssetIdentity,
    AssetVersion,
    PriceRecord,
    ProfileVersion,
    RecommendationRunRecord,
    TransactionRecord,
)

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


def put_asset(
    session: Session, asset_id: str, payload: AssetPut
) -> AssetResponse:
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


def create_price(
    session: Session, asset_id: str, payload: PriceCreate
) -> PriceResponse:
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
        unit_price=record.unit_price,
        fee=record.fee,
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
    request_hash = _transaction_hash(payload)
    with session.begin():
        _lock(session, _LEDGER_LOCK)
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
            raise ApplicationError(
                404, "ASSET_NOT_FOUND", f"asset {payload.asset_id} does not exist"
            )
        if asset.currency != payload.currency:
            raise ApplicationError(
                422, "CURRENCY_MISMATCH", "transaction currency differs from asset"
            )
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
            fee=payload.fee,
            currency=payload.currency,
            occurred_at=payload.occurred_at,
            note=payload.note,
        )
        session.add(record)
        session.flush()
        return _transaction_response(record), True


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
    quantities: dict[str, int] = {}
    cost_basis: dict[str, Decimal] = {}
    for event in events:
        quantity = quantities.get(event.asset_id, 0)
        cost = cost_basis.get(event.asset_id, Decimal("0.00"))
        if event.side == "BUY":
            quantity += event.quantity
            cost += event.unit_price * event.quantity + event.fee
        else:
            if quantity < event.quantity:
                raise ApplicationError(
                    500,
                    "LEDGER_INVARIANT_BROKEN",
                    f"negative historical position for {event.asset_id}",
                )
            average_cost = cost / quantity
            cost -= average_cost * event.quantity
            quantity -= event.quantity
        quantities[event.asset_id] = quantity
        cost_basis[event.asset_id] = quantize_minor(cost)
    return quantities, cost_basis


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
            targets=tuple(
                TargetAllocation(item.asset_id, item.target_weight) for item in assets
            ),
            fee_policy=FeePolicy(
                rate=profile.fee_rate,
                minimum=Money(profile.minimum_fee, profile.base_currency),
            ),
            calculated_at=calculated_at,
        )
        run_id = uuid4()
        response = _recommendation_response(run_id, payload.contribution, domain_request)
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
