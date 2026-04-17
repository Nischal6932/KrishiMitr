#!/usr/bin/env python3
"""
Fine-tune the local plant disease model on real-world field images.

Expected dataset layouts:

1. Recommended explicit splits:
   real_world_dataset/
     train/<class_name>/*.jpg
     val/<class_name>/*.jpg
     test/<class_name>/*.jpg   # optional

2. Single-folder fallback:
   real_world_dataset/
     <class_name>/*.jpg

In fallback mode, the script creates train/validation splits automatically.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau

from expected_classes import STRICT_15_CLASSES


AUTOTUNE = tf.data.AUTOTUNE
DEFAULT_IMAGE_SIZE = (160, 160)
DEFAULT_BATCH_SIZE = 32
DEFAULT_SEED = 42
DEFAULT_SPLIT = 0.2


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune the model on real-world field images.")
    parser.add_argument("--data-dir", required=True, help="Path to real-world dataset root")
    parser.add_argument(
        "--base-model",
        default="plant_disease_best_local.keras",
        help="Optional warm-start checkpoint. If incompatible with 15 classes, ImageNet initialization is used.",
    )
    parser.add_argument(
        "--class-index",
        default="strict_15_class_indices.json",
        help="JSON file mapping the required 15 classes to indices",
    )
    parser.add_argument(
        "--output-model",
        default="plant_disease_realworld_15class_best.keras",
        help="Fine-tuned 15-class output model path",
    )
    parser.add_argument("--output-history", default="realworld_finetune_history.json", help="Training history output path")
    parser.add_argument("--output-metadata", default="realworld_finetune_metadata.json", help="Metadata output path")
    parser.add_argument("--image-size", type=int, default=224, help="Square input size")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--epochs", type=int, default=16, help="Maximum fine-tuning epochs")
    parser.add_argument("--learning-rate", type=float, default=3e-5, help="Learning rate for fine-tuning")
    parser.add_argument("--validation-split", type=float, default=0.2, help="Validation split for single-folder mode")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--unfreeze-layers", type=int, default=120, help="How many layers from the end to unfreeze")
    parser.add_argument(
        "--backbone",
        choices=["mobilenetv3large", "efficientnetv2b0"],
        default="efficientnetv2b0",
        help="Backbone architecture for real-world fine-tuning",
    )
    parser.add_argument(
        "--label-smoothing",
        type=float,
        default=0.08,
        help="Label smoothing for better calibration on noisy web images",
    )
    return parser.parse_args()


def load_expected_classes(class_index_path: Path):
    with class_index_path.open() as f:
        class_indices = json.load(f)
    class_names = [name for name, _ in sorted(class_indices.items(), key=lambda item: item[1])]
    if class_names != STRICT_15_CLASSES:
        raise ValueError(
            "Strict 15-class training requires the exact expected class list. "
            f"Got: {class_names}"
        )
    return class_names


def build_directory_dataset(directory: Path, image_size, batch_size, shuffle, seed):
    return keras.utils.image_dataset_from_directory(
        directory,
        labels="inferred",
        label_mode="int",
        image_size=image_size,
        batch_size=batch_size,
        shuffle=shuffle,
        seed=seed,
    )


def build_split_dataset(directory: Path, image_size, batch_size, split, seed):
    train_ds = keras.utils.image_dataset_from_directory(
        directory,
        labels="inferred",
        label_mode="int",
        validation_split=split,
        subset="training",
        seed=seed,
        image_size=image_size,
        batch_size=batch_size,
        shuffle=True,
    )
    val_ds = keras.utils.image_dataset_from_directory(
        directory,
        labels="inferred",
        label_mode="int",
        validation_split=split,
        subset="validation",
        seed=seed,
        image_size=image_size,
        batch_size=batch_size,
        shuffle=False,
    )
    return train_ds, val_ds


def validate_class_names(dataset_class_names, expected_class_names):
    dataset_set = set(dataset_class_names)
    expected_set = set(expected_class_names)
    missing = sorted(expected_set - dataset_set)
    extra = sorted(dataset_set - expected_set)
    if missing or extra:
        raise ValueError(
            "Dataset class mismatch. "
            f"Missing classes: {missing or 'none'}. Extra classes: {extra or 'none'}."
        )


def get_labels(dataset):
    labels = []
    for _, batch_labels in dataset.unbatch():
        labels.append(int(batch_labels.numpy()))
    return np.array(labels, dtype=np.int32)


def compute_class_weights(labels):
    classes = np.unique(labels)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=labels)
    return {int(cls): float(weight) for cls, weight in zip(classes, weights)}


def attach_real_world_head(feature_extractor, image_shape, num_classes):
    augmentation = keras.Sequential(
        [
            layers.RandomFlip("horizontal"),
            layers.RandomRotation(0.18),
            layers.RandomZoom(0.2),
            layers.RandomTranslation(0.12, 0.12),
            layers.RandomContrast(0.25),
            layers.RandomBrightness(0.2),
        ],
        name="realworld_augmentation",
    )

    inputs = keras.Input(shape=image_shape)
    x = augmentation(inputs)
    x = feature_extractor(x, training=True)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(256, activation="relu")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)
    return keras.Model(inputs, outputs)


def build_feature_extractor(image_size, unfreeze_layers, backbone):
    if backbone == "efficientnetv2b0":
        feature_extractor = keras.applications.EfficientNetV2B0(
            input_shape=(*image_size, 3),
            include_top=False,
            weights="imagenet",
            include_preprocessing=True,
            pooling="avg",
        )
    else:
        feature_extractor = keras.applications.MobileNetV3Large(
            input_shape=(*image_size, 3),
            alpha=1.0,
            include_top=False,
            weights="imagenet",
            include_preprocessing=True,
            pooling="avg",
            dropout_rate=0.0,
        )
    feature_extractor.trainable = True
    for layer in feature_extractor.layers[:-unfreeze_layers]:
        layer.trainable = False
    return feature_extractor


def warm_start_if_compatible(model, start_model_path: Path):
    if not start_model_path.exists():
        print(f"Warm-start checkpoint not found, skipping: {start_model_path}")
        return
    try:
        previous_model = tf.keras.models.load_model(start_model_path, compile=False)
        if previous_model.output_shape[-1] != model.output_shape[-1]:
            print(
                "Warm-start checkpoint output dimension does not match strict 15 classes. "
                "Trying partial warm-start for compatible layers only."
            )
        else:
            try:
                model.set_weights(previous_model.get_weights())
                print(f"Warm-started from compatible checkpoint: {start_model_path}")
                return
            except Exception:
                print("Full-model warm-start failed. Trying partial warm-start for compatible layers only.")

        copied_layers = 0
        for new_layer, old_layer in zip(model.layers, previous_model.layers):
            old_weights = old_layer.get_weights()
            new_weights = new_layer.get_weights()
            if not old_weights or not new_weights:
                continue
            if len(old_weights) != len(new_weights):
                continue
            if all(old.shape == new.shape for old, new in zip(old_weights, new_weights)):
                new_layer.set_weights(old_weights)
                copied_layers += 1
        print(f"Partially warm-started {copied_layers} compatible layers from: {start_model_path}")
    except Exception as exc:
        print(f"Warm-start skipped for {start_model_path}: {exc}")


def compile_model(model, learning_rate, label_smoothing):
    try:
        loss = keras.losses.SparseCategoricalCrossentropy(label_smoothing=label_smoothing)
    except TypeError:
        print(
            "SparseCategoricalCrossentropy in this TensorFlow build does not support "
            "label_smoothing. Falling back to the standard sparse cross-entropy loss."
        )
        loss = keras.losses.SparseCategoricalCrossentropy()
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss=loss,
        metrics=[
            keras.metrics.SparseCategoricalAccuracy(name="accuracy"),
            keras.metrics.SparseTopKCategoricalAccuracy(k=3, name="top3_accuracy"),
        ],
    )


def cache_and_prefetch(dataset, shuffle=False, seed=DEFAULT_SEED):
    dataset = dataset.cache()
    if shuffle:
        dataset = dataset.shuffle(2048, seed=seed)
    return dataset.prefetch(AUTOTUNE)


def main():
    args = parse_args()
    tf.random.set_seed(args.seed)
    np.random.seed(args.seed)

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Dataset root does not exist: {data_dir}")

    class_index_path = Path(args.class_index)
    expected_class_names = load_expected_classes(class_index_path)
    image_size = (args.image_size, args.image_size)

    train_dir = data_dir / "train"
    val_dir = data_dir / "val"
    test_dir = data_dir / "test"

    if train_dir.exists() and val_dir.exists():
        train_ds = build_directory_dataset(train_dir, image_size, args.batch_size, shuffle=True, seed=args.seed)
        val_ds = build_directory_dataset(val_dir, image_size, args.batch_size, shuffle=False, seed=args.seed)
    else:
        train_ds, val_ds = build_split_dataset(
            data_dir,
            image_size,
            args.batch_size,
            args.validation_split,
            args.seed,
        )

    validate_class_names(train_ds.class_names, expected_class_names)
    validate_class_names(val_ds.class_names, expected_class_names)

    test_ds = None
    if test_dir.exists():
        test_ds = build_directory_dataset(test_dir, image_size, args.batch_size, shuffle=False, seed=args.seed)
        validate_class_names(test_ds.class_names, expected_class_names)

    train_labels = get_labels(train_ds)
    class_weights = compute_class_weights(train_labels)

    train_ds = cache_and_prefetch(train_ds, shuffle=True, seed=args.seed)
    val_ds = cache_and_prefetch(val_ds, shuffle=False, seed=args.seed)
    if test_ds is not None:
        test_ds = cache_and_prefetch(test_ds, shuffle=False, seed=args.seed)

    print(f"Expected classes: {expected_class_names}")
    print(f"Train samples: {len(train_labels)}")
    print(f"Validation batches: {tf.data.experimental.cardinality(val_ds).numpy()}")
    print(f"Class weights: {class_weights}")

    feature_extractor = build_feature_extractor(image_size, args.unfreeze_layers, args.backbone)
    model = attach_real_world_head(feature_extractor, (*image_size, 3), len(expected_class_names))
    warm_start_if_compatible(model, Path(args.base_model))
    compile_model(model, args.learning_rate, args.label_smoothing)

    callbacks = [
        ModelCheckpoint(
            args.output_model,
            monitor="val_accuracy",
            mode="max",
            save_best_only=True,
            verbose=1,
        ),
        EarlyStopping(
            monitor="val_accuracy",
            mode="max",
            patience=4,
            restore_best_weights=True,
            verbose=1,
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.3,
            patience=2,
            min_lr=1e-6,
            verbose=1,
        ),
    ]

    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=1,
    )

    val_results = model.evaluate(val_ds, verbose=1, return_dict=True)
    test_results = model.evaluate(test_ds, verbose=1, return_dict=True) if test_ds is not None else None

    Path(args.output_history).write_text(
        json.dumps({k: [float(v) for v in values] for k, values in history.history.items()}, indent=2)
    )

    metadata = {
        "base_model": args.base_model,
        "output_model": args.output_model,
        "class_index": args.class_index,
        "data_dir": str(data_dir),
        "image_size": list(image_size),
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "unfreeze_layers": args.unfreeze_layers,
        "backbone": args.backbone,
        "label_smoothing": args.label_smoothing,
        "validation_metrics": {k: float(v) for k, v in val_results.items()},
        "test_metrics": {k: float(v) for k, v in test_results.items()} if test_results else None,
    }
    Path(args.output_metadata).write_text(json.dumps(metadata, indent=2))

    print("Validation metrics:")
    print(json.dumps(metadata["validation_metrics"], indent=2))
    if metadata["test_metrics"] is not None:
        print("Test metrics:")
        print(json.dumps(metadata["test_metrics"], indent=2))


if __name__ == "__main__":
    main()
