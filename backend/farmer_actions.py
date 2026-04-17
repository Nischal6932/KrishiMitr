"""Structured farmer action data and helpers for the Smart Farming Assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
import uuid


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPERT_SUPPORT_PATH = DATA_DIR / "expert_support_requests.jsonl"


MARKETPLACE_CATALOG = [
    {
        "id": "bighaat-fungicides",
        "product_name": "Broad-spectrum fungicide options",
        "product_type": "Fungicide",
        "crop_tags": ["Tomato", "Potato", "Pepper"],
        "disease_tags": [
            "Tomato_Early_blight",
            "Tomato_Late_blight",
            "Tomato_Leaf_Mold",
            "Tomato_Septoria_leaf_spot",
            "Tomato__Target_Spot",
            "Potato___Early_blight",
            "Potato___Late_blight",
        ],
        "brand_or_seller": "BigHaat",
        "external_url": "https://www.bighaat.com/collections/chemical-pesticides-online",
        "verification_label": "Manually curated agri platform",
        "trust_note": "Linked to an established agriculture-input marketplace with crop-protection catalog pages.",
        "reason": "Useful when the detected issue points to fungal pressure and the farmer needs crop-protection options.",
    },
    {
        "id": "bighaat-organic-fertilizers",
        "product_name": "Organic fertilizer and recovery inputs",
        "product_type": "Organic fertilizer",
        "crop_tags": ["Tomato", "Potato", "Pepper"],
        "disease_tags": ["healthy", "recovery", "uncertain"],
        "brand_or_seller": "BigHaat",
        "external_url": "https://www.bighaat.com/collections/organic-fertilizers",
        "verification_label": "Manually curated agri platform",
        "trust_note": "Useful for low-risk plant recovery and soil-support browsing from a large agri-input catalog.",
        "reason": "Good fit when the plant looks healthy, is recovering, or the diagnosis confidence is low.",
    },
    {
        "id": "bighaat-agri-inputs",
        "product_name": "General crop-protection and nutrition catalog",
        "product_type": "Agri inputs",
        "crop_tags": ["Tomato", "Potato", "Pepper"],
        "disease_tags": ["all"],
        "brand_or_seller": "BigHaat",
        "external_url": "https://www.bighaat.com/collections/agricultural-products",
        "verification_label": "Manually curated agri platform",
        "trust_note": "Broad catalog with seeds, nutrition, and protection products for comparison before purchase.",
        "reason": "Use this when the farmer needs to browse backup options across crop care categories.",
    },
    {
        "id": "dehaat-shop",
        "product_name": "DeHaat crop protection and fertiliser shop",
        "product_type": "Marketplace",
        "crop_tags": ["Tomato", "Potato", "Pepper"],
        "disease_tags": ["all"],
        "brand_or_seller": "DeHaat",
        "external_url": "https://dehaat.in/en",
        "verification_label": "Manually curated agri platform",
        "trust_note": "Curated from DeHaat's official shop experience covering fertilisers, crop protection, seeds, and advisory services.",
        "reason": "Helpful as a second trusted source when the farmer wants another genuine platform before buying.",
    },
]


TREATMENT_GUIDES = {
    "Tomato_Bacterial_spot": {
        "summary": "Possible bacterial spot detected. Focus on leaf hygiene, splash control, and timely crop protection.",
        "actions": [
            "Remove badly infected leaves and keep them out of the field.",
            "Avoid overhead irrigation so water does not spread the infection.",
            "Disinfect pruning tools before moving to another plant row.",
            "Use a crop-protection product labelled for bacterial leaf problems only after checking the label and local guidance.",
        ],
        "product_tags": ["all"],
        "severity": "high",
    },
    "Tomato_Early_blight": {
        "summary": "Possible early blight detected. Reduce leaf wetness and protect healthy foliage quickly.",
        "actions": [
            "Remove lower infected leaves and destroy them away from the field.",
            "Improve airflow by reducing dense canopy where possible.",
            "Avoid wetting foliage during irrigation.",
            "Use an appropriate fungicide option if symptoms continue to spread.",
        ],
        "product_tags": ["Tomato_Early_blight", "all"],
        "severity": "medium",
    },
    "Tomato_Late_blight": {
        "summary": "Possible late blight detected. This can spread fast in cool and wet conditions, so act quickly.",
        "actions": [
            "Isolate the worst-affected plants or blocks immediately.",
            "Stop unnecessary leaf wetness and improve drainage.",
            "Scout nearby plants for dark water-soaked lesions.",
            "Escalate to expert review quickly if spread is active or weather is rainy/humid.",
        ],
        "product_tags": ["Tomato_Late_blight", "all"],
        "severity": "critical",
    },
    "Tomato_Leaf_Mold": {
        "summary": "Possible leaf mold detected. Humidity control and canopy ventilation are key.",
        "actions": [
            "Reduce humidity around the crop if grown in a protected structure.",
            "Remove heavily affected leaves from the lower canopy.",
            "Avoid crowding plants and improve air movement.",
            "Use a suitable fungicide option if symptoms increase after pruning and airflow correction.",
        ],
        "product_tags": ["Tomato_Leaf_Mold", "Tomato_Early_blight", "all"],
        "severity": "medium",
    },
    "Tomato_Septoria_leaf_spot": {
        "summary": "Possible septoria leaf spot detected. Early sanitation and leaf protection are important.",
        "actions": [
            "Remove infected leaves, especially the lower canopy.",
            "Keep irrigation directed at the root zone only.",
            "Avoid field operations when foliage is wet.",
            "Use a fungicide option if spotting is spreading to new leaves.",
        ],
        "product_tags": ["Tomato_Septoria_leaf_spot", "Tomato_Early_blight", "all"],
        "severity": "medium",
    },
    "Tomato_Spider_mites_Two_spotted_spider_mite": {
        "summary": "Possible mite pressure detected. Check the leaf underside and reduce plant stress.",
        "actions": [
            "Inspect the underside of leaves for mite clusters and webbing.",
            "Remove badly damaged leaves if infestation is localized.",
            "Avoid plant stress from heat and irregular watering.",
            "Use a labelled miticide or bio-solution only after confirming the pest on the leaf underside.",
        ],
        "product_tags": ["all"],
        "severity": "medium",
    },
    "Tomato__Target_Spot": {
        "summary": "Possible target spot detected. Keep the canopy dry and respond before lesions spread.",
        "actions": [
            "Prune out badly affected leaves and dispose of them away from the field.",
            "Improve spacing and airflow where practical.",
            "Avoid irrigation that splashes soil onto leaves.",
            "Use a fungicide option if lesions continue appearing on fresh leaves.",
        ],
        "product_tags": ["Tomato__Target_Spot", "Tomato_Early_blight", "all"],
        "severity": "medium",
    },
    "Tomato__Tomato_YellowLeaf__Curl_Virus": {
        "summary": "Possible yellow leaf curl virus detected. This needs vector management and fast field separation.",
        "actions": [
            "Remove severely affected plants to reduce spread pressure.",
            "Check for whitefly activity on new growth and the underside of leaves.",
            "Do not move tools or workers through heavily affected and healthy blocks without cleaning.",
            "Request expert help if spread is visible in multiple rows.",
        ],
        "product_tags": ["all"],
        "severity": "critical",
    },
    "Tomato__Tomato_mosaic_virus": {
        "summary": "Possible mosaic virus detected. Hygiene and plant separation are more important than heavy spraying.",
        "actions": [
            "Avoid touching healthy plants after handling infected foliage without washing hands.",
            "Sanitize tools before moving between plants.",
            "Remove the worst-affected plants if symptoms are progressing quickly.",
            "Request expert review if several plants show mosaic, distortion, or stunting.",
        ],
        "product_tags": ["all"],
        "severity": "high",
    },
    "Tomato_healthy": {
        "summary": "The plant appears healthy. Focus on prevention, nutrition balance, and regular scouting.",
        "actions": [
            "Keep monitoring the crop every 2 to 3 days for new spots, curling, or pest activity.",
            "Maintain balanced irrigation instead of watering too frequently.",
            "Support plant vigor with nutrition suited to the crop stage.",
            "Keep the field clean and remove old infected debris from nearby areas.",
        ],
        "product_tags": ["healthy", "recovery", "all"],
        "severity": "low",
    },
    "Potato___Early_blight": {
        "summary": "Possible potato early blight detected. Remove infected foliage and protect healthy leaves.",
        "actions": [
            "Remove badly affected lower leaves and keep debris away from the field.",
            "Avoid irrigation that leaves the canopy wet for long periods.",
            "Monitor neighboring plants for expanding concentric lesions.",
            "Use a suitable fungicide if spread continues after sanitation steps.",
        ],
        "product_tags": ["Potato___Early_blight", "all"],
        "severity": "medium",
    },
    "Potato___Late_blight": {
        "summary": "Possible potato late blight detected. This is high risk and needs quick action.",
        "actions": [
            "Inspect the entire plot immediately for fast-moving lesions.",
            "Avoid moving through wet foliage to reduce spread.",
            "Improve drainage and avoid waterlogging in affected zones.",
            "Push expert support if the disease seems active or weather is rainy/humid.",
        ],
        "product_tags": ["Potato___Late_blight", "all"],
        "severity": "critical",
    },
    "Potato___healthy": {
        "summary": "The potato crop looks healthy right now. Continue prevention and field monitoring.",
        "actions": [
            "Maintain even soil moisture and avoid sudden stress.",
            "Scout leaves for new lesions after humid or rainy spells.",
            "Keep weeds and old infected plant residues under control.",
            "Use recovery or nutrition products only when there is a clear crop need.",
        ],
        "product_tags": ["healthy", "recovery", "all"],
        "severity": "low",
    },
    "Pepper__bell___Bacterial_spot": {
        "summary": "Possible bacterial spot detected on pepper. Reduce splash spread and act on field hygiene.",
        "actions": [
            "Remove badly infected leaves and avoid leaving them near the crop.",
            "Do not irrigate over the canopy.",
            "Clean tools after handling infected plants.",
            "Use crop-protection products only after checking label fit for the crop and issue.",
        ],
        "product_tags": ["all"],
        "severity": "high",
    },
    "Pepper__bell___healthy": {
        "summary": "The pepper crop looks healthy. Keep focusing on prevention and balanced growth.",
        "actions": [
            "Continue routine scouting for leaf spots and pest pressure.",
            "Keep irrigation steady without waterlogging.",
            "Support vigor with balanced nutrition and clean field practices.",
            "Watch closely after humid spells because leaf disease pressure can rise quickly.",
        ],
        "product_tags": ["healthy", "recovery", "all"],
        "severity": "low",
    },
    "uncertain": {
        "summary": "The image was not clear enough for a strong diagnosis. Do not make a strong spray decision from this result alone.",
        "actions": [
            "Retake the photo in bright natural light with one leaf filling most of the frame.",
            "Inspect both the top and underside of leaves for pests, mold, spots, or viral symptoms.",
            "Use only low-risk recovery or hygiene steps until the issue is confirmed.",
            "Request expert support if the problem is spreading quickly.",
        ],
        "product_tags": ["uncertain", "recovery", "all"],
        "severity": "review",
    },
}


HIGH_RISK_DISEASES = {
    "Tomato_Late_blight",
    "Potato___Late_blight",
    "Tomato__Tomato_YellowLeaf__Curl_Virus",
    "Tomato__Tomato_mosaic_virus",
    "Pepper__bell___Bacterial_spot",
}


def _canonical_disease_tag(disease_key: str | None) -> str:
    if not disease_key:
        return "uncertain"
    return disease_key


def filter_marketplace_catalog(crop=None, disease_key=None, limit=None):
    """Return marketplace entries filtered for crop and diagnosis relevance."""
    disease_key = _canonical_disease_tag(disease_key)
    matched = []

    for item in MARKETPLACE_CATALOG:
        crop_match = not crop or crop in item["crop_tags"]
        disease_tags = item["disease_tags"]
        disease_match = (
            "all" in disease_tags
            or disease_key in disease_tags
            or ("healthy" in disease_tags and "healthy" in disease_key.lower())
            or (disease_key == "uncertain" and "uncertain" in disease_tags)
        )
        if crop_match and disease_match:
            matched.append(dict(item))

    if limit is not None:
        matched = matched[:limit]
    return matched


def generate_care_plan(crop, disease_key, soil, moisture, weather, uncertain=False):
    """Build a practical 7-day care plan using diagnosis and field context."""
    disease_key = _canonical_disease_tag(disease_key if not uncertain else "uncertain")
    crop_label = crop or "crop"

    try:
        moisture_val = int(moisture) if moisture is not None else 40
    except (ValueError, TypeError):
        moisture_val = 40

    irrigation_note = (
        "Give only light irrigation and keep leaves dry."
        if moisture_val < 35
        else "Do not over-irrigate; keep the root zone steady and avoid waterlogging."
    )
    weather_note = (
        "Because weather is humid/rainy, re-check the crop twice a day."
        if weather in {"Humid", "Rainy"}
        else "Keep one extra scouting round if temperatures rise sharply."
    )

    if "healthy" in disease_key.lower():
        focus = "prevention"
    elif disease_key in HIGH_RISK_DISEASES:
        focus = "rapid-response"
    elif disease_key == "uncertain":
        focus = "confirm-diagnosis"
    else:
        focus = "contain-and-monitor"

    plans = {
        "prevention": [
            ("Day 1", "Inspect", f"Walk the {crop_label} field and check 10 to 15 plants for fresh spots, curling, or pests."),
            ("Day 2", "Irrigation check", irrigation_note),
            ("Day 3", "Nutrition support", f"Review whether {soil or 'field'} nutrition needs a gentle booster only if crop stage supports it."),
            ("Day 4", "Canopy hygiene", "Remove old debris, weeds, and damaged leaves from around healthy plants."),
            ("Day 5", "Pest scouting", "Check leaf undersides and new growth for early pest pressure."),
            ("Day 6", "Weather watch", weather_note),
            ("Day 7", "Prevention review", "If no symptoms worsen, continue the same preventive schedule and re-scan if anything changes."),
        ],
        "rapid-response": [
            ("Day 1", "Immediate containment", "Separate the worst-affected area, remove heavily infected foliage, and avoid moving through wet plants."),
            ("Day 2", "Field reassessment", "Check nearby rows for fast spread and mark new hotspots."),
            ("Day 3", "Treatment window", "Apply only crop-appropriate protection steps after reading the label and local agronomy guidance."),
            ("Day 4", "Irrigation control", irrigation_note),
            ("Day 5", "Escalation check", "If symptoms expand after action, use expert support immediately."),
            ("Day 6", "Follow-up scouting", weather_note),
            ("Day 7", "Decision point", "Compare disease spread to Day 1. If still active, move to a stronger expert-led treatment decision."),
        ],
        "confirm-diagnosis": [
            ("Day 1", "Retake images", "Capture clearer close-up photos in daylight from front and underside of the leaf."),
            ("Day 2", "Manual inspection", "Check whether symptoms look fungal, bacterial, viral, or pest related before buying strong inputs."),
            ("Day 3", "Low-risk correction", irrigation_note),
            ("Day 4", "Sanitation", "Remove clearly dead or badly damaged leaves and keep tools clean."),
            ("Day 5", "Compare symptoms", "See whether symptoms are spreading to new plants or staying localized."),
            ("Day 6", "Expert escalation", "Submit an expert support request if symptoms worsen or remain unclear."),
            ("Day 7", "Re-evaluate", "Re-upload a fresh image and compare with the first result before making bigger treatment purchases."),
        ],
        "contain-and-monitor": [
            ("Day 1", "Remove hotspots", "Prune or isolate the most affected leaves and plants first."),
            ("Day 2", "Irrigation adjustment", irrigation_note),
            ("Day 3", "Targeted treatment", "Use crop-appropriate treatment only if symptoms are progressing."),
            ("Day 4", "Canopy management", "Improve airflow and reduce conditions that keep leaves wet."),
            ("Day 5", "Monitoring round", "Check new growth and neighboring plants for spread."),
            ("Day 6", "Weather response", weather_note),
            ("Day 7", "Escalation trigger", "If lesions, curling, or pest load increase, request expert help and avoid random mixing of products."),
        ],
    }

    return [
        {"day": day, "title": title, "description": description}
        for day, title, description in plans[focus]
    ]


def build_farmer_action_bundle(crop, disease_key, confidence, soil, moisture, weather, uncertain=False):
    """Assemble treatment guidance, recommended products, care plan, and support flags."""
    disease_key = _canonical_disease_tag(disease_key if not uncertain else "uncertain")
    guide = TREATMENT_GUIDES.get(disease_key, TREATMENT_GUIDES["uncertain"])
    recommended_products = filter_marketplace_catalog(crop=crop, disease_key=disease_key, limit=3)

    expert_support_recommended = uncertain or disease_key in HIGH_RISK_DISEASES
    if confidence is not None and confidence < 75:
        expert_support_recommended = True

    caution_note = None
    if uncertain or (confidence is not None and confidence < 70):
        caution_note = (
            "Confidence is limited, so use these suggestions as a safe starting point and confirm before making major spray or purchase decisions."
        )
    elif disease_key in HIGH_RISK_DISEASES:
        caution_note = "This diagnosis can affect yield quickly. Do not delay field checks and escalation if spread is active."

    treatment_summary = guide["summary"]
    if caution_note:
        treatment_summary = f"{treatment_summary} {caution_note}"

    return {
        "treatment_summary": treatment_summary,
        "recommended_actions": list(guide["actions"]),
        "recommended_products": recommended_products,
        "care_plan": generate_care_plan(crop, disease_key, soil, moisture, weather, uncertain=uncertain),
        "expert_support_recommended": expert_support_recommended,
        "caution_note": caution_note,
        "severity": guide["severity"],
    }


def validate_expert_support_payload(payload):
    """Validate the expert support request payload and normalize values."""
    name = str(payload.get("name", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    crop = str(payload.get("crop", "")).strip()
    issue = str(payload.get("issue", "")).strip()
    description = str(payload.get("description", "")).strip()
    location = str(payload.get("location", "")).strip()
    image_reference = str(payload.get("image_reference", "")).strip()

    if not name:
        return False, "Farmer name is required.", None
    if not re.fullmatch(r"[0-9+\-\s]{8,18}", phone):
        return False, "Enter a valid phone number.", None
    if not crop:
        return False, "Crop is required for expert support.", None
    if not issue:
        return False, "Issue details are required.", None
    if len(description) < 10:
        return False, "Please add a short description so the expert understands the problem.", None

    normalized = {
        "name": name,
        "phone": phone,
        "crop": crop,
        "issue": issue,
        "description": description,
        "location": location or None,
        "image_reference": image_reference or None,
    }
    return True, None, normalized


def store_expert_support_request(payload):
    """Persist an expert support request to local JSONL storage."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "id": f"support_{uuid.uuid4().hex[:10]}",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with EXPERT_SUPPORT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return record
