/**
 * GPS Simulator
 * Simulates mobile GPS coordinate collection for demo purposes.
 *
 * Distribution:
 *   60% → within 100m of hospital (indoor/on-premise check-in)
 *   30% → 100m to 500m from hospital (nearby area)
 *   10% → >500m from hospital (anomalous / suspicious)
 */

window.GPSSimulator = {
  /**
   * Generate a simulated GPS coordinate near a hospital.
   * @param {number} hospitalLat - Hospital latitude
   * @param {number} hospitalLng - Hospital longitude
   * @returns {{ lat: number, lng: number, radius: number, scenario: string }}
   */
  simulate(hospitalLat, hospitalLng) {
    const roll = Math.random();

    let radius;
    let scenario;

    if (roll < 0.60) {
      // 60%: inside hospital (0-100m)
      radius = Math.random() * 100;
      scenario = 'indoor';
    } else if (roll < 0.90) {
      // 30%: nearby (100-500m)
      radius = 100 + Math.random() * 400;
      scenario = 'nearby';
    } else {
      // 10%: anomalous (500-3000m)
      radius = 500 + Math.random() * 2500;
      scenario = 'anomalous';
    }

    // Random bearing (0–360°)
    const bearing = Math.random() * 2 * Math.PI;

    // Convert meters to degree offset
    // 1° lat ≈ 111,111 m
    // 1° lng ≈ 111,111 * cos(lat) m
    const deltaLat = (radius * Math.cos(bearing)) / 111111;
    const deltaLng = (radius * Math.sin(bearing)) / (111111 * Math.cos(hospitalLat * Math.PI / 180));

    return {
      lat: parseFloat((hospitalLat + deltaLat).toFixed(7)),
      lng: parseFloat((hospitalLng + deltaLng).toFixed(7)),
      radius: Math.round(radius),
      scenario,
    };
  },

  /**
   * Simulate GPS acquisition with a visual delay (animates "locating").
   * @param {number} hospitalLat
   * @param {number} hospitalLng
   * @param {Function} onLocating - called when "searching" starts
   * @param {Function} onDone - called with result: { lat, lng, radius, scenario }
   * @param {number} delay - ms to simulate acquisition delay (default 1200)
   */
  acquireWithDelay(hospitalLat, hospitalLng, onLocating, onDone, delay = 1200) {
    onLocating?.();
    setTimeout(() => {
      const result = this.simulate(hospitalLat, hospitalLng);
      onDone?.(result);
    }, delay);
  },

  /**
   * Haversine distance between two lat/lng points (in meters)
   */
  distance(lat1, lng1, lat2, lng2) {
    const R = 6371000;
    const phi1 = lat1 * Math.PI / 180;
    const phi2 = lat2 * Math.PI / 180;
    const dphi = (lat2 - lat1) * Math.PI / 180;
    const dlambda = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlambda / 2) ** 2;
    return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
  },

  scenarioLabels: {
    indoor:    '院内定位（100m以内）',
    nearby:    '院周边定位（100-500m）',
    anomalous: '异常定位（500m以上）',
  },
};
