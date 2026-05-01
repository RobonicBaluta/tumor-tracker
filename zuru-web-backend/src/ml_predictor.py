"""
ML predictor — modelo de regresión logística sobre los prediction_logs históricos.

Entrenamiento manual: `python ml_predictor.py train` — lee la DB y entrena.
El modelo se guarda como pickle en DATA_DIR/ml_model.pkl.

Inferencia: `predict_with_ml(prediction_dict)` carga el modelo si existe y
devuelve probabilidad de victoria del equipo azul. Si no hay modelo, None.

Features usadas (todas extraíbles del prediction_logs):
  - blue_team_tumor, red_team_tumor (medianas)
  - blue_team_sum, red_team_sum (sumas brutas)
  - median_diff, sum_diff
  - confidence
  - blue_streamers, red_streamers
  - num_blue_with_priors, num_red_with_priors

Sin sklearn (pesa demasiado en Render free) — implementación manual de
regresión logística con descenso de gradiente.
"""
import json
import math
import os
import pickle


def _data_dir():
    return os.environ.get("DATA_DIR", os.path.dirname(__file__))


MODEL_PATH = os.path.join(_data_dir(), "ml_model.pkl")


def _features_from_log(row):
    """Convierte una fila de prediction_logs a un vector de features."""
    blue_priors = json.loads(row["blue_priors"] or "[]")
    red_priors = json.loads(row["red_priors"] or "[]")
    n_blue = sum(1 for p in blue_priors if p is not None)
    n_red = sum(1 for p in red_priors if p is not None)
    return [
        1.0,  # bias
        (row["blue_team_tumor"] or 50) / 100.0,
        (row["red_team_tumor"] or 50) / 100.0,
        (row["blue_team_sum"] or 0) / 500.0,
        (row["red_team_sum"] or 0) / 500.0,
        (row["median_diff"] or 0) / 50.0,
        (row["sum_diff"] or 0) / 200.0,
        (row["confidence"] or 0) / 100.0,
        (row["blue_streamers"] or 0) / 5.0,
        (row["red_streamers"] or 0) / 5.0,
        n_blue / 5.0,
        n_red / 5.0,
    ]


def _sigmoid(x):
    if x < -500: return 0.0
    if x > 500:  return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def _dot(weights, features):
    return sum(w * f for w, f in zip(weights, features))


def train_logistic_regression(rows, epochs=500, lr=0.05, l2=0.001):
    """Entrena LR manual. Devuelve los pesos."""
    if not rows:
        return None
    n_features = len(_features_from_log(rows[0]))
    weights = [0.0] * n_features
    n = len(rows)
    for epoch in range(epochs):
        grads = [0.0] * n_features
        for r in rows:
            x = _features_from_log(r)
            y = 1 if (r.get("actual_winner") or r.get("predicted_winner")) == "blue" else 0
            pred = _sigmoid(_dot(weights, x))
            err = pred - y
            for i in range(n_features):
                grads[i] += err * x[i]
        for i in range(n_features):
            weights[i] -= lr * (grads[i] / n + l2 * weights[i])
    return weights


def evaluate(rows, weights):
    if not weights:
        return {"n": 0, "accuracy": 0}
    correct = 0
    for r in rows:
        x = _features_from_log(r)
        pred = _sigmoid(_dot(weights, x))
        actual = 1 if r.get("actual_winner") == "blue" else 0
        if (pred >= 0.5) == bool(actual):
            correct += 1
    return {"n": len(rows), "accuracy": round(correct / len(rows) * 100, 1)}


def save_model(weights, meta=None):
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"weights": weights, "meta": meta or {}}, f)


def load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def predict_with_ml(synthetic_features_dict):
    """Devuelve P(blue gana) en [0, 1] o None si no hay modelo entrenado."""
    model = load_model()
    if not model:
        return None
    fake_row = {
        "blue_team_tumor": synthetic_features_dict.get("blue_team_tumor", 50),
        "red_team_tumor":  synthetic_features_dict.get("red_team_tumor", 50),
        "blue_team_sum":   synthetic_features_dict.get("blue_team_sum", 0),
        "red_team_sum":    synthetic_features_dict.get("red_team_sum", 0),
        "median_diff":     synthetic_features_dict.get("median_diff", 0),
        "sum_diff":        synthetic_features_dict.get("sum_diff", 0),
        "confidence":      synthetic_features_dict.get("confidence", 0),
        "blue_streamers":  synthetic_features_dict.get("blue_streamers", 0),
        "red_streamers":   synthetic_features_dict.get("red_streamers", 0),
        "blue_priors":     json.dumps(synthetic_features_dict.get("blue_priors", [])),
        "red_priors":      json.dumps(synthetic_features_dict.get("red_priors", [])),
    }
    x = _features_from_log(fake_row)
    return _sigmoid(_dot(model["weights"], x))


# CLI: python ml_predictor.py train
if __name__ == "__main__":
    import sys
    import sqlite3
    if len(sys.argv) < 2 or sys.argv[1] != "train":
        print("Usage: python ml_predictor.py train")
        sys.exit(1)
    db_path = os.path.join(_data_dir(), "predictions.db")
    if not os.path.exists(db_path):
        print(f"No predictions.db at {db_path}")
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = []
    sources = [
        "SELECT * FROM prediction_logs WHERE resolved=1 AND predicted_winner IS NOT NULL AND actual_winner IS NOT NULL",
        "SELECT * FROM backtest_logs WHERE predicted_winner IS NOT NULL AND actual_winner IS NOT NULL",
    ]
    for q in sources:
        try:
            for r in conn.execute(q).fetchall():
                rows.append(dict(r))
        except Exception:
            pass
    if len(rows) < 20:
        print(f"Solo {len(rows)} filas. Necesitas al menos 20 para entrenar.")
        sys.exit(1)
    print(f"Entrenando con {len(rows)} muestras...")
    # Split 80/20
    split = int(len(rows) * 0.8)
    train, test = rows[:split], rows[split:]
    weights = train_logistic_regression(train)
    train_eval = evaluate(train, weights)
    test_eval = evaluate(test, weights)
    print(f"Train accuracy: {train_eval['accuracy']}% ({train_eval['n']} samples)")
    print(f"Test accuracy:  {test_eval['accuracy']}% ({test_eval['n']} samples)")
    save_model(weights, meta={"train_eval": train_eval, "test_eval": test_eval, "n_train": len(train)})
    print(f"Modelo guardado en {MODEL_PATH}")
