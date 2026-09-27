from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import engine, get_db

logger = logging.getLogger(__name__)


def _json(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _row(row: Any) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _ensure_column(conn: Any, table_name: str, column_name: str, definition: str) -> None:
    """Apply additive MySQL schema upgrades without rebuilding user tables."""
    exists = conn.execute(
        text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
        """),
        {"table_name": table_name, "column_name": column_name},
    ).scalar()
    if not exists:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))


def init_meal_planner_schema() -> None:
    """Create the Meal Planner tables in the CareConnect database."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS meal_planner_profiles (
          patient_id INT PRIMARY KEY,
          username VARCHAR(255) UNIQUE NOT NULL,
          weight DECIMAL(6,2) NOT NULL DEFAULT 70,
          weight_unit VARCHAR(3) NOT NULL DEFAULT 'kg',
          height_cm DECIMAL(5,1) NOT NULL DEFAULT 170,
          purpose VARCHAR(255) NOT NULL DEFAULT 'Improve Health',
          allergies JSON NULL,
          intolerances JSON NULL,
          disliked_ingredients JSON NULL,
          dietary_preferences JSON NULL,
          default_cuisine VARCHAR(100) NOT NULL DEFAULT 'Any',
          available_time_minutes INT NOT NULL DEFAULT 30,
          budget_level VARCHAR(20) NOT NULL DEFAULT 'moderate',
          servings INT NOT NULL DEFAULT 1,
          activity_level VARCHAR(30) NOT NULL DEFAULT 'moderate',
          profile_completed BOOLEAN NOT NULL DEFAULT FALSE,
          track_menstrual_cycle BOOLEAN NOT NULL DEFAULT FALSE,
          last_period_date DATE NULL,
          cycle_length INT NOT NULL DEFAULT 28,
          menstrual_preferences JSON NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          CONSTRAINT fk_meal_profile_patient FOREIGN KEY (patient_id)
            REFERENCES patients(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS saved_meal_plans (
          id INT AUTO_INCREMENT PRIMARY KEY,
          patient_id INT NOT NULL,
          meal_plan_name VARCHAR(255) DEFAULT 'My Meal Plan',
          mood_context VARCHAR(50) NOT NULL,
          breakfast_name VARCHAR(255) NOT NULL,
          breakfast_calories INT NOT NULL,
          lunch_name VARCHAR(255) NOT NULL,
          lunch_calories INT NOT NULL,
          dinner_name VARCHAR(255) NOT NULL,
          dinner_calories INT NOT NULL,
          snack_name VARCHAR(255) NOT NULL,
          snack_calories INT NOT NULL,
          total_calories INT NOT NULL,
          plan_json LONGTEXT NULL,
          warnings_json LONGTEXT NULL,
          preferences_json LONGTEXT NULL,
          context_json LONGTEXT NULL,
          generation_source VARCHAR(30) NOT NULL DEFAULT 'legacy',
          scheduled_date DATE NULL,
          servings INT NOT NULL DEFAULT 1,
          completion_status VARCHAR(20) NOT NULL DEFAULT 'planned',
          feedback_rating INT NULL,
          feedback_notes TEXT NULL,
          date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_saved_plan_patient (patient_id),
          CONSTRAINT fk_saved_plan_patient FOREIGN KEY (patient_id)
            REFERENCES patients(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS menstrual_cycle_logs (
          id INT AUTO_INCREMENT PRIMARY KEY,
          patient_id INT NOT NULL,
          period_start_date DATE NULL,
          period_end_date DATE NULL,
          cravings JSON NULL,
          symptoms JSON NULL,
          notes TEXT NULL,
          log_date DATE NOT NULL,
          mood VARCHAR(50) NULL,
          energy_level VARCHAR(50) NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY unique_patient_log_date (patient_id, log_date),
          CONSTRAINT fk_cycle_log_patient FOREIGN KEY (patient_id)
            REFERENCES patients(id) ON DELETE CASCADE
        )
        """,
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        profile_columns = {
            "allergies": "JSON NULL",
            "intolerances": "JSON NULL",
            "disliked_ingredients": "JSON NULL",
            "height_cm": "DECIMAL(5,1) NOT NULL DEFAULT 170",
            "dietary_preferences": "JSON NULL",
            "default_cuisine": "VARCHAR(100) NOT NULL DEFAULT 'Any'",
            "available_time_minutes": "INT NOT NULL DEFAULT 30",
            "budget_level": "VARCHAR(20) NOT NULL DEFAULT 'moderate'",
            "servings": "INT NOT NULL DEFAULT 1",
            "activity_level": "VARCHAR(30) NOT NULL DEFAULT 'moderate'",
        }
        plan_columns = {
            "plan_json": "LONGTEXT NULL",
            "warnings_json": "LONGTEXT NULL",
            "preferences_json": "LONGTEXT NULL",
            "context_json": "LONGTEXT NULL",
            "generation_source": "VARCHAR(30) NOT NULL DEFAULT 'legacy'",
            "scheduled_date": "DATE NULL",
            "servings": "INT NOT NULL DEFAULT 1",
            "completion_status": "VARCHAR(20) NOT NULL DEFAULT 'planned'",
            "feedback_rating": "INT NULL",
            "feedback_notes": "TEXT NULL",
        }
        for column_name, definition in profile_columns.items():
            _ensure_column(conn, "meal_planner_profiles", column_name, definition)
        for column_name, definition in plan_columns.items():
            _ensure_column(conn, "saved_meal_plans", column_name, definition)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_migrations (
              migration_key VARCHAR(190) PRIMARY KEY,
              applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        _migrate_legacy_meal_planner(conn)


def _migrate_legacy_meal_planner(conn: Any) -> None:
    """Copy legacy Express data once when meal_planner_db is still present."""
    migration_key = "merge_meal_planner_db_v1"
    if conn.execute(
        text("SELECT 1 FROM app_migrations WHERE migration_key=:key"),
        {"key": migration_key},
    ).first():
        return
    legacy_exists = conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.SCHEMATA "
        "WHERE SCHEMA_NAME='meal_planner_db'"
    )).scalar()
    if not legacy_exists:
        return
    savepoint = conn.begin_nested()
    try:
        conn.execute(text("""
            INSERT IGNORE INTO meal_planner_profiles
              (patient_id, username, weight, weight_unit, purpose,
               profile_completed, track_menstrual_cycle, last_period_date,
               cycle_length, menstrual_preferences)
            SELECT p.id, u.username, u.weight, u.weight_unit, u.purpose,
                   u.profile_completed, u.track_menstrual_cycle,
                   u.last_period_date, u.cycle_length, u.menstrual_preferences
              FROM meal_planner_db.users u
              JOIN patients p ON LOWER(p.email)=LOWER(u.email)
        """))
        conn.execute(text("""
            INSERT INTO saved_meal_plans
              (patient_id, meal_plan_name, mood_context,
               breakfast_name, breakfast_calories, lunch_name, lunch_calories,
               dinner_name, dinner_calories, snack_name, snack_calories,
               total_calories, date_created)
            SELECT p.id, s.meal_plan_name, s.mood_context,
                   s.breakfast_name, s.breakfast_calories,
                   s.lunch_name, s.lunch_calories,
                   s.dinner_name, s.dinner_calories,
                   s.snack_name, s.snack_calories,
                   s.total_calories, s.date_created
              FROM meal_planner_db.saved_meal_plans s
              JOIN patients p ON LOWER(p.email)=LOWER(s.user_email)
        """))
        conn.execute(text("""
            INSERT IGNORE INTO menstrual_cycle_logs
              (patient_id, period_start_date, period_end_date, cravings,
               symptoms, notes, log_date, mood, energy_level, created_at, updated_at)
            SELECT p.id, l.period_start_date, l.period_end_date, l.cravings,
                   l.symptoms, l.notes, l.log_date, l.mood, l.energy_level,
                   l.created_at, l.updated_at
              FROM meal_planner_db.menstrual_cycle_logs l
              JOIN meal_planner_db.users u ON u.id=l.user_id
              JOIN patients p ON LOWER(p.email)=LOWER(u.email)
        """))
        conn.execute(
            text("INSERT INTO app_migrations (migration_key) VALUES (:key)"),
            {"key": migration_key},
        )
        savepoint.commit()
        logger.info("Migrated legacy meal_planner_db data into CareConnect")
    except Exception as exc:
        # New installations and partially initialized legacy databases should
        # still start; the migration remains unapplied and can retry next boot.
        savepoint.rollback()
        logger.warning("Legacy Meal Planner data migration skipped: %s", exc)


def _patient(current_user: Any) -> Any:
    if getattr(current_user, "role", None) != "patient":
        raise HTTPException(status_code=403, detail="Patient access required")
    return current_user


def _username(email: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]", "_", email.split("@", 1)[0])[:40] or "patient"
    return f"cc_{base}"


def _ensure_profile(db: Session, patient: Any) -> dict[str, Any]:
    profile = db.execute(
        text("SELECT * FROM meal_planner_profiles WHERE patient_id = :id"),
        {"id": patient.id},
    ).mappings().first()
    if not profile:
        username = _username(patient.email)
        suffix = 1
        while db.execute(
            text("SELECT 1 FROM meal_planner_profiles WHERE username = :username"),
            {"username": username},
        ).first():
            username = f"{_username(patient.email)}_{suffix}"
            suffix += 1
        db.execute(
            text(
                "INSERT INTO meal_planner_profiles "
                "(patient_id, username, weight, weight_unit, height_cm, profile_completed) "
                "VALUES (:patient_id, :username, :weight, 'kg', :height_cm, :profile_completed)"
            ),
            {
                "patient_id": patient.id,
                "username": username,
                "weight": float(getattr(patient, "weight_kg", None) or 70),
                "height_cm": float(getattr(patient, "height_cm", None) or 170),
                "profile_completed": bool(
                    getattr(patient, "weight_kg", None)
                    and getattr(patient, "height_cm", None)
                ),
            },
        )
        db.commit()
        profile = db.execute(
            text("SELECT * FROM meal_planner_profiles WHERE patient_id = :id"),
            {"id": patient.id},
        ).mappings().first()
    result = dict(profile)
    # CareConnect's patient record is the canonical source for shared body
    # measurements. The legacy Meal Planner columns remain only so existing
    # installations can be migrated without losing data.
    if getattr(patient, "weight_kg", None) is not None:
        result["weight"] = float(patient.weight_kg)
        result["weight_unit"] = "kg"
    if getattr(patient, "height_cm", None) is not None:
        result["height_cm"] = float(patient.height_cm)
    return result


def _user_payload(patient: Any, profile: dict[str, Any]) -> dict[str, Any]:
    sex = str(getattr(patient, "gender", "") or "Other").capitalize()
    if sex not in {"Male", "Female", "Other"}:
        sex = "Other"
    return {
        "id": patient.id,
        "username": profile["username"],
        "name": patient.name,
        "age": patient.age or 30,
        "email": patient.email,
        "sex": sex,
        "weight": float(profile["weight"]),
        "weight_unit": profile["weight_unit"],
        "height_cm": float(profile.get("height_cm") or 170),
        "purpose": profile["purpose"],
        "allergies": _json(profile.get("allergies"), []),
        "intolerances": _json(profile.get("intolerances"), []),
        "disliked_ingredients": _json(profile.get("disliked_ingredients"), []),
        "dietary_preferences": _json(profile.get("dietary_preferences"), []),
        "default_cuisine": profile.get("default_cuisine") or "Any",
        "available_time_minutes": int(profile.get("available_time_minutes") or 30),
        "budget_level": profile.get("budget_level") or "moderate",
        "servings": int(profile.get("servings") or 1),
        "activity_level": profile.get("activity_level") or "moderate",
        "profile_completed": bool(profile["profile_completed"]),
        "auth_provider": "careconnect",
        "track_menstrual_cycle": bool(profile["track_menstrual_cycle"]),
        "last_period_date": profile["last_period_date"],
        "cycle_length": profile["cycle_length"],
    }


def _phase(last_period: date, cycle_length: int, on_date: date | None = None) -> tuple[str, int]:
    day = (((on_date or date.today()) - last_period).days % cycle_length) + 1
    if day <= 5:
        return "menstrual", day
    if day <= 13:
        return "follicular", day
    if day <= 16:
        return "ovulation", day
    return "luteal", day


PHASE_ADVICE = {
    "menstrual": ("Choose iron-rich foods, protein, and warm balanced meals.", ["iron", "vitamin C", "protein"]),
    "follicular": ("Favor fresh produce, whole grains, and lean proteins.", ["fiber", "B vitamins", "protein"]),
    "ovulation": ("Choose colorful produce, hydration, and balanced proteins.", ["antioxidants", "zinc", "omega-3"]),
    "luteal": ("Favor fiber-rich foods and regular balanced meals.", ["magnesium", "calcium", "fiber"]),
}

ALLERGEN_TERMS = {
    "peanuts": {"peanut", "peanuts", "groundnut", "groundnuts"},
    "tree nuts": {"almond", "almonds", "cashew", "cashews", "walnut", "walnuts", "pecan", "pecans", "pistachio", "pistachios", "hazelnut", "hazelnuts", "macadamia", "tree nut", "tree nuts"},
    "milk": {"milk", "butter", "cheese", "yogurt", "yoghurt", "cream", "whey", "casein", "ghee"},
    "eggs": {"egg", "eggs", "mayonnaise", "meringue"},
    "fish": {"fish", "salmon", "tuna", "cod", "tilapia", "trout", "sardine", "sardines", "anchovy", "anchovies"},
    "shellfish": {"shellfish", "shrimp", "prawn", "prawns", "crab", "lobster", "clam", "clams", "mussel", "mussels", "oyster", "oysters", "scallop", "scallops"},
    "soy": {"soy", "soya", "tofu", "tempeh", "edamame", "miso"},
    "wheat": {"wheat", "flour", "bread", "pasta", "couscous", "bulgur", "semolina"},
    "sesame": {"sesame", "tahini"},
    "gluten": {"gluten", "wheat", "barley", "rye", "bread", "pasta", "couscous", "bulgur", "semolina"},
}

DIET_BLOCKED_TERMS = {
    "vegetarian": ALLERGEN_TERMS["fish"] | ALLERGEN_TERMS["shellfish"] | {"chicken", "turkey", "beef", "pork", "lamb", "bacon", "ham", "meat"},
    "vegan": ALLERGEN_TERMS["fish"] | ALLERGEN_TERMS["shellfish"] | ALLERGEN_TERMS["milk"] | ALLERGEN_TERMS["eggs"] | {"chicken", "turkey", "beef", "pork", "lamb", "bacon", "ham", "meat", "honey"},
    "gluten-free": ALLERGEN_TERMS["gluten"],
    "dairy-free": ALLERGEN_TERMS["milk"],
    "paleo": ALLERGEN_TERMS["milk"] | {"rice", "oats", "quinoa", "corn", "bread", "pasta", "bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "tofu", "soy", "sugar"},
    "low-carb": {"bread", "pasta", "rice", "oats", "quinoa", "couscous", "potato", "potatoes", "sugar"},
    "keto-friendly": {"bread", "pasta", "rice", "oats", "quinoa", "couscous", "potato", "potatoes", "sugar", "beans", "lentils"},
}


def _normalise_phrase(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _contains_term(value: Any, term: str) -> bool:
    haystack = f" {_normalise_phrase(value)} "
    needle = f" {_normalise_phrase(term)} "
    return needle in haystack


def _canonical_allergies(values: Any) -> list[str]:
    result: list[str] = []
    for raw in values or []:
        clean = _normalise_phrase(raw)
        if not clean:
            continue
        canonical = next(
            (name for name, terms in ALLERGEN_TERMS.items() if clean == name or clean in terms),
            clean,
        )
        if canonical not in result:
            result.append(canonical)
    return result


def _blocked_terms(allergies: list[str], dietary: str) -> dict[str, set[str]]:
    blocked: dict[str, set[str]] = {}
    for allergy in _canonical_allergies(allergies):
        blocked[f"allergy:{allergy}"] = set(ALLERGEN_TERMS.get(allergy, {allergy}))
    diet = _normalise_phrase(dietary).replace(" ", "-")
    if diet in DIET_BLOCKED_TERMS:
        blocked[f"diet:{diet}"] = set(DIET_BLOCKED_TERMS[diet])
    return blocked


def _plan_safety_issues(plan: dict[str, Any], allergies: list[str], dietary: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    blocked = _blocked_terms(allergies, dietary)
    for meal_type in ("breakfast", "lunch", "dinner", "snack"):
        meal = plan.get(meal_type) or {}
        for ingredient in meal.get("ingredients") or []:
            for reason, terms in blocked.items():
                term = next((candidate for candidate in terms if _contains_term(ingredient, candidate)), None)
                if term:
                    issues.append({"meal": meal_type, "ingredient": str(ingredient), "reason": reason, "matched_term": term})
    return issues


def _safe_choice(candidates: list[str], allergies: list[str], dietary: str) -> str:
    blocked = _blocked_terms(allergies, dietary)
    for candidate in candidates:
        if not any(_contains_term(candidate, term) for terms in blocked.values() for term in terms):
            return candidate
    raise HTTPException(422, "No safe ingredient option could be selected for the declared restrictions")


def _validate_plan(plan: dict[str, Any], allergies: list[str], dietary: str) -> dict[str, Any]:
    issues = _plan_safety_issues(plan, allergies, dietary)
    if issues:
        logger.warning("Rejected unsafe generated meal plan: %s", issues)
        raise ValueError("Generated plan did not pass allergy and dietary validation")
    plan["safety_validation"] = {
        "passed": True,
        "allergies_checked": _canonical_allergies(allergies),
        "diet_checked": dietary or "any",
        "checked_meals": ["breakfast", "lunch", "dinner", "snack"],
    }
    return plan


def _nutrition_targets(
    patient: Any,
    profile: dict[str, Any],
    calorie_limit: int | None = None,
) -> dict[str, Any]:
    """Return a conservative wellness estimate for display and meal distribution."""
    weight_kg = float(profile.get("weight") or 70)
    height_cm = float(profile.get("height_cm") or 170)
    age = min(max(int(getattr(patient, "age", None) or 30), 18), 100)
    gender = str(getattr(patient, "gender", "") or "").lower()
    sex_adjustment = 5 if gender == "male" else -161 if gender == "female" else -78
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + sex_adjustment
    activity_multiplier = {
        "sedentary": 1.2,
        "light": 1.35,
        "moderate": 1.5,
        "active": 1.7,
        "very-active": 1.85,
    }.get(str(profile.get("activity_level") or "moderate"), 1.5)
    calories = bmr * activity_multiplier
    purpose = str(profile.get("purpose") or "").lower()
    if any(word in purpose for word in ("lose", "loss", "reduce")):
        calories -= 300
    elif any(word in purpose for word in ("gain", "muscle", "bulk")):
        calories += 250
    estimated_calories = int(round(min(max(calories, 1200), 4000) / 50) * 50)
    calories = calorie_limit if calorie_limit is not None else estimated_calories
    return {
        "calories": calories,
        "source": "user_limit" if calorie_limit is not None else "careconnect_estimate",
        "estimated_calories": estimated_calories,
        "protein_g": round(calories * 0.25 / 4),
        "carbohydrates_g": round(calories * 0.45 / 4),
        "fat_g": round(calories * 0.30 / 9),
        "fiber_g": 25 if gender == "female" else 30,
    }


def _apply_calorie_target(plan: dict[str, Any], target_calories: int) -> dict[str, Any]:
    current = sum(int((plan.get(key) or {}).get("calories") or 0) for key in ("breakfast", "lunch", "dinner", "snack"))
    if current <= 0:
        return plan
    scale = target_calories / current
    for key in ("breakfast", "lunch", "dinner", "snack"):
        meal = plan.get(key) or {}
        meal["calories"] = max(100, int(round((int(meal.get("calories") or 0) * scale) / 10) * 10))
    plan["total_calories"] = sum(plan[key]["calories"] for key in ("breakfast", "lunch", "dinner", "snack"))
    # Rounding each meal independently can otherwise put the day slightly over
    # the requested limit. Reduce the largest meals until the hard cap is met.
    while plan["total_calories"] > target_calories:
        meal = max(
            (plan[key] for key in ("breakfast", "lunch", "dinner", "snack")),
            key=lambda item: int(item.get("calories") or 0),
        )
        reducible = max(int(meal.get("calories") or 0) - 100, 0)
        if reducible <= 0:
            break
        reduction = min(plan["total_calories"] - target_calories, reducible)
        meal["calories"] -= reduction
        plan["total_calories"] -= reduction
    return plan


def _cycle_payload(profile: dict[str, Any]) -> dict[str, Any]:
    last = profile.get("last_period_date")
    if not profile.get("track_menstrual_cycle") or not last:
        return {"tracking": False, "tracking_enabled": False, "message": "Menstrual cycle tracking not enabled"}
    length = int(profile.get("cycle_length") or 28)
    phase, current_day = _phase(last, length)
    next_period = last + timedelta(days=length)
    days_until = (next_period - date.today()).days
    advice, nutrients = PHASE_ADVICE[phase]
    return {
        "tracking": True,
        "tracking_enabled": True,
        "currentPhase": phase,
        "current_phase": phase,
        "current_day": current_day,
        "cycle_length": length,
        "period_length": 5,
        "last_period_date": last,
        "nextPeriod": next_period,
        "predicted_next_period": next_period,
        "daysUntilPeriod": days_until,
        "days_until_period": days_until,
        "prediction_confidence": "estimated",
        "prediction_note": "Cycle dates are estimates based on the last period date and typical cycle length; irregular cycles may differ.",
        "isApproachingPeriod": 0 < days_until <= 3,
        "is_approaching_period": 0 < days_until <= 3,
        "nutritionAdvice": advice,
        "nutrition_advice": advice,
        "keyNutrients": nutrients,
        "key_nutrients": nutrients,
        "preferences": _json(profile.get("menstrual_preferences"), None),
    }


def _fallback_plan(payload: dict[str, Any]) -> dict[str, Any]:
    mood = payload.get("mood") or "healthy"
    diet = str(payload.get("dietary") or "any").lower()
    safety_allergies = _canonical_allergies(payload.get("allergies") or [])
    allergies = [
        *safety_allergies,
        *_clean_list(payload.get("intolerances")),
        *_clean_list(payload.get("disliked_ingredients")),
    ]
    vegan = "vegan" in diet
    vegetarian = vegan or "vegetarian" in diet
    low_carb = diet in {"low-carb", "keto-friendly", "paleo"}
    breakfast_base = _safe_choice(
        ["chia pudding", "certified gluten-free oats", "rolled oats", "quinoa porridge", "sweet potato hash"],
        allergies,
        diet,
    )
    creamy_base = _safe_choice(
        ["unsweetened coconut yogurt", "plain Greek yogurt", "oat yogurt", "mashed banana"],
        allergies,
        diet,
    )
    topping = _safe_choice(["pumpkin seeds", "sunflower seeds", "almonds", "fresh berries"], allergies, diet)
    lunch_protein = _safe_choice(
        (["roasted chickpeas", "lentils", "tofu", "black beans"] if vegetarian else ["grilled chicken", "turkey", "lentils", "tofu"]),
        allergies,
        diet,
    )
    dinner_protein = _safe_choice(
        (["lentils", "tofu", "chickpeas", "black beans"] if vegetarian else ["baked salmon", "grilled chicken", "turkey", "lentils"]),
        allergies,
        diet,
    )
    lunch_base = _safe_choice(
        (["cauliflower rice", "mixed greens", "zucchini noodles"] if low_carb else ["quinoa", "brown rice", "mixed greens"]),
        allergies,
        diet,
    )
    dinner_side = _safe_choice(
        (["cauliflower", "zucchini", "broccoli"] if low_carb else ["sweet potato", "brown rice", "broccoli"]),
        allergies,
        diet,
    )
    fruit = _safe_choice(["berries", "apple", "pear", "orange"], allergies, diet)
    cuisine = str(payload.get("cuisine") or "any")
    servings = min(max(int(payload.get("servings") or 1), 1), 12)
    meals = {
        "breakfast": {"name": f"{fruit.title()} Breakfast Bowl", "calories": 390, "prep_time": 10, "servings": servings, "ingredients": [breakfast_base, creamy_base, fruit, topping], "instructions": "Combine the ingredients in a bowl and serve."},
        "lunch": {"name": f"{cuisine.title() if cuisine.lower() != 'any' else 'Garden'} {lunch_protein.title()} Bowl", "calories": 520, "prep_time": 20, "servings": servings, "ingredients": [lunch_protein, lunch_base, "spinach", "tomato", "cucumber", "lemon"], "instructions": "Cook the protein and base, then combine with the vegetables and lemon."},
        "dinner": {"name": f"{dinner_protein.title()} and Roasted Vegetables", "calories": 570, "prep_time": 30, "servings": servings, "ingredients": [dinner_protein, dinner_side, "broccoli", "olive oil", "herbs"], "instructions": "Roast the vegetables, cook the protein thoroughly, and serve together."},
        "snack": {"name": f"{fruit.title()} Snack Cup", "calories": 190, "prep_time": 5, "servings": servings, "ingredients": [creamy_base, fruit, topping], "instructions": "Combine and serve chilled."},
    }
    extras = [
        str(item) for item in payload.get("available_ingredients") or []
        if not _plan_safety_issues({"lunch": {"ingredients": [item]}}, allergies, diet)
    ][:4]
    meals["lunch"]["ingredients"].extend(extras)
    locked = payload.get("locked_meals") or {}
    for meal_type in meals:
        if isinstance(locked.get(meal_type), dict):
            meals[meal_type] = locked[meal_type]
    plan = {
        "plan_id": f"{mood}_{int(datetime.now().timestamp())}",
        "mood_context": mood,
        **meals,
        "total_calories": sum(meal["calories"] for meal in meals.values()),
        "warnings": ["This plan is general wellness guidance and not a prescribed medical diet."],
        "generation_source": "standard_fallback",
    }
    nutrition_targets = payload.get("nutrition_targets")
    if isinstance(nutrition_targets, dict) and nutrition_targets.get("calories"):
        _apply_calorie_target(plan, int(nutrition_targets["calories"]))
        plan["nutrition_targets"] = nutrition_targets
    plan = _validate_plan(plan, safety_allergies, diet)
    plan["preferences_respected"] = {
        "intolerances": _clean_list(payload.get("intolerances")),
        "disliked_ingredients": _clean_list(payload.get("disliked_ingredients")),
    }
    return plan


def _labeled_int(
    value: Any,
    field_name: str,
    *,
    default: int = 0,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    """Parse integers that may include labels such as '15 minutes' or '420 kcal'."""
    if value in (None, ""):
        result = default
    elif isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    elif isinstance(value, (int, float)):
        result = int(round(float(value)))
    else:
        match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
        if not match:
            raise ValueError(f"{field_name} must contain a number")
        result = int(round(float(match.group(0))))
    if result < minimum or (maximum is not None and result > maximum):
        upper = f" and {maximum}" if maximum is not None else ""
        raise ValueError(f"{field_name} must be between {minimum}{upper}")
    return result


def _parse_gemini_json(raw: str) -> dict[str, Any]:
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Gemini did not return a JSON object")
    plan = json.loads(value[start : end + 1])
    total = 0
    for key in ("breakfast", "lunch", "dinner", "snack"):
        meal = plan.get(key)
        if not isinstance(meal, dict) or not meal.get("name") or not isinstance(meal.get("ingredients"), list):
            raise ValueError(f"Gemini response is missing {key}")
        meal["calories"] = _labeled_int(
            meal.get("calories"), f"{key} calories", maximum=5000
        )
        meal["prep_time"] = _labeled_int(
            meal.get("prep_time"), f"{key} prep time", maximum=600
        )
        meal["instructions"] = " ".join(meal.get("instructions")) if isinstance(meal.get("instructions"), list) else str(meal.get("instructions") or "")
        total += meal["calories"]
    plan["total_calories"] = total
    plan["warnings"] = plan.get("warnings") if isinstance(plan.get("warnings"), list) else []
    return plan


class JsonBody(BaseModel):
    model_config = {"extra": "allow"}


def _clean_list(value: Any, limit: int = 30) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        clean = str(item or "").strip()[:100]
        if clean and clean.lower() not in {entry.lower() for entry in result}:
            result.append(clean)
    return result[:limit]


def _preference_payload(data: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    try:
        time_minutes = _labeled_int(
            data.get("available_time_minutes", profile.get("available_time_minutes") or 30),
            "Available cooking time",
            default=30,
            minimum=5,
            maximum=240,
        )
        servings = _labeled_int(
            data.get("servings", profile.get("servings") or 1),
            "Servings",
            default=1,
            minimum=1,
            maximum=12,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    budget = str(data.get("budget_level", profile.get("budget_level") or "moderate")).lower()
    activity = str(data.get("activity_level", profile.get("activity_level") or "moderate")).lower()
    if budget not in {"low", "moderate", "flexible"}:
        raise HTTPException(400, "Budget level must be low, moderate, or flexible")
    if activity not in {"sedentary", "light", "moderate", "active", "very-active"}:
        raise HTTPException(400, "Unsupported activity level")
    return {
        "allergies": _canonical_allergies(data.get("allergies", _json(profile.get("allergies"), []))),
        "intolerances": _clean_list(data.get("intolerances", _json(profile.get("intolerances"), []))),
        "disliked_ingredients": _clean_list(data.get("disliked_ingredients", _json(profile.get("disliked_ingredients"), []))),
        "dietary_preferences": _clean_list(data.get("dietary_preferences", _json(profile.get("dietary_preferences"), []))),
        "default_cuisine": str(data.get("default_cuisine", profile.get("default_cuisine") or "Any"))[:100],
        "available_time_minutes": time_minutes,
        "budget_level": budget,
        "servings": servings,
        "activity_level": activity,
    }


def get_meal_profile_settings(db: Session, patient: Any) -> dict[str, Any]:
    """Return Meal Planner settings as part of the unified CareConnect profile."""
    profile = _ensure_profile(db, patient)
    return {
        "weight_kg": float(profile.get("weight") or 70),
        "height_cm": float(profile.get("height_cm") or 170),
        "purpose": profile.get("purpose") or "Improve Health",
        **_preference_payload({}, profile),
    }


def update_meal_profile_settings(
    db: Session,
    patient: Any,
    data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Update the meal-planning portion of the unified patient profile.

    The caller owns the transaction so patient measurements and meal settings
    are committed together by the main CareConnect profile endpoint.
    """
    profile = _ensure_profile(db, patient)
    incoming = data if isinstance(data, dict) else {}
    preferences = _preference_payload(incoming, profile)
    purpose = str(incoming.get("purpose", profile.get("purpose") or "Improve Health")).strip()[:255]
    if not purpose:
        raise HTTPException(400, "A health goal is required")

    weight_kg = float(getattr(patient, "weight_kg", None) or profile.get("weight") or 70)
    height_cm = float(getattr(patient, "height_cm", None) or profile.get("height_cm") or 170)
    db.execute(text("""
        UPDATE meal_planner_profiles
        SET weight=:weight,
            weight_unit='kg',
            height_cm=:height_cm,
            purpose=:purpose,
            allergies=:allergies,
            intolerances=:intolerances,
            disliked_ingredients=:disliked_ingredients,
            dietary_preferences=:dietary_preferences,
            default_cuisine=:default_cuisine,
            available_time_minutes=:available_time_minutes,
            budget_level=:budget_level,
            servings=:servings,
            activity_level=:activity_level,
            profile_completed=TRUE
        WHERE patient_id=:patient_id
    """), {
        **preferences,
        "weight": weight_kg,
        "height_cm": height_cm,
        "purpose": purpose,
        "allergies": json.dumps(preferences["allergies"]),
        "intolerances": json.dumps(preferences["intolerances"]),
        "disliked_ingredients": json.dumps(preferences["disliked_ingredients"]),
        "dietary_preferences": json.dumps(preferences["dietary_preferences"]),
        "patient_id": patient.id,
    })
    return {"purpose": purpose, **preferences}


def _care_context(db: Session, patient: Any, profile: dict[str, Any]) -> dict[str, Any]:
    prescriptions = list(db.execute(
        text("""
            SELECT medicine_name FROM prescriptions
            WHERE patient_email=:email AND COALESCE(status, 'active')='active'
            ORDER BY created_at DESC LIMIT 10
        """),
        {"email": patient.email},
    ).mappings())
    records = list(db.execute(
        text("""
            SELECT key_findings FROM medical_records
            WHERE patient_email=:email ORDER BY uploaded_at DESC LIMIT 3
        """),
        {"email": patient.email},
    ).mappings())
    feedback_rows = list(db.execute(
        text("""
            SELECT meal_plan_name, feedback_rating, feedback_notes
            FROM saved_meal_plans
            WHERE patient_id=:patient_id AND feedback_rating IS NOT NULL
            ORDER BY date_created DESC LIMIT 5
        """),
        {"patient_id": patient.id},
    ).mappings())
    findings: list[str] = []
    for record in records:
        findings.extend(str(item)[:250] for item in _json(record.get("key_findings"), []) if item)
    return {
        "patient_goal": profile.get("purpose") or "Improve Health",
        "activity_level": profile.get("activity_level") or "moderate",
        "health_status": getattr(patient, "status", None) or "not specified",
        "age": getattr(patient, "age", None),
        "active_medications": [str(row.get("medicine_name"))[:100] for row in prescriptions if row.get("medicine_name")],
        "recent_findings": findings[:6],
        "recent_meal_feedback": [
            {
                "plan": str(row.get("meal_plan_name") or "")[:100],
                "rating": row.get("feedback_rating"),
                "notes": str(row.get("feedback_notes") or "")[:300],
            }
            for row in feedback_rows
        ],
        "medical_diet_authorized": False,
    }


def _saved_plan_payload(row: Any) -> dict[str, Any]:
    data = dict(row)
    plan = _json(data.get("plan_json"), None)
    if not isinstance(plan, dict):
        plan = {
            meal_type: {
                "name": data.get(f"{meal_type}_name"),
                "calories": data.get(f"{meal_type}_calories"),
                "ingredients": [],
                "instructions": "Recipe details were not stored for this legacy plan.",
                "prep_time": None,
            }
            for meal_type in ("breakfast", "lunch", "dinner", "snack")
        }
        plan.update({"mood_context": data.get("mood_context"), "total_calories": data.get("total_calories")})
    data["plan"] = plan
    data["warnings"] = _json(data.get("warnings_json"), plan.get("warnings", []))
    data["preferences"] = _json(data.get("preferences_json"), {})
    data["context_used"] = _json(data.get("context_json"), {})
    data.pop("plan_json", None)
    data.pop("warnings_json", None)
    data.pop("preferences_json", None)
    data.pop("context_json", None)
    return data


def build_meal_planner_router(
    get_current_user: Callable[..., Any], gemini_model: Any = None
) -> APIRouter:
    router = APIRouter(prefix="/api/meal-planner", tags=["Meal Planner"])

    def current_patient(current_user=Depends(get_current_user)):
        return _patient(current_user)

    @router.post("/careconnect/session")
    def create_session(patient=Depends(current_patient), db: Session = Depends(get_db)):
        profile = _ensure_profile(db, patient)
        context = _care_context(db, patient, profile)
        return {
            "token": None,
            "user": _user_payload(patient, profile),
            "care_context": {
                "health_status": patient.status,
                "blood_type": patient.blood_type,
                "active_prescription_count": db.execute(text("SELECT COUNT(*) FROM prescriptions WHERE patient_email=:email AND COALESCE(status, 'active')='active'"), {"email": patient.email}).scalar() or 0,
                "recent_record_count": db.execute(text("SELECT COUNT(*) FROM medical_records WHERE patient_email=:email"), {"email": patient.email}).scalar() or 0,
                "personalization": context,
            },
        }

    @router.put("/preferences")
    def update_preferences(body: JsonBody, patient=Depends(current_patient), db: Session = Depends(get_db)):
        settings = update_meal_profile_settings(db, patient, body.model_dump())
        db.commit()
        updated = _ensure_profile(db, patient)
        return {"message": "Profile preferences saved", "preferences": settings, "user": _user_payload(patient, updated)}

    @router.post("/generate-ai-meal")
    def generate_meal(body: JsonBody, patient=Depends(current_patient), db: Session = Depends(get_db)):
        data = body.model_dump()
        profile = _ensure_profile(db, patient)
        stored_preferences = _preference_payload({}, profile)
        request_allergies = _clean_list(data.get("allergies"))
        data["allergies"] = _canonical_allergies([*stored_preferences["allergies"], *request_allergies])
        data["intolerances"] = _clean_list(data.get("intolerances") or stored_preferences["intolerances"])
        data["disliked_ingredients"] = _clean_list(data.get("disliked_ingredients") or stored_preferences["disliked_ingredients"])
        data["dietary"] = str(data.get("dietary") or (stored_preferences["dietary_preferences"] or ["any"])[0])
        data["cuisine"] = str(data.get("cuisine") or stored_preferences["default_cuisine"] or "any")
        try:
            data["available_time_minutes"] = _labeled_int(
                data.get("available_time_minutes") or stored_preferences["available_time_minutes"],
                "Available cooking time",
                minimum=5,
                maximum=240,
            )
            data["servings"] = _labeled_int(
                data.get("servings") or stored_preferences["servings"],
                "Servings",
                minimum=1,
                maximum=12,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        data["budget_level"] = str(data.get("budget_level") or stored_preferences["budget_level"])
        calorie_limit = None
        if data.get("calorie_limit") not in (None, ""):
            try:
                calorie_limit = _labeled_int(
                    data["calorie_limit"],
                    "Daily calorie limit",
                    minimum=1200,
                    maximum=5000,
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        data["calorie_limit"] = calorie_limit
        data["nutrition_targets"] = _nutrition_targets(patient, profile, calorie_limit)
        care_context = _care_context(db, patient, profile)
        fallback = _fallback_plan(data)
        context_used = {
            "careconnect": True,
            "fallback": gemini_model is None,
            "factors": [
                "patient goal",
                "activity level",
                "age",
                "declared allergies",
                "dietary preference",
                "cuisine",
                "cooking time",
                "budget",
                "servings",
                "user calorie limit" if calorie_limit is not None else "estimated calorie target",
                *( ["cycle phase"] if data.get("menstrualData") else [] ),
                *( ["active medication awareness"] if care_context["active_medications"] else [] ),
                *( ["recent record awareness"] if care_context["recent_findings"] else [] ),
                *( ["private meal feedback"] if care_context["recent_meal_feedback"] else [] ),
            ],
            "clinical_context": care_context,
        }
        fallback["context_used"] = context_used
        if care_context["active_medications"]:
            fallback["warnings"].append("Medication-food interactions were not verified. Confirm medication-specific dietary questions with your clinician or pharmacist.")
        if gemini_model is None:
            return fallback
        prompt = f"""You are the nutrition feature inside CareConnect. Create one practical day of meals for this request:
{json.dumps(data, default=str)}

CareConnect context (use only for conservative general-wellness personalization):
{json.dumps(care_context, default=str)}

Hard requirements:
- Exclude every declared allergy and every ingredient incompatible with the dietary preference.
- Respect the calorie target, servings, budget, cooking-time limit, cuisine, pantry ingredients, and locked meals.
- Never diagnose, prescribe a medical diet, claim medication-food compatibility, or advise changing medication.
- If clinical context suggests a medical question, add a warning to consult a clinician or registered dietitian.
Return only valid JSON with keys mood_context, breakfast, lunch, dinner, snack, warnings. Each meal must contain name, calories, prep_time, servings, ingredients (array), and instructions."""
        try:
            plan = _parse_gemini_json(gemini_model.generate_content(prompt).text)
            for meal_type, locked_meal in (data.get("locked_meals") or {}).items():
                if meal_type in {"breakfast", "lunch", "dinner", "snack"} and isinstance(locked_meal, dict):
                    plan[meal_type] = locked_meal
            plan["mood_context"] = data.get("mood") or "healthy"
            plan["plan_id"] = f"{plan['mood_context']}_{int(datetime.now().timestamp())}"
            plan["generation_source"] = "ai_generated"
            plan["nutrition_targets"] = data["nutrition_targets"]
            _apply_calorie_target(plan, data["nutrition_targets"]["calories"])
            _validate_plan(plan, data["allergies"], data["dietary"])
            if _plan_safety_issues(plan, [*data["intolerances"], *data["disliked_ingredients"]], "any"):
                raise ValueError("Generated plan included an intolerance or disliked ingredient")
            plan["preferences_respected"] = {"intolerances": data["intolerances"], "disliked_ingredients": data["disliked_ingredients"]}
            context_used["fallback"] = False
            plan["context_used"] = context_used
            if care_context["active_medications"]:
                plan.setdefault("warnings", []).append("Medication-food interactions were not verified. Confirm medication-specific dietary questions with your clinician or pharmacist.")
            return plan
        except Exception as exc:
            logger.warning("Gemini meal generation failed; using fallback: %s", exc)
            fallback["context_used"]["fallback"] = True
            return fallback

    @router.post("/swap-meal")
    def swap_meal(body: JsonBody, patient=Depends(current_patient), db: Session = Depends(get_db)):
        data = body.model_dump()
        meal_type = str(data.get("meal_type") or "")
        current_plan = data.get("current_plan")
        if meal_type not in {"breakfast", "lunch", "dinner", "snack"} or not isinstance(current_plan, dict):
            raise HTTPException(400, "A valid meal_type and current_plan are required")
        locked_meals = {
            key: current_plan[key]
            for key in ("breakfast", "lunch", "dinner", "snack")
            if key != meal_type and isinstance(current_plan.get(key), dict)
        }
        request = {
            **(data.get("preferences") or {}),
            "mood": current_plan.get("mood_context") or "healthy",
            "locked_meals": locked_meals,
            "exclude_meal_name": (current_plan.get(meal_type) or {}).get("name"),
        }
        updated_plan = generate_meal(JsonBody(**request), patient, db)
        return {"meal_type": meal_type, "meal": updated_plan[meal_type], "plan": updated_plan}

    @router.post("/save-meal-plan", status_code=201)
    def save_plan(body: JsonBody, patient=Depends(current_patient), db: Session = Depends(get_db)):
        data = body.model_dump()
        required = ("moodContext", "breakfast", "lunch", "dinner", "snack")
        if any(not data.get(key) for key in required):
            raise HTTPException(400, "Mood context and all meal data are required")
        scheduled_date = data.get("scheduledDate") or None
        if scheduled_date:
            try:
                date.fromisoformat(str(scheduled_date))
            except ValueError as exc:
                raise HTTPException(400, "scheduledDate must use YYYY-MM-DD") from exc
        plan = {key: data[key] for key in ("breakfast", "lunch", "dinner", "snack")}
        plan.update({
            "mood_context": data["moodContext"],
            "total_calories": int(data.get("totalCalories") or 0),
            "warnings": data.get("warnings") or [],
            "nutrition_targets": data.get("nutritionTargets") or {},
        })
        profile = _ensure_profile(db, patient)
        stored_preferences = _preference_payload({}, profile)
        plan_preferences = data.get("preferences") or {}
        allergies = _canonical_allergies([*stored_preferences["allergies"], *_clean_list(plan_preferences.get("allergies"))])
        dietary = str(plan_preferences.get("dietary") or (stored_preferences["dietary_preferences"] or ["any"])[0])
        try:
            _validate_plan(plan, allergies, dietary)
            avoidances = [
                *_clean_list(plan_preferences.get("intolerances") or stored_preferences["intolerances"]),
                *_clean_list(plan_preferences.get("disliked_ingredients") or stored_preferences["disliked_ingredients"]),
            ]
            if _plan_safety_issues(plan, avoidances, "any"):
                raise ValueError("Plan includes a saved intolerance or disliked ingredient")
        except ValueError as exc:
            raise HTTPException(422, "This meal plan no longer passes your saved safety preferences") from exc
        params = {
            "patient_id": patient.id,
            "name": str(data.get("mealPlanName") or "My Meal Plan")[:255],
            "mood": data["moodContext"],
            "total": int(data.get("totalCalories") or 0),
            "plan_json": json.dumps(plan),
            "warnings_json": json.dumps(data.get("warnings") or []),
            "preferences_json": json.dumps(data.get("preferences") or {}),
            "context_json": json.dumps(data.get("contextUsed") or {}),
            "generation_source": str(data.get("generationSource") or "unknown")[:30],
            "scheduled_date": scheduled_date,
            "servings": min(max(int(data.get("servings") or 1), 1), 12),
        }
        for key in ("breakfast", "lunch", "dinner", "snack"):
            params[f"{key}_name"] = data[key]["name"]
            params[f"{key}_calories"] = int(data[key].get("calories") or 0)
        result = db.execute(text("""
            INSERT INTO saved_meal_plans
              (patient_id, meal_plan_name, mood_context,
               breakfast_name, breakfast_calories, lunch_name, lunch_calories,
               dinner_name, dinner_calories, snack_name, snack_calories,
               total_calories, plan_json, warnings_json, preferences_json,
               context_json, generation_source, scheduled_date, servings)
            VALUES
              (:patient_id,:name,:mood,
               :breakfast_name,:breakfast_calories,:lunch_name,:lunch_calories,
               :dinner_name,:dinner_calories,:snack_name,:snack_calories,
               :total,:plan_json,:warnings_json,:preferences_json,
               :context_json,:generation_source,:scheduled_date,:servings)
        """), params)
        db.commit()
        saved = db.execute(text("SELECT * FROM saved_meal_plans WHERE id=:id"), {"id": result.lastrowid}).mappings().first()
        return {"message": "Meal plan saved successfully", "savedPlan": _saved_plan_payload(saved)}

    @router.get("/saved-meal-plans/{email}")
    def saved_plans(email: str, patient=Depends(current_patient), db: Session = Depends(get_db)):
        if email.lower() != patient.email.lower():
            raise HTTPException(403, "You can only access your own meal plans")
        rows = db.execute(text("SELECT * FROM saved_meal_plans WHERE patient_id=:id ORDER BY COALESCE(scheduled_date, DATE(date_created)) DESC, date_created DESC"), {"id": patient.id}).mappings()
        return [_saved_plan_payload(row) for row in rows]

    @router.put("/saved-meal-plans/{plan_id}")
    def update_saved_plan(plan_id: int, body: JsonBody, patient=Depends(current_patient), db: Session = Depends(get_db)):
        data = body.model_dump()
        status_value = str(data.get("completion_status") or "planned")
        if status_value not in {"planned", "prepared", "completed", "skipped"}:
            raise HTTPException(400, "Unsupported completion status")
        rating = data.get("feedback_rating")
        if rating is not None and int(rating) not in {1, 2, 3, 4, 5}:
            raise HTTPException(400, "Feedback rating must be between 1 and 5")
        scheduled_date = data.get("scheduled_date") or None
        if scheduled_date:
            try:
                date.fromisoformat(str(scheduled_date))
            except ValueError as exc:
                raise HTTPException(400, "scheduled_date must use YYYY-MM-DD") from exc
        result = db.execute(text("""
            UPDATE saved_meal_plans
            SET completion_status=:status,
                scheduled_date=CASE WHEN :scheduled_provided THEN :scheduled_date ELSE scheduled_date END,
                feedback_rating=COALESCE(:rating, feedback_rating),
                feedback_notes=COALESCE(:notes, feedback_notes)
            WHERE id=:plan_id AND patient_id=:patient_id
        """), {
            "status": status_value,
            "scheduled_date": scheduled_date,
            "scheduled_provided": "scheduled_date" in data,
            "rating": int(rating) if rating is not None else None,
            "notes": str(data.get("feedback_notes") or "")[:2000] or None,
            "plan_id": plan_id,
            "patient_id": patient.id,
        })
        db.commit()
        if not result.rowcount:
            raise HTTPException(404, "Meal plan not found")
        updated = db.execute(text("SELECT * FROM saved_meal_plans WHERE id=:id"), {"id": plan_id}).mappings().first()
        return _saved_plan_payload(updated)

    @router.get("/grocery-list")
    def grocery_list(
        start: date | None = Query(None),
        end: date | None = Query(None),
        patient=Depends(current_patient),
        db: Session = Depends(get_db),
    ):
        start_date = start or date.today()
        end_date = end or start_date + timedelta(days=6)
        if end_date < start_date or (end_date - start_date).days > 31:
            raise HTTPException(400, "Grocery-list range must be between 1 and 31 days")
        rows = db.execute(text("""
            SELECT * FROM saved_meal_plans
            WHERE patient_id=:patient_id
              AND scheduled_date BETWEEN :start_date AND :end_date
              AND completion_status <> 'skipped'
            ORDER BY scheduled_date
        """), {"patient_id": patient.id, "start_date": start_date, "end_date": end_date}).mappings()
        items: dict[str, dict[str, Any]] = {}
        plan_count = 0
        for row in rows:
            plan_count += 1
            saved = _saved_plan_payload(row)
            for meal_type in ("breakfast", "lunch", "dinner", "snack"):
                for ingredient in (saved["plan"].get(meal_type) or {}).get("ingredients") or []:
                    key = _normalise_phrase(ingredient)
                    if not key:
                        continue
                    item = items.setdefault(key, {"ingredient": str(ingredient), "used_in": [], "occurrences": 0})
                    item["occurrences"] += 1
                    item["used_in"].append(f"{saved['meal_plan_name']} · {meal_type}")
        return {"start": start_date, "end": end_date, "plan_count": plan_count, "items": list(items.values())}

    @router.delete("/saved-meal-plans/{plan_id}")
    def delete_plan(plan_id: int, patient=Depends(current_patient), db: Session = Depends(get_db)):
        result = db.execute(text("DELETE FROM saved_meal_plans WHERE id=:plan_id AND patient_id=:patient_id"), {"plan_id": plan_id, "patient_id": patient.id})
        db.commit()
        if not result.rowcount:
            raise HTTPException(404, "Meal plan not found")
        return {"message": "Meal plan deleted successfully"}

    @router.get("/users/cycle/{patient_id}")
    @router.get("/cycle-info/{patient_id}")
    def get_cycle(patient_id: int, patient=Depends(current_patient), db: Session = Depends(get_db)):
        if patient_id != patient.id:
            raise HTTPException(403, "You can only access your own cycle data")
        return _cycle_payload(_ensure_profile(db, patient))

    @router.put("/users/cycle/{patient_id}")
    def update_cycle(patient_id: int, body: JsonBody, patient=Depends(current_patient), db: Session = Depends(get_db)):
        if patient_id != patient.id:
            raise HTTPException(403, "You can only update your own cycle data")
        data = body.model_dump()
        length = int(data.get("cycle_length") or 28)
        if not 21 <= length <= 45:
            raise HTTPException(400, "Cycle length must be between 21 and 45 days")
        db.execute(text("UPDATE meal_planner_profiles SET last_period_date=COALESCE(:last,last_period_date), cycle_length=:length, track_menstrual_cycle=TRUE WHERE patient_id=:id"), {"last": data.get("last_period_date"), "length": length, "id": patient.id})
        db.commit()
        return {"message": "Cycle settings updated successfully", "cycleData": _cycle_payload(_ensure_profile(db, patient))}

    @router.get("/cycle-logs/{patient_id}")
    def cycle_logs(patient_id: int, limit: int = 10, patient=Depends(current_patient), db: Session = Depends(get_db)):
        if patient_id != patient.id:
            raise HTTPException(403, "You can only access your own cycle logs")
        rows = db.execute(text("SELECT * FROM menstrual_cycle_logs WHERE patient_id=:id ORDER BY log_date DESC LIMIT :limit"), {"id": patient.id, "limit": min(max(limit, 1), 100)}).mappings()
        return [dict(row) for row in rows]

    @router.post("/log-cycle-entry", status_code=201)
    def log_cycle(body: JsonBody, patient=Depends(current_patient), db: Session = Depends(get_db)):
        data = body.model_dump()
        if not data.get("log_date"):
            raise HTTPException(400, "log_date is required")
        params = {"id": patient.id, "date": data["log_date"], "cravings": json.dumps(data.get("cravings") or []), "symptoms": json.dumps(data.get("symptoms") or []), "mood": data.get("mood"), "energy": str(data.get("energy_level") or ""), "notes": data.get("notes")}
        db.execute(text("INSERT INTO menstrual_cycle_logs (patient_id,log_date,cravings,symptoms,mood,energy_level,notes) VALUES (:id,:date,:cravings,:symptoms,:mood,:energy,:notes) ON DUPLICATE KEY UPDATE cravings=:cravings,symptoms=:symptoms,mood=:mood,energy_level=:energy,notes=:notes"), params)
        db.commit()
        return {"message": "Entry logged successfully"}

    @router.get("/analyze-cycle-patterns/{patient_id}")
    def analyze_patterns(patient_id: int, patient=Depends(current_patient), db: Session = Depends(get_db)):
        if patient_id != patient.id:
            raise HTTPException(403, "You can only access your own cycle data")
        logs = list(db.execute(text("SELECT cravings,symptoms,mood FROM menstrual_cycle_logs WHERE patient_id=:id ORDER BY log_date DESC LIMIT 50"), {"id": patient.id}).mappings())
        cravings, symptoms, moods = Counter(), Counter(), Counter()
        for log in logs:
            cravings.update(_json(log["cravings"], [])); symptoms.update(_json(log["symptoms"], []))
            if log["mood"]: moods.update([log["mood"]])
        return {"totalLogs": len(logs), "topCravings": [{"name": k, "count": v} for k, v in cravings.most_common(5)], "topSymptoms": [{"name": k, "count": v} for k, v in symptoms.most_common(5)], "moodTrends": [{"mood": k, "count": v} for k, v in moods.most_common()], "phasePatterns": {}}

    @router.post("/generate-cycle-insights")
    def cycle_insights(body: JsonBody, patient=Depends(current_patient)):
        logs = body.model_dump().get("logs") or []
        if len(logs) < 5:
            return {"message": "Need at least 5 log entries for AI insights", "summary": "Keep logging your symptoms and cravings to get personalized insights!"}
        return {"summary": "Your recent entries can help reveal recurring patterns. Continue tracking and discuss persistent or severe symptoms with a clinician.", "recommendations": ["Eat regular balanced meals.", "Stay hydrated.", "Keep tracking cravings, mood, and symptoms."], "cravingAlternatives": {}, "symptomManagement": {}}

    @router.post("/speech-mood")
    def speech_mood(body: JsonBody):
        transcript = str(body.model_dump().get("transcript") or "").lower()
        if not transcript:
            raise HTTPException(400, "transcript is required")
        moods = {"energetic": ("energy", "active", "energetic"), "comfort": ("sad", "comfort", "tired"), "spicy": ("spicy", "hot"), "fresh": ("fresh", "light")}
        mood = next((name for name, words in moods.items() if any(word in transcript for word in words)), "healthy")
        return {"mood": mood, "confidence": 0.75 if len(transcript.split()) >= 4 else 0.55, "language": "en"}

    @router.post("/chat")
    def chat(body: JsonBody, patient=Depends(current_patient), db: Session = Depends(get_db)):
        data = body.model_dump()
        message = str(data.get("message") or "").strip()
        if not message:
            raise HTTPException(400, "message is required")
        profile = _ensure_profile(db, patient)
        preferences = _preference_payload({}, profile)
        response = f"For {patient.name}, a balanced option is a meal with vegetables, whole grains, and a protein source. I will avoid your saved allergies ({', '.join(preferences['allergies']) or 'none declared'}). Tell me which ingredients you have, and I can narrow it down."
        if gemini_model is not None:
            try:
                response = gemini_model.generate_content(
                    f"You are CareConnect's meal-planning assistant. Give general wellness guidance, never recommend any declared allergy or intolerance, do not diagnose, and do not change medication. Server-verified meal preferences: {json.dumps(preferences, default=str)}. Patient goal/context: {json.dumps(data.get('user') or {}, default=str)}. User: {message}"
                ).text
            except Exception as exc:
                logger.warning("Gemini meal chat failed; using fallback: %s", exc)
        return {"response": response, "mood": "healthy", "language": "en", "user_context": {"personalized": True, "careconnect_aware": True}}

    @router.post("/detect-ingredients")
    async def detect_ingredients(image: UploadFile = File(...), patient=Depends(current_patient)):
        if not (image.content_type or "").startswith("image/"):
            raise HTTPException(400, "File must be an image")
        data = await image.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(400, "Image too large. Maximum size is 10MB.")
        ingredients: list[str] = []
        method, confidence = "Manual confirmation", "Manual"
        if gemini_model is not None:
            try:
                result = gemini_model.generate_content([
                    "Identify only visible food ingredients in this image. Return a JSON array of concise ingredient names and nothing else.",
                    {"mime_type": image.content_type, "data": data},
                ])
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", result.text.strip(), flags=re.I)
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    ingredients = [str(item).strip() for item in parsed if str(item).strip()]
                    method, confidence = "Gemini image analysis", "AI"
            except Exception as exc:
                logger.warning("Gemini ingredient detection failed: %s", exc)
        return {
            "ingredients": ingredients,
            "total_detected": len(ingredients),
            "food_items_found": len(ingredients),
            "detection_methods": method,
            "success": True,
            "confidence": confidence,
            "confirmation_required": True,
            "message": "Review and confirm every detected ingredient before using it in a plan.",
        }

    return router
