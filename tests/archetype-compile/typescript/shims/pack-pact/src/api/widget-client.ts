// HARNESS STUB: the consumer's API client that testing/contract-testing.md's pact test drives. It reads the
// envelope: GET /api/v1/widgets/:id → { data, meta }.
export interface Widget {
  id: string;
  name: string;
  status: string;
}

export class WidgetClient {
  constructor(private readonly baseUrl: string) {}

  async getWidget(id: string): Promise<Widget> {
    const res = await fetch(`${this.baseUrl}/api/v1/widgets/${encodeURIComponent(id)}`, {
      headers: { Authorization: "Bearer token", Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`GET widget: HTTP ${res.status}`);
    const body = (await res.json()) as { data: Widget; meta: { request_id: string } };
    return body.data;
  }
}
