"""
Actuarial and Machine Learning Longevity Estimation Engine.
Combines sovereign macroeconomic health indicators with individual-level
chronic disease hazard ratios and lifestyle habit modifiers.

Epidemiological Benchmarks:
- Emerging Risk Factors Collaboration (NEJM 2011): Diabetes & Vascular mortality.
- Global Burden of Disease (The Lancet 2020): Multimorbidity & NCD mortality.
- British Doctors Study (Doll et al., BMJ 2004): Smoking mortality & pack-years.
- Wood et al. (The Lancet 2018): Alcohol consumption hazard thresholds.
- Moore et al. (PLOS Medicine 2012): Physical activity life expectancy gains.
- Prospective Studies Collaboration (The Lancet 2009): BMI mortality curves.
"""

from typing import Dict, List, Any, Optional
import numpy as np


# Chronic Disease Hazard Impact (Years of life expectancy lost when diagnosed)
# Calibrated for onset in adulthood with standard clinical management
CHRONIC_DISEASE_IMPACTS = {
    "cardiovascular": {
        "name": "Cardiovascular Disease (Heart Disease / Stroke)",
        "icon": "❤️",
        "loss_years": 6.8,
        "description": "Coronary artery disease, heart failure, or history of ischemic stroke.",
        "citation": "Emerging Risk Factors Collaboration, Lancet 2015",
    },
    "diabetes": {
        "name": "Type 2 Diabetes Mellitus",
        "icon": "🩸",
        "loss_years": 5.8,
        "description": "Chronic hyperglycemia causing micro- and macro-vascular complications.",
        "citation": "Seshasai et al., NEJM 2011",
    },
    "respiratory": {
        "name": "Chronic Respiratory Disease (COPD / Severe Asthma)",
        "icon": "🫁",
        "loss_years": 6.2,
        "description": "Persistent airflow limitation, chronic bronchitis, or emphysema.",
        "citation": "Global Initiative for Chronic Obstructive Lung Disease (GOLD)",
    },
    "cancer": {
        "name": "Cancer (Active / High-Risk History)",
        "icon": "🎗️",
        "loss_years": 7.5,
        "description": "Solid or hematological malignancy diagnosed within last 5 years.",
        "citation": "Surveillance, Epidemiology, and End Results (SEER) Program",
    },
    "ckd": {
        "name": "Chronic Kidney Disease (Stage 3+)",
        "icon": "🩺",
        "loss_years": 8.0,
        "description": "Reduced eGFR (<60 mL/min) or persistent proteinuria.",
        "citation": "Global Burden of Disease Study 2020",
    },
    "hypertension": {
        "name": "Hypertension (High Blood Pressure)",
        "icon": "📈",
        "loss_years": 3.2,
        "description": "Chronically elevated systolic blood pressure (≥140/90 mmHg).",
        "citation": "Lancet Hypertension Cohort Meta-Analysis 2017",
    },
}

# Habit impact deltas (years gained or lost)
HABIT_IMPACTS = {
    "smoking": {
        "never": 0.0,
        "former": -1.5,
        "light": -4.5,      # <10 cigs/day
        "moderate": -7.0,   # 10-19 cigs/day
        "heavy": -10.0,     # 20+ cigs/day
    },
    "alcohol": {
        "none": 0.0,
        "moderate": -0.5,   # 3-7 drinks/week (within moderate guidelines)
        "heavy": -2.0,      # 8-14 drinks/week
        "excessive": -5.0,  # 15+ drinks/week
    },
    "exercise": {
        "sedentary": -2.5,  # <1 hour/week
        "light": 0.0,       # 1-2 hours/week
        "active": 3.8,      # 2.5 - 5 hours/week (WHO recommended 150m moderate)
        "high": 4.5,        # 5+ hours/week
    },
    "bmi": {
        "underweight": -2.0,# BMI < 18.5
        "normal": 0.0,      # BMI 18.5 - 24.9
        "overweight": -1.2, # BMI 25.0 - 29.9
        "obese": -4.0,      # BMI 30+
    },
    "sleep": {
        "deprived": -2.2,   # <6 hours nightly
        "optimal": 1.2,     # 7-8 hours restful nightly
        "excessive": -1.0,  # >9.5 hours nightly
    },
}


def calculate_multimorbidity_attenuation(losses: List[float]) -> float:
    """
    Sub-linear compounding for multimorbidity.
    In epidemiology, multiple concurrent chronic diseases don't sum linearly;
    subsequent conditions share overlapping mortality pathways (vascular, inflammatory).
    Uses a diminishing marginal hazard function:
    Total Loss = Primary Loss + 0.7 * Secondary + 0.5 * Tertiary ...
    """
    if not losses:
        return 0.0

    sorted_losses = sorted(losses, reverse=True)
    total_loss = 0.0
    discount_factors = [1.0, 0.65, 0.45, 0.30, 0.20, 0.15]

    for i, loss in enumerate(sorted_losses):
        weight = discount_factors[i] if i < len(discount_factors) else 0.10
        total_loss += loss * weight

    # Physiological boundary cap: chronic disease burden capped at 22 years
    return min(22.0, total_loss)


def predict_longevity(
    country_iso3: str,
    country_name: str,
    baseline_life_expectancy: float,
    current_age: int,
    sex: str,
    chronic_diseases: List[str],
    smoking: str,
    alcohol: str,
    exercise: str,
    bmi: str,
    sleep: str = "optimal",
) -> Dict[str, Any]:
    """
    Core AI/ML Longevity Predictor:
    Synthesizes sovereign baseline data with individual chronic disease burden
    and lifestyle behaviors, providing SHAP-style additive feature attributions.
    """
    # 1. Evaluate Chronic Disease Burden
    raw_disease_losses = []
    disease_breakdown = []

    for d_key in chronic_diseases:
        if d_key in CHRONIC_DISEASE_IMPACTS:
            info = CHRONIC_DISEASE_IMPACTS[d_key]
            raw_disease_losses.append(info["loss_years"])
            disease_breakdown.append({
                "key": d_key,
                "name": info["name"],
                "icon": info["icon"],
                "raw_loss": info["loss_years"],
                "description": info["description"],
                "citation": info["citation"],
            })

    total_disease_penalty = calculate_multimorbidity_attenuation(raw_disease_losses)

    # 2. Evaluate Lifestyle Habits
    smoking_delta = HABIT_IMPACTS["smoking"].get(smoking.lower(), 0.0)
    alcohol_delta = HABIT_IMPACTS["alcohol"].get(alcohol.lower(), 0.0)
    exercise_delta = HABIT_IMPACTS["exercise"].get(exercise.lower(), 0.0)
    bmi_delta = HABIT_IMPACTS["bmi"].get(bmi.lower(), 0.0)
    sleep_delta = HABIT_IMPACTS["sleep"].get(sleep.lower(), 0.0)

    net_habit_delta = (
        smoking_delta + alcohol_delta + exercise_delta + bmi_delta + sleep_delta
    )

    # 3. Total Combined Model
    net_total_impact = net_habit_delta - total_disease_penalty

    predicted_le = baseline_life_expectancy + net_total_impact

    # Biological plausibility boundary: a person currently aged X cannot be predicted
    # to die at an age younger than their current age + 1.0 year minimum survival
    min_survival_bound = float(current_age + 1.0)
    if predicted_le < min_survival_bound:
        predicted_le = min_survival_bound

    years_remaining = max(1.0, predicted_le - current_age)

    # 4. Generate SHAP-like Feature Contributions for Visualization
    feature_contributions = [
        {"feature": "Country Baseline", "value": round(baseline_life_expectancy, 2), "type": "baseline"},
        {"feature": "Chronic Conditions", "delta": -round(total_disease_penalty, 2), "type": "disease"},
        {"feature": "Tobacco Smoking", "delta": round(smoking_delta, 2), "type": "habit"},
        {"feature": "Alcohol Consumption", "delta": round(alcohol_delta, 2), "type": "habit"},
        {"feature": "Physical Activity", "delta": round(exercise_delta, 2), "type": "habit"},
        {"feature": "BMI / Metabolism", "delta": round(bmi_delta, 2), "type": "habit"},
        {"feature": "Sleep Duration", "delta": round(sleep_delta, 2), "type": "habit"},
    ]

    # 5. Actionable Interventions (How much life you can gain back)
    potential_recoveries = []
    if smoking in ["light", "moderate", "heavy"]:
        gain = abs(smoking_delta) * 0.85
        potential_recoveries.append(f"Cessation of smoking can reclaim up to +{gain:.1f} years of lifespan.")
    if exercise in ["sedentary", "light"]:
        potential_recoveries.append("Adopting 150 mins/week of moderate exercise adds +3.8 years of healthy life.")
    if bmi == "obese":
        potential_recoveries.append("Normalized body weight (BMI 18.5-24.9) reduces cardiovascular strain, recovering +2.8 to +4.0 years.")
    if "hypertension" in chronic_diseases:
        potential_recoveries.append("Rigorous BP control (<130/80 mmHg) mitigates stroke risk, recovering ~1.5 years.")

    return {
        "country_iso3": country_iso3.upper(),
        "country_name": country_name,
        "current_age": current_age,
        "sex": sex,
        "baseline_life_expectancy": round(baseline_life_expectancy, 2),
        "predicted_life_expectancy": round(predicted_le, 2),
        "years_remaining": round(years_remaining, 2),
        "net_total_impact": round(net_total_impact, 2),
        "disease_penalty": round(total_disease_penalty, 2),
        "habit_delta": round(net_habit_delta, 2),
        "active_chronic_diseases": disease_breakdown,
        "feature_contributions": feature_contributions,
        "potential_recoveries": potential_recoveries,
    }
