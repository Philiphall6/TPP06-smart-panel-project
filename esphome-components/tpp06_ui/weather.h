#pragma once

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>

namespace esphome::tpp06_ui {

inline bool fresh(bool received, uint32_t now, uint32_t stamp, uint32_t max_age) {
  return received && static_cast<uint32_t>(now - stamp) < max_age;
}

inline std::string condition_fr(const std::string &state) {
  if (state == "sunny") return "Ensoleille";
  if (state == "clear-night") return "Nuit claire";
  if (state == "partlycloudy") return "Eclaircies";
  if (state == "cloudy") return "Nuageux";
  if (state == "fog") return "Brouillard";
  if (state == "hail") return "Grele";
  if (state == "lightning") return "Orage";
  if (state == "lightning-rainy") return "Pluie et orages";
  if (state == "pouring") return "Forte pluie";
  if (state == "rainy") return "Pluvieux";
  if (state == "snowy") return "Neige";
  if (state == "snowy-rainy") return "Pluie et neige";
  if (state == "windy") return "Venteux";
  if (state == "windy-variant") return "Vent et nuages";
  if (state == "exceptional") return "Conditions exceptionnelles";
  return "Meteo indisponible";
}

inline bool known_condition(const std::string &state) {
  return condition_fr(state) != "Meteo indisponible";
}

inline std::string temperature(bool valid, float value, const std::string &unit) {
  // Never silently assume Celsius: HA can use Fahrenheit.
  if (!valid || !std::isfinite(value) || (unit != "°C" && unit != "°F")) return "--";
  char out[40];
  if (value < -999 || value > 999) return "--";
  snprintf(out, sizeof(out), "%.0f %s", value, unit.c_str());
  return out;
}

inline std::string percent(bool valid, float value) {
  if (!valid || !std::isfinite(value) || value < 0 || value > 100) return "-- %";
  char out[24];
  snprintf(out, sizeof(out), "%.0f %%", value);
  return out;
}

inline std::string wind_speed(bool valid, float value, const std::string &unit) {
  if (!valid || !std::isfinite(value) || value < 0 || value > 999 ||
      (unit != "km/h" && unit != "m/s" && unit != "mph" && unit != "kn")) return "--";
  char out[40];
  snprintf(out, sizeof(out), "%.0f %s", value, unit.c_str());
  return out;
}

inline std::string receipt_age(bool received, uint32_t now, uint32_t stamp) {
  if (!received) return "En attente de Home Assistant";
  char out[64];
  snprintf(out, sizeof(out), "Recu il y a %lu min", static_cast<unsigned long>(
      static_cast<uint32_t>(now - stamp) / 60000));
  return out;
}

}  // namespace esphome::tpp06_ui
