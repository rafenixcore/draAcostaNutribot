// k6 load profile: 10 VUs, 30s.
import http from 'k6/http';
import { check, sleep } from 'k6';
export const options = { vus: 10, duration: '30s' };
export default function () {
  const health = __ENV.HEALTH_PATH || '/health';
  check(http.get(__ENV.BASE_URL + health), { '200': (r) => r.status === 200 });
  sleep(0.2);
}
export function handleSummary(data) {
  return { '/out/summary.json': JSON.stringify({ p95_ms: data.metrics.http_req_duration.values['p(95)'] }) };
}
