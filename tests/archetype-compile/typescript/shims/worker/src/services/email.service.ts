// HARNESS STUB: project service the worker archetype's EmailSendHandler depends on.
export interface EmailService {
  renderTemplate(templateId: string, variables: Record<string, unknown>): Promise<string>;
  send(msg: { to: string; subject: string; html: string }): Promise<void>;
}
