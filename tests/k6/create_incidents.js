import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 100,
  duration: "1m",
  thresholds: {
    http_req_duration: ["p(95)<200"],
    http_req_failed: ["rate<0.01"],
  },
};

const baseUrl = __ENV.API_BASE_URL || "http://localhost:8080";

export default function () {
  const payload = JSON.stringify({
    service: "order",
    symptom: "Order checkout latency is rising and users report intermittent failures.",
    severity: "SEV2",
  });
  const params = {
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `k6-${__VU}-${__ITER}`,
    },
  };
  const res = http.post(`${baseUrl}/api/incidents`, payload, params);
  check(res, {
    "created or deduped": (r) => r.status === 201 || r.status === 200,
  });
  sleep(1);
}

