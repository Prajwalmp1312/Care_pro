import unittest
from datetime import date
import sys
import types

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    fastapi_stub = types.ModuleType("fastapi")
    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
    fastapi_stub.APIRouter = object
    fastapi_stub.Depends = lambda value=None: value
    fastapi_stub.File = lambda *args, **kwargs: None
    fastapi_stub.Query = lambda value=None, *args, **kwargs: value
    fastapi_stub.UploadFile = object
    fastapi_stub.HTTPException = HTTPException
    fastapi_stub.status = types.SimpleNamespace(HTTP_413_REQUEST_ENTITY_TOO_LARGE=413)
    sys.modules["fastapi"] = fastapi_stub

try:
    import pydantic  # noqa: F401
except ModuleNotFoundError:
    pydantic_stub = types.ModuleType("pydantic")
    pydantic_stub.BaseModel = type("BaseModel", (), {})
    sys.modules["pydantic"] = pydantic_stub

try:
    import sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    sqlalchemy_stub = types.ModuleType("sqlalchemy")
    sqlalchemy_stub.text = lambda value: value
    sqlalchemy_orm_stub = types.ModuleType("sqlalchemy.orm")
    sqlalchemy_orm_stub.Session = object
    sys.modules["sqlalchemy"] = sqlalchemy_stub
    sys.modules["sqlalchemy.orm"] = sqlalchemy_orm_stub

if "database" not in sys.modules:
    database_stub = types.ModuleType("database")
    database_stub.engine = object()
    database_stub.get_db = lambda: None
    sys.modules["database"] = database_stub

from meal_planner import (
    _apply_calorie_target,
    _canonical_allergies,
    _fallback_plan,
    _nutrition_targets,
    _phase,
    _plan_safety_issues,
    _parse_gemini_json,
    _saved_plan_payload,
    _user_payload,
)
from ai_resilience import call_with_transient_retry, provider_status_code


class ProviderError(Exception):
    def __init__(self, code):
        super().__init__(f"provider returned {code}")
        self.code = code


class AIResilienceTests(unittest.TestCase):
    def test_transient_capacity_error_is_retried_then_succeeds(self):
        calls = []
        delays = []

        def operation():
            calls.append(True)
            if len(calls) < 3:
                raise ProviderError(503)
            return "generated"

        result = call_with_transient_retry(
            operation,
            attempts=3,
            base_delay_seconds=0.5,
            sleep=delays.append,
            random_value=lambda: 0.5,
        )

        self.assertEqual(result, "generated")
        self.assertEqual(len(calls), 3)
        self.assertEqual(delays, [0.5, 1.0])

    def test_non_transient_error_is_not_retried(self):
        calls = []

        def operation():
            calls.append(True)
            raise ProviderError(400)

        with self.assertRaises(ProviderError):
            call_with_transient_retry(operation, attempts=3, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)

    def test_status_can_be_extracted_from_provider_message(self):
        self.assertEqual(provider_status_code(RuntimeError("503 UNAVAILABLE")), 503)


class MealPlannerSafetyTests(unittest.TestCase):
    def test_common_allergen_names_are_canonicalized(self):
        self.assertEqual(
            _canonical_allergies(["Peanut", "PEANUTS", "Tofu", "Milk"]),
            ["peanuts", "soy", "milk"],
        )

    def test_fish_and_soy_are_detected_in_generated_ingredients(self):
        plan = {
            "dinner": {"ingredients": ["baked salmon", "tofu"]},
        }
        issues = _plan_safety_issues(plan, ["fish", "soy"], "any")
        self.assertEqual({issue["reason"] for issue in issues}, {"allergy:fish", "allergy:soy"})

    def test_vegan_diet_rejects_animal_products(self):
        plan = {"breakfast": {"ingredients": ["Greek yogurt", "eggs"]}}
        issues = _plan_safety_issues(plan, [], "vegan")
        self.assertGreaterEqual(len(issues), 2)

    def test_fallback_avoids_declared_major_allergens(self):
        plan = _fallback_plan({
            "mood": "healthy",
            "dietary": "vegetarian",
            "allergies": ["milk", "fish", "soy", "tree nuts"],
            "available_ingredients": ["tofu", "spinach"],
            "servings": 2,
        })
        self.assertEqual(_plan_safety_issues(plan, ["milk", "fish", "soy", "tree nuts"], "vegetarian"), [])
        self.assertTrue(plan["safety_validation"]["passed"])

    def test_calorie_distribution_reaches_target_with_rounding_tolerance(self):
        plan = _fallback_plan({"dietary": "any", "allergies": []})
        _apply_calorie_target(plan, 2200)
        self.assertLessEqual(abs(plan["total_calories"] - 2200), 30)
        self.assertLessEqual(plan["total_calories"], 2200)

    def test_user_calorie_limit_replaces_estimate_and_recalculates_macros(self):
        patient = types.SimpleNamespace(age=40, gender="female")
        profile = {
            "weight": 70,
            "height_cm": 165,
            "activity_level": "moderate",
            "purpose": "Improve Health",
        }
        targets = _nutrition_targets(patient, profile, 1750)
        self.assertEqual(targets["calories"], 1750)
        self.assertEqual(targets["source"], "user_limit")
        self.assertEqual(targets["protein_g"], 109)

    def test_locked_unsafe_meal_is_rejected(self):
        with self.assertRaises(ValueError):
            _fallback_plan({
                "dietary": "any",
                "allergies": ["fish"],
                "locked_meals": {"dinner": {"name": "Salmon", "calories": 500, "ingredients": ["salmon"]}},
            })


class MealPlannerWorkflowTests(unittest.TestCase):
    def test_gemini_parser_accepts_labeled_calories_and_minutes(self):
        meal = {
            "name": "Vegetable bowl",
            "calories": "420 kcal",
            "prep_time": "15 minutes",
            "ingredients": ["vegetables", "rice"],
            "instructions": ["Cook", "Serve"],
        }
        parsed = _parse_gemini_json(__import__("json").dumps({
            "breakfast": meal,
            "lunch": meal,
            "dinner": meal,
            "snack": meal,
        }))
        self.assertEqual(parsed["breakfast"]["calories"], 420)
        self.assertEqual(parsed["breakfast"]["prep_time"], 15)
        self.assertEqual(parsed["total_calories"], 1680)

    def test_shared_patient_measurements_override_legacy_meal_profile(self):
        patient = types.SimpleNamespace(
            id=7,
            name="Patient",
            age=35,
            email="patient@example.com",
            gender="female",
            weight_kg=64.5,
            height_cm=168,
        )
        profile = {
            "username": "legacy",
            "weight": 91,
            "weight_unit": "lb",
            "height_cm": 180,
            "purpose": "Improve Health",
            "profile_completed": True,
            "track_menstrual_cycle": False,
            "last_period_date": None,
            "cycle_length": 28,
        }
        payload = _user_payload(patient, {**profile, "weight": patient.weight_kg, "weight_unit": "kg", "height_cm": patient.height_cm})
        self.assertEqual(payload["weight"], 64.5)
        self.assertEqual(payload["height_cm"], 168)
        self.assertEqual(payload["weight_unit"], "kg")

    def test_cycle_phase_boundaries(self):
        start = date(2026, 1, 1)
        self.assertEqual(_phase(start, 28, start)[0], "menstrual")
        self.assertEqual(_phase(start, 28, date(2026, 1, 6))[0], "follicular")
        self.assertEqual(_phase(start, 28, date(2026, 1, 14))[0], "ovulation")
        self.assertEqual(_phase(start, 28, date(2026, 1, 17))[0], "luteal")

    def test_saved_plan_payload_preserves_complete_recipe(self):
        recipe = {
            "breakfast": {"name": "Oats", "calories": 400, "prep_time": 10, "ingredients": ["oats"], "instructions": "Cook."},
            "lunch": {"name": "Bowl", "calories": 500, "ingredients": ["rice"], "instructions": "Mix."},
            "dinner": {"name": "Soup", "calories": 500, "ingredients": ["lentils"], "instructions": "Simmer."},
            "snack": {"name": "Fruit", "calories": 150, "ingredients": ["apple"], "instructions": "Serve."},
            "warnings": ["General wellness only."],
        }
        payload = _saved_plan_payload({
            "id": 1,
            "plan_json": __import__("json").dumps(recipe),
            "warnings_json": __import__("json").dumps(recipe["warnings"]),
            "preferences_json": "{}",
            "context_json": "{}",
        })
        self.assertEqual(payload["plan"]["breakfast"]["ingredients"], ["oats"])
        self.assertEqual(payload["warnings"], ["General wellness only."])


if __name__ == "__main__":
    unittest.main()
