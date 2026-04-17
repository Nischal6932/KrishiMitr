# Model Retraining Runbook

This project's current deployed model is usable for demos, but it is not yet reliable enough on the local PlantVillage-style test split.

Current measured baseline from the repo test split:

- Top-1 accuracy: `19.84%`
- Average confidence: `23.38%`
- Uncertain rate: `87.54%`

Use this runbook to retrain and evaluate the model on a proper GPU machine.

## Goal

Train a replacement model that clearly beats the current baseline on the same test split and is safe to promote into the app.

Minimum promotion target:

- Top-1 accuracy: `>= 60%`
- Average confidence when correct: higher than average confidence when incorrect by a meaningful margin
- Uncertain rate: materially lower than the current baseline
- No obvious class-collapse on tomato classes

Recommended promotion target:

- Top-1 accuracy: `>= 75%`
- Top-3 accuracy: `>= 90%`
- Stable per-class behavior across all 15 labels

## Recommended Environment

Use a machine with:

- NVIDIA GPU with at least 12 GB VRAM, or a strong Apple Silicon machine with enough memory
- Python `3.10` or `3.11`
- TensorFlow version matched to the accelerator environment
- At least 30 GB free disk space

Recommended setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements_gpu.txt
```

If you are using a dedicated GPU setup, install the TensorFlow build appropriate for that machine instead of relying on the local desktop environment.

You can also use the helper launcher:

```bash
chmod +x train_on_gpu.sh
./train_on_gpu.sh setup
```

On this repo's Apple Silicon path, a ready-to-use local env may exist at:

```bash
.venv-metal312/bin/python
```

The launcher will prefer that interpreter automatically when present.

## Dataset Checks

Before training, verify the dataset layout:

```text
data/datasets/plant_disease_dataset/
  train/
  test/
```

Expected class folders are the current repo names:

- `Pepper_Bacterial_spot`
- `Pepper_Healthy`
- `Potato_Early_blight`
- `Potato_Healthy`
- `Potato_Late_blight`
- `Tomato_Bacterial_spot`
- `Tomato_Early_blight`
- `Tomato_Healthy`
- `Tomato_Late_blight`
- `Tomato_Leaf_mold`
- `Tomato_Mosaic_virus`
- `Tomato_Septoria_leaf_spot`
- `Tomato_Spider_mites`
- `Tomato_Target_spot`
- `Tomato_Yellow_leaf_curl_virus`

The training script already skips unreadable images, but if possible, clean those files out before a full run.

## Training Strategy

Do not rely on a short CPU training run to judge model quality.

Recommended strategy:

1. Start with transfer learning from a modern backbone.
2. Train the classifier head first with the backbone frozen.
3. Fine-tune only the last part of the backbone.
4. Compare every saved candidate on the same repo test split.
5. Promote only the best evaluated checkpoint.

## Recommended Experiments

Run these experiments in order and keep the metadata for each.

### Experiment A: MobileNetV3Large

```bash
./train_on_gpu.sh mobilenet
```

### Experiment B: EfficientNetV2B0

```bash
./train_on_gpu.sh efficientnet
```

### Experiment C: Resume From Existing Checkpoint

Only use this if the shipped checkpoint has a healthy validation curve in the new environment.

```bash
./train_on_gpu.sh resume
```

## Evaluation

After every experiment:

```bash
./train_on_gpu.sh evaluate
```

What to compare:

- `top1_accuracy`
- `avg_confidence`
- `avg_confidence_correct`
- `avg_confidence_incorrect`
- `uncertain_rate`
- `top_confident_mistakes`

Do not promote a model just because training accuracy improved.
Promotion must be based on the held-out repo test split.

## Promotion Rule

Promote a candidate only if all of these are true:

- It beats the current deployed baseline on top-1 accuracy
- It reduces obvious high-confidence mistakes
- It does not collapse on tomato subclasses
- It keeps the same 15-class mapping from [models/strict_15_class_indices.json](/Users/nischalmittal/Downloads/FINAL-main/models/strict_15_class_indices.json)

If a candidate wins, rename or copy it to:

- `models/plant_disease_repo_finetuned.keras`

The app already prefers that filename first in runtime loading.

## Important Notes

- The current [models/model_config.json](/Users/nischalmittal/Downloads/FINAL-main/models/model_config.json) metadata does not match the architecture of the shipped `.keras` checkpoint exactly, so trust measured evaluation more than historical metadata.
- A bad early curve on CPU is not conclusive, but a healthy GPU run should show much stronger validation movement than what we saw locally.
- If accuracy still stalls after proper GPU runs, the next problem is likely dataset quality, label noise, or domain mismatch rather than inference code.

## Fast Checklist

- Set up a GPU-capable Python environment
- Verify the dataset folders are present
- Run Experiment A
- Run Experiment B
- Evaluate all saved models
- Keep the best checkpoint and metadata
- Promote only if it clearly beats the current baseline
- Re-run app evaluation after promotion

## Final Verification After Promotion

Run:

```bash
python3 models/evaluate_saved_models.py
python3 -m pytest -q
```

Then manually test a few real uploads through the app and confirm:

- the predicted label is plausible
- confidence is not artificially low
- uncertainty messaging appears only when appropriate
