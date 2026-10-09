/** The API only accepts points inside Bangladesh (BR Locations 1). */
const BD = { minLat: 20.5, maxLat: 26.7, minLng: 88.0, maxLng: 92.7 };

/** Gulshan 1, Dhaka: used when the browser can't give a Bangladeshi location (demo). */
export const DEMO_POINT = { lat: 23.781, lng: 90.414 };

export type Point = { lat: number; lng: number };

export function inBangladesh({ lat, lng }: Point): boolean {
  return lat >= BD.minLat && lat <= BD.maxLat && lng >= BD.minLng && lng <= BD.maxLng;
}

/**
 * Best current position. Falls back to the demo point when location is denied, unavailable,
 * slow, or outside Bangladesh, and says so (`demo: true`) so the UI can tell the user.
 */
export function currentLocation(timeoutMs = 8000): Promise<Point & { demo: boolean }> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      resolve({ ...DEMO_POINT, demo: true });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const point = { lat: coords.latitude, lng: coords.longitude };
        resolve(inBangladesh(point) ? { ...point, demo: false } : { ...DEMO_POINT, demo: true });
      },
      () => resolve({ ...DEMO_POINT, demo: true }),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 30_000 },
    );
  });
}
