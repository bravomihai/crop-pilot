// Inbound SMS / WhatsApp webhook. Written for Twilio (form-encoded From/Body, TwiML reply);
// WhatsApp messages arrive on the same webhook with From = "whatsapp:+40...".
// To switch provider, only parseInbound() and reply() change.
//
// TODO(P5): verify the X-Twilio-Signature header with TWILIO_AUTH_TOKEN before trusting the
// request, otherwise anyone can trigger analyses for any phone number.
import { handleMessage, type InboundMessage } from "@/lib/sms";

export async function POST(req: Request) {
  const msg = parseInbound(await req.formData());
  if (!msg) return reply("");
  return reply(await handleMessage(msg));
}

function parseInbound(form: FormData): InboundMessage | null {
  const rawFrom = String(form.get("From") ?? "");
  const text = String(form.get("Body") ?? "");
  if (!rawFrom) return null;
  const channel = rawFrom.startsWith("whatsapp:") ? "whatsapp" : "sms";
  return { from: rawFrom.replace(/^whatsapp:/, ""), text, channel };
}

function reply(text: string) {
  const escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const body = text ? `<Response><Message>${escaped}</Message></Response>` : "<Response/>";
  return new Response(`<?xml version="1.0" encoding="UTF-8"?>${body}`, {
    headers: { "Content-Type": "text/xml; charset=utf-8" },
  });
}
