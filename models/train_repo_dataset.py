#!/usr/bin/env python3
"""Train a production candidate model using the repo's current dataset layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image, UnidentifiedImageError
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras import callbacks, layers

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


def parse_args():
    parser = argparse.ArgumentParser(description="Train a new candidate model from the repo dataset.")
    parser.add_argument(
        "--dataset-root",
        default="../data/datasets/plant_disease_dataset",
        help="Dataset root containing train/ and test/ directories",
    )
    parser.add_argument("--image-size", type=int, default=160, help="Square image size")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--frozen-epochs", type=int, default=5, help="Warm-up epochs with backbone frozen")
    parser.add_argument("--finetune-epochs", type=int, default=12, help="Fine-tuning epochs after unfreezing")
    parser.add_argument("--warmup-learning-rate", type=float, default=7e-4, help="Learning rate for warm-up")
    parser.add_argument("--finetune-learning-rate", type=float, default=2e-5, help="Learning rate for fine-tuning")
    parser.add_argument("--validation-split", type=float, default=0.15, help="Validation split from train set")
    parser.add_argument("--output-model", default="../models/plant_disease_repo_finetuned.keras", help="Output model path")
    parser.add_argument("--output-metadata", default="../models/plant_disease_repo_finetuned_metadata.json", help="Output metadata path")
    parser.add_argument("--base-model-path", default="", help="Optional existing .keras model to continue fine-tuning")
    parser.add_argument("--backbone", default="MobileNetV3Large", choices=["MobileNetV3Large", "EfficientNetV2B0"], help="Transfer-learning backbone")
    parser.add_argument("--imagenet-weights", default="imagenet", choices=["imagenet", "none"], help="Pretrained weights source")
    parser.add_argument("--unfreeze-layers", type=int, default=60, help="How many backbone layers to unfreeze for fine-tuning")
    parser.add_argument("--dropout", type=float, default=0.30, help="Dropout before classifier head")
    parser.add_argument("--label-smoothing", type=float, default=0.06, help="Label smoothing for cross entropy")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def collect_examples(split_dir: Path):
    examples = []
    skipped = []
    for class_dir in sorted([p for p in split_dir.iterdir() if p.is_dir()]):
        if class_dir.name not in DATASET_LABEL_MAP:
            continue
        _, canonical_label = DATASET_LABEL_MAP[class_dir.name]
        label_index = STRICT_15_CLASSES.index(canonical_label)
        for image_path in sorted([p for p in class_dir.iterdir() if p.is_file()]):
            try:
                with Image.open(image_path) as img:
                    img.verify()
            except (UnidentifiedImageError, OSError) as exc:
                skipped.append({"image": str(image_path), "error": str(exc)})
                continue
            examples.append((str(image_path), label_index))
    return examples, skipped


def decode_image(path, label, image_size):
    image = tf.io.read_file(path)
    image = tf.image.decode_image(image, channels=3, expand_animations=False)
    image = tf.image.resize(image, [image_size, image_size])
    image = tf.cast(image, tf.float32) / 255.0
    return image, label


def make_dataset(paths, labels, image_size, batch_size, training):
    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    if training:
        ds = ds.shuffle(len(paths), reshuffle_each_iteration=True)
    ds = ds.map(lambda p, y: decode_image(p, y, image_size), num_parallel_calls=tf.data.AUTOTUNE)
    if training:
        augmentation = keras.Sequential(
            [
                layers.RandomFlip("horizontal"),
                layers.RandomRotation(0.08),
                layers.RandomZoom(0.10),
                layers.RandomContrast(0.12),
                layers.RandomBrightness(0.10),
            ]
        )
        ds = ds.map(lambda x, y: (augmentation(x, training=True), y), num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds


def get_backbone(backbone_name, image_size, weights):
    if backbone_name == "MobileNetV3Large":
        return keras.applications.MobileNetV3Large(
            include_top=False,
            input_shape=(image_size, image_size, 3),
            include_preprocessing=False,
            weights=weights,
            pooling="avg",
        )
    if backbone_name == "EfficientNetV2B0":
        return keras.applications.EfficientNetV2B0(
            include_top=False,
            input_shape=(image_size, image_size, 3),
            include_preprocessing=False,
            weights=weights,
            pooling="avg",
        )
    raise ValueError(f"Unsupported backbone: {backbone_name}")


def build_model(image_size, backbone_name, weights, dropout, base_model_path=""):
    if base_model_path:
        model = keras.models.load_model(base_model_path, compile=False)
        return model, None
    base = get_backbone(backbone_name, image_size, weights)
    base.trainable = False

    inputs = keras.Input(shape=(image_size, image_size, 3))
    x = layers.Rescaling(scale=2.0, offset=-1.0)(inputs)
    x = base(x, training=False)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout)(x)
    x = layers.Dense(256, activation="swish")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout * 0.5)(x)
    outputs = layers.Dense(len(STRICT_15_CLASSES), activation="softmax")(x)
    model = keras.Model(inputs, outputs)
    return model, base


def compile_model(model, learning_rate, label_smoothing):
    del label_smoothing
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=[
            keras.metrics.SparseCategoricalAccuracy(name="accuracy"),
            keras.metrics.SparseTopKCategoricalAccuracy(k=3, name="top3_accuracy"),
        ],
    )


def unfreeze_backbone(base, unfreeze_layers):
    if base is None:
        return
    base.trainable = True
    cutoff = max(len(base.layers) - max(int(unfreeze_layers), 0), 0)
    for idx, layer in enumerate(base.layers):
        should_train = idx >= cutoff
        if isinstance(layer, layers.BatchNormalization):
            layer.trainable = False
        else:
            layer.trainable = should_train


def fit_phase(model, train_ds, val_ds, epochs, class_weight, checkpoint_path):
    if epochs <= 0:
        return None
    return model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        class_weight=class_weight,
        callbacks=[
            callbacks.EarlyStopping(monitor="val_accuracy", patience=4, restore_best_weights=True),
            callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.4, patience=2, min_lr=1e-6),
            callbacks.ModelCheckpoint(checkpoint_path, monitor="val_accuracy", save_best_only=True),
        ],
        verbose=1,
    )


def main():
    args = parse_args()
    tf.keras.utils.set_random_seed(args.seed)

    dataset_root = Path(args.dataset_root).resolve()
    train_dir = dataset_root / "train"
    test_dir = dataset_root / "test"

    train_examples, skipped_train = collect_examples(train_dir)
    test_examples, skipped_test = collect_examples(test_dir)
    if not train_examples or not test_examples:
        raise SystemExit("Expected train/ and test/ folders with class subdirectories.")

    train_paths, train_labels = zip(*train_examples)
    test_paths, test_labels = zip(*test_examples)

    train_paths, val_paths, train_labels, val_labels = train_test_split(
        np.array(train_paths),
        np.array(train_labels),
        test_size=args.validation_split,
        random_state=args.seed,
        stratify=np.array(train_labels),
    )

    train_ds = make_dataset(train_paths, train_labels, args.image_size, args.batch_size, training=True)
    val_ds = make_dataset(val_paths, val_labels, args.image_size, args.batch_size, training=False)
    test_ds = make_dataset(np.array(test_paths), np.array(test_labels), args.image_size, args.batch_size, training=False)

    weights = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(train_labels),
        y=np.array(train_labels),
    )
    class_weight = {int(cls): float(weight) for cls, weight in zip(np.unique(train_labels), weights)}

    checkpoint_path = Path(args.output_model)
    imagenet_weights = None if args.imagenet_weights == "none" else args.imagenet_weights

    model, base = build_model(
        args.image_size,
        backbone_name=args.backbone,
        weights=imagenet_weights,
        dropout=args.dropout,
        base_model_path=args.base_model_path,
    )

    if base is None:
        warmup_history = None
        compile_model(model, args.finetune_learning_rate, args.label_smoothing)
        finetune_history = fit_phase(
            model,
            train_ds,
            val_ds,
            epochs=args.finetune_epochs,
            class_weight=class_weight,
            checkpoint_path=checkpoint_path,
        )
    else:
        compile_model(model, args.warmup_learning_rate, args.label_smoothing)
        warmup_history = fit_phase(
            model,
            train_ds,
            val_ds,
            epochs=args.frozen_epochs,
            class_weight=class_weight,
            checkpoint_path=checkpoint_path,
        )

        unfreeze_backbone(base, args.unfreeze_layers)
        compile_model(model, args.finetune_learning_rate, args.label_smoothing)
        finetune_history = fit_phase(
            model,
            train_ds,
            val_ds,
            epochs=args.finetune_epochs,
            class_weight=class_weight,
            checkpoint_path=checkpoint_path,
        )

    best_model = keras.models.load_model(checkpoint_path, compile=False)
    compile_model(best_model, args.finetune_learning_rate, args.label_smoothing)
    test_metrics = best_model.evaluate(test_ds, verbose=0)
    metric_names = best_model.metrics_names
    metrics = {name: float(value) for name, value in zip(metric_names, test_metrics)}

    metadata = {
        "class_names": STRICT_15_CLASSES,
        "image_size": [args.image_size, args.image_size],
        "batch_size": args.batch_size,
        "frozen_epochs": args.frozen_epochs,
        "finetune_epochs": args.finetune_epochs,
        "warmup_learning_rate": args.warmup_learning_rate,
        "finetune_learning_rate": args.finetune_learning_rate,
        "validation_split": args.validation_split,
        "base_model_path": args.base_model_path,
        "backbone": args.backbone,
        "imagenet_weights": args.imagenet_weights,
        "unfreeze_layers": args.unfreeze_layers,
        "dropout": args.dropout,
        "label_smoothing": args.label_smoothing,
        "skipped_train_images": skipped_train,
        "skipped_test_images": skipped_test,
        "test_metrics": metrics,
        "history": {
            "warmup": {key: [float(v) for v in values] for key, values in (warmup_history.history if warmup_history else {}).items()},
            "finetune": {key: [float(v) for v in values] for key, values in (finetune_history.history if finetune_history else {}).items()},
        },
    }

    metadata_path = Path(args.output_metadata)
    metadata_path.write_text(json.dumps(metadata, indent=2))
    print(json.dumps({"saved_model": str(checkpoint_path), "metadata": str(metadata_path), "test_metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
