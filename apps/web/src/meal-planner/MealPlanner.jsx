import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Camera,
  ChefHat,
  CheckCircle2,
  Clock,
  Heart,
  Info,
  Lock,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Unlock,
  Utensils,
  X,
} from "lucide-react";
import Chatbot from "./Chatbot";
import CycleDashboard from "./CycleDashboard";
import CycleLogger from "./CycleLogger";
import CyclePhaseBadge from "./CyclePhaseBadge";
import UserMealPlans from "./UserMealPlans";
import {
  API_BASE_URL,
  authFetch,
  createCareConnectMealSession,
} from "./services/api";

const MOODS = [
  ["energetic", "⚡", "Energetic"],
  ["comfort", "🤗", "Comfort"],
  ["healthy", "🥗", "Healthy"],
  ["indulgent", "🍰", "Indulgent"],
  ["fresh", "🌿", "Fresh"],
  ["spicy", "🌶️", "Spicy"],
];

const DIETS = ["Any", "vegetarian", "vegan", "gluten-free", "keto-friendly", "high-protein", "low-carb", "dairy-free", "paleo", "mediterranean"];
const CUISINES = ["Any", "Italian", "Asian", "Mexican", "Indian", "American", "Mediterranean", "French", "Thai", "Japanese", "Greek", "Chinese"];
const COMMON_INGREDIENTS = ["Chicken", "Eggs", "Rice", "Pasta", "Tomatoes", "Spinach", "Broccoli", "Quinoa", "Salmon", "Lentils", "Potatoes", "Avocado"];
const COMMON_ALLERGIES = ["Peanuts", "Milk", "Eggs", "Fish", "Tree Nuts", "Shellfish", "Soy", "Wheat", "Sesame"];
const MEAL_LABELS = { breakfast: "🌅 Breakfast", lunch: "🥗 Lunch", dinner: "🍽️ Dinner", snack: "🍎 Snack" };

const ChipInput = ({ value, onChange, suggestions, placeholder, tone = "green" }) => {
  const [text, setText] = useState("");
  const add = (item) => {
    const clean = String(item || "").trim();
    if (clean && !value.some((existing) => existing.toLowerCase() === clean.toLowerCase())) {
      onChange([...value, clean]);
    }
    setText("");
  };

  return (
    <div>
      <div className="flex gap-2">
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add(text);
            }
          }}
          placeholder={placeholder}
          className="min-w-0 flex-1 rounded-lg border border-gray-200 px-3 py-2 outline-none focus:border-orange-400"
        />
        <button type="button" onClick={() => add(text)} className="rounded-lg bg-orange-500 px-3 text-white hover:bg-orange-600">
          <Plus size={18} />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((item) => (
          <button
            type="button"
            key={item}
            disabled={value.includes(item)}
            onClick={() => add(item)}
            className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700 hover:bg-gray-200 disabled:opacity-40"
          >
            {item}
          </button>
        ))}
      </div>
      {value.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {value.map((item) => (
            <span key={item} className={`flex items-center gap-1 rounded-full px-3 py-1 text-sm ${tone === "red" ? "bg-red-100 text-red-800" : "bg-green-100 text-green-800"}`}>
              {item}
              <button type="button" onClick={() => onChange(value.filter((entry) => entry !== item))} aria-label={`Remove ${item}`}>
                <X size={14} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

const MealCard = ({ type, meal, onOpen }) => (
  <button
    type="button"
    onClick={() => onOpen(meal)}
    className="w-full rounded-xl border border-orange-100 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
  >
    <p className="text-sm font-semibold text-orange-700">{MEAL_LABELS[type]}</p>
    <h4 className="mt-1 text-lg font-bold text-gray-800">{meal.name}</h4>
    <p className="mt-2 text-sm text-gray-500">{meal.calories} cal • {meal.prep_time} min</p>
  </button>
);

const RecipeModal = ({ meal, onClose }) => {
  if (!meal) return null;
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-2xl font-bold text-orange-600">{meal.name}</h3>
            <p className="mt-1 text-sm text-gray-500">{meal.calories} calories • {meal.prep_time} minutes</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-gray-100"><X /></button>
        </div>
        <h4 className="mt-6 font-bold text-gray-800">Ingredients</h4>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-gray-700">
          {(meal.ingredients || []).map((item) => <li key={item}>{item}</li>)}
        </ul>
        <h4 className="mt-6 font-bold text-gray-800">Instructions</h4>
        <p className="mt-2 whitespace-pre-wrap text-gray-700">{Array.isArray(meal.instructions) ? meal.instructions.join("\n") : meal.instructions}</p>
      </div>
    </div>
  );
};

const MealPlanner = ({ careConnectUser }) => {
  const [user, setUser] = useState(null);
  const [careContext, setCareContext] = useState(null);
  const [booting, setBooting] = useState(true);
  const [error, setError] = useState("");
  const [mood, setMood] = useState("healthy");
  const [diet, setDiet] = useState("Any");
  const [cuisine, setCuisine] = useState("Any");
  const [ingredients, setIngredients] = useState([]);
  const [allergies, setAllergies] = useState([]);
  const [intolerances, setIntolerances] = useState([]);
  const [dislikes, setDislikes] = useState([]);
  const [availableTime, setAvailableTime] = useState(30);
  const [budget, setBudget] = useState("moderate");
  const [servings, setServings] = useState(1);
  const [activityLevel, setActivityLevel] = useState("moderate");
  const [calorieLimit, setCalorieLimit] = useState("");
  const [pantryOnly, setPantryOnly] = useState(false);
  const [plan, setPlan] = useState(null);
  const [lockedMeals, setLockedMeals] = useState([]);
  const [swappingMeal, setSwappingMeal] = useState("");
  const [scanCandidates, setScanCandidates] = useState([]);
  const [scheduledDate, setScheduledDate] = useState("");
  const [selectedMeal, setSelectedMeal] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [showSave, setShowSave] = useState(false);
  const [showPlans, setShowPlans] = useState(false);
  const [showCycle, setShowCycle] = useState(false);
  const [showCycleLogger, setShowCycleLogger] = useState(false);
  const [cycleData, setCycleData] = useState(null);
  const [notice, setNotice] = useState("");
  const imageInput = useRef(null);
  const chatRef = useRef(null);

  const loadCycle = useCallback(async (mealUser) => {
    if (!mealUser?.id) return;
    try {
      const response = await authFetch(`${API_BASE_URL}/users/cycle/${mealUser.id}`);
      if (response.ok) setCycleData(await response.json());
    } catch (requestError) {
      console.warn("Cycle data unavailable", requestError);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        setBooting(true);
        const session = await createCareConnectMealSession();
        if (!active) return;
        setUser(session.user);
        setCareContext(session.care_context);
        setAllergies(Array.isArray(session.user.allergies) ? session.user.allergies : []);
        setIntolerances(Array.isArray(session.user.intolerances) ? session.user.intolerances : []);
        setDislikes(Array.isArray(session.user.disliked_ingredients) ? session.user.disliked_ingredients : []);
        setDiet(session.user.dietary_preferences?.[0] || "Any");
        setCuisine(session.user.default_cuisine || "Any");
        setAvailableTime(session.user.available_time_minutes || 30);
        setBudget(session.user.budget_level || "moderate");
        setServings(session.user.servings || 1);
        setActivityLevel(session.user.activity_level || "moderate");
        await loadCycle(session.user);
      } catch (requestError) {
        if (active) setError(requestError.message);
      } finally {
        if (active) setBooting(false);
      }
    })();
    return () => { active = false; };
  }, [loadCycle]);

  const detectIngredients = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setDetecting(true);
    try {
      const formData = new FormData();
      formData.append("image", file);
      const response = await authFetch(`${API_BASE_URL}/detect-ingredients`, { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Ingredient detection failed");
      setScanCandidates(data.ingredients || []);
      if (!(data.ingredients || []).length) setNotice("No ingredients were detected. You can add them manually.");
    } catch (requestError) {
      alert(requestError.message);
    } finally {
      setDetecting(false);
    }
  };

  const currentPreferences = () => ({
    dietary: diet === "Any" ? "any" : diet,
    cuisine: cuisine === "Any" ? "any" : cuisine,
    available_ingredients: ingredients,
    allergies,
    intolerances,
    disliked_ingredients: dislikes,
    available_time_minutes: Number(availableTime),
    budget_level: budget,
    servings: Number(servings),
    activity_level: activityLevel,
    calorie_limit: calorieLimit === "" ? null : Number(calorieLimit),
    pantry_only: pantryOnly,
  });

  const persistPreferences = async () => {
    const response = await authFetch(`${API_BASE_URL}/preferences`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        allergies,
        intolerances,
        disliked_ingredients: dislikes,
        dietary_preferences: diet === "Any" ? [] : [diet],
        default_cuisine: cuisine,
        available_time_minutes: Number(availableTime),
        budget_level: budget,
        servings: Number(servings),
        activity_level: activityLevel,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || "Could not save meal preferences");
    if (data.user) setUser(data.user);
  };

  const generatePlan = async () => {
    setGenerating(true);
    setError("");
    try {
      if (calorieLimit !== "" && (Number(calorieLimit) < 1200 || Number(calorieLimit) > 5000)) {
        throw new Error("Daily calorie limit must be between 1,200 and 5,000 kcal.");
      }
      await persistPreferences();
      let menstrualData = null;
      if (user?.sex === "Female" && user?.track_menstrual_cycle) {
        const cycleResponse = await authFetch(`${API_BASE_URL}/cycle-info/${user.id}`);
        if (cycleResponse.ok) menstrualData = await cycleResponse.json();
      }
      const response = await authFetch(`${API_BASE_URL}/generate-ai-meal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mood,
          ...currentPreferences(),
          menstrualData,
          locked_meals: Object.fromEntries(lockedMeals.filter((key) => plan?.[key]).map((key) => [key, plan[key]])),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Meal generation failed");
      setPlan(data);
      setNotice(data.generation_source === "standard_fallback" ? "A safe standard plan was used because AI generation was unavailable or did not pass validation." : "Your plan passed server-side allergy and dietary validation.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setGenerating(false);
    }
  };

  const swapMeal = async (mealType) => {
    if (!plan || lockedMeals.includes(mealType)) return;
    setSwappingMeal(mealType);
    setError("");
    try {
      const response = await authFetch(`${API_BASE_URL}/swap-meal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meal_type: mealType, current_plan: plan, preferences: currentPreferences() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Could not swap this meal");
      setPlan(data.plan);
      setNotice(`${MEAL_LABELS[mealType]} was replaced and the updated plan passed safety validation.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSwappingMeal("");
    }
  };

  const savePlan = async () => {
    if (!plan) return;
    setSaving(true);
    try {
      const response = await authFetch(`${API_BASE_URL}/save-meal-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userEmail: user.email,
          mealPlanName: saveName || `${mood} Meal Plan`,
          moodContext: plan.mood_context,
          breakfast: plan.breakfast,
          lunch: plan.lunch,
          dinner: plan.dinner,
          snack: plan.snack,
          totalCalories: plan.total_calories,
          warnings: plan.warnings || [],
          nutritionTargets: plan.nutrition_targets || {},
          preferences: currentPreferences(),
          contextUsed: plan.context_used || {},
          generationSource: plan.generation_source,
          scheduledDate: scheduledDate || null,
          servings,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Could not save the meal plan");
      setShowSave(false);
      setSaveName("");
      setScheduledDate("");
      setNotice("Meal plan saved. Open Saved plans to schedule, complete, or build a grocery list.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  if (booting) {
    return <div className="flex min-h-[420px] items-center justify-center"><Loader2 className="animate-spin text-orange-500" size={42} /></div>;
  }

  if (!user) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
        <h2 className="font-bold">Meal Planner could not start</h2>
        <p className="mt-2">{error || "Confirm that the Meal Planner API is running and shares the CareConnect JWT secret."}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-gradient-to-r from-orange-500 to-emerald-600 p-6 text-white shadow-lg">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-center">
          <div>
            <div className="flex items-center gap-2"><ChefHat /><span className="font-semibold uppercase tracking-wide">CareConnect Meal Planner</span></div>
            <h2 className="mt-2 text-3xl font-bold">Mood-aware meals connected to your care profile</h2>
            <p className="mt-2 max-w-3xl text-orange-50">Build safety-checked meals, confirm pantry ingredients, plan your week, create grocery lists, and track what worked.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => setShowPlans(true)} className="flex items-center gap-2 rounded-lg bg-white/15 px-4 py-2 hover:bg-white/25"><Heart size={18} /> Saved plans</button>
            {user.sex === "Female" && <button type="button" onClick={() => setShowCycle(true)} className="rounded-lg bg-white/15 px-4 py-2 hover:bg-white/25">Cycle dashboard</button>}
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3 text-sm">
          <span className="rounded-full bg-white/15 px-3 py-1">Status: {careContext?.health_status || "not specified"}</span>
          <span className="rounded-full bg-white/15 px-3 py-1">Active prescriptions: {careContext?.active_prescription_count || 0}</span>
          <span className="rounded-full bg-white/15 px-3 py-1">Recent records: {careContext?.recent_record_count || 0}</span>
          <CyclePhaseBadge cycleData={cycleData} onClick={() => setShowCycle(true)} />
        </div>
      </section>

      {error && <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700"><AlertTriangle className="mt-0.5" />{error}</div>}
      {notice && <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-800"><CheckCircle2 className="mt-0.5 shrink-0" />{notice}</div>}

      <section className="grid gap-6 xl:grid-cols-[400px_1fr]">
        <div className="space-y-5 rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
          <div>
            <div className="flex items-center justify-between gap-3">
              <div><p className="text-xs font-bold uppercase tracking-wide text-red-600">Step 1 · Safety</p><h3 className="font-bold text-gray-800">Food allergies</h3></div>
              <span className="rounded-full bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">Saved to profile</span>
            </div>
            <p className="mt-1 text-xs text-gray-500">Every generated and swapped meal is checked on the server.</p>
            <div className="mt-4"><ChipInput value={allergies} onChange={setAllergies} suggestions={COMMON_ALLERGIES} placeholder="Add an allergy" tone="red" /></div>
            <details className="mt-4 rounded-lg bg-slate-50 p-3">
              <summary className="cursor-pointer text-sm font-semibold text-slate-700">Intolerances and dislikes</summary>
              <p className="mt-2 text-xs text-slate-500">Keep medical allergies separate from foods you avoid for comfort or preference.</p>
              <div className="mt-3"><p className="mb-1 text-xs font-semibold text-slate-600">Intolerances</p><ChipInput value={intolerances} onChange={setIntolerances} suggestions={[]} placeholder="e.g. lactose" tone="red" /></div>
              <div className="mt-3"><p className="mb-1 text-xs font-semibold text-slate-600">Disliked ingredients</p><ChipInput value={dislikes} onChange={setDislikes} suggestions={[]} placeholder="e.g. mushrooms" /></div>
            </details>
          </div>
          <div className="border-t border-gray-100 pt-5">
            <p className="text-xs font-bold uppercase tracking-wide text-orange-600">Step 2 · Preferences</p>
            <h3 className="font-bold text-gray-800">Current mood</h3>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {MOODS.map(([id, emoji, label]) => (
                <button type="button" key={id} onClick={() => setMood(id)} className={`rounded-lg border p-3 text-left ${mood === id ? "border-orange-500 bg-orange-50 text-orange-800" : "border-gray-200 hover:border-orange-200"}`}>
                  <span className="mr-2">{emoji}</span>{label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <h3 className="font-bold text-gray-800">Dietary preference</h3>
            <select value={diet} onChange={(event) => setDiet(event.target.value)} className="mt-2 w-full rounded-lg border border-gray-200 px-3 py-2">
              {DIETS.map((item) => <option key={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <h3 className="font-bold text-gray-800">Cuisine</h3>
            <select value={cuisine} onChange={(event) => setCuisine(event.target.value)} className="mt-2 w-full rounded-lg border border-gray-200 px-3 py-2">
              {CUISINES.map((item) => <option key={item}>{item}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs font-semibold text-gray-600">Cooking time
              <select value={availableTime} onChange={(event) => setAvailableTime(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800"><option value={15}>15 minutes</option><option value={30}>30 minutes</option><option value={45}>45 minutes</option><option value={60}>60 minutes</option></select>
            </label>
            <label className="text-xs font-semibold text-gray-600">Budget
              <select value={budget} onChange={(event) => setBudget(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800"><option value="low">Low</option><option value="moderate">Moderate</option><option value="flexible">Flexible</option></select>
            </label>
            <label className="text-xs font-semibold text-gray-600">Servings
              <input type="number" min="1" max="12" value={servings} onChange={(event) => setServings(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800" />
            </label>
            <label className="text-xs font-semibold text-gray-600">Activity
              <select value={activityLevel} onChange={(event) => setActivityLevel(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800"><option value="sedentary">Sedentary</option><option value="light">Light</option><option value="moderate">Moderate</option><option value="active">Active</option><option value="very-active">Very active</option></select>
            </label>
            <label className="col-span-2 text-xs font-semibold text-gray-600">Daily calorie limit <span className="font-normal text-gray-400">(optional)</span>
              <div className="relative mt-1">
                <input type="number" min="1200" max="5000" step="50" value={calorieLimit} onChange={(event) => setCalorieLimit(event.target.value)} placeholder="Use CareConnect estimate" className="w-full rounded-lg border border-gray-200 px-3 py-2 pr-14 text-sm text-gray-800" />
                <span className="absolute right-3 top-2 text-sm text-gray-400">kcal</span>
              </div>
              <span className="mt-1 block font-normal text-gray-400">1,200–5,000 kcal per person. Leave blank to use your profile estimate.</span>
            </label>
          </div>
          <div className="rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
            <p className="font-semibold text-slate-800">Care profile used</p>
            <p className="mt-1">Goal: {user.purpose || "Improve Health"} · {activityLevel} activity · {careContext?.active_prescription_count || 0} active prescription(s)</p>
            <p className="mt-2 text-slate-500">Update height, weight, goals and saved food preferences from your CareConnect profile menu.</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between"><h3 className="font-bold text-gray-800">Available ingredients</h3><button type="button" onClick={() => imageInput.current?.click()} className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700"><Camera size={17} />{detecting ? "Detecting..." : "Scan photo"}</button></div>
              <input ref={imageInput} type="file" accept="image/*" className="hidden" onChange={detectIngredients} />
              <div className="mt-4"><ChipInput value={ingredients} onChange={setIngredients} suggestions={COMMON_INGREDIENTS} placeholder="Add an ingredient" /></div>
            </div>
            <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-bold uppercase tracking-wide text-blue-600">Step 3 · Pantry</p>
              <h3 className="font-bold text-gray-800">How ingredient scanning works</h3>
              <p className="mt-2 text-sm text-gray-600">Detected foods are never added automatically. You review and confirm every item first.</p>
              <div className="mt-4 flex items-center gap-2 text-xs text-slate-500"><Info size={16} /> Images are analyzed in memory and are not returned or stored by this workflow.</div>
            </div>
          </div>

          <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-5 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-emerald-700">Step 4 · Review and generate</p>
                <p className="mt-1 text-sm text-emerald-900">{diet} · {cuisine} · {allergies.length ? `${allergies.length} allergen(s)` : "No allergies declared"} · {availableTime} min · {servings} serving(s) · {calorieLimit ? `${calorieLimit} kcal limit` : "Profile calorie estimate"}</p>
              </div>
              <button type="button" onClick={generatePlan} disabled={generating} className="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-orange-500 to-emerald-600 px-5 py-3 font-bold text-white disabled:opacity-60">
                {generating ? <Loader2 className="animate-spin" /> : <Sparkles />} {generating ? "Validating and generating..." : "Generate safe meal plan"}
              </button>
            </div>
          </div>

          {!plan ? (
            <div className="rounded-2xl border-2 border-dashed border-orange-200 bg-orange-50/50 p-12 text-center">
              <Utensils className="mx-auto text-orange-400" size={52} />
              <h3 className="mt-4 text-xl font-bold text-gray-800">Your personalized plan will appear here</h3>
              <p className="mt-2 text-gray-600">Confirm your safety settings and pantry, then generate a plan that is validated before display.</p>
            </div>
          ) : (
            <div className="space-y-5">
              <div className="rounded-2xl border border-orange-100 bg-white p-6 shadow-sm">
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                  <div><p className="text-sm font-semibold uppercase text-orange-600">{plan.mood_context} plan · {plan.generation_source === "ai_generated" ? "AI generated" : "Standard fallback"}</p><h3 className="text-2xl font-bold text-gray-800">{plan.total_calories} estimated calories</h3><p className="mt-1 text-xs text-gray-500">{plan.nutrition_targets?.source === "user_limit" ? "Your limit" : "CareConnect target"}: {plan.nutrition_targets?.calories || "not calculated"} calories · {servings} serving(s)</p></div>
                  <div className="flex gap-2">
                    <button type="button" onClick={generatePlan} className="flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2"><RefreshCw size={17} /> New plan</button>
                    <button type="button" onClick={() => setShowSave(true)} className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-white"><Save size={17} /> Save</button>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button type="button" onClick={() => { setAvailableTime(15); setNotice("Cooking time set to 15 minutes. Generate a new plan to apply it."); }} className="rounded-full bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700"><Clock size={14} className="mr-1 inline" />Make it faster</button>
                  <button type="button" onClick={() => { setBudget("low"); setNotice("Budget set to low. Generate a new plan to apply it."); }} className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">Make it cheaper</button>
                  <button type="button" onClick={() => { setPantryOnly((current) => !current); setNotice("Pantry-only preference updated. Generate a new plan to apply it."); }} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${pantryOnly ? "bg-violet-600 text-white" : "bg-violet-50 text-violet-700"}`}>Prioritize pantry</button>
                </div>
                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  {Object.keys(MEAL_LABELS).map((type) => plan[type] && (
                    <div key={type} className="space-y-2">
                      <MealCard type={type} meal={plan[type]} onOpen={setSelectedMeal} />
                      <div className="flex gap-2">
                        <button type="button" onClick={() => setLockedMeals((current) => current.includes(type) ? current.filter((item) => item !== type) : [...current, type])} className={`flex flex-1 items-center justify-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold ${lockedMeals.includes(type) ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-600"}`}>
                          {lockedMeals.includes(type) ? <Lock size={14} /> : <Unlock size={14} />} {lockedMeals.includes(type) ? "Locked" : "Lock meal"}
                        </button>
                        <button type="button" onClick={() => swapMeal(type)} disabled={lockedMeals.includes(type) || Boolean(swappingMeal)} className="flex flex-1 items-center justify-center gap-1 rounded-lg bg-orange-100 px-3 py-2 text-xs font-semibold text-orange-700 disabled:opacity-40">
                          <RefreshCw size={14} className={swappingMeal === type ? "animate-spin" : ""} /> {swappingMeal === type ? "Swapping" : "Swap meal"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-5 grid gap-3 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-2">
                  <div><p className="font-bold text-slate-800">Nutrition target</p><p className="mt-1 text-slate-600">Protein {plan.nutrition_targets?.protein_g || "—"}g · Carbs {plan.nutrition_targets?.carbohydrates_g || "—"}g · Fat {plan.nutrition_targets?.fat_g || "—"}g · Fiber {plan.nutrition_targets?.fiber_g || "—"}g</p></div>
                  <div><p className="font-bold text-slate-800">Safety and context</p><p className="mt-1 text-slate-600">{plan.safety_validation?.passed ? "Allergen and diet check passed" : "Validation unavailable"} · {(plan.context_used?.factors || []).length} personalization factor(s)</p></div>
                </div>
              </div>
              {plan.warnings?.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
                  <h4 className="font-bold">Safety reminders</h4>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{plan.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <p className="rounded-xl bg-blue-50 p-4 text-sm text-blue-800">Meal plans are general wellness suggestions. They do not replace medical advice, a prescribed diet, or medication guidance.</p>

      {scanCandidates.length > 0 && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50 p-4" onClick={() => setScanCandidates([])}>
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-start justify-between"><div><h3 className="text-xl font-bold text-gray-800">Confirm detected ingredients</h3><p className="mt-1 text-sm text-gray-500">Remove incorrect items or add anything the scan missed.</p></div><button type="button" onClick={() => setScanCandidates([])}><X /></button></div>
            <div className="mt-5"><ChipInput value={scanCandidates} onChange={setScanCandidates} suggestions={[]} placeholder="Add a missing ingredient" /></div>
            <div className="mt-6 flex gap-3"><button type="button" onClick={() => setScanCandidates([])} className="flex-1 rounded-lg bg-gray-100 py-2.5 font-semibold text-gray-700">Cancel</button><button type="button" onClick={() => { setIngredients((current) => [...new Set([...current, ...scanCandidates])]); setScanCandidates([]); setNotice("Confirmed ingredients were added to your pantry."); }} className="flex-1 rounded-lg bg-blue-600 py-2.5 font-semibold text-white">Confirm ingredients</button></div>
          </div>
        </div>
      )}

      <RecipeModal meal={selectedMeal} onClose={() => setSelectedMeal(null)} />
      {showSave && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-4" onClick={() => setShowSave(false)}><div className="w-full max-w-md rounded-2xl bg-white p-6" onClick={(event) => event.stopPropagation()}><h3 className="text-xl font-bold">Save and schedule meal plan</h3><label className="mt-4 block text-sm font-semibold text-gray-700">Plan name<input autoFocus value={saveName} onChange={(event) => setSaveName(event.target.value)} placeholder={`${mood} Meal Plan`} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 font-normal" /></label><label className="mt-4 block text-sm font-semibold text-gray-700">Schedule date (optional)<input type="date" value={scheduledDate} onChange={(event) => setScheduledDate(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 font-normal" /></label><div className="mt-5 flex gap-3"><button type="button" onClick={() => setShowSave(false)} className="flex-1 rounded-lg bg-gray-100 py-2">Cancel</button><button type="button" onClick={savePlan} disabled={saving} className="flex-1 rounded-lg bg-purple-600 py-2 text-white">{saving ? "Saving..." : "Save plan"}</button></div></div></div>}
      {showPlans && <UserMealPlans user={user} onClose={() => setShowPlans(false)} />}
      {showCycle && <CycleDashboard user={user} cycleData={cycleData} onClose={() => setShowCycle(false)} onUpdateCycle={(updated) => setCycleData(updated)} onOpenLogger={() => { setShowCycle(false); setShowCycleLogger(true); }} />}
      {showCycleLogger && <CycleLogger user={user} cycleData={cycleData} onClose={() => setShowCycleLogger(false)} onLogSaved={() => loadCycle(user)} />}
      <Chatbot ref={chatRef} user={user} />
    </div>
  );
};

export default MealPlanner;
