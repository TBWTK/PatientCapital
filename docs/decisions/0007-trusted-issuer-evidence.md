---
title: "ADR 0007: доверенные данные эмитента"
type: decision
status: accepted
updated: 2026-08-16
---

# ADR 0007: доверенные данные эмитента

## Контекст

PC4 доказал торговую ликвидность полного TQBR universe, но акции остаются `unknown`: MOEX ISS
история дивидендов не содержит достаточных official financial, audit, governance и material-event
facts. Существующий `DividendResearchEvidence` агрегирует значения без issuer/ISIN/share-class
binding, document hash, effective dates, binding authority и conflict semantics. Подключить его
напрямую к runtime означало бы снова выдать screen за полный issuer audit.

Официальные структурированные API НРД и шлюза Интерфакс требуют авторизованный доступ; открытые
issuer IR документы неоднородны. Поэтому отсутствие credentials нельзя маскировать secondary news,
LLM summary или статическим ticker verdict.

## Решение

Ввести `issuer-evidence-v2` как единственный input `equity-dividend-quality-v2`.

- Identity связывает MOEX security, ISIN, issuer stable id/legal name и share class. Mismatch даёт
  `unknown`, а не негативный вывод об активе.
- Каждый material fact ссылается на primary document id/URL/hash, publication/effective/observed
  time, период, unit/currency/basis и explicit supersession. Свежесть загрузки не заменяет свежесть
  отчётного периода или dividend decision/payment.
- Event taxonomy различает binding decision, proposal и management comment. Binding suspension,
  overdue declared payment, default/insolvency и delisting могут быть strategy hard kill;
  non-binding adverse signal даёт `watch`; конфликт равноправных primary facts даёт `unknown`.
- Numeric gates используют только typed Decimal facts. Narrative, модель и пользовательское мнение
  не входят в evidence hash или решение.
- Reviewed primary-source packet provider является первым trusted adapter. Его registry определяет
  доверенную identity/source lineage, но не whitelist пригодных тикеров: verdict всегда выводится
  policy. Authenticated NSD/Interfax adapters могут быть добавлены за тем же contract после наличия
  credentials/licensing; provider outage не повышает status.
- Admission run identity включает `issuer_evidence_set_hash`, поэтому один market snapshot может
  иметь несколько immutable переоценок разными evidence sets без cache collision.
- Selection потребляет exact persisted profile mapping. Повторная независимая оценка candidate в
  ranking path запрещена.

## Минимальная dividend policy v2

Для `eligible` нужны: exact identity; latest-due official reporting and audit coverage; прибыль
в последнем и минимум трёх из четырёх завершённых FY; positive binding distribution минимум в трёх
из четырёх due FY, включая последний due period; payout `0 < ratio <= 100%` на совпадающем basis;
positive equity/minimum balance evidence; complete governance/material-event coverage; отсутствие
active hard kill. Missing/stale/conflicting material gate даёт `unknown`, qualified/non-binding
review case — `watch`, подтверждённый fail — `reject`.

Отсутствие дивидендов исключает dividend strategy, но не доказывает плохой growth asset. Growth,
sector leverage, bank/developer/oil-specific quality и valuation требуют отдельных policy.

## Последствия

- Legacy `dividend-quality-v1` и `market_screen` остаются читаемыми в старых runs, но не дают новый
  v2 admission.
- Первоначальный eligible equity set может быть мал: это честная цена отсутствующих trusted facts.
- Corpus gate требует zero false-eligible, exact status/reasons/hard-kills, identity/conflict failure,
  input-order/narrative invariance и no ledger/order side effects.
- Новый evidence источник добавляется adapter review, tests и policy-version bump, а не prompt edit.
