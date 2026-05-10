"use client";

import { useState, useEffect } from "react";
import { useLocalAuth } from "@/lib/local-auth";
import { 
  createBloodRequest, 
  listBloodRequests,
  getPatientPortalMe,
  listDoctors,
  type BloodRequest,
  type PatientPortalProfile,
  type DoctorListItem
} from "@/services/api";
import { Button } from "@/components/ui/button";
import { 
  Droplet, 
  AlertCircle, 
  Calendar, 
  MapPin, 
  Phone, 
  User,
  FileText,
  Loader2,
  CheckCircle2,
  Clock,
  XCircle,
  Stethoscope
} from "lucide-react";
import Link from "next/link";

const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

export default function BloodRequestPage() {
  const { user, isAuthenticated } = useLocalAuth();
  const authUserId = user?.sub ?? "";

  const [profile, setProfile] = useState<PatientPortalProfile | null>(null);
  const [requests, setRequests] = useState<BloodRequest[]>([]);
  const [doctors, setDoctors] = useState<DoctorListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Form state
  const [patientName, setPatientName] = useState("");
  const [bloodGroup, setBloodGroup] = useState("");
  const [unitsNeeded, setUnitsNeeded] = useState(1);
  const [location, setLocation] = useState("");
  const [neededByDate, setNeededByDate] = useState("");
  const [contactNumber, setContactNumber] = useState("");
  const [alternativeContact, setAlternativeContact] = useState("");
  const [isEmergency, setIsEmergency] = useState(false);
  const [reason, setReason] = useState("");
  const [medicalCondition, setMedicalCondition] = useState("");
  const [hospitalName, setHospitalName] = useState("");
  const [selectedDoctorId, setSelectedDoctorId] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!isAuthenticated || !authUserId) {
      setLoading(false);
      return;
    }

    const loadData = async () => {
      try {
        const [profileData, doctorsData] = await Promise.all([
          getPatientPortalMe(authUserId),
          listDoctors()
        ]);
        
        setProfile(profileData);
        setDoctors(doctorsData);
        
        if (profileData) {
          setPatientName(profileData.name || "");
          setContactNumber(profileData.phone || "");
          setSelectedDoctorId(profileData.doctor_id || "");
          
          // Load existing requests
          const requestsData = await listBloodRequests({ patient_id: profileData.id });
          setRequests(requestsData);
        }
      } catch (err) {
        console.error("Failed to load data:", err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [authUserId, isAuthenticated]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!profile) {
      setMessage({ type: "error", text: "Please complete your profile first" });
      return;
    }

    if (!bloodGroup || !location || !neededByDate || !contactNumber) {
      setMessage({ type: "error", text: "Please fill in all required fields" });
      return;
    }

    setSubmitting(true);
    setMessage(null);

    try {
      const newRequest = await createBloodRequest({
        patient_id: profile.id,
        patient_name: patientName,
        blood_group: bloodGroup,
        units_needed: unitsNeeded,
        location: location,
        needed_by_date: neededByDate,
        contact_number: contactNumber,
        alternative_contact: alternativeContact || undefined,
        is_emergency: isEmergency,
        reason: reason || undefined,
        medical_condition: medicalCondition || undefined,
        hospital_name: hospitalName || undefined,
        doctor_id: selectedDoctorId || undefined,
        notes: notes || undefined,
      });

      setMessage({ 
        type: "success", 
        text: isEmergency 
          ? "🚨 Emergency blood request submitted! Doctors have been notified." 
          : "✅ Blood request submitted successfully!"
      });

      // Reset form
      setBloodGroup("");
      setUnitsNeeded(1);
      setLocation("");
      setNeededByDate("");
      setAlternativeContact("");
      setIsEmergency(false);
      setReason("");
      setMedicalCondition("");
      setHospitalName("");
      setNotes("");

      // Reload requests
      const requestsData = await listBloodRequests({ patient_id: profile.id });
      setRequests(requestsData);

      // Scroll to top to show message
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to submit blood request";
      setMessage({ type: "error", text: errorMsg });
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending": return "text-yellow-600 bg-yellow-50";
      case "acknowledged": return "text-blue-600 bg-blue-50";
      case "arranged": return "text-purple-600 bg-purple-50";
      case "fulfilled": return "text-green-600 bg-green-50";
      case "cancelled": return "text-red-600 bg-red-50";
      case "expired": return "text-gray-600 bg-gray-50";
      default: return "text-gray-600 bg-gray-50";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending": return <Clock className="w-4 h-4" />;
      case "acknowledged": return <CheckCircle2 className="w-4 h-4" />;
      case "fulfilled": return <CheckCircle2 className="w-4 h-4" />;
      case "cancelled": return <XCircle className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-pink-50 p-6 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-red-600" />
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-pink-50 p-6 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">Authentication Required</h2>
          <p className="text-gray-600 mb-6">Please sign in to request blood.</p>
          <Link href="/sign-in">
            <Button>Sign In</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-pink-50 p-6 flex items-center justify-center">
        <div className="text-center max-w-md">
          <User className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">Profile Setup Required</h2>
          <p className="text-gray-600 mb-6">Please complete your patient profile first.</p>
          <Link href="/patient">
            <Button>Complete Profile</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-pink-50 p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link href="/patient">
            <Button variant="ghost" className="mb-4">
              ← Back to Dashboard
            </Button>
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-3 bg-red-100 rounded-xl">
              <Droplet className="w-8 h-8 text-red-600" />
            </div>
            <div>
              <h1 className="text-3xl md:text-4xl font-bold text-gray-900">Blood Request</h1>
              <p className="text-gray-600">Request blood for yourself or a loved one</p>
            </div>
          </div>
        </div>

        {/* Message */}
        {message && (
          <div className={`mb-6 p-4 rounded-lg ${
            message.type === "success" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
          }`}>
            <div className="flex items-start gap-2">
              {message.type === "success" ? (
                <CheckCircle2 className="w-5 h-5 mt-0.5 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
              )}
              <p>{message.text}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Request Form */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-2xl shadow-lg p-6 md:p-8">
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                <FileText className="w-6 h-6 text-red-600" />
                New Blood Request
              </h2>

              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Emergency Alert */}
                <div className={`p-4 rounded-lg border-2 transition-all ${
                  isEmergency 
                    ? "border-red-500 bg-red-50" 
                    : "border-gray-200 bg-gray-50"
                }`}>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isEmergency}
                      onChange={(e) => setIsEmergency(e.target.checked)}
                      className="w-5 h-5 text-red-600 rounded focus:ring-red-500"
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 font-semibold text-gray-900">
                        <AlertCircle className="w-5 h-5 text-red-600" />
                        Mark as Emergency
                      </div>
                      <p className="text-sm text-gray-600 mt-1">
                        {isEmergency 
                          ? "🚨 All available doctors will be notified immediately"
                          : "Check this if you need blood urgently"}
                      </p>
                    </div>
                  </label>
                </div>

                {/* Basic Information */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Patient Name *
                    </label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="text"
                        value={patientName}
                        onChange={(e) => setPatientName(e.target.value)}
                        required
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                        placeholder="Enter patient name"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Blood Group *
                    </label>
                    <div className="relative">
                      <Droplet className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <select
                        value={bloodGroup}
                        onChange={(e) => setBloodGroup(e.target.value)}
                        required
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent appearance-none bg-white"
                      >
                        <option value="">Select blood group</option>
                        {BLOOD_GROUPS.map((group) => (
                          <option key={group} value={group}>{group}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Units Needed *
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={unitsNeeded}
                      onChange={(e) => setUnitsNeeded(parseInt(e.target.value))}
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Needed By Date *
                    </label>
                    <div className="relative">
                      <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="datetime-local"
                        value={neededByDate}
                        onChange={(e) => setNeededByDate(e.target.value)}
                        required
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                </div>

                {/* Doctor Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Send Request To *
                  </label>
                  <div className="relative">
                    <Stethoscope className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <select
                      value={selectedDoctorId}
                      onChange={(e) => setSelectedDoctorId(e.target.value)}
                      required
                      className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent appearance-none bg-white"
                    >
                      <option value="">Select a doctor</option>
                      {doctors.map((doctor) => (
                        <option key={doctor.id} value={doctor.id}>
                          {doctor.name} ({doctor.specialty})
                        </option>
                      ))}
                    </select>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Select which doctor should receive and manage this blood request.
                  </p>
                </div>

                {/* Location & Hospital */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Location/Address *
                    </label>
                    <div className="relative">
                      <MapPin className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
                      <textarea
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                        required
                        rows={2}
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                        placeholder="Hospital name, room number, or address"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Hospital Name (Optional)
                    </label>
                    <input
                      type="text"
                      value={hospitalName}
                      onChange={(e) => setHospitalName(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      placeholder="e.g., City General Hospital"
                    />
                  </div>
                </div>

                {/* Contact */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Contact Number *
                    </label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="tel"
                        value={contactNumber}
                        onChange={(e) => setContactNumber(e.target.value)}
                        required
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                        placeholder="+1234567890"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Alternative Contact (Optional)
                    </label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="tel"
                        value={alternativeContact}
                        onChange={(e) => setAlternativeContact(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                        placeholder="+0987654321"
                      />
                    </div>
                  </div>
                </div>

                {/* Medical Details */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Reason for Blood Request (Optional)
                    </label>
                    <input
                      type="text"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      placeholder="e.g., Surgery, Accident"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Medical Condition (Optional)
                    </label>
                    <textarea
                      value={medicalCondition}
                      onChange={(e) => setMedicalCondition(e.target.value)}
                      rows={2}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      placeholder="Brief description of medical condition"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Additional Notes (Optional)
                    </label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={2}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      placeholder="Any other information"
                    />
                  </div>
                </div>

                {/* Submit Button */}
                <Button
                  type="submit"
                  disabled={submitting}
                  className={`w-full py-6 text-lg font-semibold ${
                    isEmergency 
                      ? "bg-red-600 hover:bg-red-700" 
                      : "bg-blue-600 hover:bg-blue-700"
                  }`}
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin mr-2" />
                      Submitting...
                    </>
                  ) : isEmergency ? (
                    <>
                      <AlertCircle className="w-5 h-5 mr-2" />
                      Submit Emergency Request
                    </>
                  ) : (
                    <>
                      <Droplet className="w-5 h-5 mr-2" />
                      Submit Blood Request
                    </>
                  )}
                </Button>
              </form>
            </div>
          </div>

          {/* Previous Requests Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-lg p-6 sticky top-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Clock className="w-5 h-5 text-gray-600" />
                Your Requests ({requests.length})
              </h3>

              {requests.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-8">
                  No previous requests
                </p>
              ) : (
                <div className="space-y-3 max-h-[600px] overflow-y-auto">
                  {requests.map((req) => (
                    <div
                      key={req.id}
                      className="p-3 border border-gray-200 rounded-lg hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Droplet className="w-4 h-4 text-red-600" />
                          <span className="font-semibold text-gray-900">
                            {req.blood_group}
                          </span>
                          {req.is_emergency && (
                            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                              Emergency
                            </span>
                          )}
                        </div>
                        <div className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${getStatusColor(req.status)}`}>
                          {getStatusIcon(req.status)}
                          <span className="capitalize">{req.status}</span>
                        </div>
                      </div>
                      
                      <div className="text-sm text-gray-600 space-y-1">
                        <p className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {new Date(req.needed_by_date).toLocaleDateString()}
                        </p>
                        <p className="flex items-start gap-1">
                          <MapPin className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          <span className="line-clamp-2">{req.location}</span>
                        </p>
                        {req.units_needed > 1 && (
                          <p className="text-xs text-gray-500">
                            {req.units_needed} units needed
                          </p>
                        )}
                      </div>
                      
                      {req.acknowledged_at && (
                        <div className="mt-2 pt-2 border-t border-gray-100">
                          <p className="text-xs text-green-600 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" />
                            Acknowledged {new Date(req.acknowledged_at).toLocaleDateString()}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
