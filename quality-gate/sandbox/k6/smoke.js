// k6 smoke profile: 1 VU, 10s. Writes p95 to /out/summary.json via handleSummary.
import http from 'k6/http';
import { check } from 'k6';
export const options = { vus: 1, duration: '10s' };
export default function () {
  const health = __ENV.HEALTH_PATH || '/health';
  check(http.get(__ENV.BASE_URL + health), { '200': (r) => r.status === 200 });
}
export function handleSummary(data) {
  return { '/out/summary.json': JSON.stringify({ p95_ms: data.metrics.http_req_duration.values['p(95)'] }) };
}
