#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DATASET_ROOT="${DATASET_ROOT:-data/datasets/plant_disease_dataset}"
MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x ".venv-metal312/bin/python" ]]; then
    PYTHON_BIN=".venv-metal312/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

usage() {
  cat <<'EOF'
Usage:
  ./train_on_gpu.sh setup
  ./train_on_gpu.sh potato-import
  ./train_on_gpu.sh potato-specialist
  ./train_on_gpu.sh mobilenet
  ./train_on_gpu.sh efficientnet
  ./train_on_gpu.sh resume
  ./train_on_gpu.sh evaluate
  ./train_on_gpu.sh full

Commands:
  setup         Install GPU training dependencies from requirements_gpu.txt
  potato-import Import the local potato sources into a specialist dataset layout
  potato-specialist Train a potato-only specialist model
  mobilenet     Run MobileNetV3Large transfer-learning experiment
  efficientnet  Run EfficientNetV2B0 transfer-learning experiment
  resume        Resume fine-tuning from the shipped checkpoint
  evaluate      Evaluate all saved models in models/
  full          Import potato data, train the potato specialist, run generic experiments, then evaluate all saved models

Environment overrides:
  PYTHON_BIN    Python executable to use
  DATASET_ROOT  Dataset root directory
  MPLCONFIGDIR  Matplotlib cache directory
EOF
}

run_train() {
  local output_model="$1"
  local output_metadata="$2"
  shift 2

  MPLCONFIGDIR="$MPLCONFIGDIR" "$PYTHON_BIN" models/train_repo_dataset.py \
    --dataset-root "$DATASET_ROOT" \
    --output-model "$output_model" \
    --output-metadata "$output_metadata" \
    "$@"
}

case "${1:-}" in
  setup)
    "$PYTHON_BIN" -m pip install --upgrade pip
    "$PYTHON_BIN" -m pip install -r requirements_gpu.txt
    ;;
  potato-import)
    "$PYTHON_BIN" models/import_potato_specialist_dataset.py
    ;;
  potato-specialist)
    MPLCONFIGDIR="$MPLCONFIGDIR" "$PYTHON_BIN" models/train_potato_specialist.py \
      --dataset-root "$DATASET_ROOT/potato_specialist" \
      --output-model models/potato_specialist.keras \
      --output-metadata models/potato_specialist_metadata.json \
      --base-model-path "" \
      --backbone CustomPotatoCNN \
      --image-size 96 \
      --batch-size 64 \
      --frozen-epochs 6 \
      --finetune-epochs 0 \
      --field-epochs 2 \
      --warmup-learning-rate 8e-4 \
      --finetune-learning-rate 2e-5 \
      --field-learning-rate 2e-5 \
      --unfreeze-layers 0 \
      --dropout 0.30 \
      --max-train-per-class 4000 \
      --max-val-per-class 600 \
      --max-test-per-class 600 \
      --max-field-per-class 120
    ;;
  mobilenet)
    run_train \
      models/plant_disease_repo_mobilenet.keras \
      models/plant_disease_repo_mobilenet_metadata.json \
      --backbone MobileNetV3Large \
      --image-size 224 \
      --batch-size 32 \
      --frozen-epochs 8 \
      --finetune-epochs 20 \
      --warmup-learning-rate 5e-4 \
      --finetune-learning-rate 1e-5 \
      --unfreeze-layers 80 \
      --dropout 0.25 \
      --validation-split 0.15
    ;;
  efficientnet)
    run_train \
      models/plant_disease_repo_efficientnet.keras \
      models/plant_disease_repo_efficientnet_metadata.json \
      --backbone EfficientNetV2B0 \
      --image-size 224 \
      --batch-size 24 \
      --frozen-epochs 8 \
      --finetune-epochs 20 \
      --warmup-learning-rate 3e-4 \
      --finetune-learning-rate 8e-6 \
      --unfreeze-layers 100 \
      --dropout 0.30 \
      --validation-split 0.15
    ;;
  resume)
    run_train \
      models/plant_disease_repo_resume.keras \
      models/plant_disease_repo_resume_metadata.json \
      --base-model-path models/plant_disease_realworld_15class_best_v4.keras \
      --frozen-epochs 0 \
      --finetune-epochs 12 \
      --finetune-learning-rate 1e-5 \
      --validation-split 0.15
    ;;
  evaluate)
    MPLCONFIGDIR="$MPLCONFIGDIR" "$PYTHON_BIN" models/evaluate_saved_models.py
    ;;
  full)
    "$0" potato-import
    "$0" potato-specialist
    "$0" mobilenet
    "$0" efficientnet
    "$0" evaluate
    ;;
  *)
    usage
    exit 1
    ;;
esac
