// import React, { useEffect, useRef, useState } from "react";
// import axios from "axios";

// const Notifications = () => {
//   const [notifications, setNotifications] = useState([]);
//   const [unreadCount, setUnreadCount] = useState(0);
//   const [open, setOpen] = useState(false);
//   const dropdownRef = useRef(null);

//   const getIcon = (type) => {
//     if (["appointment", "appointment_reminder"].includes(type))
//       return type === "appointment_reminder" ? "fa-clock" : "fa-calendar-check";
//     if (type === "prescription") return "fa-prescription-bottle-medical";
//     if (type === "message") return "fa-comments";
//     if (["alert", "emergency"].includes(type))
//       return "fa-triangle-exclamation";
//     if (type === "admin") return "fa-shield-alt";
//     return "fa-bell";
//   };

//   const getIconClasses = (type) => {
//     if (["appointment", "appointment_reminder"].includes(type))
//       return "bg-blue-100 text-blue-600";
//     if (type === "prescription") return "bg-purple-100 text-purple-600";
//     if (type === "message") return "bg-green-100 text-green-600";
//     if (["alert", "emergency"].includes(type))
//       return "bg-red-100 text-red-600";
//     if (type === "admin") return "bg-gray-100 text-gray-600";
//     return "bg-yellow-100 text-yellow-600";
//   };

//   const loadNotifications = async () => {
//     try {
//       const res = await axios.get("/api/notifications");
//       setNotifications(res.data.notifications || []);
//     } catch (err) {
//       console.error("Failed to load notifications:", err);
//     }
//   };

//   const loadUnreadCount = async () => {
//     try {
//       const res = await axios.get("/api/notifications/unread-count");
//       setUnreadCount(res.data.unread_count || 0);
//     } catch (err) {
//       console.error("Failed to load unread count:", err);
//     }
//   };

//   const refreshNotifications = async () => {
//     await loadNotifications();
//     await loadUnreadCount();
//   };

//   useEffect(() => {
//     refreshNotifications();

//     const interval = setInterval(() => {
//       refreshNotifications();
//     }, 30000);
//     const handleNotificationUpdate = () => refreshNotifications();
//     window.addEventListener(
//       "careconnect:notifications-updated",
//       handleNotificationUpdate,
//     );

//     return () => {
//       clearInterval(interval);
//       window.removeEventListener(
//         "careconnect:notifications-updated",
//         handleNotificationUpdate,
//       );
//     };
//   }, []);

//   useEffect(() => {
//     const handleClickOutside = (event) => {
//       if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
//         setOpen(false);
//       }
//     };

//     document.addEventListener("mousedown", handleClickOutside);
//     return () => document.removeEventListener("mousedown", handleClickOutside);
//   }, []);

//   const markAsRead = async (notificationId) => {
//     try {
//       await axios.put(`/api/notifications/${notificationId}/read`);
//       await refreshNotifications();
//     } catch (err) {
//       console.error("Failed to mark notification as read:", err);
//     }
//   };

//   const markAllAsRead = async () => {
//     try {
//       await axios.put("/api/notifications/read-all");
//       await refreshNotifications();
//     } catch (err) {
//       console.error("Failed to mark all as read:", err);
//     }
//   };

//   const deleteNotification = async (notificationId) => {
//     try {
//       await axios.delete(`/api/notifications/${notificationId}`);
//       await refreshNotifications();
//     } catch (err) {
//       console.error("Failed to delete notification:", err);
//     }
//   };

//   return (
//     <div className="relative" ref={dropdownRef}>
//       <button
//         onClick={() => setOpen((prev) => !prev)}
//         className="relative bg-white hover:bg-gray-100 text-gray-700 w-11 h-11 rounded-full shadow flex items-center justify-center transition"
//         title="Notifications"
//       >
//         <i className="fas fa-bell text-lg"></i>

//         {unreadCount > 0 && (
//           <span className="absolute -top-1 -right-1 bg-red-600 text-white text-xs min-w-5 h-5 px-1 rounded-full flex items-center justify-center font-bold">
//             {unreadCount > 9 ? "9+" : unreadCount}
//           </span>
//         )}
//       </button>

//       {open && (
//         <div className="absolute right-0 mt-3 w-96 bg-white rounded-xl shadow-2xl border border-gray-100 z-50 overflow-hidden">
//           <div className="p-4 border-b border-gray-100 flex items-center justify-between">
//             <div>
//               <h3 className="font-bold text-gray-800">Notifications</h3>
//               <p className="text-xs text-gray-500">
//                 {unreadCount} unread notification{unreadCount !== 1 ? "s" : ""}
//               </p>
//             </div>

//             {unreadCount > 0 && (
//               <button
//                 onClick={markAllAsRead}
//                 className="text-sm text-blue-600 hover:text-blue-700 font-semibold"
//               >
//                 Mark all read
//               </button>
//             )}
//           </div>

//           <div className="max-h-96 overflow-y-auto">
//             {notifications.length === 0 ? (
//               <div className="p-8 text-center text-gray-500">
//                 <i className="fas fa-bell-slash text-3xl mb-3 text-gray-300"></i>
//                 <p>No notifications</p>
//               </div>
//             ) : (
//               notifications.map((notification) => (
//                 <div
//                   key={notification.id}
//                   className={`p-4 border-b border-gray-100 hover:bg-gray-50 transition ${
//                     !notification.is_read ? "bg-blue-50" : "bg-white"
//                   }`}
//                 >
//                   <div className="flex gap-3">
//                     <div
//                       className={`w-10 h-10 rounded-full flex items-center justify-center ${getIconClasses(
//                         notification.type
//                       )}`}
//                     >
//                       <i className={`fas ${getIcon(notification.type)}`}></i>
//                     </div>

//                     <div className="flex-1">
//                       <div className="flex items-start justify-between gap-2">
//                         <h4 className="font-semibold text-gray-800 text-sm">
//                           {notification.title}
//                         </h4>

//                         <button
//                           onClick={() => deleteNotification(notification.id)}
//                           className="text-gray-400 hover:text-red-600"
//                           title="Delete"
//                         >
//                           <i className="fas fa-times"></i>
//                         </button>
//                       </div>

//                       <p className="text-sm text-gray-600 mt-1">
//                         {notification.message}
//                       </p>

//                       <div className="flex items-center justify-between mt-2">
//                         <span className="text-xs text-gray-400">
//                           {notification.created_at
//                             ? new Date(notification.created_at).toLocaleString()
//                             : ""}
//                         </span>

//                         {!notification.is_read && (
//                           <button
//                             onClick={() => markAsRead(notification.id)}
//                             className="text-xs text-blue-600 hover:text-blue-700 font-semibold"
//                           >
//                             Mark read
//                           </button>
//                         )}
//                       </div>
//                     </div>
//                   </div>
//                 </div>
//               ))
//             )}
//           </div>

//           <div className="p-3 bg-gray-50 text-center">
//             <button
//               onClick={refreshNotifications}
//               className="text-sm text-gray-600 hover:text-gray-800 font-medium"
//             >
//               <i className="fas fa-sync-alt mr-2"></i>
//               Refresh
//             </button>
//           </div>
//         </div>
//       )}
//     </div>
//   );
// };

// export default Notifications;

import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";

const notificationFilters = [
  { key: "all", label: "All", icon: "fa-layer-group" },
  { key: "unread", label: "Unread", icon: "fa-envelope" },
  { key: "appointment", label: "Appointments", icon: "fa-calendar-check" },
  {
    key: "prescription",
    label: "Prescriptions",
    icon: "fa-prescription-bottle-medical",
  },
  { key: "message", label: "Messages", icon: "fa-comments" },
  // { key: "record", label: "Records", icon: "fa-file-medical" },
  // { key: "emergency", label: "Emergency", icon: "fa-triangle-exclamation" },
  { key: "admin", label: "Admin", icon: "fa-shield-alt" },
];

const Notifications = () => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [showCenter, setShowCenter] = useState(false);
  const [activeFilter, setActiveFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [error, setError] = useState("");

  const dropdownRef = useRef(null);

  const normalizeType = (type) => {
    const value = String(type || "info").toLowerCase();

    if (["appointment", "appointment_reminder", "reminder"].includes(value)) {
      return "appointment";
    }

    if (["prescription", "medicine", "medication"].includes(value)) {
      return "prescription";
    }

    if (["message", "chat", "messages", "care_message"].includes(value)) {
      return "message";
    }

    if (["record", "records", "medical_record", "report"].includes(value)) {
      return "record";
    }

    if (["alert", "emergency", "sos"].includes(value)) {
      return "emergency";
    }

    if (["admin", "system"].includes(value)) {
      return "admin";
    }

    return "info";
  };

  const getIcon = (type) => {
    const normalizedType = normalizeType(type);

    if (normalizedType === "appointment") return "fa-calendar-check";
    if (normalizedType === "prescription")
      return "fa-prescription-bottle-medical";
    if (normalizedType === "message") return "fa-comments";
    if (normalizedType === "record") return "fa-file-medical";
    if (normalizedType === "emergency") return "fa-triangle-exclamation";
    if (normalizedType === "admin") return "fa-shield-alt";

    return "fa-bell";
  };

  const getToneClasses = (type, isRead = false) => {
    const normalizedType = normalizeType(type);

    const tones = {
      appointment: {
        icon: "bg-blue-100 text-blue-700",
        card: isRead ? "bg-white" : "bg-blue-50 border-blue-100",
        pill: "bg-blue-100 text-blue-700",
      },
      prescription: {
        icon: "bg-purple-100 text-purple-700",
        card: isRead ? "bg-white" : "bg-purple-50 border-purple-100",
        pill: "bg-purple-100 text-purple-700",
      },
      message: {
        icon: "bg-emerald-100 text-emerald-700",
        card: isRead ? "bg-white" : "bg-emerald-50 border-emerald-100",
        pill: "bg-emerald-100 text-emerald-700",
      },
      record: {
        icon: "bg-orange-100 text-orange-700",
        card: isRead ? "bg-white" : "bg-orange-50 border-orange-100",
        pill: "bg-orange-100 text-orange-700",
      },
      emergency: {
        icon: "bg-red-100 text-red-700",
        card: isRead ? "bg-white" : "bg-red-50 border-red-100",
        pill: "bg-red-100 text-red-700",
      },
      admin: {
        icon: "bg-slate-100 text-slate-700",
        card: isRead ? "bg-white" : "bg-slate-50 border-slate-200",
        pill: "bg-slate-100 text-slate-700",
      },
      info: {
        icon: "bg-yellow-100 text-yellow-700",
        card: isRead ? "bg-white" : "bg-yellow-50 border-yellow-100",
        pill: "bg-yellow-100 text-yellow-700",
      },
    };

    return tones[normalizedType] || tones.info;
  };

  const formatDateTime = (value) => {
    if (!value) return "";

    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  };

  const loadNotifications = async () => {
    try {
      setLoading(true);
      setError("");

      const [notificationsResult, countResult] = await Promise.all([
        axios.get("/api/notifications"),
        axios.get("/api/notifications/unread-count"),
      ]);

      setNotifications(notificationsResult.data.notifications || []);
      setUnreadCount(countResult.data.unread_count || 0);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load notifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();

    const interval = setInterval(() => {
      loadNotifications();
    }, 30000);

    const handleNotificationUpdate = () => loadNotifications();

    window.addEventListener(
      "careconnect:notifications-updated",
      handleNotificationUpdate,
    );

    return () => {
      clearInterval(interval);
      window.removeEventListener(
        "careconnect:notifications-updated",
        handleNotificationUpdate,
      );
    };
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const filteredNotifications = useMemo(() => {
    const search = searchTerm.trim().toLowerCase();

    return notifications.filter((notification) => {
      const type = normalizeType(notification.type);

      const matchesFilter =
        activeFilter === "all" ||
        (activeFilter === "unread" && !notification.is_read) ||
        activeFilter === type;

      const matchesSearch =
        !search ||
        String(notification.title || "")
          .toLowerCase()
          .includes(search) ||
        String(notification.message || "")
          .toLowerCase()
          .includes(search) ||
        String(notification.type || "")
          .toLowerCase()
          .includes(search);

      return matchesFilter && matchesSearch;
    });
  }, [notifications, activeFilter, searchTerm]);

  const summary = useMemo(() => {
    const result = {
      total: notifications.length,
      unread: notifications.filter((item) => !item.is_read).length,
      appointment: 0,
      prescription: 0,
      message: 0,
      record: 0,
      emergency: 0,
    };

    notifications.forEach((notification) => {
      const type = normalizeType(notification.type);

      if (result[type] !== undefined) {
        result[type] += 1;
      }
    });

    return result;
  }, [notifications]);

  const markAsRead = async (notificationId) => {
    try {
      setActionLoadingId(notificationId);
      setError("");

      await axios.put(`/api/notifications/${notificationId}/read`);
      await loadNotifications();
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to mark notification as read",
      );
    } finally {
      setActionLoadingId(null);
    }
  };

  const markAllAsRead = async () => {
    try {
      setActionLoadingId("all");
      setError("");

      await axios.put("/api/notifications/read-all");
      await loadNotifications();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Failed to mark all notifications as read",
      );
    } finally {
      setActionLoadingId(null);
    }
  };

  const deleteNotification = async (notificationId) => {
    try {
      setActionLoadingId(notificationId);
      setError("");

      await axios.delete(`/api/notifications/${notificationId}`);
      await loadNotifications();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete notification");
    } finally {
      setActionLoadingId(null);
    }
  };

  const openFullCenter = () => {
    setShowCenter(true);
    setOpen(false);
  };

  const NotificationItem = ({ notification, compact = false }) => {
    const type = normalizeType(notification.type);
    const tones = getToneClasses(notification.type, notification.is_read);

    return (
      <div
        className={`rounded-xl border p-4 transition hover:shadow-sm ${
          tones.card
        } ${notification.is_read ? "border-slate-100" : ""}`}
      >
        <div className="flex gap-3">
          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${tones.icon}`}
          >
            <i className={`fas ${getIcon(notification.type)}`}></i>
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="font-bold text-slate-900">
                    {notification.title}
                  </h4>

                  {!notification.is_read && (
                    <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[11px] font-bold text-white">
                      New
                    </span>
                  )}

                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-bold capitalize ${tones.pill}`}
                  >
                    {type}
                  </span>
                </div>

                <p
                  className={`mt-1 text-sm leading-6 text-slate-600 ${
                    compact ? "line-clamp-2" : ""
                  }`}
                >
                  {notification.message}
                </p>
              </div>

              <button
                type="button"
                onClick={() => deleteNotification(notification.id)}
                disabled={actionLoadingId === notification.id}
                className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                title="Delete notification"
              >
                <i className="fas fa-times"></i>
              </button>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs font-semibold text-slate-400">
                {formatDateTime(notification.created_at)}
              </span>

              {!notification.is_read ? (
                <button
                  type="button"
                  onClick={() => markAsRead(notification.id)}
                  disabled={actionLoadingId === notification.id}
                  className="text-xs font-bold text-blue-600 hover:text-blue-700 disabled:opacity-50"
                >
                  {actionLoadingId === notification.id
                    ? "Updating..."
                    : "Mark as read"}
                </button>
              ) : (
                <span className="text-xs font-bold text-slate-400">Read</span>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const FilterChips = () => (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {notificationFilters.map((filter) => {
        const isActive = activeFilter === filter.key;

        return (
          <button
            key={filter.key}
            type="button"
            onClick={() => setActiveFilter(filter.key)}
            className={`shrink-0 rounded-full px-3 py-2 text-xs font-bold transition ${
              isActive
                ? "bg-blue-600 text-white shadow"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            <i className={`fas ${filter.icon} mr-2`}></i>
            {filter.label}
          </button>
        );
      })}
    </div>
  );

  return (
    <>
      <div className="relative" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="relative flex h-11 w-11 items-center justify-center rounded-full bg-white text-slate-700 shadow transition hover:bg-slate-100"
          title="Notifications"
        >
          <i className="fas fa-bell text-lg"></i>

          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-xs font-bold text-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>

        {open && (
          <div
            className="fixed right-4 top-20 z-[99999] w-[calc(100vw-2rem)] max-w-[430px] max-h-[80vh] overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="border-b border-slate-100 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-black text-slate-900">
                    Notifications
                  </h3>
                  <p className="mt-1 text-xs font-semibold text-slate-500">
                    {unreadCount} unread out of {notifications.length}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={loadNotifications}
                    disabled={loading}
                    className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-200 disabled:opacity-50"
                  >
                    <i
                      className={`fas ${
                        loading ? "fa-spinner fa-spin" : "fa-sync-alt"
                      } mr-1`}
                    ></i>
                    Refresh
                  </button>

                  <button
                    type="button"
                    onClick={openFullCenter}
                    className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700"
                  >
                    View all
                  </button>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="rounded-lg bg-red-50 px-3 py-2 text-xs font-bold text-red-600 hover:bg-red-100"
                  >
                    Close
                  </button>
                </div>
              </div>

              <div className="mt-4">
                <FilterChips />
              </div>

              <div className="relative mt-3">
                <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"></i>
                <input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search notifications..."
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </div>

              {error && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
                  {error}
                </div>
              )}
            </div>

            <div className="max-h-[55vh] overflow-y-auto p-3">
              {filteredNotifications.length === 0 ? (
                <div className="p-8 text-center text-slate-500">
                  <i className="fas fa-bell-slash mb-3 text-3xl text-slate-300"></i>
                  <p className="font-bold text-slate-700">
                    No notifications found
                  </p>
                  <p className="mt-1 text-sm">
                    Try changing the filter or search text.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredNotifications.slice(0, 6).map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                      compact
                    />
                  ))}

                  {filteredNotifications.length > 6 && (
                    <button
                      type="button"
                      onClick={openFullCenter}
                      className="w-full rounded-xl bg-slate-100 px-4 py-3 text-sm font-bold text-slate-700 hover:bg-slate-200"
                    >
                      View {filteredNotifications.length - 6} more
                    </button>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50 p-3">
              {unreadCount > 0 ? (
                <button
                  type="button"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    markAllAsRead();
                  }}
                  disabled={actionLoadingId === "all"}
                  className="text-sm font-bold text-blue-600 hover:text-blue-700 disabled:opacity-50"
                >
                  {actionLoadingId === "all"
                    ? "Updating..."
                    : "Mark all as read"}
                </button>
              ) : (
                <span className="text-sm font-semibold text-slate-400">
                  All caught up
                </span>
              )}

              <button
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  setOpen(false);
                }}
                className="relative z-[100000] rounded-xl bg-white px-4 py-3 text-sm font-bold text-blue-600 shadow-sm hover:bg-blue-50"
              >
                <i className="fas fa-times mr-2"></i>
                Close
              </button>
            </div>
          </div>
        )}
      </div>

      {showCenter && (
        <div className="fixed inset-0 z-[999999] bg-slate-950/60">
          <div className="fixed right-0 top-0 z-[1000000] flex h-screen w-full max-w-3xl flex-col bg-white shadow-2xl">
            <div className="shrink-0 bg-gradient-to-r from-blue-600 to-indigo-700 p-6 text-white">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.25em] text-blue-100">
                    Patient Notification Center
                  </p>

                  <h2 className="mt-2 text-2xl font-black">
                    Your care updates
                  </h2>

                  <p className="mt-1 text-sm text-blue-100">
                    Appointments, prescriptions, messages, records, and alerts.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setShowCenter(false)}
                  className="rounded-xl bg-white px-4 py-2 text-sm font-bold text-blue-700 hover:bg-blue-50"
                >
                  <i className="fas fa-times mr-2"></i>
                  Close
                </button>
              </div>
            </div>

            <div className="shrink-0 border-b border-slate-100 bg-white p-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-xl bg-slate-50 p-3">
                  <p className="text-xs font-bold uppercase text-slate-500">
                    Total
                  </p>
                  <p className="mt-1 text-2xl font-black text-slate-900">
                    {summary.total}
                  </p>
                </div>

                <div className="rounded-xl bg-blue-50 p-3">
                  <p className="text-xs font-bold uppercase text-blue-600">
                    Unread
                  </p>
                  <p className="mt-1 text-2xl font-black text-blue-700">
                    {summary.unread}
                  </p>
                </div>

                <div className="rounded-xl bg-purple-50 p-3">
                  <p className="text-xs font-bold uppercase text-purple-600">
                    Prescriptions
                  </p>
                  <p className="mt-1 text-2xl font-black text-purple-700">
                    {summary.prescription}
                  </p>
                </div>

                <div className="rounded-xl bg-emerald-50 p-3">
                  <p className="text-xs font-bold uppercase text-emerald-600">
                    Messages
                  </p>
                  <p className="mt-1 text-2xl font-black text-emerald-700">
                    {summary.message}
                  </p>
                </div>
              </div>

              <div className="mt-4">
                <FilterChips />
              </div>

              <div className="mt-4 flex gap-2">
                <div className="relative flex-1">
                  <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"></i>
                  <input
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    placeholder="Search notifications..."
                    className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  />
                </div>

                <button
                  type="button"
                  onClick={loadNotifications}
                  disabled={loading}
                  className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                >
                  Refresh
                </button>

                {unreadCount > 0 && (
                  <button
                    type="button"
                    onClick={markAllAsRead}
                    disabled={actionLoadingId === "all"}
                    className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    Mark all read
                  </button>
                )}
              </div>

              {error && (
                <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
                  {error}
                </div>
              )}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50 p-4">
              {filteredNotifications.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-10 text-center">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                    <i className="fas fa-bell-slash text-xl"></i>
                  </div>

                  <h3 className="mt-4 text-lg font-black text-slate-900">
                    No notifications found
                  </h3>

                  <p className="mt-2 text-sm text-slate-500">
                    No notifications match the current filter.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredNotifications.map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Notifications;