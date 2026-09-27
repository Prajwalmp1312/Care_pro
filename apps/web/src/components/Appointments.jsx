import React, { useEffect, useState } from "react";
import axios from "axios";
import { Calendar, dateFnsLocalizer } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import "react-big-calendar/lib/css/react-big-calendar.css";
import VideoConsultationButton from "./VideoConsultationButton";
import AppointmentDetailsDrawer from "./AppointmentDetailsDrawer";
import AppointmentActions from "./AppointmentActions";

import enUS from "date-fns/locale/en-US";

const locales = {
  "en-US": enUS,
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 1 }),
  getDay,
  locales,
});

const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

const calendarTypeIcons = {
  phone_call: "fa-phone",
  video_call: "fa-video",
  in_person: "fa-hospital-user",
};

const AppointmentCalendarEvent = ({ event }) => (
  <div
    className="flex min-w-0 items-center gap-1.5 font-semibold"
    title={event.title}
  >
    <i
      className={`fas ${
        calendarTypeIcons[event.appointment.appointment_type] ||
        "fa-calendar-check"
      } shrink-0 text-[11px]`}
    ></i>
    <span className="shrink-0 text-[11px]">{format(event.start, "p")}</span>
    <span className="truncate">{event.displayName}</span>
  </div>
);

const Appointments = ({ user, onOpenPatientProfile, onMessagePatient }) => {
  const [appointments, setAppointments] = useState([]);
  const [clinicians, setClinicians] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [availableSlots, setAvailableSlots] = useState([]);
  const [appointmentStatusFilter, setAppointmentStatusFilter] = useState("all");
  const [appointmentSearch, setAppointmentSearch] = useState("");

  const [formData, setFormData] = useState({
    clinician_email: "",
    appointment_date: "",
    appointment_time: "",
    appointment_type: "phone_call",
    reason: "",
  });

  const [notesByAppointment, setNotesByAppointment] = useState({});
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [patientSummaryState, setPatientSummaryState] = useState({
    appointmentId: null,
    data: null,
    loading: false,
    error: "",
  });

  const calendarEvents = appointments.map((appointment) => {
    const startDate = new Date(
      `${appointment.appointment_date}T${appointment.appointment_time}`,
    );

    const endDate = new Date(startDate);
    endDate.setMinutes(
      endDate.getMinutes() + (appointment.consultation_duration_minutes || 15),
    );

    return {
      id: appointment.id,
      displayName:
        user?.role === "patient"
          ? `Dr. ${appointment.clinician_name}`
          : appointment.patient_name,
      title:
        user?.role === "patient"
          ? `Dr. ${appointment.clinician_name} - ${appointment.reason}`
          : `${appointment.patient_name} - ${appointment.reason}`,
      start: startDate,
      end: endDate,
      status: appointment.status,
      appointment,
    };
  });

  const getStatusClasses = (status) => {
    if (status === "pending") return "bg-yellow-100 text-yellow-700";
    if (status === "approved") return "bg-green-100 text-green-700";
    if (status === "rejected") return "bg-red-100 text-red-700";
    if (status === "completed") return "bg-blue-100 text-blue-700";
    if (status === "cancelled") return "bg-gray-100 text-gray-700";
    if (status === "expired") return "bg-orange-100 text-orange-700";
    return "bg-gray-100 text-gray-700";
  };

  const appointmentStatusTabs = [
    { key: "all", label: "All" },
    { key: "pending", label: "Pending" },
    { key: "approved", label: "Approved" },
    { key: "completed", label: "Completed" },
    { key: "cancelled", label: "Cancelled" },
    { key: "expired", label: "Expired" },
    { key: "rejected", label: "Rejected" },
  ];

  const appointmentSearchText = appointmentSearch.trim().toLowerCase();

  const selectedClinician = clinicians.find(
    (clinician) => clinician.email === formData.clinician_email,
  );

  const statusFilteredAppointments =
    appointmentStatusFilter === "all"
      ? appointments
      : appointments.filter(
          (appointment) => appointment.status === appointmentStatusFilter,
        );

  const filteredAppointments = statusFilteredAppointments.filter(
    (appointment) => {
      if (!appointmentSearchText) return true;

      const searchableValues = [
        appointment.appointment_date,
        appointment.appointment_time,
        appointment.appointment_type,
        appointment.patient_name,
        appointment.patient_email,
        appointment.clinician_name,
        appointment.clinician_email,
        appointment.clinician_specialization,
        appointment.reason,
        appointment.status,
        appointment.notes,
      ];

      return searchableValues
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(appointmentSearchText),
        );
    },
  );

  const getAppointmentStatusCount = (status) => {
    const source =
      status === "all"
        ? appointments
        : appointments.filter((appointment) => appointment.status === status);

    if (!appointmentSearchText) {
      return source.length;
    }

    return source.filter((appointment) => {
      const searchableValues = [
        appointment.appointment_date,
        appointment.appointment_time,
        appointment.appointment_type,
        appointment.patient_name,
        appointment.patient_email,
        appointment.clinician_name,
        appointment.clinician_email,
        appointment.clinician_specialization,
        appointment.reason,
        appointment.status,
        appointment.notes,
      ];

      return searchableValues
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(appointmentSearchText),
        );
    }).length;
  };

  const loadAppointments = async () => {
    try {
      setLoading(true);
      const res = await axios.get("/api/appointments");
      const nextAppointments = res.data.appointments || [];
      setAppointments(nextAppointments);
      setNotesByAppointment((current) => {
        const nextNotes = { ...current };
        nextAppointments.forEach((appointment) => {
          if (nextNotes[appointment.id] === undefined) {
            nextNotes[appointment.id] = appointment.notes || "";
          }
        });
        return nextNotes;
      });
      setSelectedAppointment((current) => {
        if (!current) return null;
        return (
          nextAppointments.find(
            (appointment) => appointment.id === current.id,
          ) || null
        );
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load appointments");
    } finally {
      setLoading(false);
    }
  };

  const loadClinicians = async () => {
    if (user?.role !== "patient") return;

    try {
      const res = await axios.get("/api/clinicians");
      setClinicians(res.data.clinicians || []);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load clinicians");
    }
  };

  const loadReminders = async () => {
    if (user?.role !== "patient") {
      setReminders([]);
      return;
    }
    try {
      const res = await axios.get("/api/appointment-reminders");
      setReminders(res.data.reminders || []);
      window.dispatchEvent(new Event("careconnect:notifications-updated"));
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to load appointment reminders",
      );
    }
  };

  useEffect(() => {
    loadAppointments();
    loadClinicians();
    loadReminders();
  }, [user?.role]);

  useEffect(() => {
    if (!selectedAppointment) return undefined;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setSelectedAppointment(null);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [selectedAppointment]);

  useEffect(() => {
    if (
      user?.role !== "patient" ||
      !formData.clinician_email ||
      !formData.appointment_date
    ) {
      setAvailableSlots([]);
      return;
    }
    axios
      .get(
        `/api/clinicians/${encodeURIComponent(formData.clinician_email)}/available-slots`,
        {
          params: { date: formData.appointment_date },
        },
      )
      .then((res) => setAvailableSlots(res.data.slots || []))
      .catch((err) =>
        setError(
          err.response?.data?.detail || "Failed to load available slots",
        ),
      );
  }, [user?.role, formData.clinician_email, formData.appointment_date]);

  const handleChange = (e) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
      ...(["clinician_email", "appointment_date"].includes(e.target.name)
        ? { appointment_time: "" }
        : {}),
    }));

    setMessage("");
    setError("");
  };

  const handleBookAppointment = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    if (!formData.clinician_email) {
      setError("Please select a clinician");
      return;
    }

    if (!formData.appointment_date) {
      setError("Please select appointment date");
      return;
    }

    if (!formData.appointment_time) {
      setError("Please select appointment time");
      return;
    }

    if (!formData.reason.trim()) {
      setError("Please enter appointment reason");
      return;
    }

    try {
      setLoading(true);

      await axios.post("/api/appointments", {
        clinician_email: formData.clinician_email,
        appointment_date: formData.appointment_date,
        appointment_time: formData.appointment_time,
        appointment_type: formData.appointment_type,
        reason: formData.reason,
      });

      setMessage("Appointment request submitted successfully");

      setFormData({
        clinician_email: "",
        appointment_date: "",
        appointment_time: "",
        appointment_type: "phone_call",
        reason: "",
      });

      await loadAppointments();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to book appointment");
    } finally {
      setLoading(false);
    }
  };

  const updateAppointmentStatus = async (appointmentId, status) => {
    setMessage("");
    setError("");

    try {
      setLoading(true);

      const appointment = appointments.find(
        (item) => item.id === appointmentId,
      );

      if (status === "cancelled") {
        await axios.put(`/api/appointments/${appointmentId}/cancel`, {
          reason: "Cancelled by patient",
        });

        setMessage("Appointment cancelled successfully");
      } else {
        await axios.put(`/api/appointments/${appointmentId}/status`, {
          status,
          notes: notesByAppointment[appointmentId] ?? appointment?.notes ?? "",
        });

        setMessage(`Appointment ${status} successfully`);
      }

      setSelectedAppointment((current) =>
        current?.id === appointmentId ? null : current,
      );

      await loadAppointments();
      await loadReminders();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update appointment");
    } finally {
      setLoading(false);
    }
  };

  const saveAppointmentNotes = async (appointmentId) => {
    setMessage("");
    setError("");
    try {
      setLoading(true);
      await axios.put(`/api/appointments/${appointmentId}/notes`, {
        notes: notesByAppointment[appointmentId] || "",
      });
      setMessage("Appointment notes saved successfully");
      await loadAppointments();
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to save appointment notes",
      );
    } finally {
      setLoading(false);
    }
  };

  const openAppointmentDetails = (appointment) => {
    setMessage("");
    setError("");
    setNotesByAppointment((current) => ({
      ...current,
      [appointment.id]: current[appointment.id] ?? appointment.notes ?? "",
    }));
    setSelectedAppointment(appointment);
    if (["clinician", "admin"].includes(user?.role)) {
      setPatientSummaryState({
        appointmentId: appointment.id,
        data: null,
        loading: true,
        error: "",
      });
      axios
        .get(
          `/api/patients/${encodeURIComponent(
            appointment.patient_email,
          )}/appointment-summary`,
          { params: { appointment_id: appointment.id } },
        )
        .then((response) => {
          setPatientSummaryState((current) =>
            current.appointmentId === appointment.id
              ? { ...current, data: response.data, loading: false }
              : current,
          );
        })
        .catch((err) => {
          setPatientSummaryState((current) =>
            current.appointmentId === appointment.id
              ? {
                  ...current,
                  loading: false,
                  error:
                    err.response?.data?.detail ||
                    "Unable to load the patient summary.",
                }
              : current,
          );
        });
    } else {
      setPatientSummaryState({
        appointmentId: null,
        data: null,
        loading: false,
        error: "",
      });
    }
  };

  const deleteAppointment = async (appointmentId) => {
    const confirmDelete = window.confirm(
      "Are you sure you want to delete this appointment?",
    );

    if (!confirmDelete) return;

    setMessage("");
    setError("");

    try {
      setLoading(true);

      await axios.delete(`/api/appointments/${appointmentId}`);

      setMessage("Appointment deleted successfully");

      setSelectedAppointment((current) =>
        current?.id === appointmentId ? null : current,
      );

      await loadAppointments();
      await loadReminders();
    } catch (err) {
      console.error("Delete appointment error:", err);

      const detail =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        "Failed to delete appointment";

      alert(detail);
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const formatDateForICS = (date) => {
    return date.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  };

  const downloadAppointmentCalendarFile = (appointment) => {
    try {
      const startDate = new Date(
        `${appointment.appointment_date}T${appointment.appointment_time}`,
      );

      const endDate = new Date(startDate);
      endDate.setMinutes(
        endDate.getMinutes() +
          (appointment.consultation_duration_minutes || 15),
      );

      const title =
        user?.role === "patient"
          ? `Appointment with Dr. ${appointment.clinician_name}`
          : `Appointment with ${appointment.patient_name}`;

      const description = [
        `Reason: ${appointment.reason || "N/A"}`,
        `Status: ${appointment.status || "N/A"}`,
        `Type: ${(appointment.appointment_type || "appointment").replace("_", " ")}`,
        appointment.notes ? `Notes: ${appointment.notes}` : "",
      ]
        .filter(Boolean)
        .join("\\n");

      const location =
        appointment.appointment_type === "in_person"
          ? "Clinic"
          : appointment.appointment_type === "video_call"
            ? "Video consultation"
            : "Phone consultation";

      const icsContent = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CareConnect//Appointment Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        `UID:careconnect-appointment-${appointment.id}@careconnect`,
        `DTSTAMP:${formatDateForICS(new Date())}`,
        `DTSTART:${formatDateForICS(startDate)}`,
        `DTEND:${formatDateForICS(endDate)}`,
        `SUMMARY:${title}`,
        `DESCRIPTION:${description}`,
        `LOCATION:${location}`,
        "END:VEVENT",
        "END:VCALENDAR",
      ].join("\r\n");

      const blob = new Blob([icsContent], {
        type: "text/calendar;charset=utf-8",
      });

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = `careconnect-appointment-${appointment.id}.ics`;
      document.body.appendChild(link);
      link.click();

      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Calendar download failed:", error);
      setError("Failed to download calendar file");
    }
  };

  const eventStyleGetter = (event) => {
    let backgroundColor = "#f59e0b";

    if (event.status === "approved") {
      backgroundColor = "#16a34a";
    } else if (event.status === "rejected") {
      backgroundColor = "#dc2626";
    } else if (event.status === "completed") {
      backgroundColor = "#2563eb";
    } else if (event.status === "cancelled") {
      backgroundColor = "#6b7280";
    } else if (event.status === "expired") {
      backgroundColor = "#ea580c";
    }

    return {
      style: {
        backgroundColor,
        borderRadius: "8px",
        color: "white",
        border:
          selectedAppointment?.id === event.id ? "2px solid #172554" : "none",
        padding: "4px",
        fontSize: "13px",
        cursor: "pointer",
        boxShadow:
          selectedAppointment?.id === event.id
            ? "0 0 0 3px rgba(59, 130, 246, 0.25)"
            : "none",
      },
    };
  };

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl p-6 text-white shadow-lg">
        <h2 className="text-2xl font-bold mb-2">
          <i className="fas fa-calendar-check mr-2"></i>
          Appointment Booking
        </h2>
        <p className="opacity-90">
          {user?.role === "patient"
            ? "Book and manage your appointments with clinicians"
            : user?.role === "clinician"
              ? "Review and manage appointment requests from patients"
              : "View and manage all appointments"}
        </p>
      </div>

      {message && (
        <div className="bg-green-100 border border-green-300 text-green-700 px-4 py-3 rounded-lg">
          {message}
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-300 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {user?.role === "patient" && (
        <div className="rounded-xl border border-blue-100 bg-gradient-to-r from-blue-50 to-indigo-50 p-5 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="flex items-center gap-2 text-lg font-bold text-slate-900">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white">
                  <i className="fas fa-bell"></i>
                </span>
                Appointment reminders
              </h3>
              <p className="mt-1 text-sm text-slate-600">
                Approved visits receive automatic in-app reminders 24 hours and
                1 hour before the scheduled time.
              </p>
            </div>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-blue-700 ring-1 ring-blue-200">
              <i className="fas fa-clock mr-1"></i>
              Automatic
            </span>
          </div>

          {reminders.length > 0 ? (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {reminders.slice(0, 6).map((reminder) => (
                <div
                  key={reminder.id}
                  className="rounded-lg border border-white bg-white/90 p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-800">
                        {reminder.clinician_name}
                      </p>
                      <p className="text-sm text-slate-600">
                        {reminder.appointment_date} at{" "}
                        {reminder.appointment_time}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {reminder.reminder_type === "24_hour"
                          ? "24-hour reminder"
                          : "1-hour reminder"}{" "}
                        · {reminder.appointment_timezone}
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-bold ${
                        reminder.status === "sent"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-blue-100 text-blue-700"
                      }`}
                    >
                      {reminder.status === "sent" ? "Sent" : "Scheduled"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 rounded-lg border border-dashed border-blue-200 bg-white/60 p-4 text-sm text-slate-600">
              Reminder schedules will appear here after a clinician approves an
              upcoming appointment.
            </p>
          )}
        </div>
      )}

      {user?.role === "patient" && (
        <div className="bg-white rounded-xl shadow-md p-6 border border-gray-100">
          <h3 className="text-xl font-bold text-gray-800 mb-4">
            Book New Appointment
          </h3>

          <form onSubmit={handleBookAppointment} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Select Clinician
              </label>
              <select
                name="clinician_email"
                value={formData.clinician_email}
                onChange={handleChange}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Choose a clinician</option>
                {clinicians.map((clinician) => (
                  <option key={clinician.email} value={clinician.email}>
                    Dr. {clinician.name} -{" "}
                    {clinician.specialization || "General"}
                    {clinician.department ? ` (${clinician.department})` : ""}
                  </option>
                ))}
              </select>
              {formData.clinician_email &&
                (() => {
                  const clinician = clinicians.find(
                    (item) => item.email === formData.clinician_email,
                  );
                  const activeDays = WEEKDAYS.filter(
                    (day) => clinician?.consultation_hours?.[day]?.length,
                  );
                  if (!activeDays.length) {
                    return (
                      <p className="mt-2 text-sm text-blue-700">
                        This clinician has not published consultation hours yet.
                      </p>
                    );
                  }
                  const hoursSummary = activeDays
                    .map(
                      (day) =>
                        `${day.slice(0, 3)} ${clinician.consultation_hours[day]
                          .map((window) => `${window.start}-${window.end}`)
                          .join(" / ")}`,
                    )
                    .join(", ");
                  const breakSummary = activeDays
                    .flatMap((day) =>
                      (clinician.consultation_breaks?.[day] || []).map(
                        (item) =>
                          `${day.slice(0, 3)} ${item.label} ${item.start}-${item.end}`,
                      ),
                    )
                    .join(", ");
                  return (
                    <div className="mt-2 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-800">
                      <p>
                        <span className="font-semibold">Available:</span>{" "}
                        {hoursSummary}
                      </p>
                      {breakSummary && (
                        <p className="mt-1 text-xs text-amber-800">
                          <span className="font-semibold">Unavailable:</span>{" "}
                          {breakSummary}
                        </p>
                      )}
                    </div>
                  );
                })()}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Appointment Date
                </label>
                <input
                  type="date"
                  name="appointment_date"
                  value={formData.appointment_date}
                  onChange={handleChange}
                  min={new Date().toISOString().split("T")[0]}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Appointment Time
                </label>

                <select
                  name="appointment_time"
                  value={formData.appointment_time}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                >
                  <option value="">
                    {formData.appointment_date
                      ? "Choose an available slot"
                      : "Select a date first"}
                  </option>

                  {availableSlots.map((slot) => (
                    <option key={slot} value={slot}>
                      {slot}
                    </option>
                  ))}
                </select>

                {formData.clinician_email && formData.appointment_date && (
                  <div
                    className={`mt-2 rounded-lg px-3 py-2 text-sm ${
                      availableSlots.length > 0
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-100"
                        : "bg-amber-50 text-amber-700 border border-amber-100"
                    }`}
                  >
                    {availableSlots.length > 0 ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">
                          <i className="fas fa-check-circle mr-1"></i>
                          {availableSlots.length} slot
                          {availableSlots.length > 1 ? "s" : ""} available
                        </span>

                        <span className="text-xs">
                          Next available:{" "}
                          <span className="font-bold">{availableSlots[0]}</span>
                        </span>

                        {selectedClinician?.consultation_duration_minutes && (
                          <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold">
                            {selectedClinician.consultation_duration_minutes}{" "}
                            min visit
                          </span>
                        )}
                      </div>
                    ) : (
                      <div>
                        <span className="font-semibold">
                          <i className="fas fa-info-circle mr-1"></i>
                          No slots available
                        </span>
                        <p className="mt-1 text-xs">
                          Try another date or select a different clinician.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Appointment Type
                </label>
                <select
                  name="appointment_type"
                  value={formData.appointment_type}
                  onChange={handleChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                >
                  <option value="phone_call">Phone Call</option>
                  <option value="video_call">Video Call</option>
                  <option value="in_person">In Person</option>
                </select>
                {formData.appointment_type === "video_call" && (
                  <p className="mt-2 text-sm leading-5 text-violet-700">
                    Video visits open in Comm360 after approval. Each
                    participant reviews the external-service consent before
                    joining.
                  </p>
                )}
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Reason
              </label>
              <textarea
                name="reason"
                value={formData.reason}
                onChange={handleChange}
                rows="4"
                placeholder="Describe the reason for appointment"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition disabled:opacity-50"
            >
              <i className="fas fa-calendar-plus mr-2"></i>
              {loading ? "Booking..." : "Book Appointment"}
            </button>
          </form>
        </div>
      )}
      <div className="bg-white rounded-xl shadow-md border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-bold text-gray-800">
              Appointment Calendar
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Select any appointment to open its complete details and actions.
            </p>
          </div>

          <div className="flex items-center gap-3 text-sm">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-yellow-500"></span>
              Pending
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-green-600"></span>
              Approved
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-red-600"></span>
              Rejected
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-blue-600"></span>
              Completed
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-orange-600"></span>
              Expired
            </span>
          </div>
        </div>

        <div style={{ height: "650px" }}>
          <Calendar
            localizer={localizer}
            events={calendarEvents}
            startAccessor="start"
            endAccessor="end"
            views={["month", "week", "day", "agenda"]}
            defaultView="month"
            popup
            eventPropGetter={eventStyleGetter}
            components={{ event: AppointmentCalendarEvent }}
            tooltipAccessor={(event) =>
              `${event.displayName} · ${event.appointment.reason} · ${event.appointment.status}`
            }
            onSelectEvent={(event) => openAppointmentDetails(event.appointment)}
          />
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-md border border-gray-100 overflow-hidden">
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center justify-between gap-4">
            <h3 className="text-xl font-bold text-gray-800">
              {user?.role === "patient"
                ? "My Appointments"
                : user?.role === "clinician"
                  ? "Patient Appointment Requests"
                  : "All Appointments"}
            </h3>

            <button
              onClick={() => {
                loadAppointments();
                if (user?.role === "patient") {
                  loadReminders();
                }
              }}
              className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg font-medium"
            >
              <i className="fas fa-sync-alt mr-2"></i>
              Refresh
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {appointmentStatusTabs.map((tab) => {
              const isActive = appointmentStatusFilter === tab.key;
              const count = getAppointmentStatusCount(tab.key);

              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setAppointmentStatusFilter(tab.key)}
                  className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition ${
                    isActive
                      ? "bg-blue-600 text-white shadow-md"
                      : "bg-gray-100 text-gray-700 hover:bg-blue-50 hover:text-blue-700"
                  }`}
                >
                  <span>{tab.label}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      isActive
                        ? "bg-white/20 text-white"
                        : "bg-white text-gray-600"
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="mt-4 relative max-w-xl">
            <i className="fas fa-search absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"></i>

            <input
              type="text"
              value={appointmentSearch}
              onChange={(e) => setAppointmentSearch(e.target.value)}
              placeholder={
                user?.role === "patient"
                  ? "Search by doctor, date, reason, status..."
                  : "Search by patient, date, reason, status..."
              }
              className="w-full rounded-xl border border-gray-200 bg-gray-50 py-3 pl-11 pr-10 text-sm text-gray-700 outline-none transition focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100"
            />

            {appointmentSearch && (
              <button
                type="button"
                onClick={() => setAppointmentSearch("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700"
              >
                <i className="fas fa-times"></i>
              </button>
            )}
          </div>
        </div>

        {loading && appointments.length === 0 ? (
          <div className="p-10 text-center text-gray-500">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-blue-600">
              <i className="fas fa-spinner fa-spin text-xl"></i>
            </div>

            <p className="font-semibold text-gray-700">
              Loading appointments...
            </p>

            <p className="mt-1 text-sm text-gray-500">
              Please wait while we fetch your latest appointment details.
            </p>
          </div>
        ) : filteredAppointments.length === 0 ? (
          <div className="p-10 text-center text-gray-500">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-50 text-gray-400">
              <i className="fas fa-calendar-times text-2xl"></i>
            </div>

            <p className="text-lg font-bold text-gray-800">
              {appointmentSearch
                ? "No matching appointments found"
                : appointmentStatusFilter === "all"
                  ? user?.role === "patient"
                    ? "No appointments booked yet"
                    : user?.role === "clinician"
                      ? "No patient appointment requests yet"
                      : "No appointments available"
                  : `No ${appointmentStatusFilter} appointments found`}
            </p>

            <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
              {appointmentSearch
                ? "Try searching with a different doctor name, patient name, date, reason, or status."
                : appointmentStatusFilter !== "all"
                  ? `There are currently no appointments with ${appointmentStatusFilter} status.`
                  : user?.role === "patient"
                    ? "Book your first appointment with a clinician using the appointment form above."
                    : user?.role === "clinician"
                      ? "New appointment requests from patients will appear here when they book with you."
                      : "Appointments from patients and clinicians will appear here once available."}
            </p>

            <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
              {appointmentSearch && (
                <button
                  type="button"
                  onClick={() => setAppointmentSearch("")}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Clear search
                </button>
              )}

              {appointmentStatusFilter !== "all" && (
                <button
                  type="button"
                  onClick={() => setAppointmentStatusFilter("all")}
                  className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-200"
                >
                  View all appointments
                </button>
              )}

              <button
                type="button"
                onClick={() => {
                  loadAppointments();
                  if (user?.role === "patient") {
                    loadReminders();
                  }
                }}
                className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-200"
              >
                <i className="fas fa-sync-alt mr-2"></i>
                Refresh
              </button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 text-left text-sm text-gray-600">
                  <th className="px-6 py-3">Date & Time</th>
                  <th className="px-6 py-3">
                    {user?.role === "patient" ? "Clinician" : "Patient"}
                  </th>
                  <th className="px-6 py-3">Reason</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Notes</th>
                  <th className="px-6 py-3">Actions</th>
                </tr>
              </thead>

              <tbody>
                {filteredAppointments.map((appointment) => (
                  <tr key={appointment.id} className="border-t border-gray-100">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-gray-800">
                        {appointment.appointment_date}
                      </div>
                      <div className="text-sm text-gray-500">
                        {appointment.appointment_time}
                      </div>
                      <p className="text-sm text-gray-600">
                        <span className="font-semibold">Type:</span>{" "}
                        {appointment.appointment_type === "phone_call"
                          ? "Phone Call"
                          : appointment.appointment_type === "video_call"
                            ? "Video Call"
                            : "In Person"}
                      </p>
                    </td>

                    <td className="px-6 py-4">
                      {user?.role === "patient" ? (
                        <div>
                          <div className="font-semibold text-gray-800">
                            Dr. {appointment.clinician_name}
                          </div>
                          <div className="text-sm text-gray-500">
                            {appointment.clinician_specialization || "General"}
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div className="font-semibold text-gray-800">
                            {appointment.patient_name}
                          </div>
                          <div className="text-sm text-gray-500">
                            {appointment.patient_email}
                          </div>
                        </div>
                      )}
                    </td>

                    <td className="px-6 py-4 max-w-xs">
                      <p className="text-gray-700 line-clamp-2">
                        {appointment.reason}
                      </p>
                    </td>

                    <td className="px-6 py-4">
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusClasses(
                          appointment.status,
                        )}`}
                      >
                        {appointment.status}
                      </span>
                    </td>

                    <td className="px-6 py-4">
                      {user?.role === "clinician" || user?.role === "admin" ? (
                        <div>
                          <textarea
                            rows="2"
                            value={
                              notesByAppointment[appointment.id] ??
                              appointment.notes ??
                              ""
                            }
                            onChange={(e) =>
                              setNotesByAppointment((prev) => ({
                                ...prev,
                                [appointment.id]: e.target.value,
                              }))
                            }
                            placeholder="Add notes"
                            className="w-48 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                          />
                          <button
                            type="button"
                            onClick={() => saveAppointmentNotes(appointment.id)}
                            disabled={loading}
                            className="mt-1 block text-xs font-semibold text-blue-700 hover:text-blue-900 disabled:opacity-50"
                          >
                            <i className="fas fa-floppy-disk mr-1"></i>
                            Save notes
                          </button>
                        </div>
                      ) : (
                        <span className="text-sm text-gray-600">
                          {appointment.notes || "No notes"}
                        </span>
                      )}
                    </td>

                    <td className="px-6 py-4">
                      <div className="flex flex-wrap items-start gap-2">
                        <button
                          onClick={() => setSelectedAppointment(appointment)}
                          className="inline-flex h-7 items-center gap-1 rounded-md bg-blue-50 px-2 text-xs font-medium text-blue-600 hover:bg-blue-100"
                        >
                          <i className="fas fa-eye text-xs"></i>
                          Details
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            downloadAppointmentCalendarFile(appointment)
                          }
                          className="inline-flex h-7 items-center gap-1 rounded-md bg-emerald-50 px-2 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
                        >
                          <i className="fas fa-calendar-plus text-xs"></i>
                          Calendar
                        </button>

                        {["patient", "clinician"].includes(user?.role) && (
                          <VideoConsultationButton appointment={appointment} />
                        )}

                        {user?.role === "clinician" &&
                          appointment.status === "pending" && (
                            <>
                              <button
                                onClick={() =>
                                  updateAppointmentStatus(
                                    appointment.id,
                                    "approved",
                                  )
                                }
                                className="bg-green-600 hover:bg-green-700 text-white px-3 py-2 rounded-lg text-sm"
                              >
                                Approve
                              </button>

                              <button
                                onClick={() =>
                                  updateAppointmentStatus(
                                    appointment.id,
                                    "rejected",
                                  )
                                }
                                className="bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded-lg text-sm"
                              >
                                Reject
                              </button>
                            </>
                          )}

                        {user?.role === "clinician" &&
                          appointment.status === "approved" && (
                            <button
                              onClick={() =>
                                updateAppointmentStatus(
                                  appointment.id,
                                  "completed",
                                )
                              }
                              className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-lg text-sm"
                            >
                              Complete
                            </button>
                          )}

                        {/* {user?.role === "patient" &&
                          ["pending", "approved"].includes(
                            appointment.status,
                          ) && (
                            <button
                              onClick={() =>
                                handleCancelAppointment(appointment.id)
                              }
                              className="inline-flex h-7 items-center rounded-md bg-gray-600 px-2 text-xs font-medium text-white hover:bg-gray-700"
                            >
                              Cancel
                            </button>
                          )} */}

                        {user?.role === "admin" && (
                          <>
                            <button
                              onClick={() =>
                                updateAppointmentStatus(
                                  appointment.id,
                                  "approved",
                                )
                              }
                              className="bg-green-600 hover:bg-green-700 text-white px-3 py-2 rounded-lg text-sm"
                            >
                              Approve
                            </button>

                            <button
                              onClick={() =>
                                updateAppointmentStatus(
                                  appointment.id,
                                  "rejected",
                                )
                              }
                              className="bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded-lg text-sm"
                            >
                              Reject
                            </button>

                            <button
                              onClick={() =>
                                updateAppointmentStatus(
                                  appointment.id,
                                  "completed",
                                )
                              }
                              className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-lg text-sm"
                            >
                              Complete
                            </button>
                          </>
                        )}
                        <AppointmentActions
                          appointment={appointment}
                          onRefresh={loadAppointments}
                        />

                        {user?.role === "admin" ||
                        (user?.role === "patient" &&
                          ["cancelled", "rejected", "expired"].includes(
                            appointment.status,
                          )) ||
                        (user?.role === "clinician" &&
                          ["rejected", "expired"].includes(appointment.status)) ? (
                          <button
                            onClick={() => deleteAppointment(appointment.id)}
                            className="bg-red-100 hover:bg-red-200 text-red-700 px-3 py-2 rounded-lg text-sm"
                          >
                            Delete
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <AppointmentDetailsDrawer
        appointment={selectedAppointment}
        user={user}
        message={message}
        error={error}
        patientSummary={
          patientSummaryState.appointmentId === selectedAppointment?.id
            ? patientSummaryState.data
            : null
        }
        patientSummaryLoading={
          patientSummaryState.appointmentId === selectedAppointment?.id &&
          patientSummaryState.loading
        }
        patientSummaryError={
          patientSummaryState.appointmentId === selectedAppointment?.id
            ? patientSummaryState.error
            : ""
        }
        notes={
          selectedAppointment
            ? (notesByAppointment[selectedAppointment.id] ??
              selectedAppointment.notes ??
              "")
            : ""
        }
        busy={loading}
        onClose={() => setSelectedAppointment(null)}
        onNotesChange={(notes) =>
          setNotesByAppointment((current) => ({
            ...current,
            [selectedAppointment.id]: notes,
          }))
        }
        onSaveNotes={() => saveAppointmentNotes(selectedAppointment.id)}
        onStatusChange={(status) =>
          updateAppointmentStatus(selectedAppointment.id, status)
        }
        onDelete={() => deleteAppointment(selectedAppointment.id)}
        onOpenPatientProfile={() => {
          const patient = {
            id: patientSummaryState.data?.patient?.id,
            email: selectedAppointment.patient_email,
            name: selectedAppointment.patient_name,
            canExport:
              user?.role === "admin" ||
              Boolean(patientSummaryState.data?.can_message),
          };
          setSelectedAppointment(null);
          onOpenPatientProfile?.(patient);
        }}
        onMessagePatient={() => {
          const patient = {
            email: selectedAppointment.patient_email,
            name: selectedAppointment.patient_name,
          };
          setSelectedAppointment(null);
          onMessagePatient?.(patient);
        }}
      />
    </div>
  );
};

export default Appointments;
