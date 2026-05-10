"use client";

import { useState, useEffect, useCallback } from "react";
import { useLocalAuth } from "@/lib/local-auth";
import {
  listBloodRequests,
  listBloodRequestNotifications,
  acknowledgeBloodRequest,
  fulfillBloodRequest,
  updateBloodRequestStatus,
  markNotificationRead,
  markAllNotificationsRead,
  getBloodRequestStats,
  type BloodRequest,
  type BloodRequestNotification,
  type BloodRequestStats,
} from "@/services/api";
import { Button } from "@/components/ui/button";
import {
  Droplet,
  AlertCircle,
  Calendar,
  MapPin,
  Phone,
  User,
  Clock,
  CheckCircle2,
  Bell,
  BellOff,
  Filter,
  Loader2,
  TrendingUp,
  Activity,
  AlertTriangle,
  Package,
  XCircle,
  FileText,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const STATUS_COLORS = {
  pending: "bg-yellow-50 text-yellow-700 border-yellow-200",
  acknowledged: "bg-blue-50 text-blue-700 border-blue-200",
  arranged: "bg-purple-50 text-purple-700 border-purple-200",
  fulfilled: "bg-green-50 text-green-700 border-green-200",
  cancelled: "bg-red-50 text-red-700 border-red-200",
  expired: "bg-gray-50 text-gray-700 border-gray-200",
};

const PRIORITY_COLORS = {
  critical: "bg-red-100 text-red-800 border-red-300",
  high: "bg-orange-100 text-orange-800 border-orange-300",
  normal: "bg-blue-100 text-blue-800 border-blue-300",
  low: "bg-gray-100 text-gray-800 border-gray-300",
};

export default function BloodRequestsPage() {
  const router = useRouter();
  const { user } = useLocalAuth();
  const doctorId = user?.doctor_id || user?.sub;

  const [requests, setRequests] = useState<BloodRequest[]>([]);
  const [notifications, setNotifications] = useState<BloodRequestNotification[]>([]);
  const [stats, setStats] = useState<BloodRequestStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [expandedRequest, setExpandedRequest] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [emergencyFilter, setEmergencyFilter] = useState<boolean | undefined>(undefined);
  const [bloodGroupFilter, setBloodGroupFilter] = useState<string>("all");
  const [showNotifications, setShowNotifications] = useState(true);

  const loadData = useCallback(async () => {
    if (!doctorId) return;

    try {
      setLoading(true);

      const filters: any = { doctor_id: doctorId };
      if (statusFilter !== "all") filters.status = statusFilter;
      if (emergencyFilter !== undefined) filters.is_emergency = emergencyFilter;
      if (bloodGroupFilter !== "all") filters.blood_group = bloodGroupFilter;

      const [requestsData, notificationsData, statsData] = await Promise.all([
        listBloodRequests(filters),
        listBloodRequestNotifications(doctorId, false),
        getBloodRequestStats(doctorId),
      ]);

      setRequests(requestsData);
      setNotifications(notificationsData);
      setStats(statsData);
    } catch (err) {
      console.error("Failed to load blood requests:", err);
    } finally {
      setLoading(false);
    }
  }, [doctorId, statusFilter, emergencyFilter, bloodGroupFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAcknowledge = async (requestId: string) => {
    if (!doctorId) return;
    setActionLoading(requestId);
    try {
      await acknowledgeBloodRequest(requestId, doctorId);
      router.push(`/blood-campaign?request_id=${requestId}`);
    } catch (err) {
      console.error("Failed to acknowledge:", err);
      alert("Failed to acknowledge request");
    } finally {
      setActionLoading(null);
    }
  };

  const handleFulfill = async (requestId: string) => {
    if (!doctorId) return;
    const notes = prompt("Enter fulfillment notes (optional):");
    setActionLoading(requestId);
    try {
      await fulfillBloodRequest(requestId, doctorId, notes || undefined);
      await loadData();
    } catch (err) {
      console.error("Failed to fulfill:", err);
      alert("Failed to fulfill request");
    } finally {
      setActionLoading(null);
    }
  };

  const handleStatusChange = async (requestId: string, newStatus: string) => {
    if (!doctorId) return;
    setActionLoading(requestId);
    try {
      await updateBloodRequestStatus(requestId, newStatus, doctorId);
      await loadData();
    } catch (err) {
      console.error("Failed to update status:", err);
      alert("Failed to update status");
    } finally {
      setActionLoading(null);
    }
  };

  const handleMarkAllRead = async () => {
    if (!doctorId) return;
    try {
      await markAllNotificationsRead(doctorId);
      await loadData();
    } catch (err) {
      console.error("Failed to mark all as read:", err);
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;
  const emergencyRequests = requests.filter((r) => r.is_emergency && r.status === "pending");

  if (loading) {
    return (
      <div className="min-h-screen bg-background bg-grain p-6 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
          <p className="mt-2 text-muted-foreground font-medium">Loading blood requests...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background bg-grain p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <div className="p-4 bg-red-50 rounded-2xl shadow-sm">
                <Droplet className="w-8 h-8 text-red-600" />
              </div>
              <div>
                <h1 className="text-3xl md:text-5xl font-serif font-bold text-foreground">Blood Requests</h1>
                <p className="text-muted-foreground italic font-medium">Coordinate emergency response & patient matching</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                onClick={() => setShowNotifications(!showNotifications)}
                className="relative"
              >
                {showNotifications ? (
                  <BellOff className="w-5 h-5" />
                ) : (
                  <>
                    <Bell className="w-5 h-5" />
                    {unreadCount > 0 && (
                      <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                        {unreadCount}
                      </span>
                    )}
                  </>
                )}
              </Button>
              <Link href="/dashboard">
                <Button variant="outline">Back to Dashboard</Button>
              </Link>
            </div>
          </div>

          {/* Emergency Alert */}
          {emergencyRequests.length > 0 && (
            <div className="bg-red-600 text-white rounded-2xl p-5 mb-6 shadow-xl shadow-red-900/10 animate-in fade-in slide-in-from-top-4 duration-500">
              <div className="flex items-start gap-4">
                <div className="bg-white/20 p-2 rounded-lg">
                  <AlertCircle className="w-6 h-6 text-white shrink-0" />
                </div>
                <div>
                  <h3 className="font-bold text-lg">
                    🚨 {emergencyRequests.length} Emergency Request{emergencyRequests.length > 1 ? "s" : ""} Pending
                  </h3>
                  <p className="text-red-50 text-sm mt-1 font-medium">
                    Immediate blood matching required. These patients are in critical condition.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="bg-card border border-border rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">Total Requests</p>
                  <p className="text-3xl font-bold text-foreground">{stats.total_requests}</p>
                </div>
                <div className="p-3 bg-stone-100 rounded-xl">
                  <Activity className="w-6 h-6 text-stone-600" />
                </div>
              </div>
            </div>

            <div className="bg-card border border-border rounded-2xl p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">Pending</p>
                  <p className="text-3xl font-bold text-warning">{stats.pending_requests}</p>
                </div>
                <div className="p-3 bg-warning/10 rounded-xl">
                  <Clock className="w-6 h-6 text-warning" />
                </div>
              </div>
            </div>

            <div className="bg-card border border-border rounded-2xl p-5 shadow-sm border-l-4 border-l-red-500">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">Emergency</p>
                  <p className="text-3xl font-bold text-red-600">{stats.emergency_requests}</p>
                </div>
                <div className="p-3 bg-red-50 rounded-xl">
                  <AlertTriangle className="w-6 h-6 text-red-600" />
                </div>
              </div>
            </div>

            <div className="bg-card border border-border rounded-2xl p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">Fulfilled</p>
                  <p className="text-3xl font-bold text-success">{stats.fulfilled_requests}</p>
                </div>
                <div className="p-3 bg-success/10 rounded-xl">
                  <CheckCircle2 className="w-6 h-6 text-success" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-card border border-border rounded-2xl p-6 shadow-sm mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="w-4 h-4 text-muted-foreground" />
            <h3 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Search Filters</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full px-4 py-2.5 bg-background border border-border rounded-xl focus:ring-2 focus:ring-primary outline-none text-sm transition-all shadow-sm"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="acknowledged">Acknowledged</option>
                <option value="arranged">Arranged</option>
                <option value="fulfilled">Fulfilled</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Blood Group</label>
              <select
                value={bloodGroupFilter}
                onChange={(e) => setBloodGroupFilter(e.target.value)}
                className="w-full px-4 py-2.5 bg-background border border-border rounded-xl focus:ring-2 focus:ring-primary outline-none text-sm transition-all shadow-sm"
              >
                <option value="all">All Blood Groups</option>
                {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((group) => (
                  <option key={group} value={group}>{group}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Emergency</label>
              <select
                value={emergencyFilter === undefined ? "all" : emergencyFilter ? "yes" : "no"}
                onChange={(e) => {
                  const val = e.target.value;
                  setEmergencyFilter(val === "all" ? undefined : val === "yes");
                }}
                className="w-full px-4 py-2.5 bg-background border border-border rounded-xl focus:ring-2 focus:ring-primary outline-none text-sm transition-all shadow-sm"
              >
                <option value="all">All Requests</option>
                <option value="yes">Emergency Only</option>
                <option value="no">Non-Emergency</option>
              </select>
            </div>

            <div className="flex items-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setStatusFilter("all");
                    setBloodGroupFilter("all");
                    setEmergencyFilter(undefined);
                  }}
                  className="w-full h-11 rounded-xl border-border hover:bg-muted font-bold"
                >
                  Reset Filters
                </Button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Requests List */}
          <div className="lg:col-span-2">
            <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
              <div className="p-5 border-b border-border bg-stone-100/30">
                <h2 className="text-lg font-serif font-bold flex items-center gap-2">
                  <Package className="w-5 h-5 text-red-600" />
                  Blood Requests ({requests.length})
                </h2>
              </div>

              <div className="divide-y divide-gray-200 max-h-[calc(100vh-300px)] overflow-y-auto">
                {requests.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <Droplet className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p>No blood requests found</p>
                  </div>
                ) : (
                  requests.map((request) => (
                    <div
                      key={request.id}
                      className={`p-4 hover:bg-gray-50 transition-colors ${
                        request.is_emergency ? "bg-red-50" : ""
                      }`}
                    >
                      {/* Request Header */}
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <div className="flex items-center gap-2">
                              <Droplet className="w-5 h-5 text-red-600" />
                              <span className="text-xl font-bold text-gray-900">
                                {request.blood_group}
                              </span>
                            </div>
                            
                            {request.is_emergency && (
                              <span className="px-2 py-1 bg-red-500 text-white text-xs font-bold rounded-full animate-pulse">
                                🚨 EMERGENCY
                              </span>
                            )}

                            <span className={`px-2 py-1 text-xs font-medium rounded-full border ${PRIORITY_COLORS[request.priority]}`}>
                              {request.priority.toUpperCase()}
                            </span>

                            <span className={`px-2 py-1 text-xs font-medium rounded-full border ${STATUS_COLORS[request.status]}`}>
                              {request.status.toUpperCase()}
                            </span>
                          </div>

                          <div className="flex items-center gap-4 text-sm text-gray-600">
                            <span className="flex items-center gap-1">
                              <User className="w-4 h-4" />
                              {request.patient_name}
                            </span>
                            <span className="flex items-center gap-1">
                              <Package className="w-4 h-4" />
                              {request.units_needed} unit{request.units_needed > 1 ? "s" : ""}
                            </span>
                            <span className="flex items-center gap-1">
                              <Calendar className="w-4 h-4" />
                              {new Date(request.needed_by_date).toLocaleString()}
                            </span>
                          </div>
                        </div>

                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setExpandedRequest(expandedRequest === request.id ? null : request.id)}
                        >
                          {expandedRequest === request.id ? (
                            <ChevronUp className="w-5 h-5" />
                          ) : (
                            <ChevronDown className="w-5 h-5" />
                          )}
                        </Button>
                      </div>

                      {/* Expanded Details */}
                      {expandedRequest === request.id && (
                        <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                            <div className="flex items-start gap-2">
                              <MapPin className="w-4 h-4 text-gray-500 shrink-0 mt-0.5" />
                              <div>
                                <p className="font-medium text-gray-700">Location</p>
                                <p className="text-gray-600">{request.location}</p>
                              </div>
                            </div>

                            <div className="flex items-start gap-2">
                              <Phone className="w-4 h-4 text-gray-500 shrink-0 mt-0.5" />
                              <div>
                                <p className="font-medium text-gray-700">Contact</p>
                                <p className="text-gray-600">{request.contact_number}</p>
                                {request.alternative_contact && (
                                  <p className="text-gray-500 text-xs">Alt: {request.alternative_contact}</p>
                                )}
                              </div>
                            </div>

                            {request.hospital_name && (
                              <div className="flex items-start gap-2">
                                <FileText className="w-4 h-4 text-gray-500 shrink-0 mt-0.5" />
                                <div>
                                  <p className="font-medium text-gray-700">Hospital</p>
                                  <p className="text-gray-600">{request.hospital_name}</p>
                                </div>
                              </div>
                            )}

                            {request.reason && (
                              <div className="flex items-start gap-2">
                                <AlertCircle className="w-4 h-4 text-gray-500 shrink-0 mt-0.5" />
                                <div>
                                  <p className="font-medium text-gray-700">Reason</p>
                                  <p className="text-gray-600">{request.reason}</p>
                                </div>
                              </div>
                            )}
                          </div>

                          {request.medical_condition && (
                            <div className="bg-blue-50 p-3 rounded-lg">
                              <p className="text-sm font-medium text-blue-900 mb-1">Medical Condition</p>
                              <p className="text-sm text-blue-700">{request.medical_condition}</p>
                            </div>
                          )}

                          {request.notes && (
                            <div className="bg-gray-50 p-3 rounded-lg">
                              <p className="text-sm font-medium text-gray-900 mb-1">Notes</p>
                              <p className="text-sm text-gray-700">{request.notes}</p>
                            </div>
                          )}

                          {request.acknowledged_at && (
                            <div className="bg-green-50 p-3 rounded-lg">
                              <p className="text-sm text-green-700">
                                ✓ Acknowledged on {new Date(request.acknowledged_at).toLocaleString()}
                              </p>
                            </div>
                          )}

                          {/* Action Buttons */}
                          <div className="flex gap-2 pt-2">
                            {request.status === "pending" && (
                              <Button
                                size="sm"
                                onClick={() => handleAcknowledge(request.id)}
                                disabled={actionLoading === request.id}
                                className="bg-black hover:bg-black/80 text-white px-4 py-2 rounded-xl"
                              >
                                {actionLoading === request.id ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                  <>
                                    <CheckCircle2 className="w-4 h-4 mr-1" />
                                    Acknowledge
                                  </>
                                )}
                              </Button>
                            )}

                            {(request.status === "acknowledged" || request.status === "arranged") && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleStatusChange(request.id, "arranged")}
                                  disabled={actionLoading === request.id || request.status === "arranged"}
                                >
                                  Mark as Arranged
                                </Button>
                                <Button
                                  size="sm"
                                  onClick={() => handleFulfill(request.id)}
                                  disabled={actionLoading === request.id}
                                  className="bg-green-600 hover:bg-green-700"
                                >
                                  {actionLoading === request.id ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                  ) : (
                                    <>
                                      <CheckCircle2 className="w-4 h-4 mr-1" />
                                      Mark as Fulfilled
                                    </>
                                  )}
                                </Button>
                              </>
                            )}

                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                const reason = prompt("Cancellation reason:");
                                if (reason) handleStatusChange(request.id, "cancelled");
                              }}
                              disabled={actionLoading === request.id || request.status === "fulfilled"}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            >
                              <XCircle className="w-4 h-4 mr-1" />
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Notifications Sidebar */}
          {showNotifications && (
            <div className="lg:col-span-1">
              <div className="bg-card border border-border rounded-2xl shadow-sm sticky top-6 overflow-hidden">
                <div className="p-5 border-b border-border bg-stone-100/30 flex items-center justify-between">
                  <h3 className="font-bold font-serif flex items-center gap-2">
                    <Bell className="w-5 h-5 text-red-600" />
                    Notifications ({unreadCount})
                  </h3>
                  {unreadCount > 0 && (
                    <Button size="sm" variant="ghost" onClick={handleMarkAllRead}>
                      Mark all read
                    </Button>
                  )}
                </div>

                <div className="divide-y divide-gray-200 max-h-[calc(100vh-250px)] overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">
                      <Bell className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">No notifications</p>
                    </div>
                  ) : (
                    notifications.map((notif) => (
                      <div
                        key={notif.id}
                        className={`p-3 hover:bg-gray-50 cursor-pointer ${
                          !notif.is_read ? "bg-blue-50" : ""
                        }`}
                        onClick={async () => {
                          if (!notif.is_read) {
                            await markNotificationRead(notif.id);
                            await loadData();
                          }
                        }}
                      >
                        <div className="flex items-start gap-2">
                          {!notif.is_read && (
                            <div className="w-2 h-2 bg-blue-600 rounded-full shrink-0 mt-2" />
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm text-gray-900 mb-1">
                              {notif.title}
                            </p>
                            <p className="text-xs text-gray-600 mb-2">
                              {notif.message}
                            </p>
                            <p className="text-xs text-gray-500">
                              {new Date(notif.created_at).toLocaleString()}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
