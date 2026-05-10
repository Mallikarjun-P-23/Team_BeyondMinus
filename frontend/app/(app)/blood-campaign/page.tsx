"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useLocalAuth } from "@/lib/local-auth";
import {
  getBloodRequest,
  listDonors,
  createDonor,
  uploadDonorList,
} from "@/services/api";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Droplet,
  MapPin,
  Search,
  Filter,
  ArrowLeft,
  Phone,
  Mail,
  User,
  Calendar,
  AlertCircle,
  ChevronRight,
  Map as MapIcon,
  Table as TableIcon,
  CheckCircle2,
  XCircle,
  Plus,
  UserPlus,
  Upload,
} from "lucide-react";

// Leaflet imports
import dynamic from "next/dynamic";
import "leaflet/dist/leaflet.css";

const MapContainer = dynamic(() => import("react-leaflet").then((mod) => mod.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then((mod) => mod.TileLayer), { ssr: false });
const Marker = dynamic(() => import("react-leaflet").then((mod) => mod.Marker), { ssr: false });
const Popup = dynamic(() => import("react-leaflet").then((mod) => mod.Popup), { ssr: false });
const Circle = dynamic(() => import("react-leaflet").then((mod) => mod.Circle), { ssr: false });

// Fix for default marker icons in Leaflet with Next.js
let L: any;
if (typeof window !== "undefined") {
  L = require("leaflet");
  delete (L.Icon.Default.prototype as any)._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  });
}

const RED_ICON = typeof window !== "undefined" ? new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
}) : null;

const BLUE_ICON = typeof window !== "undefined" ? new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
}) : null;

export default function BloodCampaignPage() {
  const searchParams = useSearchParams();
  const requestId = searchParams.get("request_id");
  const { user } = useLocalAuth();
  const doctorId = user?.doctor_id || user?.sub;

  const [request, setRequest] = useState<any>(null);
  const [donors, setDonors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [bloodTypeFilter, setBloodTypeFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [viewMode, setViewMode] = useState<"table" | "map">("table");
  const [showAddDonor, setShowAddDonor] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [newDonor, setNewDonor] = useState({
    name: "",
    blood_type: "",
    phone_number: "",
    location: "",
    gender: "male",
    age: "",
    last_donated_date: new Date().toISOString().split('T')[0],
  });

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !doctorId) return;

    setUploading(true);
    try {
      const result = await uploadDonorList(doctorId, file);
      alert(`Import complete! ${result.summary.donors.created} new donors added, ${result.summary.donors.updated} updated.`);
      loadData();
    } catch (err) {
      console.error("Failed to upload donor list:", err);
      alert("Failed to process file. Please ensure it is a valid CSV or Excel file.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleAddDonor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!doctorId) return;
    try {
      await createDonor({
        ...newDonor,
        doctor_id: doctorId,
        age: parseInt(newDonor.age) || undefined,
      });
      setShowAddDonor(false);
      setNewDonor({
        name: "",
        blood_type: "",
        phone_number: "",
        location: "",
        gender: "male",
        age: "",
        last_donated_date: new Date().toISOString().split('T')[0],
      });
      loadData();
      alert("Donor registered successfully!");
    } catch (err) {
      console.error("Failed to register donor:", err);
      alert("Failed to register donor");
    }
  };

  const loadData = useCallback(async () => {
    if (!doctorId) return;
    setLoading(true);
    try {
      let bType = bloodTypeFilter;
      let loc = locationFilter;

      if (requestId) {
        const reqData = await getBloodRequest(requestId);
        if (reqData) {
          setRequest(reqData);
          if (!bloodTypeFilter) {
            bType = reqData.blood_group;
            setBloodTypeFilter(reqData.blood_group);
          }
          if (!locationFilter) {
            loc = reqData.location;
            setLocationFilter(reqData.location);
          }
        }
      }

      const donorsData = await listDonors({
        doctor_id: doctorId,
        blood_type: bType || undefined,
        location: loc || undefined,
      });
      setDonors(donorsData);
    } catch (err) {
      console.error("Failed to load blood campaign data:", err);
    } finally {
      setLoading(false);
    }
  }, [doctorId, requestId, bloodTypeFilter, locationFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const patientCoords = useMemo(() => {
    if (request?.latitude && request?.longitude) {
      return [parseFloat(request.latitude), parseFloat(request.longitude)];
    }
    return null;
  }, [request]);

  const donorMarkers = useMemo(() => {
    return donors.filter(d => d.latitude && d.longitude).map(d => ({
      ...d,
      coords: [parseFloat(d.latitude), parseFloat(d.longitude)]
    }));
  }, [donors]);

  const mapCenter = useMemo(() => {
    if (patientCoords) return patientCoords;
    if (donorMarkers.length > 0) return donorMarkers[0].coords;
    return [15.3647, 75.1240]; // Default Hubli center
  }, [patientCoords, donorMarkers]);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Header */}
      <header className="border-b border-border bg-card px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <Link href="/blood-requests">
            <Button variant="ghost" size="sm" className="gap-2">
              <ArrowLeft className="size-4" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Droplet className="size-5 text-red-600" />
              Blood Campaign Coordination
            </h1>
            {request && (
              <p className="text-xs text-muted-foreground mt-0.5">
                Finding donors for <span className="font-semibold text-foreground">{request.patient_name}</span> ({request.blood_group})
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-muted rounded-lg p-1">
            <Button 
              variant={viewMode === "table" ? "secondary" : "ghost"} 
              size="sm" 
              className="h-8 gap-2"
              onClick={() => setViewMode("table")}
            >
              <TableIcon className="size-4" />
              List
            </Button>
            <Button 
              variant={viewMode === "map" ? "secondary" : "ghost"} 
              size="sm" 
              className="h-8 gap-2"
              onClick={() => setViewMode("map")}
            >
              <MapIcon className="size-4" />
              Map
            </Button>
          </div>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            accept=".csv,.xlsx,.xls" 
            className="hidden" 
          />
          <Button variant="outline" className="gap-2" onClick={() => fileInputRef.current?.click()}>
            <Upload className="size-4" />
            Import List
          </Button>
          <Button variant="outline" className="gap-2" onClick={() => setShowAddDonor(true)}>
            <UserPlus className="size-4" />
            Register Donor
          </Button>
          <Button onClick={loadData} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh Donors"}
          </Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar: Filters and Request Details */}
        <aside className="w-80 border-r border-border bg-muted/30 overflow-y-auto p-6 space-y-6">
          {request && (
            <section className="space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Request Details</h3>
              <div className="bg-card border border-red-100 rounded-xl p-4 shadow-sm border-l-4 border-l-red-600">
                <div className="flex justify-between items-start mb-3">
                  <div className="bg-red-50 text-red-700 px-2 py-1 rounded text-xl font-bold">
                    {request.blood_group}
                  </div>
                  {request.is_emergency && (
                    <span className="bg-red-600 text-white px-2 py-0.5 rounded text-[10px] font-bold animate-pulse">
                      EMERGENCY
                    </span>
                  )}
                </div>
                <div className="space-y-2 text-sm">
                  <p className="font-semibold">{request.patient_full_name || request.patient_name}</p>
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <MapPin className="size-3.5" />
                    <span className="truncate">{request.location}</span>
                  </div>
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Calendar className="size-3.5" />
                    <span>Needed by: {new Date(request.needed_by_date).toLocaleDateString()}</span>
                  </div>
                  <div className="pt-2 border-t border-border mt-2">
                    <p className="text-xs text-muted-foreground">Contact: {request.contact_number}</p>
                  </div>
                </div>
              </div>
            </section>
          )}

          <section className="space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Donor Filters</h3>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium px-1">Blood Group</label>
                <div className="relative">
                  <Droplet className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <select 
                    value={bloodTypeFilter}
                    onChange={(e) => setBloodTypeFilter(e.target.value)}
                    className="w-full bg-card border border-border rounded-lg pl-10 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  >
                    <option value="">All Groups</option>
                    {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(bt => (
                      <option key={bt} value={bt}>{bt}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium px-1">Location / Area</label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <input 
                    type="text"
                    value={locationFilter}
                    onChange={(e) => setLocationFilter(e.target.value)}
                    placeholder="Search by city or area..."
                    className="w-full bg-card border border-border rounded-lg pl-10 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                </div>
              </div>

              <Button variant="outline" className="w-full" onClick={() => { setBloodTypeFilter(""); setLocationFilter(""); }}>
                Clear Filters
              </Button>
            </div>
          </section>

          <section className="bg-blue-50 border border-blue-100 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2 text-blue-700">
              <AlertCircle className="size-4" />
              <h4 className="text-xs font-bold uppercase">Smart Matching</h4>
            </div>
            <p className="text-xs text-blue-600 leading-relaxed">
              We are showing donors matching the patient&apos;s blood group and location. Donors within 10km are prioritized.
            </p>
          </section>
        </aside>

        {/* Main Content: Table or Map */}
        <main className="flex-1 bg-background relative overflow-hidden flex flex-col">
          {(loading || uploading) ? (
            <div className="flex-1 flex flex-col items-center justify-center space-y-4">
              <div className="size-12 border-4 border-red-600 border-t-transparent rounded-full animate-spin" />
              <div className="text-center">
                <p className="text-muted-foreground font-medium animate-pulse">
                  {uploading ? "Processing your donor list..." : "Scanning donor database..."}
                </p>
                {uploading && (
                  <p className="text-[10px] text-muted-foreground mt-2 max-w-xs">
                    This may take a moment while we geocode locations for the map.
                  </p>
                )}
              </div>
            </div>
          ) : viewMode === "table" ? (
            <div className="flex-1 overflow-auto">
              <table className="w-full text-sm border-collapse">
                <thead className="sticky top-0 bg-card z-10 border-b border-border shadow-sm">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Donor</th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Group</th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Age/Gender</th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Location</th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Stats (W/H)</th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Registered</th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">Status</th>
                    <th className="px-4 py-3 text-right font-semibold text-muted-foreground">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {donors.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-20 text-center text-muted-foreground italic">
                        No matching donors found for this criteria. Try expanding your search area.
                      </td>
                    </tr>
                  ) : (
                    donors.map((donor) => (
                      <tr key={donor.id} className="hover:bg-muted/30 transition-colors group">
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-3">
                            <div className="size-9 rounded-full bg-red-50 flex items-center justify-center text-red-600 font-bold shrink-0">
                              {donor.name[0].toUpperCase()}
                            </div>
                            <div className="min-w-0">
                              <p className="font-semibold truncate">{donor.name}</p>
                              <p className="text-[10px] text-muted-foreground truncate">{donor.phone_number}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <span className="inline-flex items-center justify-center min-w-[32px] h-[32px] bg-red-100 text-red-800 font-bold rounded-lg text-xs">
                            {donor.blood_type || donor.blood_group}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-muted-foreground">
                          {donor.age || "??"}Y · {donor.gender?.charAt(0).toUpperCase() || "?"}
                        </td>
                        <td className="px-4 py-4">
                          <div className="flex flex-col">
                            <span className="truncate max-w-[150px]">{donor.city || donor.location}</span>
                            <span className="text-[10px] text-muted-foreground truncate">{donor.state || donor.address || ""}</span>
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <div className="text-[10px] space-y-0.5">
                            <p><span className="text-muted-foreground">W:</span> {donor.weight_kg || "-"}kg</p>
                            <p><span className="text-muted-foreground">Hb:</span> {donor.hemoglobin_g_dL || "-"}g/dL</p>
                          </div>
                        </td>
                        <td className="px-4 py-4 text-[10px] text-muted-foreground">
                          {donor.created_at ? new Date(donor.created_at).toLocaleDateString() : "-"}
                        </td>
                        <td className="px-4 py-4">
                          {donor.eligible_for_donation !== false ? (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600">
                              <CheckCircle2 className="size-3" /> Eligible
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600">
                              <XCircle className="size-3" /> Cooling Down
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-4 text-right">
                          <Button size="sm" variant="outline" className="opacity-0 group-hover:opacity-100 transition-opacity">
                            View Profile
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex-1 h-full z-0">
              <MapContainer 
                center={mapCenter as [number, number]} 
                zoom={13} 
                className="w-full h-full"
                key={`${mapCenter[0]}-${mapCenter[1]}`}
              >
                <TileLayer
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                
                {patientCoords && (
                  <>
                    <Marker position={patientCoords as [number, number]} icon={RED_ICON}>
                      <Popup>
                        <div className="p-1">
                          <p className="font-bold text-red-600">PATIENT: {request.patient_name}</p>
                          <p className="text-xs">{request.location}</p>
                          <p className="text-xs font-bold mt-1">Needs: {request.blood_group}</p>
                        </div>
                      </Popup>
                    </Marker>
                    <Circle 
                      center={patientCoords as [number, number]} 
                      radius={5000} 
                      pathOptions={{ color: 'red', fillColor: 'red', fillOpacity: 0.05 }} 
                    />
                  </>
                )}

                {donorMarkers.map((donor) => (
                  <Marker key={donor.id} position={donor.coords as [number, number]} icon={BLUE_ICON}>
                    <Popup>
                      <div className="p-1 space-y-1">
                        <p className="font-bold">{donor.name}</p>
                        <p className="text-[10px] bg-red-50 text-red-700 px-1.5 py-0.5 rounded inline-block font-bold">
                          {donor.blood_type || donor.blood_group}
                        </p>
                        <p className="text-xs flex items-center gap-1">
                          <Phone className="size-3" /> {donor.phone_number}
                        </p>
                        <p className="text-xs italic text-muted-foreground">{donor.location}</p>
                        <Button size="sm" className="w-full mt-2 h-7 text-[10px] bg-blue-600 hover:bg-blue-700">
                          Initiate Campaign
                        </Button>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </MapContainer>
            </div>
          )}

          {/* Footer Stats */}
          <footer className="border-t border-border bg-card px-6 py-2 flex items-center justify-between text-[11px] text-muted-foreground">
            <div className="flex items-center gap-4">
              <span>Total Donors Found: <span className="font-bold text-foreground">{donors.length}</span></span>
              <span>Available Map Markers: <span className="font-bold text-foreground">{donorMarkers.length}</span></span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <div className="size-2 rounded-full bg-red-600" />
                <span>Patient</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="size-2 rounded-full bg-blue-600" />
                <span>Donor</span>
              </div>
            </div>
          </footer>
        </main>
      </div>

      {/* Add Donor Modal */}
      {showAddDonor && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-card w-full max-w-md rounded-2xl shadow-2xl border border-border overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
              <h2 className="text-lg font-bold flex items-center gap-2">
                <UserPlus className="size-5 text-red-600" />
                Register New Donor
              </h2>
              <Button variant="ghost" size="icon" onClick={() => setShowAddDonor(false)}>
                <XCircle className="size-5" />
              </Button>
            </div>
            <form onSubmit={handleAddDonor} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5 col-span-2">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Full Name</label>
                  <input 
                    required
                    type="text"
                    value={newDonor.name}
                    onChange={(e) => setNewDonor({...newDonor, name: e.target.value})}
                    placeholder="Enter donor name"
                    className="w-full bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Blood Type</label>
                  <select 
                    required
                    value={newDonor.blood_type}
                    onChange={(e) => setNewDonor({...newDonor, blood_type: e.target.value})}
                    className="w-full bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  >
                    <option value="">Select Type</option>
                    {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(bt => (
                      <option key={bt} value={bt}>{bt}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Gender</label>
                  <select 
                    value={newDonor.gender}
                    onChange={(e) => setNewDonor({...newDonor, gender: e.target.value})}
                    className="w-full bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Phone Number</label>
                  <input 
                    required
                    type="tel"
                    value={newDonor.phone_number}
                    onChange={(e) => setNewDonor({...newDonor, phone_number: e.target.value})}
                    placeholder="+91..."
                    className="w-full bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Age</label>
                  <input 
                    type="number"
                    value={newDonor.age}
                    onChange={(e) => setNewDonor({...newDonor, age: e.target.value})}
                    placeholder="Years"
                    className="w-full bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                </div>
                <div className="space-y-1.5 col-span-2">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Location / City</label>
                  <input 
                    required
                    type="text"
                    value={newDonor.location}
                    onChange={(e) => setNewDonor({...newDonor, location: e.target.value})}
                    placeholder="City, State"
                    className="w-full bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                </div>
              </div>
              <div className="pt-4 flex gap-3">
                <Button variant="outline" type="button" className="flex-1" onClick={() => setShowAddDonor(false)}>
                  Cancel
                </Button>
                <Button type="submit" className="flex-1 bg-red-600 hover:bg-red-700">
                  Register Donor
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
