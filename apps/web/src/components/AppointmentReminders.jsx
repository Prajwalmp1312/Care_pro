import React, { useEffect, useState } from "react";
import axios from "axios";

const AppointmentReminders = () => {
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadReminders = async () => {
    try {
      setLoading(true);

      const token = localStorage.getItem("access_token");

      const response = await axios.get(
        "http://localhost:8000/api/appointment-reminders",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setReminders(response.data.reminders || []);
    } catch (error) {
      console.error("Error loading appointment reminders:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReminders();
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl bg-white p-5 shadow">
        Loading appointment reminders...
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-white p-5 shadow">
      <h2 className="mb-4 text-xl font-bold text-gray-900">
        Appointment Reminders
      </h2>

      {reminders.length === 0 ? (
        <p className="text-sm text-gray-500">
          No upcoming reminders.
        </p>
      ) : (
        <div className="space-y-3">
          {reminders.map((reminder) => (
            <div
              key={reminder.id}
              className="rounded-lg border border-gray-200 p-3"
            >
              <p className="font-semibold text-gray-900">
                {reminder.clinician_name}
              </p>

              <p className="text-sm text-gray-600">
                {reminder.appointment_date} at {reminder.appointment_time}
              </p>

              <p className="text-sm text-gray-600">
                Reminder: {reminder.reminder_type}
              </p>

              <p className="text-sm text-gray-600">
                Status: {reminder.status}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AppointmentReminders;