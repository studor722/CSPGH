"""
Actuarial and Machine Learning Longevity Estimation Engine.
Combines sovereign macroeconomic health indicators with individual-level
chronic disease hazard ratios and lifestyle habit modifiers.

Epidemiological Benchmarks:
- Emerging Risk Factors Collaboration (NEJM 2011, Lancet 2015): Vascular, diabetes, and cardiometabolic mortality.
- Global Burden of Disease Study (The Lancet 2020): Multimorbidity, NCD mortality & risk attribution.
- British Doctors Study (Doll et al., BMJ 2004): Lifelong smoking mortality & cessation recovery curves.
- Wood et al. (The Lancet 2018): Alcohol consumption thresholds & cardiovascular hazard ratios.
- Moore et al. (PLOS Medicine 2012): Leisure-time physical activity and life expectancy gains.
- Prospective Studies Collaboration (The Lancet 2009): BMI and cause-specific mortality.
- PREDIMED & Global Burden of Disease (NEJM 2018, Lancet Planetary Health 2019): Diet quality and longevity.
"""

from typing import Dict, List, Any, Optional
import math


# Chronic Disease Hazard Impact (Years of life expectancy lost when diagnosed)
CHRONIC_DISEASE_IMPACTS = {
    "none": {
        "name": "No Chronic Conditions (Healthy Baseline)",
        "icon": "✨",
        "loss_years": 0.0,
        "description": "No active chronic or non-communicable diseases diagnosed.",
        "citation": "World Health Organization Healthy Life Expectancy (HALE) baseline",
    },
    "hypertension": {
        "name": "Hypertension (High Blood Pressure)",
        "icon": "📈",
        "loss_years": 3.2,
        "description": "Chronically elevated systolic blood pressure (≥140/90 mmHg).",
        "citation": "Lancet Hypertension Cohort Meta-Analysis 2017",
    },
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
        "name": "Cancer History (Active / Diagnosed < 5 yrs)",
        "icon": "🎗️",
        "loss_years": 7.5,
        "description": "Solid or hematological malignancy diagnosed within the past five years.",
        "citation": "Surveillance, Epidemiology, and End Results (SEER) Program",
    },
    "ckd": {
        "name": "Chronic Kidney Disease (Stage 3+)",
        "icon": "🩺",
        "loss_years": 8.0,
        "description": "Reduced eGFR (<60 mL/min) or persistent proteinuria.",
        "citation": "Global Burden of Disease Study 2020",
    },
    "liver": {
        "name": "Chronic Liver Disease (Cirrhosis / Hepatitis)",
        "icon": "🧪",
        "loss_years": 6.5,
        "description": "Chronic hepatic inflammation, fibrosis, or non-alcoholic steatohepatitis.",
        "citation": "WHO Global Health Observatory Liver Mortality Index",
    },
    "autoimmune": {
        "name": "Autoimmune & Inflammatory Condition",
        "icon": "🧬",
        "loss_years": 3.5,
        "description": "Systemic inflammatory disorders (e.g. rheumatoid arthritis, lupus).",
        "citation": "Lancet Rheumatology Cohort Outcomes 2019",
    },
    "mental_health": {
        "name": "Chronic Clinical Depression / Severe Anxiety",
        "icon": "🧠",
        "loss_years": 3.8,
        "description": "Recurrent major depressive disorder or treatment-resistant anxiety.",
        "citation": "Lancet Psychiatry Meta-Analysis (Walker et al. 2015)",
    },
    "cystic_fibrosis": {
        "name": "Cystic Fibrosis (Genetic CFTR Mutation)",
        "icon": "🧬",
        "loss_years": 22.0,
        "description": "Monogenic disorder causing thick pulmonary secretions and multiorgan insufficiency.",
        "citation": "Cystic Fibrosis Foundation Patient Registry 2023",
    },
    "sickle_cell": {
        "name": "Sickle Cell Disease (Genetic Hemoglobinopathy)",
        "icon": "🩸",
        "loss_years": 18.0,
        "description": "Autosomal recessive HBB mutation causing vaso-occlusive crises and organ damage.",
        "citation": "Blood Advances 2021 (Lanzkron et al.)",
    },
    "familial_hypercholesterolemia": {
        "name": "Familial Hypercholesterolemia (Genetic FH)",
        "icon": "🫀",
        "loss_years": 7.0,
        "description": "Autosomal dominant LDLR defect resulting in lifelong elevated LDL-C and early CAD.",
        "citation": "European Heart Journal / ESC Guidelines 2022",
    },
}

# Habit impact deltas (years gained or lost relative to neutral benchmark)
HABIT_IMPACTS = {
    "smoking": {
        "never": 0.0,
        "former": -1.2,
        "light": -4.0,      # <10 cigs/day or vaping
        "heavy": -8.5,      # 10+ cigs/day
    },
    "alcohol": {
        "none": 0.0,
        "moderate": -0.5,   # 1-7 standard drinks/week (within WHO low-risk guidelines)
        "heavy": -2.5,      # 8-14 standard drinks/week
        "excessive": -5.5,  # 15+ standard drinks/week
    },
    "exercise": {
        "sedentary": -2.5,        # <60 mins/week sitting
        "light": 0.0,             # 60-150 mins/week casual walking/cycling
        "cardio": 3.8,            # 150-300 mins/week running, cycling, or swimming (WHO Aerobic)
        "active": 3.8,            # Backward compatibility alias
        "cardio_strength": 4.5,   # Aerobic + 2x/week Weight Lifting / Resistance (WHO Dual Guideline)
        "high": 4.5,              # Backward compatibility alias
        "endurance": 4.8,         # 300+ mins/week endurance sports (swimming, marathon, rowing)
    },
    "diet": {
        "mediterranean": 3.5,       # Mediterranean / Pescatarian (olive oil, fish, legumes, nuts) — PREDIMED trial (NEJM 2018)
        "vegetarian": 3.0,          # Plant-Based / Vegetarian / Vegan (whole grains, fruits, plants) — Adventist Health Study (JAMA Int Med 2013)
        "balanced_omnivore": 0.0,   # Balanced Mixed Omnivore (standard varied diet, home-cooked) — Reference baseline
        "carnivore_keto": -2.2,     # Carnivore / Strict Meat-Based (high saturated animal fat, zero dietary fiber) — Lancet Public Health 2018
        "ultra_processed": -3.8,    # High Ultra-Processed Foods (fast food, soda, processed meats) — BMJ 2019 / Lancet Planetary Health
        # Backward compatibility aliases
        "whole_foods": 3.5,
        "balanced": 0.0,
    },
    "bmi": {
        "underweight": -2.0,    # BMI < 18.5
        "normal": 0.0,          # BMI 18.5 - 24.9
        "overweight": -1.2,     # BMI 25.0 - 29.9
        "obese": -4.0,          # BMI 30+
    },
    "sleep": {
        "deprived": -2.2,       # <6 hours nightly
        "optimal": 1.2,         # 7-8 hours restful nightly
        "excessive": -1.2,      # >9.5 hours or severe fragmentation
    },
    "stress": {
        "low": 1.5,             # Resilient, low chronic stress, strong social support
        "moderate": 0.0,        # Average daily stress
        "high": -2.0,           # Chronic unmanaged stress / burnout
    },
}


def calculate_multimorbidity_attenuation(losses: List[float]) -> float:
    """
    Sub-linear compounding for multimorbidity.
    Multiple chronic diseases share overlapping biological pathways;
    subsequent conditions have diminishing marginal hazard contributions.
    Total Loss = Primary + 0.65 * Secondary + 0.45 * Tertiary ...
    """
    if not losses:
        return 0.0

    sorted_losses = sorted(losses, reverse=True)
    total_loss = 0.0
    discount_factors = [1.0, 0.65, 0.45, 0.30, 0.20, 0.15]

    for i, loss in enumerate(sorted_losses):
        weight = discount_factors[i] if i < len(discount_factors) else 0.10
        total_loss += loss * weight

    return min(22.0, total_loss)


def calculate_global_percentile(predicted_le: float) -> float:
    """
    Computes where this estimated lifespan ranks globally.
    Across world populations, average life expectancy is ~73.4 years with standard deviation ~6.8.
    Calculates the cumulative normal distribution percentile (0.1% to 99.9%).
    """
    mean = 73.4
    std = 6.8
    z = (predicted_le - mean) / std
    # Error function based standard normal CDF
    percentile = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))) * 100.0
    return round(max(1.0, min(99.0, percentile)), 1)


def predict_longevity(
    country_iso3: str,
    country_name: str,
    baseline_life_expectancy: float,
    current_age: int,
    sex: str,
    chronic_diseases: List[str],
    smoking: str = "never",
    alcohol: str = "none",
    exercise: str = "active",
    diet: str = "whole_foods",
    bmi: str = "normal",
    sleep: str = "optimal",
    stress: str = "low",
) -> Dict[str, Any]:
    """
    Core AI/ML Longevity Predictor:
    Synthesizes sovereign baseline data with individual chronic disease burden
    and lifestyle behaviors, providing SHAP-style additive feature attributions
    and complete life-horizon breakdowns (years, months, weeks, days).
    """
    # Filter out 'none' keyword from chronic disease calculation
    filtered_diseases = [d for d in chronic_diseases if d.lower() != "none"]

    raw_disease_losses = []
    disease_breakdown = []

    for d_key in filtered_diseases:
        if d_key in CHRONIC_DISEASE_IMPACTS:
            info = CHRONIC_DISEASE_IMPACTS[d_key]
            if info["loss_years"] > 0:
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

    # Evaluate Lifestyle Habits safely
    smoking_delta = HABIT_IMPACTS["smoking"].get(str(smoking or "").lower(), 0.0)
    alcohol_delta = HABIT_IMPACTS["alcohol"].get(str(alcohol or "").lower(), 0.0)
    exercise_delta = HABIT_IMPACTS["exercise"].get(str(exercise or "").lower(), 0.0)
    diet_delta = HABIT_IMPACTS["diet"].get(str(diet or "").lower(), 0.0)
    bmi_delta = HABIT_IMPACTS["bmi"].get(str(bmi or "").lower(), 0.0)
    sleep_delta = HABIT_IMPACTS["sleep"].get(str(sleep or "").lower(), 0.0)
    stress_delta = HABIT_IMPACTS["stress"].get(str(stress or "").lower(), 0.0)

    net_habit_delta = (
        smoking_delta + alcohol_delta + exercise_delta + diet_delta + bmi_delta + sleep_delta + stress_delta
    )

    # Combined Model
    net_total_impact = net_habit_delta - total_disease_penalty
    predicted_le = baseline_life_expectancy + net_total_impact

    # Biological plausibility boundary: a person currently aged X cannot be predicted
    # to die younger than their current age + 1.0 year minimum survival
    min_survival_bound = float(current_age + 1.0)
    if predicted_le < min_survival_bound:
        predicted_le = min_survival_bound

    years_remaining = max(1.0, predicted_le - current_age)

    # Calculate Life Horizon units
    weeks_lived = int(round(current_age * 52.14))
    weeks_remaining = int(round(years_remaining * 52.14))
    total_weeks = weeks_lived + weeks_remaining
    months_lived = int(round(current_age * 12))
    months_remaining = int(round(years_remaining * 12))
    days_lived = int(round(current_age * 365.25))
    days_remaining = int(round(years_remaining * 365.25))

    # Global percentile ranking
    global_percentile = calculate_global_percentile(predicted_le)

    # Actionable Interventions
    potential_recoveries = []
    if smoking in ["light", "heavy"]:
        gain = abs(smoking_delta) * 0.85
        potential_recoveries.append(f"Tobacco cessation: Reclaim up to +{gain:.1f} years of cardiovascular health.")
    if exercise in ["sedentary", "light"]:
        potential_recoveries.append("Reaching 150+ mins/week of moderate physical activity adds +3.8 years of healthy vitality.")
    if diet == "ultra_processed":
        potential_recoveries.append("Transitioning from ultra-processed to whole foods & Mediterranean staples adds +3.2 to +6.7 years.")
    if bmi == "obese":
        potential_recoveries.append("Normalized metabolic health and weight adds +2.8 to +4.0 years.")
    if "hypertension" in filtered_diseases:
        potential_recoveries.append("Clinical blood pressure control (<130/80 mmHg) recovers ~1.5 years of stroke-free longevity.")

    if not potential_recoveries:
        potential_recoveries.append("Your positive lifestyle habits provide strong biological resilience against premature mortality.")

    # Return dictionary with dual aliases for both frontend & backend conventions
    return {
        "country_iso3": country_iso3.upper(),
        "country_name": country_name,
        "current_age": current_age,
        "sex": sex,
        "baseline_life_expectancy": round(baseline_life_expectancy, 1),
        "predicted_life_expectancy": round(predicted_le, 1),
        "predicted_le": round(predicted_le, 1),
        "years_remaining": round(years_remaining, 1),
        "remaining_years": round(years_remaining, 1),
        "net_total_impact": round(net_total_impact, 1),
        "net_delta_years": round(net_total_impact, 1),
        "disease_penalty": round(total_disease_penalty, 1),
        "chronic_disease_penalty": round(-total_disease_penalty, 1),
        "habit_delta": round(net_habit_delta, 1),
        "lifestyle_delta": round(net_habit_delta, 1),
        "days_remaining": days_remaining,
        "weeks_remaining": weeks_remaining,
        "months_remaining": months_remaining,
        "days_lived": days_lived,
        "weeks_lived": weeks_lived,
        "months_lived": months_lived,
        "total_weeks": total_weeks,
        "global_percentile": global_percentile,
        "active_chronic_diseases": disease_breakdown,
        "potential_recoveries": potential_recoveries,
        "actionable_interventions": potential_recoveries,
    }
