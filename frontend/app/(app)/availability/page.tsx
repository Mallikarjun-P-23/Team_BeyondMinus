"use client";

import { useLocalAuth } from "@/lib/local-auth";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createDoctorSlot,
  deleteDoctorSlot,
  getDoctorAvailabilitySettings,
  listDoctorAppointments,
  listDoctorSlots,
  updateDoctorAvailabilitySettings,
  type DoctorAppointmentItem,
  type DoctorAvailabilitySettings,
  type DoctorManagedSlot,
} from "@/services/api";
import { Button } from "@/components/ui/button";
import { CalendarClock, Loader2, Plus, RefreshCw, Trash2, X } from "lucide-react";

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatDayLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function formatTimeLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function slotTone(status: string) {
  if (status === "available") return "border-success/40 bg-success/10 text-success";
  if (status === "reserved") return "border-warning/40 bg-warning/10 text-warning";
  if (status === "completed") return "border-emerald-400/50 bg-emerald-50 text-emerald-700";
  if (status === "booked") return "border-primary/40 bg-primary/10 text-primary";
  return "border-border bg-muted/40 text-muted-foreground";
}

export default function AvailabilityPage() {
  const { user } = useLocalAuth();
  const doctorId = user?.doctor_id || user?.sub;

  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState<DoctorAvailabilitySettings | null>(null);
  const [slots, setSlots] = useState<DoctorManagedSlot[]>([]);
  const [appointmentStatusBySlotId, setAppointmentStatusBySlotId] = useState<Record<string, string>>({});
  const [statusFilter, setStatusFilter] = useState("all");
  const [toggling, setToggling] = useState(false);

  const [message, setMessage] = useState<string | null>(null);
  
  // Slot management state
  const [showAddSlotModal, setShowAddSlotModal] = useState(false);
  const [newSlotDate, setNewSlotDate] = useState("");
  const [newSlotStartTime, setNewSlotStartTime] = useState("10:30");
  const [newSlotEndTime, setNewSlotEndTime] = useState("11:00");
  const [isCreatingSlot, setIsCreatingSlot] = useState(false);
  const [isDeletingSlot, setIsDeletingSlot] = useState<string | null>(null);
  
  // Date selector for viewing specific day
  const [selectedViewDate, setSelectedViewDate] = useState("");
  
  // Bulk delete state
  const [showBulkDeleteModal, setShowBulkDeleteModal] = useState(false);
  const [bulkDeleteDate, setBulkDeleteDate] = useState("");
  const [bulkDeleteStartTime, setBulkDeleteStartTime] = useState("10:30");
  const [bulkDeleteEndTime, setBulkDeleteEndTime] = useState("16:30");
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  const fetchAvailabilityContext = useCallback(async () => {
    if (!doctorId) {
      setSettings(null);
      setSlots([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const [settingsData, slotsData, appointmentsData] = await Promise.all([
        getDoctorAvailabilitySettings(doctorId),
        listDoctorSlots(doctorId, { includePast: false }),
        listDoctorAppointments(doctorId),
      ]);
      setSettings(settingsData);
      setSlots(slotsData);

      const statusBySlot: Record<string, string> = {};
      for (const appt of (appointmentsData as DoctorAppointmentItem[])) {
        if (appt?.slot_id) {
          statusBySlot[appt.slot_id] = appt.status;
        }
      }
      setAppointmentStatusBySlotId(statusBySlot);
    } catch (err) {
      const text = err instanceof Error ? err.message : "Failed to load availability.";
      setMessage(text);
      setSettings(null);
      setSlots([]);
      setAppointmentStatusBySlotId({});
    } finally {
      setLoading(false);
    }
  }, [doctorId]);

  const getDisplayStatus = useCallback((slot: DoctorManagedSlot) => {
    const appointmentStatus = appointmentStatusBySlotId[slot.id];
    if (slot.status === "booked" && appointmentStatus === "completed") {
      return "completed";
    }
    return slot.status;
  }, [appointmentStatusBySlotId]);

  useEffect(() => {
    fetchAvailabilityContext();
  }, [fetchAvailabilityContext]);

  // Set default dates
  useEffect(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];
    setNewSlotDate(tomorrowStr);
    setSelectedViewDate(tomorrowStr);
    setBulkDeleteDate(tomorrowStr);
  }, []);

  const filteredSlots = useMemo(() => {
    let filtered = slots;
    
    // Filter by status
    if (statusFilter !== "all") {
      filtered = filtered.filter((slot) => getDisplayStatus(slot) === statusFilter);
    }
    
    // Filter by selected date
    if (selectedViewDate) {
      filtered = filtered.filter((slot) => {
        const slotDate = new Date(slot.slot_start).toISOString().split('T')[0];
        return slotDate === selectedViewDate;
      });
    }
    
    return filtered;
  }, [slots, statusFilter, getDisplayStatus, selectedViewDate]);

  const calendarData = useMemo(() => {
    const slotsMap = new Map<string, DoctorManagedSlot>();
    const allTimes = new Set<string>();

    for (const slot of filteredSlots) {
      const start = new Date(slot.slot_start);
      if (Number.isNaN(start.getTime())) continue;

      const timeKey = start.toISOString().slice(11, 16);
      allTimes.add(timeKey);
      slotsMap.set(timeKey, slot);
    }

    const times = Array.from(allTimes).sort((a, b) => a.localeCompare(b));

    return { times, slotsMap };
  }, [filteredSlots]);
  
  // Get available dates from all slots
  const availableDates = useMemo(() => {
    const dates = new Set<string>();
    for (const slot of slots) {
      const slotDate = new Date(slot.slot_start).toISOString().split('T')[0];
      dates.add(slotDate);
    }
    return Array.from(dates).sort();
  }, [slots]);

  const handleToggleAvailability = useCallback(async (nextValue: boolean) => {
    if (!doctorId) return;
    setToggling(true);
    setMessage(null);

    try {
      const updated = await updateDoctorAvailabilitySettings(doctorId, {
        is_available: nextValue,
        confirm_reschedule_today: false,
      });
      setSettings(updated);
      setMessage(nextValue ? "Doctor marked available. Rolling slots regenerated." : "Doctor marked unavailable.");
      const refreshedSlots = await listDoctorSlots(doctorId, { includePast: false });
      setSlots(refreshedSlots);
      return;
    } catch (err) {
      const knownErr = err as Error & {
        status?: number;
        detail?: { detail?: { code?: string; pending_today_appointments?: number } };
      };
      const maybeCode = knownErr.detail?.detail?.code;
      const pendingCount = knownErr.detail?.detail?.pending_today_appointments || 0;

      if (knownErr.status === 409 && maybeCode === "CONFIRM_REQUIRED") {
        const proceed = window.confirm(
          `${pendingCount} appointment(s) for today will be moved to the next working day. Continue?`,
        );
        if (!proceed) {
          setMessage("Toggle cancelled. No appointments were moved.");
          return;
        }

        const confirmed = await updateDoctorAvailabilitySettings(doctorId, {
          is_available: nextValue,
          confirm_reschedule_today: true,
        });
        setSettings(confirmed);
        setMessage(
          `Doctor marked unavailable. ${confirmed.rescheduled_appointments || 0} appointment(s) moved to next working day.`,
        );
        const refreshedSlots = await listDoctorSlots(doctorId, { includePast: false });
        setSlots(refreshedSlots);
        return;
      }

      const text = err instanceof Error ? err.message : "Could not update availability status.";
      setMessage(text);
    } finally {
      setToggling(false);
    }
  }, [doctorId]);

  const handleCreateSlot = useCallback(async () => {
    if (!doctorId || !newSlotDate || !newSlotStartTime || !newSlotEndTime) {
      setMessage("Please fill in all slot details.");
      return;
    }

    setIsCreatingSlot(true);
    setMessage(null);

    try {
      const slotStart = `${newSlotDate}T${newSlotStartTime}:00`;
      const slotEnd = `${newSlotDate}T${newSlotEndTime}:00`;

      await createDoctorSlot(doctorId, {
        slot_start: slotStart,
        slot_end: slotEnd,
        status: "available",
      });

      setMessage("Slot created successfully!");
      setShowAddSlotModal(false);
      
      // Reset form
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      setNewSlotDate(tomorrow.toISOString().split('T')[0]);
      setNewSlotStartTime("10:30");
      setNewSlotEndTime("11:00");

      // Refresh slots
      await fetchAvailabilityContext();
    } catch (err) {
      const text = err instanceof Error ? err.message : "Failed to create slot.";
      setMessage(text);
    } finally {
      setIsCreatingSlot(false);
    }
  }, [doctorId, newSlotDate, newSlotStartTime, newSlotEndTime, fetchAvailabilityContext]);

  const handleDeleteSlot = useCallback(async (slotId: string, slotStatus: string) => {
    if (!doctorId) return;

    if (slotStatus === "booked" || slotStatus === "completed") {
      setMessage("Cannot delete booked or completed slots.");
      return;
    }

    const confirm = window.confirm("Are you sure you want to delete this slot?");
    if (!confirm) return;

    setIsDeletingSlot(slotId);
    setMessage(null);

    try {
      await deleteDoctorSlot(doctorId, slotId);
      setMessage("Slot deleted successfully!");
      await fetchAvailabilityContext();
    } catch (err) {
      const text = err instanceof Error ? err.message : "Failed to delete slot.";
      setMessage(text);
    } finally {
      setIsDeletingSlot(null);
    }
  }, [doctorId, fetchAvailabilityContext]);

  const handleBulkDeleteSlots = useCallback(async () => {
    if (!doctorId || !bulkDeleteDate || !bulkDeleteStartTime || !bulkDeleteEndTime) {
      setMessage("Please fill in all bulk delete details.");
      return;
    }

    // Find slots within the time range for the selected date
    const slotsToDelete = slots.filter((slot) => {
      const slotDate = new Date(slot.slot_start).toISOString().split('T')[0];
      if (slotDate !== bulkDeleteDate) return false;

      const slotTime = new Date(slot.slot_start).toISOString().slice(11, 16);
      const canDelete = slot.status === "available" || slot.status === "cancelled";
      
      return canDelete && slotTime >= bulkDeleteStartTime && slotTime <= bulkDeleteEndTime;
    });

    if (slotsToDelete.length === 0) {
      setMessage("No available slots found in the specified time range.");
      return;
    }

    const confirm = window.confirm(
      `Are you sure you want to delete ${slotsToDelete.length} slot(s) from ${bulkDeleteStartTime} to ${bulkDeleteEndTime}?`
    );
    if (!confirm) return;

    setIsBulkDeleting(true);
    setMessage(null);

    try {
      let deletedCount = 0;
      let errorCount = 0;

      for (const slot of slotsToDelete) {
        try {
          await deleteDoctorSlot(doctorId, slot.id);
          deletedCount++;
        } catch (err) {
          errorCount++;
          console.error(`Failed to delete slot ${slot.id}:`, err);
        }
      }

      if (errorCount === 0) {
        setMessage(`Successfully deleted ${deletedCount} slot(s)!`);
      } else {
        setMessage(`Deleted ${deletedCount} slot(s), but ${errorCount} failed.`);
      }

      setShowBulkDeleteModal(false);
      await fetchAvailabilityContext();
    } catch (err) {
      const text = err instanceof Error ? err.message : "Failed to delete slots.";
      setMessage(text);
    } finally {
      setIsBulkDeleting(false);
    }
  }, [doctorId, bulkDeleteDate, bulkDeleteStartTime, bulkDeleteEndTime, slots, fetchAvailabilityContext]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Manage Availability</h1>
        <p className="text-sm text-muted-foreground">
          Toggle your day planning and keep an auto-managed 30-day rolling slot window.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold">Doctor Toggle</h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            disabled={loading || toggling || settings?.is_available === true}
            onClick={() => handleToggleAvailability(true)}
          >
            {toggling && settings?.is_available === false ? "Updating..." : "Set Available"}
          </Button>
          <Button
            variant="outline"
            disabled={loading || toggling || settings?.is_available === false}
            onClick={() => handleToggleAvailability(false)}
          >
            {toggling && settings?.is_available === true ? "Updating..." : "Set Not Available"}
          </Button>
          <Button variant="ghost" disabled={loading || toggling} onClick={fetchAvailabilityContext}>
            <RefreshCw className="mr-2 size-4" />Refresh
          </Button>
          <span className="rounded-full border border-border px-2 py-1 text-xs text-muted-foreground">
            Current: {settings?.is_available ? "Available" : "Not Available"}
          </span>
          <span className="rounded-full border border-border px-2 py-1 text-xs text-muted-foreground">
            Pending today: {settings?.pending_today_appointments || 0}
          </span>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Rule set: 10:30 AM to 4:30 PM, 30-minute slots, 1:30 PM to 2:30 PM break, Sundays closed, rolling 30-day window.
        </p>
      </div>

      {/* Manual Slot Management Section */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold">Manual Slot Management</h2>
            <p className="text-xs text-muted-foreground">
              Add or remove specific time slots beyond the automated schedule.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowBulkDeleteModal(!showBulkDeleteModal)}
              disabled={loading}
            >
              <Trash2 className="mr-2 size-4" />
              {showBulkDeleteModal ? "Cancel" : "Bulk Delete"}
            </Button>
            <Button
              size="sm"
              onClick={() => setShowAddSlotModal(!showAddSlotModal)}
              disabled={loading}
            >
              <Plus className="mr-2 size-4" />
              {showAddSlotModal ? "Cancel" : "Add Slot"}
            </Button>
          </div>
        </div>

        {showAddSlotModal && (
          <div className="mt-4 rounded-lg border border-border bg-muted/30 p-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-foreground">
                  Date
                </label>
                <input
                  type="date"
                  value={newSlotDate}
                  onChange={(e) => setNewSlotDate(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  disabled={isCreatingSlot}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-foreground">
                  Start Time
                </label>
                <input
                  type="time"
                  value={newSlotStartTime}
                  onChange={(e) => setNewSlotStartTime(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  disabled={isCreatingSlot}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-foreground">
                  End Time
                </label>
                <input
                  type="time"
                  value={newSlotEndTime}
                  onChange={(e) => setNewSlotEndTime(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  disabled={isCreatingSlot}
                />
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <Button
                onClick={handleCreateSlot}
                disabled={isCreatingSlot || !newSlotDate || !newSlotStartTime || !newSlotEndTime}
                size="sm"
              >
                {isCreatingSlot ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus className="mr-2 size-4" />
                    Create Slot
                  </>
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAddSlotModal(false)}
                disabled={isCreatingSlot}
              >
                <X className="mr-2 size-4" />
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Bulk Delete Modal */}
        {showBulkDeleteModal && (
          <div className="mt-4 rounded-lg border border-border bg-muted/30 p-4">
            <h3 className="mb-3 text-sm font-semibold">Bulk Delete Slots</h3>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-foreground">
                  Date
                </label>
                <input
                  type="date"
                  value={bulkDeleteDate}
                  onChange={(e) => setBulkDeleteDate(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  disabled={isBulkDeleting}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-foreground">
                  From Time
                </label>
                <input
                  type="time"
                  value={bulkDeleteStartTime}
                  onChange={(e) => setBulkDeleteStartTime(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  disabled={isBulkDeleting}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-foreground">
                  To Time
                </label>
                <input
                  type="time"
                  value={bulkDeleteEndTime}
                  onChange={(e) => setBulkDeleteEndTime(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  disabled={isBulkDeleting}
                />
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Only available and cancelled slots can be deleted. Booked and completed slots will be skipped.
            </p>
            <div className="mt-4 flex gap-2">
              <Button
                onClick={handleBulkDeleteSlots}
                disabled={isBulkDeleting || !bulkDeleteDate || !bulkDeleteStartTime || !bulkDeleteEndTime}
                size="sm"
                variant="destructive"
              >
                {isBulkDeleting ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 size-4" />
                    Delete Slots
                  </>
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowBulkDeleteModal(false)}
                disabled={isBulkDeleting}
              >
                <X className="mr-2 size-4" />
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Daily Slots View</h2>
            <p className="text-xs text-muted-foreground">View and manage slots for a specific day. Click trash icon to delete individual slots.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={selectedViewDate}
              onChange={(e) => setSelectedViewDate(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium"
            >
              <option value="">Select Date</option>
              {availableDates.map((date) => (
                <option key={date} value={date}>
                  {new Date(date + 'T12:00:00').toLocaleDateString(undefined, { 
                    weekday: 'short', 
                    month: 'short', 
                    day: 'numeric',
                    year: 'numeric'
                  })}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-xs"
            >
              <option value="all">All Status</option>
              <option value="available">Available</option>
              <option value="reserved">Reserved</option>
              <option value="completed">Completed</option>
              <option value="booked">Booked</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <span className="rounded-full border border-success/30 bg-success/10 px-2 py-1 text-[11px] text-success">Available</span>
            <span className="rounded-full border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">Reserved</span>
            <span className="rounded-full border border-emerald-400/50 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">Completed</span>
            <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-1 text-[11px] text-primary">Booked</span>
            <span className="rounded-full border border-border bg-muted/30 px-2 py-1 text-[11px] text-muted-foreground">Cancelled</span>
          </div>
        </div>

        {loading ? (
          <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading slots...
          </div>
        ) : !selectedViewDate ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-8 text-center">
            <p className="text-sm text-muted-foreground">Please select a date from the dropdown to view slots.</p>
          </div>
        ) : filteredSlots.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-8 text-center">
            <p className="text-sm text-muted-foreground">No slots found for the selected date and filters.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {calendarData.times.map((timeKey) => {
              const slot = calendarData.slotsMap.get(timeKey);
              if (!slot) return null;
              
              const displayStatus = getDisplayStatus(slot);
              const canDelete = slot.status === "available" || slot.status === "cancelled";
              const isDeleting = isDeletingSlot === slot.id;
              
              return (
                <div
                  key={timeKey}
                  className={`group relative flex items-center justify-between rounded-lg border p-3 ${slotTone(displayStatus || slot.status)}`}
                >
                  <div className="flex items-center gap-3">
                    <CalendarClock className="size-5" />
                    <div>
                      <p className="text-sm font-semibold">
                        {formatTimeLabel(`1970-01-01T${timeKey}:00Z`)}
                      </p>
                      <p className="text-xs opacity-80">
                        {formatDateTime(slot.slot_start)} - {formatDateTime(slot.slot_end)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide">
                      {displayStatus || slot.status}
                    </span>
                    {canDelete && !isDeleting && (
                      <button
                        onClick={() => handleDeleteSlot(slot.id, slot.status)}
                        className="rounded bg-destructive p-2 text-destructive-foreground opacity-0 transition-opacity hover:opacity-100 group-hover:opacity-100"
                        title="Delete slot"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    )}
                    {isDeleting && (
                      <div className="flex items-center justify-center p-2">
                        <Loader2 className="size-4 animate-spin" />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {message && (
        <div className={`rounded-lg border px-3 py-2 text-xs ${
          message.includes("success") || message.includes("marked available") || message.includes("marked unavailable")
            ? "border-success/30 bg-success/10 text-success"
            : message.includes("Failed") || message.includes("Cannot")
            ? "border-destructive/30 bg-destructive/10 text-destructive"
            : "border-border bg-muted/30 text-muted-foreground"
        }`}>
          {message}
        </div>
      )}
    </div>
  );
}