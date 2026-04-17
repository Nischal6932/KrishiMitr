#!/usr/bin/env python3
"""Evaluate all saved Keras models in the local models directory on the repo test split."""

from __future__ import annotations

import json
import os
from pathlib import Path
from statistics import mean

import numpy as np
from PIL import Image, ImageEnhance, UnidentifiedImageError

os.environ.setdefault("MPLCONFIGDIR", "/tmp")

from expected_classes import STRICT_15_CLASSES

DATASET_LABEL_MAP = {
    "Pepper_Bacterial_spot": ("Pepper", "Pepper__bell___Bacterial_spot"),
    "Pepper_Healthy": ("Pepper", "Pepper__bell___healthy"),
    "Potato_Early_blight": ("Potato", "Potato___Early_blight"),
    "Potato_Healthy": ("Potato", "Potato___healthy"),
    "Potato_Late_blight": ("Potato", "Potato___Late_blight"),
    "Tomato_Bacterial_spot": ("Tomato", "Tomato_Bacterial_spot"),
    "Tomato_Early_blight": ("Tomato", "Tomato_Early_blight"),
    "Tomato_Healthy": ("Tomato", "Tomato_healthy"),
    "Tomato_Late_blight": ("Tomato", "Tomato_Late_blight"),
    "Tomato_Leaf_mold": ("Tomato", "Tomato_Leaf_Mold"),
    "Tomato_Mosaic_virus": ("Tomato", "Tomato__Tomato_mosaic_virus"),
    "Tomato_Septoria_leaf_spot": ("Tomato", "Tomato_Septoria_leaf_spot"),
    "Tomato_Spider_mites": ("Tomato", "Tomato_Spider_mites_Two_spotted_spider_mite"),
    "Tomato_Target_spot": ("Tomato", "Tomato__Target_Spot"),
    "Tomato_Yellow_leaf_curl_virus": ("Tomato", "Tomato__Tomato_YellowLeaf__Curl_Virus"),
}

CROP_CLASS_PREFIXES = {
    "Tomato": ("Tomato",),
    "Potato": ("Potato",),
    "Pepper": ("Pepper", "Pepper__bell"),
}


def normalize_prediction_scores(raw_prediction, temperature=1.0):
    scores = np.asarray(raw_prediction, dtype=np.float64).squeeze()
    if scores.ndim != 1:
        scores = scores.reshape(-1)
    if np.any(np.isnan(scores)) or np.any(np.isinf(scores)):
        scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)

    positive_scores = np.clip(scores, 0.0, None)
    if np.all(scores >= 0.0) and np.isclose(np.sum(positive_scores), 1.0, atol=1e-3):
        probs = positive_scores
    else:
        logits = scores / max(float(temperature), 1e-3)
        logits = logits - np.max(logits)
        exp_logits = np.exp(logits)
        probs = exp_logits / np.sum(exp_logits)

    probs = np.clip(probs, 1e-10, None)
    return probs / np.sum(probs)


def geometric_consensus(predictions):
    stacked = np.asarray(predictions, dtype=np.float64)
    stacked = np.clip(stacked, 1e-10, 1.0)
    consensus = np.exp(np.mean(np.log(stacked), axis=0))
    return consensus / np.sum(consensus)


def apply_crop_context(prediction, crop_name):
    probs = normalize_prediction_scores(prediction)
    prefixes = CROP_CLASS_PREFIXES.get(crop_name)
    if not prefixes:
        return probs
    indices = [idx for idx, name in enumerate(STRICT_15_CLASSES) if any(name.startswith(prefix) for prefix in prefixes)]
    indices = [idx for idx in indices if idx < len(probs)]
    if not indices:
        return probs
    mass = float(np.sum(probs[indices]))
    if mass <= 0:
        return probs
    result = np.zeros_like(probs)
    result[indices] = probs[indices] / mass
    return result


def summarize_prediction(prediction):
    probs = normalize_prediction_scores(prediction)
    order = np.argsort(probs)[::-1]
    best_idx = int(order[0])
    second_idx = int(order[1]) if len(order) > 1 else best_idx
    return {
        "best_idx": best_idx,
        "second_idx": second_idx,
        "confidence": float(probs[best_idx]),
        "second_confidence": float(probs[second_idx]),
        "probabilities": probs,
    }


def assess_prediction_uncertainty(prediction):
    probs = normalize_prediction_scores(prediction)
    sorted_probs = np.sort(probs)[::-1]
    best = float(sorted_probs[0])
    second = float(sorted_probs[1]) if len(sorted_probs) > 1 else 0.0
    margin = best - second
    entropy = -np.sum(probs * np.log(probs))
    normalized_entropy = float(entropy / np.log(len(probs))) if len(probs) > 1 else 0.0
    return {
        "margin": margin,
        "is_uncertain": best < 0.5 or margin < 0.1 or normalized_entropy > 0.72,
    }


def discover_models(models_dir: Path):
    return sorted([p for p in models_dir.iterdir() if p.suffix in {".keras", ".h5"} and p.is_file()])


def load_image_variants(image_path: Path, image_size):
    img = Image.open(image_path).convert("RGB").resize(image_size)
    return [
        np.array(img, dtype=np.float32) / 255.0,
        np.array(ImageEnhance.Contrast(img).enhance(1.08), dtype=np.float32) / 255.0,
        np.array(ImageEnhance.Brightness(img).enhance(1.04), dtype=np.float32) / 255.0,
        np.array(ImageEnhance.Sharpness(img).enhance(1.08), dtype=np.float32) / 255.0,
    ]


def evaluate_model(model_path: Path, test_dir: Path, image_size=(160, 160), batch_size=64, ensemble_temperature=1.0):
    import tensorflow as tf

    model = tf.keras.models.load_model(model_path, compile=False)
    rows = []
    skipped = []

    for class_dir in sorted([p for p in test_dir.iterdir() if p.is_dir()]):
        crop, true_label = DATASET_LABEL_MAP[class_dir.name]
        image_paths = sorted([p for p in class_dir.iterdir() if p.is_file()])

        valid_paths = []
        variants = [[], [], [], []]
        for image_path in image_paths:
            try:
                loaded_variants = load_image_variants(image_path, image_size)
            except (UnidentifiedImageError, OSError) as exc:
                skipped.append({"image": str(image_path), "error": str(exc)})
                continue
            valid_paths.append(image_path)
            for idx, arr in enumerate(loaded_variants):
                variants[idx].append(arr)

        if not valid_paths:
            continue

        variant_arrays = [np.stack(arrs) for arrs in variants]
        variant_predictions = []
        for variant_array in variant_arrays:
            preds = []
            for start in range(0, len(valid_paths), batch_size):
                preds.append(model.predict(variant_array[start:start + batch_size], verbose=0))
            variant_predictions.append(np.concatenate(preds, axis=0))

        for idx, image_path in enumerate(valid_paths):
            probs = [
                normalize_prediction_scores(variant_predictions[0][idx], temperature=ensemble_temperature),
                normalize_prediction_scores(variant_predictions[1][idx], temperature=ensemble_temperature),
                normalize_prediction_scores(variant_predictions[2][idx], temperature=ensemble_temperature),
                normalize_prediction_scores(variant_predictions[3][idx], temperature=ensemble_temperature),
            ]
            consensus = geometric_consensus(probs)
            final_pred = (0.55 * probs[0]) + (0.45 * consensus)
            final_pred = final_pred / np.sum(final_pred)
            final_pred = apply_crop_context(final_pred, crop)
            summary = summarize_prediction(final_pred)
            uncertainty = assess_prediction_uncertainty(summary["probabilities"])
            predicted_label = STRICT_15_CLASSES[summary["best_idx"]]
            rows.append({
                "true_label": true_label,
                "predicted_label": predicted_label,
                "correct": predicted_label == true_label,
                "confidence": summary["confidence"],
                "uncertain": uncertainty["is_uncertain"],
                "image": image_path.name,
            })

    n = len(rows)
    correct = sum(r["correct"] for r in rows)
    mistakes = [r for r in rows if not r["correct"]]
    mistakes.sort(key=lambda item: item["confidence"], reverse=True)

    return {
        "model": model_path.name,
        "samples_evaluated": n,
        "samples_skipped": len(skipped),
        "top1_accuracy": round(correct / n, 4) if n else 0.0,
        "avg_confidence": round(mean(r["confidence"] for r in rows), 4) if rows else 0.0,
        "avg_confidence_correct": round(mean(r["confidence"] for r in rows if r["correct"]), 4) if correct else 0.0,
        "avg_confidence_incorrect": round(mean(r["confidence"] for r in rows if not r["correct"]), 4) if mistakes else 0.0,
        "uncertain_rate": round(sum(r["uncertain"] for r in rows) / n, 4) if n else 0.0,
        "top_confident_mistakes": mistakes[:10],
        "skipped_examples": skipped[:10],
    }


def main():
    models_dir = Path(__file__).resolve().parent
    test_dir = models_dir.parent / "data" / "datasets" / "plant_disease_dataset" / "test"
    metadata_path = models_dir / "model_config.json"

    with metadata_path.open() as f:
        metadata = json.load(f)

    image_size = tuple(metadata.get("preprocessing", {}).get("image_size", [160, 160]))
    ensemble_temperature = float(metadata.get("ensemble", {}).get("temperature", 1.0))

    models = discover_models(models_dir)
    if not models:
        raise SystemExit("No .keras or .h5 models found in models/")

    results = [evaluate_model(path, test_dir, image_size=image_size, ensemble_temperature=ensemble_temperature) for path in models]
    results.sort(key=lambda item: item["top1_accuracy"], reverse=True)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
