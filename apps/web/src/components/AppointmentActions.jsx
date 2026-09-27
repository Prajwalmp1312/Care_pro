import React, { useEffect, useState } from "react";
import axios from "axios";

const AppointmentActions = ({ appointment, onRefresh }) => {
  const [showReschedule, setShowReschedule] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [loading, setLoading] = useState(false);

  const [rescheduleForm, setRescheduleForm] = useState({
    appointment_date: appointment.appointment_date || "",
    appointment_time: appointment.appointment_time || "",
    reason: "",
  });

  const [cancelReason, setCancelReason] = useState("");

  const [availableSlots, setAvailableSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);

  const token = localStorage.getItem("access_token");

  useEffect(() => {
    if (
      !showReschedule ||
      !appointment?.clinician_email ||
      !rescheduleForm.appointment_date
    ) {
      setAvailableSlots([]);
      return;
    }

    const loadAvailableSlots = async () => {
      try {
        setSlotsLoading(true);

        const response = await axios.get(
          `/api/clinicians/${encodeURIComponent(
            appointment.clinician_email,
          )}/available-slots`,
          {
            params: {
              date: rescheduleForm.appointment_date,
            },
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        );

        const slots = response.data.slots || [];

        const filteredSlots = slots.filter(
          (slot) =>
            !(
              appointment.appointment_date ===
                rescheduleForm.appointment_date &&
              slot === appointment.appointment_time
            ),
        );

        setAvailableSlots(filteredSlots);

        if (
          rescheduleForm.appointment_time &&
          !slots.includes(rescheduleForm.appointment_time)
        ) {
          setRescheduleForm((current) => ({
            ...current,
            appointment_time: "",
          }));
        }
      } catch (error) {
        console.error("Failed to load available slots:", error);
        setAvailableSlots([]);
      } finally {
        setSlotsLoading(false);
      }
    };

    loadAvailableSlots();
  }, [
    showReschedule,
    appointment?.clinician_email,
    rescheduleForm.appointment_date,
    token,
  ]);

  // const token = localStorage.getItem("access_token");

  const canChange = ["pending", "approved"].includes(appointment.status);

  const handleReschedule = async () => {
    if (!availableSlots.includes(rescheduleForm.appointment_time)) {
      alert("Please select a valid available doctor slot");
      return;
    }

    try {
      setLoading(true);

      await axios.put(
        `http://localhost:8000/api/appointments/${appointment.id}/reschedule`,
        rescheduleForm,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      alert("Appointment rescheduled successfully");
      setShowReschedule(false);

      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      alert(error.response?.data?.detail || "Failed to reschedule appointment");
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    const confirmed = window.confirm(
      "Are you sure you want to cancel this appointment?",
    );

    if (!confirmed) return;

    setLoading(true);

    try {
      const token = localStorage.getItem("access_token");

      await axios.put(
        `/api/appointments/${appointment.id}/cancel`,
        { reason: cancelReason },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      alert("Appointment cancelled successfully");

      setShowCancel(false);
      setCancelReason("");

      try {
        if (onRefresh) {
          await onRefresh();
        }
      } catch (refreshError) {
        console.error("Refresh after cancel failed:", refreshError);
      }
    } catch (error) {
      const detail = error.response?.data?.detail;

      console.error("Cancel appointment error:", error);

      try {
        const token = localStorage.getItem("access_token");

        const refreshResponse = await axios.get("/api/appointments", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        const latestAppointment = refreshResponse.data.appointments?.find(
          (item) => item.id === appointment.id,
        );

        // Case 1: appointment disappeared after refresh
        // This means backend cancelled/deleted/removed it from current list.
        if (!latestAppointment) {
          alert("Appointment cancelled successfully");

          setShowCancel(false);
          setCancelReason("");

          try {
            if (onRefresh) {
              await onRefresh();
            }
          } catch (refreshError) {
            console.error(
              "Refresh after cancel verification failed:",
              refreshError,
            );
          }

          return;
        }

        // Case 2: appointment is present but status is cancelled
        if (latestAppointment.status === "cancelled") {
          alert("Appointment cancelled successfully");

          setShowCancel(false);
          setCancelReason("");

          try {
            if (onRefresh) {
              await onRefresh();
            }
          } catch (refreshError) {
            console.error(
              "Refresh after cancel verification failed:",
              refreshError,
            );
          }

          return;
        }
      } catch (verifyError) {
        console.error("Failed to verify cancelled appointment:", verifyError);
      }

      if (
        detail &&
        String(detail).toLowerCase().includes("already cancelled")
      ) {
        alert("Appointment is already cancelled");

        setShowCancel(false);
        setCancelReason("");

        try {
          if (onRefresh) {
            await onRefresh();
          }
        } catch (refreshError) {
          console.error(
            "Refresh after already cancelled failed:",
            refreshError,
          );
        }

        return;
      }

      alert(detail || "Failed to cancel appointment");
    } finally {
      setLoading(false);
    }
  };

  if (!canChange) {
    return (
      <p className="text-xs text-gray-400">
        No actions available for {appointment.status} appointment
      </p>
    );
  }

  return (
    <div className="mt-3 space-y-3">
      <div className="flex flex-wrap items-start gap-2">
        <button
          onClick={() => setShowReschedule(!showReschedule)}
          className="inline-flex h-7 items-center rounded-md bg-blue-600 px-2 text-xs font-semibold text-white hover:bg-blue-700"
        >
          Reschedule
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() => setShowCancel(!showCancel)}
          className="inline-flex h-7 items-center rounded-md bg-red-600 px-2 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-60"
        >
          Cancel
        </button>
      </div>

      {showReschedule && (
        <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
          <h4 className="mb-3 font-semibold text-blue-900">
            Reschedule Appointment
          </h4>

          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                New Date
              </label>
              <input
                type="date"
                value={rescheduleForm.appointment_date}
                onChange={(e) =>
                  setRescheduleForm({
                    ...rescheduleForm,
                    appointment_date: e.target.value,
                  })
                }
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                New Time
              </label>
              <select
                value={rescheduleForm.appointment_time}
                onChange={(e) =>
                  setRescheduleForm({
                    ...rescheduleForm,
                    appointment_time: e.target.value,
                  })
                }
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="">
                  {slotsLoading
                    ? "Loading available slots..."
                    : rescheduleForm.appointment_date
                      ? "Doctor available time"
                      : "Select date first"}
                </option>

                {availableSlots.map((slot) => (
                  <option key={slot} value={slot}>
                    {slot}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Reason
            </label>
            <textarea
              value={rescheduleForm.reason}
              onChange={(e) =>
                setRescheduleForm({
                  ...rescheduleForm,
                  reason: e.target.value,
                })
              }
              placeholder="Reason for rescheduling"
              rows={3}
              className="w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </div>

          <button
            onClick={handleReschedule}
            disabled={loading}
            className="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? "Saving..." : "Confirm Reschedule"}
          </button>
        </div>
      )}

      {showCancel && (
        <div className="rounded-xl border border-red-100 bg-red-50 p-4">
          <h4 className="mb-3 font-semibold text-red-900">
            Cancel Appointment
          </h4>

          <label className="mb-1 block text-sm font-medium text-gray-700">
            Reason
          </label>

          <textarea
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            placeholder="Reason for cancellation"
            rows={3}
            className="w-full rounded-lg border border-gray-300 px-3 py-2"
          />

          <button
            type="button"
            onClick={handleCancel}
            disabled={loading}
            className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
          >
            {loading ? "Cancelling..." : "Confirm Cancel"}
          </button>
        </div>
      )}
    </div>
  );
};

export default AppointmentActions;
