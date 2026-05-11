/**
 * The 5 sample support messages from `tests/fixtures/sample_messages.json`.
 *
 * Kept in sync by hand for the take-home; a production version would either
 * fetch them from a `/api/v1/samples` endpoint or import them at build time.
 */

export interface SampleMessage {
  id: string;
  label: string;
  message: string;
}

export const SAMPLE_MESSAGES: SampleMessage[] = [
  {
    id: "critical_bug_deadline",
    label: "Critical bug — board demo in 2 hours",
    message:
      "Our mobile app keeps crashing right after login for all our supervisors. We have a board demo in 2 hours and the team can't see the dashboard. Please help urgently!",
  },
  {
    id: "billing_question",
    label: "Billing — double charge investigation",
    message:
      "Hi - I think we got billed twice for our March subscription. Could someone look into it and send me a corrected invoice?",
  },
  {
    id: "howto_sip_trunk",
    label: "How-to — SIP trunk configuration",
    message:
      "We're new to VoiceSpin and trying to configure our SIP trunk. Where do I find documentation on the right SIP signaling settings for our PBX?",
  },
  {
    id: "multi_tenant_outage",
    label: "Outage — inbound failing across tenants",
    message:
      "Inbound calls aren't connecting for ANY of our tenants since around 9am Eastern. Customers are calling our reps directly. This is hitting our entire production fleet.",
  },
  {
    id: "feature_request_slack",
    label: "Feature request — Slack integration",
    message:
      "Hey - it would be amazing if VoiceSpin could push missed-call alerts to our Slack workspace. Right now our team has to manually check the dashboard which slows everything down.",
  },
];
