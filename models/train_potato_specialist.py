#!/usr/bin/env python3
"""Train and evaluate a 3-class potato specialist model."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image, UnidentifiedImageError
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras import callbacks, layers


CLASS_NAMES = [
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Train a potato specialist model.")
    parser.add_argument(
        "--dataset-root",
        default="../data/datasets/plant_disease_dataset/potato_specialist",
        help="Dataset root containing train/ val/ test/ and optional field_* splits",
    )
    parser.add_argument("--image-size", type=int, default=224, help="Square image size")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--frozen-epochs", type=int, default=5, help="Warm-up epochs")
    parser.add_argument("--finetune-epochs", type=int, default=10, help="Fine-tuning epochs")
    parser.add_argument("--field-epochs", type=int, default=6, help="Optional field adaptation epochs")
    parser.add_argument("--warmup-learning-rate", type=float, default=4e-4, help="Warm-up learning rate")
    parser.add_argument("--finetune-learning-rate", type=float, default=1e-5, help="Fine-tuning learning rate")
    parser.add_argument("--field-learning-rate", type=float, default=6e-6, help="Field adaptation learning rate")
    parser.add_argument("--output-model", default="../models/potato_specialist.keras", help="Output model path")
    parser.add_argument(
        "--output-metadata",
        default="../models/potato_specialist_metadata.json",
        help="Output metadata path",
    )
    parser.add_argument(
        "--base-model-path",
        default="../models/plant_disease_realworld_15class_best_v4.keras",
        help="Optional local checkpoint to reuse as the feature extractor",
    )
    parser.add_argument(
        "--backbone",
        default="CustomPotatoCNN",
        choices=["CustomPotatoCNN", "EfficientNetV2B0", "MobileNetV3Large"],
        help="Backbone architecture",
    )
    parser.add_argument("--unfreeze-layers", type=int, default=120, help="How many layers to unfreeze")
    parser.add_argument("--dropout", type=float, default=0.3, help="Dropout before classifier head")
    parser.add_argument("--max-train-per-class", type=int, default=0, help="Optional cap per class for train split")
    parser.add_argument("--max-val-per-class", type=int, default=0, help="Optional cap per class for val split")
    parser.add_argument("--max-test-per-class", type=int, default=0, help="Optional cap per class for test split")
    parser.add_argument("--max-field-per-class", type=int, default=0, help="Optional cap per class for each field split")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def collect_examples(directory: Path, limit_per_class=0, seed=42):
    if not directory.exists():
        return [], []
    class_dirs = [p for p in directory.iterdir() if p.is_dir()]
    if not class_dirs:
        return [], []
    examples = []
    skipped = []
    for class_name in CLASS_NAMES:
        class_dir = directory / class_name
        if not class_dir.exists():
            continue
        label = CLASS_NAMES.index(class_name)
        image_paths = [p for p in class_dir.iterdir() if p.is_file()]
        if limit_per_class:
            rng = random.Random(seed + label)
            image_paths = sorted(image_paths)
            rng.shuffle(image_paths)
            image_paths = image_paths[:limit_per_class]
        else:
            image_paths = sorted(image_paths)
        for image_path in image_paths:
            try:
                with Image.open(image_path) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError) as exc:
                skipped.append({"image": str(image_path), "error": str(exc)})
                continue
            examples.append((str(image_path), label))
    return examples, skipped


def decode_image(path, label, image_size):
    image = tf.io.read_file(path)
    image = tf.image.decode_image(image, channels=3, expand_animations=False)
    image = tf.image.resize(image, [image_size, image_size])
    image = tf.cast(image, tf.float32) / 255.0
    return image, label


def build_examples_dataset(examples, image_size, batch_size, shuffle, seed):
    if not examples:
        return None
    paths, labels = zip(*examples)
    ds = tf.data.Dataset.from_tensor_slices((list(paths), list(labels)))
    if shuffle:
        ds = ds.shuffle(len(paths), seed=seed, reshuffle_each_iteration=True)
    ds = ds.map(lambda p, y: decode_image(p, y, image_size), num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.ignore_errors()
    ds = ds.batch(batch_size)
    return ds


def normalize_dataset(dataset, training):
    if dataset is None:
        return None
    augmentation = keras.Sequential(
        [
            layers.RandomFlip("horizontal"),
            layers.RandomRotation(0.10),
            layers.RandomZoom(0.14),
            layers.RandomTranslation(0.08, 0.08),
            layers.RandomContrast(0.15),
            layers.RandomBrightness(0.12),
        ]
    )

    def _normalize(images, labels):
        images = tf.cast(images, tf.float32) / 255.0
        if training:
            images = augmentation(images, training=True)
        return images, labels

    return dataset.map(_normalize, num_parallel_calls=tf.data.AUTOTUNE).prefetch(tf.data.AUTOTUNE)


def get_labels(dataset):
    labels = []
    for _, batch_labels in dataset.unbatch():
        labels.append(int(batch_labels.numpy()))
    return np.asarray(labels, dtype=np.int32)


def compute_weights(labels):
    classes = np.unique(labels)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=labels)
    return {int(cls): float(weight) for cls, weight in zip(classes, weights)}


def get_backbone(name, image_size):
    if name == "CustomPotatoCNN":
        return None
    if name == "EfficientNetV2B0":
        return keras.applications.EfficientNetV2B0(
            include_top=False,
            input_shape=(image_size, image_size, 3),
            include_preprocessing=False,
            weights="imagenet",
            pooling="avg",
        )
    return keras.applications.MobileNetV3Large(
        include_top=False,
        input_shape=(image_size, image_size, 3),
        include_preprocessing=False,
        weights="imagenet",
        pooling="avg",
    )


def build_custom_cnn(image_size, dropout):
    inputs = keras.Input(shape=(image_size, image_size, 3))
    x = inputs
    for filters in (32, 64, 128, 192):
        x = layers.Conv2D(filters, 3, padding="same", activation=None)(x)
        x = layers.BatchNormalization()(x)
        x = layers.Activation("swish")(x)
        x = layers.MaxPooling2D()(x)
        x = layers.Dropout(0.08)(x)
    x = layers.Conv2D(256, 3, padding="same", activation=None)(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("swish")(x)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(dropout)(x)
    x = layers.Dense(256, activation="swish")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout * 0.5)(x)
    outputs = layers.Dense(len(CLASS_NAMES), activation="softmax")(x)
    return keras.Model(inputs, outputs), None


def build_model(image_size, backbone_name, dropout, base_model_path=""):
    if backbone_name == "CustomPotatoCNN":
        return build_custom_cnn(image_size, dropout)
    if base_model_path and Path(base_model_path).exists():
        pretrained = keras.models.load_model(base_model_path, compile=False)
        backbone = keras.Model(
            inputs=pretrained.inputs[0],
            outputs=pretrained.layers[-2].output,
            name="plant_feature_extractor",
        )
    else:
        backbone = get_backbone(backbone_name, image_size)
    backbone.trainable = False

    inputs = keras.Input(shape=(image_size, image_size, 3))
    x = inputs
    if not base_model_path or not Path(base_model_path).exists():
        x = layers.Rescaling(scale=2.0, offset=-1.0)(x)
    x = backbone(x, training=False)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout)(x)
    x = layers.Dense(256, activation="swish")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout * 0.5)(x)
    outputs = layers.Dense(len(CLASS_NAMES), activation="softmax")(x)
    return keras.Model(inputs, outputs), backbone


def compile_model(model, learning_rate):
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=[
            keras.metrics.SparseCategoricalAccuracy(name="accuracy"),
            keras.metrics.SparseTopKCategoricalAccuracy(k=2, name="top2_accuracy"),
        ],
    )


def unfreeze_backbone(backbone, unfreeze_layers):
    backbone.trainable = True
    cutoff = max(len(backbone.layers) - max(int(unfreeze_layers), 0), 0)
    for idx, layer in enumerate(backbone.layers):
        should_train = idx >= cutoff
        if isinstance(layer, layers.BatchNormalization):
            layer.trainable = False
        else:
            layer.trainable = should_train


def fit(model, train_ds, val_ds, epochs, class_weight, checkpoint_path):
    if train_ds is None or val_ds is None or epochs <= 0:
        return None
    return model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        class_weight=class_weight,
        callbacks=[
            callbacks.EarlyStopping(monitor="val_accuracy", patience=3, restore_best_weights=True),
            callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.35, patience=2, min_lr=1e-6),
            callbacks.ModelCheckpoint(checkpoint_path, monitor="val_accuracy", save_best_only=True),
        ],
        verbose=1,
    )


def evaluate_dataset(model, dataset):
    if dataset is None:
        return None
    probabilities = model.predict(dataset, verbose=0)
    predictions = np.argmax(probabilities, axis=1)
    labels = get_labels(dataset)
    report = classification_report(labels, predictions, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
    matrix = confusion_matrix(labels, predictions, labels=list(range(len(CLASS_NAMES)))).tolist()
    return {
        "samples": int(len(labels)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "avg_confidence": float(np.mean(np.max(probabilities, axis=1))),
        "classification_report": report,
        "confusion_matrix": matrix,
    }


def history_payload(history):
    if history is None:
        return {}
    return {key: [float(value) for value in values] for key, values in history.history.items()}


def main():
    args = parse_args()
    tf.keras.utils.set_random_seed(args.seed)

    dataset_root = Path(args.dataset_root).resolve()
    train_examples, skipped_train = collect_examples(
        dataset_root / "train",
        limit_per_class=args.max_train_per_class,
        seed=args.seed,
    )
    val_examples, skipped_val = collect_examples(
        dataset_root / "val",
        limit_per_class=args.max_val_per_class,
        seed=args.seed + 10,
    )
    test_examples, skipped_test = collect_examples(
        dataset_root / "test",
        limit_per_class=args.max_test_per_class,
        seed=args.seed + 20,
    )
    field_finetune_examples, skipped_field_finetune = collect_examples(
        dataset_root / "field_finetune",
        limit_per_class=args.max_field_per_class,
        seed=args.seed + 30,
    )
    field_val_examples, skipped_field_val = collect_examples(
        dataset_root / "field_val",
        limit_per_class=args.max_field_per_class,
        seed=args.seed + 40,
    )
    field_test_examples, skipped_field_test = collect_examples(
        dataset_root / "field_test",
        limit_per_class=args.max_field_per_class,
        seed=args.seed + 50,
    )

    train_ds = build_examples_dataset(train_examples, args.image_size, args.batch_size, True, args.seed)
    val_ds = build_examples_dataset(val_examples, args.image_size, args.batch_size, False, args.seed)
    test_ds = build_examples_dataset(test_examples, args.image_size, args.batch_size, False, args.seed)
    field_finetune_ds = build_examples_dataset(field_finetune_examples, args.image_size, args.batch_size, True, args.seed)
    field_val_ds = build_examples_dataset(field_val_examples, args.image_size, args.batch_size, False, args.seed)
    field_test_ds = build_examples_dataset(field_test_examples, args.image_size, args.batch_size, False, args.seed)

    if train_ds is None or val_ds is None or test_ds is None:
        raise SystemExit("Expected train/, val/, and test/ directories for the potato specialist dataset.")

    raw_train_labels = np.asarray([label for _, label in train_examples], dtype=np.int32)
    class_weight = compute_weights(raw_train_labels)
    if args.backbone == "CustomPotatoCNN":
        class_weight = None

    train_ds = normalize_dataset(train_ds, training=True)
    val_ds = normalize_dataset(val_ds, training=False)
    test_ds = normalize_dataset(test_ds, training=False)
    field_finetune_ds = normalize_dataset(field_finetune_ds, training=True)
    field_val_ds = normalize_dataset(field_val_ds, training=False)
    field_test_ds = normalize_dataset(field_test_ds, training=False)

    output_model_path = Path(args.output_model).resolve()
    output_metadata_path = Path(args.output_metadata).resolve()

    model, backbone = build_model(
        args.image_size,
        args.backbone,
        args.dropout,
        base_model_path=args.base_model_path,
    )
    compile_model(model, args.warmup_learning_rate)
    warmup = fit(model, train_ds, val_ds, args.frozen_epochs, class_weight, output_model_path)

    unfreeze_backbone(backbone, args.unfreeze_layers)
    compile_model(model, args.finetune_learning_rate)
    finetune = fit(model, train_ds, val_ds, args.finetune_epochs, class_weight, output_model_path)

    field_history = None
    if field_finetune_ds is not None and field_val_ds is not None:
        compile_model(model, args.field_learning_rate)
        field_history = fit(model, field_finetune_ds, field_val_ds, args.field_epochs, None, output_model_path)

    reloaded = keras.models.load_model(output_model_path, compile=False)
    compile_model(reloaded, args.field_learning_rate)

    metadata = {
        "model_name": output_model_path.name,
        "task": "potato_specialist",
        "class_names": CLASS_NAMES,
        "image_size": [args.image_size, args.image_size],
        "backbone": args.backbone,
        "base_model_path": str(Path(args.base_model_path).resolve()) if args.base_model_path else "",
        "source_dataset": str(dataset_root),
        "sample_limits": {
            "train": args.max_train_per_class,
            "val": args.max_val_per_class,
            "test": args.max_test_per_class,
            "field": args.max_field_per_class,
        },
        "skipped_files": {
            "train": skipped_train[:20],
            "val": skipped_val[:20],
            "test": skipped_test[:20],
            "field_finetune": skipped_field_finetune[:20],
            "field_val": skipped_field_val[:20],
            "field_test": skipped_field_test[:20],
        },
        "metrics": {
            "test": evaluate_dataset(reloaded, test_ds),
            "field_test": evaluate_dataset(reloaded, field_test_ds),
        },
        "histories": {
            "warmup": history_payload(warmup),
            "finetune": history_payload(finetune),
            "field": history_payload(field_history),
        },
    }

    output_metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
