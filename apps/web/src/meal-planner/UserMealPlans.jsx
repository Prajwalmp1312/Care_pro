import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Loader2,
  ShoppingCart,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { API_BASE_URL, authFetch } from "./services/api";

const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];

const isoDate = (value) => {
  const date = value ? new Date(value) : new Date();
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 10);
};

const startOfWeek = () => {
  const result = new Date();
  result.setHours(12, 0, 0, 0);
  result.setDate(result.getDate() - result.getDay());
  return isoDate(result);
};

const addDays = (value, days) => {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + days);
  return isoDate(date);
};

const UserMealPlans = ({ user, onClose }) => {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [weekStart, setWeekStart] = useState(startOfWeek());
  const [grocery, setGrocery] = useState(null);
  const [groceryLoading, setGroceryLoading] = useState(false);
  const [feedback, setFeedback] = useState({ rating: 5, notes: "" });

  const loadPlans = useCallback(async () => {
    if (!user?.email) return;
    setLoading(true);
    setError("");
    try {
      const response = await authFetch(`${API_BASE_URL}/saved-meal-plans/${encodeURIComponent(user.email)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Could not load saved plans");
      setPlans(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [user?.email]);

  useEffect(() => { loadPlans(); }, [loadPlans]);

  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)), [weekStart]);
  const scheduledPlans = useMemo(() => Object.fromEntries(weekDays.map((day) => [day, plans.filter((plan) => String(plan.scheduled_date || "").slice(0, 10) === day)])), [plans, weekDays]);

  const updatePlan = async (planId, patch, successMessage) => {
    setError("");
    const response = await authFetch(`${API_BASE_URL}/saved-meal-plans/${planId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || "Could not update the plan");
    setPlans((current) => current.map((plan) => plan.id === planId ? data : plan));
    setSelectedPlan((current) => current?.id === planId ? data : current);
    setNotice(successMessage);
    return data;
  };

  const schedulePlan = async (plan, scheduledDate) => {
    try {
      await updatePlan(plan.id, { completion_status: plan.completion_status || "planned", scheduled_date: scheduledDate }, "Schedule updated.");
    } catch (requestError) { setError(requestError.message); }
  };

  const markStatus = async (plan, completionStatus) => {
    try {
      await updatePlan(plan.id, { completion_status: completionStatus, scheduled_date: plan.scheduled_date || null }, `Plan marked ${completionStatus}.`);
    } catch (requestError) { setError(requestError.message); }
  };

  const saveFeedback = async () => {
    if (!selectedPlan) return;
    try {
      await updatePlan(selectedPlan.id, {
        completion_status: selectedPlan.completion_status || "completed",
        scheduled_date: selectedPlan.scheduled_date || null,
        feedback_rating: feedback.rating,
        feedback_notes: feedback.notes,
      }, "Private meal feedback saved.");
    } catch (requestError) { setError(requestError.message); }
  };

  const deletePlan = async () => {
    if (!deleteTarget) return;
    const response = await authFetch(`${API_BASE_URL}/saved-meal-plans/${deleteTarget.id}`, { method: "DELETE" });
    if (response.ok) {
      setPlans((current) => current.filter((plan) => plan.id !== deleteTarget.id));
      if (selectedPlan?.id === deleteTarget.id) setSelectedPlan(null);
      setNotice("Meal plan deleted.");
      setDeleteTarget(null);
    } else {
      const data = await response.json();
      setError(data.detail || data.error || "Could not delete the plan");
    }
  };

  const loadGroceryList = async () => {
    setGroceryLoading(true);
    setError("");
    try {
      const response = await authFetch(`${API_BASE_URL}/grocery-list?start=${weekStart}&end=${addDays(weekStart, 6)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not build grocery list");
      setGrocery(data);
    } catch (requestError) { setError(requestError.message); }
    finally { setGroceryLoading(false); }
  };

  const openPlan = (plan) => {
    setSelectedPlan(plan);
    setFeedback({ rating: plan.feedback_rating || 5, notes: plan.feedback_notes || "" });
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/55 p-3">
      <div className="max-h-[94vh] w-full max-w-7xl overflow-y-auto rounded-2xl bg-slate-50 shadow-2xl">
        <header className="sticky top-0 z-10 flex items-center justify-between rounded-t-2xl bg-gradient-to-r from-purple-600 to-indigo-600 p-5 text-white">
          <div className="flex items-center gap-3"><CalendarDays /><div><h2 className="text-2xl font-bold">Saved plans and weekly schedule</h2><p className="text-sm text-purple-100">Recipes, planning, groceries and private progress</p></div></div>
          <button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-white/15" aria-label="Close"><X /></button>
        </header>

        <main className="space-y-6 p-5">
          {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
          {notice && <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-700"><CheckCircle2 size={18} />{notice}</div>}

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div><h3 className="text-lg font-bold text-slate-900">Week of {new Date(`${weekStart}T12:00:00`).toLocaleDateString()}</h3><p className="text-sm text-slate-500">Schedule one daily plan per date or keep several options.</p></div>
              <div className="flex gap-2"><button type="button" onClick={() => setWeekStart(addDays(weekStart, -7))} className="rounded-lg bg-slate-100 px-3 py-2 text-sm">Previous</button><button type="button" onClick={() => setWeekStart(startOfWeek())} className="rounded-lg bg-slate-100 px-3 py-2 text-sm">Current week</button><button type="button" onClick={() => setWeekStart(addDays(weekStart, 7))} className="rounded-lg bg-slate-100 px-3 py-2 text-sm">Next</button></div>
            </div>
            <div className="mt-5 grid gap-3 md:grid-cols-4 xl:grid-cols-7">
              {weekDays.map((day) => <div key={day} className="min-h-32 rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs font-bold uppercase text-slate-500">{new Date(`${day}T12:00:00`).toLocaleDateString(undefined, { weekday: "short" })}</p><p className="text-sm font-semibold text-slate-800">{new Date(`${day}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</p><div className="mt-3 space-y-2">{scheduledPlans[day].map((plan) => <button type="button" key={plan.id} onClick={() => openPlan(plan)} className="w-full rounded-lg bg-white p-2 text-left text-xs shadow-sm"><span className="font-semibold text-indigo-700">{plan.meal_plan_name}</span><span className="mt-1 block capitalize text-slate-500">{plan.completion_status}</span></button>)}</div></div>)}
            </div>
            <button type="button" onClick={loadGroceryList} disabled={groceryLoading} className="mt-5 flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 font-semibold text-white disabled:opacity-60">{groceryLoading ? <Loader2 size={18} className="animate-spin" /> : <ShoppingCart size={18} />}Build this week’s grocery list</button>
          </section>

          {grocery && <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5"><div className="flex items-center justify-between"><div><h3 className="font-bold text-emerald-900">Grocery list</h3><p className="text-sm text-emerald-700">Combined from {grocery.plan_count} scheduled plan(s)</p></div><button type="button" onClick={() => setGrocery(null)}><X size={18} /></button></div>{grocery.items.length ? <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{grocery.items.map((item) => <label key={item.ingredient} className="flex items-start gap-2 rounded-lg bg-white p-3 text-sm"><input type="checkbox" className="mt-1" /><span><span className="font-semibold text-slate-800">{item.ingredient}</span><span className="block text-xs text-slate-500">Used {item.occurrences} time(s)</span></span></label>)}</div> : <p className="mt-4 text-sm text-emerald-800">Schedule plans in this week to create a grocery list.</p>}</section>}

          <section>
            <div className="mb-4 flex items-center justify-between"><div><h3 className="text-xl font-bold text-slate-900">All saved plans</h3><p className="text-sm text-slate-500">{plans.length} plan(s)</p></div></div>
            {loading ? <div className="flex justify-center p-12"><Loader2 className="animate-spin text-purple-600" size={36} /></div> : !plans.length ? <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white p-12 text-center text-slate-500"><ClipboardList className="mx-auto mb-3" size={40} />No saved plans yet.</div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{plans.map((plan) => <article key={plan.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase text-purple-600">{plan.generation_source || "saved plan"}</p><h4 className="mt-1 text-lg font-bold text-slate-900">{plan.meal_plan_name}</h4><p className="mt-1 text-sm text-slate-500">{plan.total_calories} cal · {plan.servings || 1} serving(s)</p></div><button type="button" onClick={() => setDeleteTarget(plan)} className="rounded-lg p-2 text-red-500 hover:bg-red-50"><Trash2 size={17} /></button></div><label className="mt-4 block text-xs font-semibold text-slate-600">Schedule date<input type="date" value={String(plan.scheduled_date || "").slice(0, 10)} onChange={(event) => schedulePlan(plan, event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" /></label><div className="mt-3 flex gap-2"><button type="button" onClick={() => markStatus(plan, plan.completion_status === "completed" ? "planned" : "completed")} className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold ${plan.completion_status === "completed" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"}`}>{plan.completion_status === "completed" ? "Completed" : "Mark completed"}</button><button type="button" onClick={() => openPlan(plan)} className="flex items-center justify-center gap-1 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white">Details <ChevronRight size={14} /></button></div></article>)}</div>}
          </section>
        </main>
      </div>

      {selectedPlan && <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/65 p-4" onClick={() => setSelectedPlan(null)}><div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase text-purple-600">{selectedPlan.generation_source}</p><h3 className="text-2xl font-bold text-slate-900">{selectedPlan.meal_plan_name}</h3><p className="mt-1 text-sm text-slate-500">{selectedPlan.total_calories} calories · {selectedPlan.servings || 1} serving(s)</p></div><button type="button" onClick={() => setSelectedPlan(null)}><X /></button></div><div className="mt-6 grid gap-4 md:grid-cols-2">{MEAL_TYPES.map((type) => { const meal = selectedPlan.plan?.[type]; return meal && <section key={type} className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-bold uppercase text-orange-600">{type}</p><h4 className="mt-1 font-bold text-slate-900">{meal.name}</h4><p className="mt-1 text-xs text-slate-500">{meal.calories} cal · {meal.prep_time || "—"} min</p><p className="mt-3 text-sm font-semibold text-slate-700">Ingredients</p><ul className="mt-1 list-disc pl-5 text-sm text-slate-600">{(meal.ingredients || []).map((ingredient) => <li key={ingredient}>{ingredient}</li>)}</ul><p className="mt-3 text-sm font-semibold text-slate-700">Instructions</p><p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{Array.isArray(meal.instructions) ? meal.instructions.join("\n") : meal.instructions}</p></section>; })}</div>{selectedPlan.warnings?.length > 0 && <div className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-900"><p className="font-bold">Safety reminders</p><ul className="mt-2 list-disc pl-5">{selectedPlan.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>}<section className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4"><h4 className="font-bold text-slate-900">Private meal feedback</h4><p className="text-xs text-slate-500">Visible only in this saved plan and used to remember what worked for you.</p><div className="mt-3 flex gap-1">{[1,2,3,4,5].map((rating) => <button type="button" key={rating} onClick={() => setFeedback((current) => ({ ...current, rating }))}><Star size={22} className={rating <= feedback.rating ? "fill-amber-400 text-amber-400" : "text-slate-300"} /></button>)}</div><textarea value={feedback.notes} onChange={(event) => setFeedback((current) => ({ ...current, notes: event.target.value }))} placeholder="What worked? What would you change next time?" rows={3} className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" /><button type="button" onClick={saveFeedback} className="mt-3 rounded-lg bg-purple-600 px-4 py-2 text-sm font-semibold text-white">Save private feedback</button></section></div></div>}

      {deleteTarget && <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/65 p-4"><div className="w-full max-w-sm rounded-2xl bg-white p-6"><h3 className="text-lg font-bold text-slate-900">Delete this meal plan?</h3><p className="mt-2 text-sm text-slate-600">{deleteTarget.meal_plan_name} will be permanently removed.</p><div className="mt-5 flex gap-3"><button type="button" onClick={() => setDeleteTarget(null)} className="flex-1 rounded-lg bg-slate-100 py-2">Cancel</button><button type="button" onClick={deletePlan} className="flex-1 rounded-lg bg-red-600 py-2 font-semibold text-white">Delete</button></div></div></div>}
    </div>
  );
};

export default UserMealPlans;
