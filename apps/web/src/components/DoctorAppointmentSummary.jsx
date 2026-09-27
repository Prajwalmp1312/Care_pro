import React, { useEffect, useState } from "react";
import axios from "axios";

const DoctorAppointmentSummary = ({ user }) => {
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadAppointmentSummary = async () => {
    if (user?.role !== "clinician") return;

    try {
      setLoading(true);
      setError("");

      const response = await axios.get("/api/clinician/appointment-summary");

      setSummaryData(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Failed to load doctor appointment summary",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAppointmentSummary();
  }, [user?.role]);

  if (user?.role !== "clinician") {
    return null;
  }

  const summary = summaryData?.summary || {};

  const cards = [
    {
      title: "Today's Appointments",
      value: summary.today_appointments || 0,
      icon: "fa-calendar-day",
      bg: "bg-blue-50",
      text: "text-blue-700",
      border: "border-blue-100",
    },
    {
      title: "Pending Requests",
      value: summary.pending_requests || 0,
      icon: "fa-hourglass-half",
      bg: "bg-yellow-50",
      text: "text-yellow-700",
      border: "border-yellow-100",
    },
    {
      title: "Approved",
      value: summary.approved_appointments || 0,
      icon: "fa-circle-check",
      bg: "bg-green-50",
      text: "text-green-700",
      border: "border-green-100",
    },
    {
      title: "Completed This Week",
      value: summary.completed_this_week || 0,
      icon: "fa-check-double",
      bg: "bg-indigo-50",
      text: "text-indigo-700",
      border: "border-indigo-100",
    },
    {
      title: "Cancelled This Week",
      value: summary.cancelled_this_week || 0,
      icon: "fa-ban",
      bg: "bg-red-50",
      text: "text-red-700",
      border: "border-red-100",
    },
    {
      title: "Upcoming 7 Days",
      value: summary.upcoming_7_days || 0,
      icon: "fa-calendar-week",
      bg: "bg-purple-50",
      text: "text-purple-700",
      border: "border-purple-100",
    },
  ];

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-md">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-xl font-bold text-gray-900">
            Doctor Appointment Summary
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            Quick overview of your appointment workload and pending requests.
          </p>
        </div>

        <button
          type="button"
          onClick={loadAppointmentSummary}
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
        >
          <i className={`fas ${loading ? "fa-spinner fa-spin" : "fa-sync-alt"} mr-2`}></i>
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && !summaryData ? (
        <div className="rounded-lg border border-dashed border-gray-200 p-6 text-center text-gray-500">
          <i className="fas fa-spinner fa-spin mr-2"></i>
          Loading appointment summary...
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {cards.map((card) => (
              <div
                key={card.title}
                className={`rounded-xl border ${card.border} ${card.bg} p-5`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-600">
                      {card.title}
                    </p>
                    <p className={`mt-2 text-3xl font-bold ${card.text}`}>
                      {card.value}
                    </p>
                  </div>

                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded-full bg-white ${card.text}`}
                  >
                    <i className={`fas ${card.icon} text-xl`}></i>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="rounded-xl border border-gray-100 bg-gray-50 p-5">
              <div className="mb-4 flex items-center justify-between">
                <h4 className="font-bold text-gray-900">
                  Today's Appointments
                </h4>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-blue-700">
                  {summary.today_appointments || 0}
                </span>
              </div>

              {summaryData?.today_preview?.length ? (
                <div className="space-y-3">
                  {summaryData.today_preview.map((appointment) => (
                    <div
                      key={appointment.id}
                      className="rounded-lg border border-gray-100 bg-white p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-gray-900">
                            {appointment.patient_name}
                          </p>
                          <p className="mt-1 text-sm text-gray-500">
                            {appointment.reason || "No reason provided"}
                          </p>
                          <p className="mt-1 text-xs text-gray-400">
                            {appointment.appointment_type?.replace("_", " ")}
                          </p>
                        </div>

                        <div className="text-right">
                          <p className="text-sm font-bold text-blue-700">
                            {appointment.appointment_time}
                          </p>
                          <span className="mt-1 inline-block rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold capitalize text-gray-600">
                            {appointment.status}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="rounded-lg border border-dashed border-gray-200 bg-white p-4 text-sm text-gray-500">
                  No appointments scheduled for today.
                </p>
              )}
            </div>

            <div className="rounded-xl border border-gray-100 bg-gray-50 p-5">
              <div className="mb-4 flex items-center justify-between">
                <h4 className="font-bold text-gray-900">
                  Upcoming Appointments
                </h4>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-purple-700">
                  Next 7 days
                </span>
              </div>

              {summaryData?.upcoming_preview?.length ? (
                <div className="space-y-3">
                  {summaryData.upcoming_preview.map((appointment) => (
                    <div
                      key={appointment.id}
                      className="rounded-lg border border-gray-100 bg-white p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-gray-900">
                            {appointment.patient_name}
                          </p>
                          <p className="mt-1 text-sm text-gray-500">
                            {appointment.reason || "No reason provided"}
                          </p>
                          <p className="mt-1 text-xs text-gray-400">
                            {appointment.appointment_date}
                          </p>
                        </div>

                        <div className="text-right">
                          <p className="text-sm font-bold text-purple-700">
                            {appointment.appointment_time}
                          </p>
                          <span className="mt-1 inline-block rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold capitalize text-gray-600">
                            {appointment.status}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="rounded-lg border border-dashed border-gray-200 bg-white p-4 text-sm text-gray-500">
                  No upcoming appointments in the next 7 days.
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default DoctorAppointmentSummary;