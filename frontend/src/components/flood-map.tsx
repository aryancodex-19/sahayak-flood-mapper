import { motion } from "framer-motion";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, Tooltip } from "react-leaflet";
import type { FloodGeoJSON, Settlement } from "@/types/data";

interface FloodMapProps {
  flood: FloodGeoJSON;
  settlements: Settlement[];
  showFlood: boolean;
  showSettlements: boolean;
}

function getSettlementType(s: Settlement): string {
  const rawType =
    (s as { type?: string }).type ||
    (s.population >= 5000
      ? "town"
      : s.population >= 3000
      ? "suburb"
      : s.population >= 1500
      ? "neighbourhood"
      : s.population >= 1000
      ? "locality"
      : s.population <= 200
      ? "hamlet"
      : "village");
  return rawType.charAt(0).toUpperCase() + rawType.slice(1);
}

export function FloodMap({ flood, settlements, showFlood, showSettlements }: FloodMapProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
    <div id="map" className="relative">
      <MapContainer center={[26.3, 91.7]} zoom={10} style={{ height: 500, width: "100%" }} className="rounded-lg border border-border z-0">
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap contributors' />
        {showFlood && (
          <GeoJSON
            key={flood.features.length + "-" + (flood.features[0]?.properties?.id || "empty")}
            data={flood}
            style={{ fillColor: "#38BDF8", color: "#38BDF8", weight: 1, fillOpacity: 0.35 }}
          />
        )}
        {showSettlements && settlements.map((s) => {
          const markerColor =
            s.statusType === "strict-cutoff"
              ? "#FF4757"
              : s.statusType === "practical-cutoff"
              ? "#F59E0B"
              : "#2ED573";
          const typeLabel = getSettlementType(s);

          return (
            <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={7} pathOptions={{ color: markerColor, fillColor: markerColor, fillOpacity: 0.85, weight: 2 }}>
              <Tooltip>{s.name}</Tooltip>
              <Popup autoPan={true}>
                <div className="min-w-[220px] space-y-2 p-0.5 text-slate-900">
                  <div className="flex items-start justify-between gap-2 border-b border-slate-200 pb-2">
                    <div>
                      <h4 className="text-base font-bold leading-tight text-slate-900">{s.name}</h4>
                      <p className="mt-0.5 text-xs font-medium text-slate-500">{typeLabel}</p>
                    </div>
                    {s.statusType === "strict-cutoff" && (
                      <span className="shrink-0 rounded-full border border-red-200 bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700">
                        Strict Cut-off
                      </span>
                    )}
                    {s.statusType === "practical-cutoff" && (
                      <span className="shrink-0 rounded-full border border-amber-200 bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                        Practical Cut-off
                      </span>
                    )}
                    {(!s.statusType || s.statusType === "connected") && (
                      <span className="shrink-0 rounded-full border border-emerald-200 bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                        Accessible
                      </span>
                    )}
                  </div>
                  <div className="space-y-1 text-xs text-slate-600">
                    <p className="flex justify-between">
                      <span className="text-slate-500">Population:</span>
                      <span className="font-semibold text-slate-800">{s.population.toLocaleString()}</span>
                    </p>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Priority Score:</span>
                      <span className="font-semibold text-slate-900">{s.priorityScore.toFixed(2)}</span>
                    </p>
                    {s.distanceToHospitalKm != null && (
                      <p className="border-t border-slate-100 pt-1 text-slate-600">
                        Nearest service center: <span className="font-medium text-slate-800">{s.distanceToHospitalKm} km away</span>
                      </p>
                    )}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
      <div className="absolute bottom-4 left-4 z-[1000] space-y-2 rounded-lg border border-border bg-background/80 p-3 text-xs backdrop-blur-md">
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#38BDF8]" /><span>Flood Extent</span></div>
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#FF4757]" /><span>Strict Cut-off</span></div>
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#F59E0B]" /><span>Practical Cut-off</span></div>
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#2ED573]" /><span>Accessible Settlement</span></div>
      </div>
    </div>
    </motion.div>
  );
}