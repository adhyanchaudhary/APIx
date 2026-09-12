"""Airfare direction classifier neural network (Phase 2, standalone).

Predicts whether a flight's fare will go DOWN / stay STABLE / go UP over the
next sampling point, given the cleared flight row plus market context.

INTENTIONALLY NOT WIRED into the MVP pipeline. This module exists as the
open-ended Phase 2 model. It is not imported anywhere in the app, and it
depends on a future `tensorflow` install (see PRD roadmap — not in
requirements.txt for the MVP).

Architecture (per the agreed spec):
    Input  : 20 features (see FEATURES)
    Hidden : 2 Dense layers, ReLU activation, Dropout(0.3) after each
    Output : 3 units, Softmax over [DOWN, STABLE, UP]
Regularization: Dropout(0.3) + EarlyStopping(restore_best_weights=True).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tensorflow.keras import Input, Model
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.layers import Dense, Dropout

# Direction classes in output order (Softmax argmax index).
CLASSES: list[str] = ["DOWN", "STABLE", "UP"]

N_FEATURES: int = 20

# Ordered description of the 20 input features. Names follow the
# cleaned_flights columns where possible; derived fields are noted as such.
FEATURES: list[str] = [
    "total_fare_scaled",        # total_fare normalized to ~[0,1]
    "base_fare_scaled",         # base_fare normalized to ~[0,1]
    "taxes_scaled",             # taxes normalized to ~[0,1]
    "fare_vs_route_avg",        # total_fare / route avg fare (derived)
    "fare_vs_carrier_avg",      # total_fare / carrier avg fare (derived)
    "lead_window_days_scaled",  # lead_window_days / 90 -> ~[0,1]
    "departure_hour_scaled",    # depart_time.hour / 24 -> ~[0,1]
    "duration_mins_scaled",     # duration_mins / 720 -> ~[0,1]
    "stops",                    # 0..5
    "route_index_current",      # latest daily route_index (derived)
    "aggregate_index_current",  # latest daily aggregate_index (derived)
    "price_change_pct",         # % change vs previous sample (derived)
    "samples_seen",             # times this departure date was sampled (derived)
    "is_weekend",               # 1 if departure is Sat/Sun else 0
    "dow_mon",                  # day-of-week one-hot
    "dow_tue",
    "dow_wed",
    "dow_thu",
    "dow_fri",
    "dow_sat",
]

assert len(FEATURES) == N_FEATURES, "Feature list must match N_FEATURES"


@dataclass(frozen=True)
class PredictorConfig:
    """Architecture/hyper-parameter defaults for the fare classifier."""

    n_features: int = N_FEATURES
    hidden_units: tuple[int, int] = (64, 32)
    hidden_activation: str = "relu"
    dropout_rate: float = 0.3
    n_classes: int = len(CLASSES)
    output_activation: str = "softmax"
    learning_rate: float = 1e-3
    early_stop_patience: int = 8
    early_stop_min_delta: float = 1e-4


def build_predictor(cfg: PredictorConfig | None = None) -> Model:
    """Construct the Keras model: 2 hidden ReLU layers + Softmax output."""
    c = cfg or PredictorConfig()

    inp = Input(shape=(c.n_features,), name="features")
    x = Dense(c.hidden_units[0], activation=c.hidden_activation, name="hidden_1")(inp)
    x = Dropout(c.dropout_rate, name="dropout_1")(x)
    x = Dense(c.hidden_units[1], activation=c.hidden_activation, name="hidden_2")(x)
    x = Dropout(c.dropout_rate, name="dropout_2")(x)
    out = Dense(c.n_classes, activation=c.output_activation, name="direction_logits")(x)

    model = Model(inputs=inp, outputs=out, name="airfare_direction_classifier")
    model.compile(
        optimizer="adam",
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def make_early_stopping(cfg: PredictorConfig | None = None) -> EarlyStopping:
    """EarlyStopping callback used as regularizer (best weights restored)."""
    c = cfg or PredictorConfig()
    return EarlyStopping(
        monitor="val_loss",
        patience=c.early_stop_patience,
        min_delta=c.early_stop_min_delta,
        restore_best_weights=True,
        verbose=1,
    )


def train_predictor(
    model: Model,
    X,
    y,
    *,
    epochs: int = 50,
    batch_size: int = 32,
    validation_split: float = 0.2,
    cfg: PredictorConfig | None = None,
) -> dict:
    """Fit the predictor with Dropout + EarlyStopping regularization.

    Pure training utility — not called anywhere in the MVP. X is a
    ``(n, 20)`` feature matrix, y the one-hot label matrix over
    ``[DOWN, STABLE, UP]``. Returns the history.

    NOTE: start with a small padded/upsampled set — scraped fare spans are
    heavily class-imbalanced (UP dominates), so add class weights when you
    get to Phase 2.
    """
    history = model.fit(
        X,
        y,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=validation_split,
        callbacks=[make_early_stopping(cfg)],
        verbose=1,
    )
    return history.history