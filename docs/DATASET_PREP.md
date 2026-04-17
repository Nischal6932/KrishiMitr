# Dataset Prep

Use PlantVillage only for pretraining.

Recommended layout:

```text
data/datasets/plant_disease_dataset/
  pretrain_plantvillage/
  finetune_realworld/
  val_realworld/
  test_realworld/
```

Rules:

- `pretrain_plantvillage/` is clean base data only
- `finetune_realworld/` is real-world training data only
- `val_realworld/` is real-world validation data only
- `test_realworld/` is real-world holdout data only
- do not mix PlantVillage into validation/test

Import PlantVillage with:

```bash
python3 models/import_plantvillage.py
```

The importer writes a manifest at:

- `data/datasets/plant_disease_dataset/pretrain_plantvillage/manifest.json`

Potato specialist import:

```bash
python3 models/import_potato_specialist_dataset.py
```

This creates:

```text
data/datasets/plant_disease_dataset/potato_specialist/
  train/
  val/
  test/
  field_finetune/
  field_val/
  field_test/
```

Sources used:

- `Datasett/8286529` for the large 3-class potato base dataset
- `Datasett/Potato Leaf Disease Dataset in Uncontrolled Environment`
  - `Healthy` -> `Potato___healthy`
  - `Phytopthora` -> `Potato___Late_blight`
- `Datasett/PlantVillage` potato classes as supplemental clean training data
