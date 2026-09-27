import React, { useEffect, useState } from "react";
import axios from "axios";

const AppointmentFeedback = ({ appointment, user }) => {
  const [feedback, setFeedback] = useState(null);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [wouldRecommend, setWouldRecommend] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const canSubmit =
    user?.role === "patient" &&
    appointment?.status === "completed";

  const canView =
    user?.role === "admin" ||
    user?.role === "clinician" ||
    user?.role === "patient";

  const loadFeedback = async () => {
    if (!appointment?.id || !canView) return;

    try {
      setLoading(true);
      setError("");

      const response = await axios.get(
        `/api/appointments/${appointment.id}/feedback`,
      );

      const existingFeedback = response.data.feedback;

      setFeedback(existingFeedback);

      if (existingFeedback) {
        setRating(existingFeedback.rating || 5);
        setComment(existingFeedback.comment || "");
        setWouldRecommend(Boolean(existingFeedback.would_recommend));
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Failed to load appointment feedback",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFeedback();
  }, [appointment?.id]);

  const submitFeedback = async () => {
    if (!appointment?.id) return;

    try {
      setSaving(true);
      setMessage("");
      setError("");

      const payload = {
        rating,
        comment,
        would_recommend: wouldRecommend,
      };

      const response = feedback
        ? await axios.put(
            `/api/appointments/${appointment.id}/feedback`,
            payload,
          )
        : await axios.post(
            `/api/appointments/${appointment.id}/feedback`,
            payload,
          );

      setFeedback(response.data.feedback);
      setMessage(
        feedback
          ? "Feedback updated successfully"
          : "Feedback submitted successfully",
      );
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Failed to save appointment feedback",
      );
    } finally {
      setSaving(false);
    }
  };

  if (!appointment) return null;

  if (appointment.status !== "completed" && !feedback) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-600">
            <i className="fas fa-star"></i>
          </div>

          <div>
            <h3 className="text-lg font-bold text-slate-900">
              Appointment Feedback
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Feedback can be submitted after the appointment is completed.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
            Feedback
          </p>
          <h3 className="mt-1 text-lg font-bold text-slate-900">
            Appointment Feedback & Rating
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Rate the completed appointment and share your experience.
          </p>
        </div>

        {feedback && (
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">
            Submitted
          </span>
        )}
      </div>

      {loading ? (
        <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">
          Loading feedback...
        </div>
      ) : (
        <>
          <div className="mb-5">
            <p className="mb-2 text-sm font-semibold text-slate-700">
              Rating
            </p>

            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  disabled={!canSubmit}
                  onClick={() => setRating(star)}
                  className={`text-3xl transition ${
                    star <= rating
                      ? "text-yellow-400"
                      : "text-slate-300"
                  } ${canSubmit ? "hover:scale-110" : "cursor-default"}`}
                >
                  ★
                </button>
              ))}

              <span className="ml-2 text-sm font-bold text-slate-600">
                {rating}/5
              </span>
            </div>
          </div>

          <div className="mb-5">
            <label className="mb-2 block text-sm font-semibold text-slate-700">
              Comments
            </label>

            <textarea
              value={comment}
              disabled={!canSubmit}
              onChange={(event) => setComment(event.target.value)}
              rows={4}
              placeholder="Share your experience with this appointment..."
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50 disabled:text-slate-500"
            />
          </div>

          <label className="mb-5 flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <input
              type="checkbox"
              checked={wouldRecommend}
              disabled={!canSubmit}
              onChange={(event) => setWouldRecommend(event.target.checked)}
              className="h-4 w-4"
            />

            <span className="text-sm font-semibold text-slate-700">
              I would recommend this clinician
            </span>
          </label>

          {message && (
            <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {message}
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {canSubmit ? (
            <button
              type="button"
              onClick={submitFeedback}
              disabled={saving}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {saving
                ? "Saving..."
                : feedback
                  ? "Update Feedback"
                  : "Submit Feedback"}
            </button>
          ) : (
            <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">
              Feedback is read-only for your role.
            </p>
          )}
        </>
      )}
    </section>
  );
};

export default AppointmentFeedback;