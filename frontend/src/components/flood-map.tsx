import { motion } from "framer-motion";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, Tooltip } from "react-leaflet";
import { useLanguage } from "@/lib/language-context";
import type { FloodGeoJSON, Settlement } from "@/types/data";

interface FloodMapProps {
  flood: FloodGeoJSON;
  settlements: Settlement[];
  showFlood: boolean;
  showSettlements: boolean;
}

export function FloodMap({ flood, settlements, showFlood, showSettlements }: FloodMapProps) {
  const { t } = useLanguage();
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
          <GeoJSON data={flood} style={{ fillColor: "#38BDF8", color: "#38BDF8", weight: 1, fillOpacity: 0.35 }} />
        )}
        {showSettlements && settlements.map((s) => (
          <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={7} pathOptions={{ color: s.status === "cut-off" ? "#FF4757" : "#2ED573", fillColor: s.status === "cut-off" ? "#FF4757" : "#2ED573", fillOpacity: 0.85, weight: 2 }}>
            <Tooltip>{s.name}</Tooltip>
            <Popup>
              <div className="space-y-1 text-sm">
                <p className="font-semibold">{s.name}</p>
                <p>Population: {s.population.toLocaleString()}</p>
                <p>Priority: {s.priorityScore.toFixed(2)}</p>
                <p>Status: {s.status === "cut-off" ? t("cutOff") : t("accessible")}</p>
                <p>Distance to hospital: {s.distanceToHospitalKm} km</p>
                <p>Isolated since: {s.isolatedSinceHours}h</p>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="absolute bottom-4 left-4 z-[1000] space-y-2 rounded-lg border border-border bg-background/80 p-3 text-xs backdrop-blur-md">
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#38BDF8]" /><span>{t("floodExtent")}</span></div>
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#FF4757]" /><span>{t("cutOffSettlement")}</span></div>
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#2ED573]" /><span>{t("accessibleSettlement")}</span></div>
      </div>
    </div>
    </motion.div>
  );
}