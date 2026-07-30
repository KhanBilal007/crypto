"""Repositories for feature, prediction, and signal snapshots."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from sqlite3 import Connection
from uuid import uuid4

from abtp.db.models import Tables
from abtp.domain import FeatureVector, Prediction, Signal
from abtp.repositories.serialization import (
    dumps_model,
    feature_vector_from_payload,
    pair_symbol,
    prediction_from_payload,
    signal_from_payload,
)


class IntelligenceRepository:
    """Persist AI-adjacent artifacts without model training or inference."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def add_feature_vector(self, features: FeatureVector) -> str:
        feature_id = str(uuid4())
        self._connection.execute(
            """
            INSERT INTO feature_snapshots (
                id, pair, generated_at, feature_version, inputs_ref, values_json, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feature_id,
                pair_symbol(features.pair),
                features.generated_at.isoformat(),
                features.feature_version,
                features.inputs_ref,
                dumps_model(features),
                dumps_model(features),
            ),
        )
        self._connection.commit()
        return feature_id

    def add_indicator_value(
        self,
        *,
        pair: str,
        generated_at: datetime,
        indicator_name: str,
        indicator_value: Decimal,
        source_ref: str,
    ) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO indicator_values (
                pair, generated_at, indicator_name, indicator_value, source_ref
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                pair,
                generated_at.isoformat(),
                indicator_name,
                str(indicator_value),
                source_ref,
            ),
        )
        self._connection.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("indicator insert did not return a row id")
        return cursor.lastrowid

    def get_feature_vector(self, feature_id: str) -> FeatureVector | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {Tables.FEATURES} WHERE id = ?",
            (feature_id,),
        ).fetchone()
        return feature_vector_from_payload(str(row["payload_json"])) if row else None

    def add_prediction(self, prediction: Prediction) -> str:
        prediction_id = str(uuid4())
        self._connection.execute(
            """
            INSERT INTO predictions (
                id, pair, generated_at, horizon, model_version, features_ref, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prediction_id,
                pair_symbol(prediction.pair),
                prediction.generated_at.isoformat(),
                prediction.horizon.value,
                prediction.model_version,
                prediction.features_ref,
                dumps_model(prediction),
            ),
        )
        self._connection.commit()
        return prediction_id

    def get_prediction(self, prediction_id: str) -> Prediction | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {Tables.PREDICTIONS} WHERE id = ?",
            (prediction_id,),
        ).fetchone()
        return prediction_from_payload(str(row["payload_json"])) if row else None

    def add_signal(self, signal: Signal) -> str:
        signal_id = str(uuid4())
        self._connection.execute(
            """
            INSERT INTO signals (
                id, source, pair, generated_at, direction, confidence, inputs_ref,
                prediction_ref, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                signal.source,
                pair_symbol(signal.pair),
                signal.generated_at.isoformat(),
                signal.direction.value,
                str(signal.confidence),
                signal.inputs_ref,
                signal.prediction_ref,
                dumps_model(signal),
            ),
        )
        self._connection.commit()
        return signal_id

    def get_signal(self, signal_id: str) -> Signal | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {Tables.SIGNALS} WHERE id = ?",
            (signal_id,),
        ).fetchone()
        return signal_from_payload(str(row["payload_json"])) if row else None
