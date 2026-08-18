/**
 * Footer weather widget backed by the National Weather Service API
 * (api.weather.gov). Fetched once on page load; the refresh button
 * re-triggers the same lookup on demand — no polling.
 */
(function () {
  const LATITUDE = 38.8894;
  const LONGITUDE = -77.0352;

  // Ordered keyword -> Bootstrap Icon class; first match wins.
  const CONDITION_ICONS = [
    [/thunder|lightning/i, "bi-cloud-lightning-rain-fill"],
    [/snow|flurr|sleet|blizzard/i, "bi-snow2"],
    [/rain|shower|drizzle/i, "bi-cloud-rain-heavy-fill"],
    [/fog|mist|haze/i, "bi-cloud-fog2-fill"],
    [/wind/i, "bi-wind"],
    [/overcast|cloudy|clouds/i, "bi-cloud-fill"],
    [/partly|mostly sunny|mostly clear/i, "bi-cloud-sun-fill"],
    [/clear|sunny/i, "bi-sun-fill"],
  ];
  const DEFAULT_ICON = "bi-thermometer-half";

  function iconForForecast(shortForecast) {
    const match = CONDITION_ICONS.find(([pattern]) => pattern.test(shortForecast));
    return match ? match[1] : DEFAULT_ICON;
  }

  function setIcon(iconClass) {
    const icon = document.getElementById("weather-icon");
    if (!icon) return;
    icon.className = `bi ${iconClass} text-muted`;
  }

  async function fetchJson(url) {
    const response = await fetch(url, {
      headers: { Accept: "application/geo+json" },
    });
    if (!response.ok) {
      throw new Error(`Weather request failed (${response.status})`);
    }
    return response.json();
  }

  async function loadWeather() {
    const content = document.getElementById("weather-content");
    const refreshButton = document.getElementById("weather-refresh");
    if (!content) return;

    content.textContent = "Loading weather\u2026";
    if (refreshButton) refreshButton.disabled = true;

    try {
      const points = await fetchJson(
        `https://api.weather.gov/points/${LATITUDE},${LONGITUDE}`
      );
      const relativeLocation = points.properties.relativeLocation?.properties;
      const place = relativeLocation
        ? `${relativeLocation.city}, ${relativeLocation.state}`
        : "Current location";

      const forecast = await fetchJson(points.properties.forecast);
      const period = forecast.properties.periods[0];

      setIcon(iconForForecast(period.shortForecast));
      content.textContent = `${place}: ${period.temperature}\u00b0${period.temperatureUnit}, ${period.shortForecast}`;
    } catch (err) {
      setIcon("bi-question-circle");
      content.textContent = "Weather unavailable.";
    } finally {
      if (refreshButton) refreshButton.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    loadWeather();
    const refreshButton = document.getElementById("weather-refresh");
    if (refreshButton) {
      refreshButton.addEventListener("click", loadWeather);
    }
  });
})();
