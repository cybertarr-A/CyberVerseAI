// frontend/src/lib/api.ts

const API_URL =
  "https://cyberverseai-production.up.railway.app//api/v1";

console.log("API URL:", API_URL);

export async function apiRequest(
  endpoint: string,
  options: RequestInit = {}
) {

  const url =
    `${API_URL}${endpoint.startsWith("/") ? endpoint : "/" + endpoint}`;

  console.log("Request:", url);

  const response = await fetch(
    url,
    {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      }
    }
  );

  if (!response.ok) {

    const error = await response.text();

    throw new Error(
      `API Error ${response.status}: ${error}`
    );
  }

  return response.json();
}
