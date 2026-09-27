import React, { useEffect, useState } from "react";
import axios from "axios";

const DoctorFeedbackSummary = ({ user }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadSummary = async () => {
    if (user?.role !== "clinician") return;

    try {
      setLoading(true);

      const response = await axios.get("/api/clinician/feedback-summary");
      setData(response.data);
    } catch (error) {
      console.error("Failed to load feedback summary:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, [user?.role]);

  if (user?.role !== "clinician") return null;

  const summary = data?.summary || {};

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-md">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-gray-900">
            Patient Feedback
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            Ratings from completed appointments.
          </p>
        </div>

        <button
          type="button"
          onClick={loadSummary}
          className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-200"
        >
          Refresh
        </button>
      </div>

      {loading && !data ? (
        <p className="text-sm text-gray-500">Loading feedback...</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl bg-yellow-50 p-5">
              <p className="text-sm font-semibold text-gray-600">
                Average Rating
              </p>
              <p className="mt-2 text-3xl font-bold text-yellow-700">
                {summary.average_rating || 0}/5
              </p>
            </div>

            <div className="rounded-xl bg-blue-50 p-5">
              <p className="text-sm font-semibold text-gray-600">
                Total Reviews
              </p>
              <p className="mt-2 text-3xl font-bold text-blue-700">
                {summary.total_reviews || 0}
              </p>
            </div>

            <div className="rounded-xl bg-emerald-50 p-5">
              <p className="text-sm font-semibold text-gray-600">
                Recommended
              </p>
              <p className="mt-2 text-3xl font-bold text-emerald-700">
                {summary.recommend_count || 0}
              </p>
            </div>
          </div>

          <div className="mt-6">
            <h4 className="mb-3 font-bold text-gray-900">
              Latest Feedback
            </h4>

            {data?.latest_feedback?.length ? (
              <div className="space-y-3">
                {data.latest_feedback.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-lg border border-gray-100 bg-gray-50 p-4"
                  >
                    <div className="flex items-center justify-between">
                      <p className="font-bold text-yellow-600">
                        {"★".repeat(item.rating)}
                        {"☆".repeat(5 - item.rating)}
                      </p>

                      <span className="text-xs text-gray-500">
                        {item.created_at
                          ? new Date(item.created_at).toLocaleDateString()
                          : ""}
                      </span>
                    </div>

                    <p className="mt-2 text-sm text-gray-600">
                      {item.comment || "No comment provided"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="rounded-lg bg-gray-50 p-4 text-sm text-gray-500">
                No feedback submitted yet.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default DoctorFeedbackSummary;