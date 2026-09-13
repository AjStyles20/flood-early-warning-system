// Public provider identifiers come from Jinja, not committed credentials.
// A missing or malformed config must fall back to the existing email-draft
// option. Private API keys and session cookies never enter this request.
function readEmailConfig() {
  try {
    return JSON.parse(document.getElementById("emailjs-config")?.textContent || "{}") || {};
  } catch {
    return {};
  }
}

const emailConfig = readEmailConfig();
let contactSubmissionInFlight = false;
let lastContactAttempt = -Infinity;

function emailjsReady() {
  return [emailConfig.publicKey, emailConfig.serviceId, emailConfig.contactTemplateId]
    .every((value) => typeof value === "string" && value.trim().length > 0);
}

function contactStatus(message) {
  const status = document.getElementById("contact-status");
  if (status) status.textContent = message;
}

function contactValues() {
  return {
    from_name: document.getElementById("name").value.trim(),
    from_email: document.getElementById("email").value.trim(),
    reply_to: document.getElementById("email").value.trim(),
    subject: document.getElementById("subject").value.trim(),
    message: document.getElementById("message").value.trim(),
  };
}

async function submitContact(event) {
  event.preventDefault();
  const form = event.currentTarget;
  // Disabling the button helps users; this flag also rejects repeat Enter or
  // scripted submit events while the previous request is still pending.
  if (contactSubmissionInFlight || !form.reportValidity()) return;
  const data = contactValues();
  if (Object.values(data).some((value) => !value)) {
    contactStatus("Please complete every field before sending.");
    return;
  }
  if (!emailjsReady()) {
    if (mailto(`FloodWatch: ${data.subject}`, `Name: ${data.from_name}\nEmail: ${data.from_email}\n\n${data.message}`)) {
      contactStatus("An email draft was requested. Review and send it in your email application; your entries remain here.");
    } else {
      contactStatus("The contact service is not connected yet. Your entries have been kept.");
    }
    return;
  }
  // EmailJS documents a one-request-per-second limit. No automatic retries:
  // a timeout may happen after the provider has already accepted the message.
  if (Date.now() - lastContactAttempt < 1000) {
    contactStatus("Please wait a moment before sending another message.");
    return;
  }
  lastContactAttempt = Date.now();
  contactSubmissionInFlight = true;
  const button = document.getElementById("contact-submit");
  if (button) button.disabled = true;
  form.setAttribute("aria-busy", "true");
  contactStatus("Sending your message...");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch("https://api.emailjs.com/api/v1.0/email/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "omit",
      redirect: "error",
      signal: controller.signal,
      body: JSON.stringify({
        service_id: emailConfig.serviceId,
        template_id: emailConfig.contactTemplateId,
        user_id: emailConfig.publicKey,
        // This whitelist is the approved contact payload. The receiving inbox
        // is fixed in the provider template, never chosen by a visitor.
        template_params: data,
      }),
    });
    if (response.status === 200) {
      // Do not erase edits typed while the older message was being submitted.
      if (JSON.stringify(contactValues()) === JSON.stringify(data)) form.reset();
      contactStatus("EmailJS accepted your message for sending. Inbox delivery has not been confirmed.");
    } else if (response.status === 429) {
      contactStatus("The email service is receiving too many requests. Please wait before trying again. Your entries have been kept.");
    } else {
      contactStatus("The email service did not accept this request. Your entries have been kept; please try again later.");
    }
  } catch {
    contactStatus("We could not confirm whether the email service accepted your message. Your entries have been kept. Please check before resending to avoid a duplicate.");
  } finally {
    clearTimeout(timeout);
    contactSubmissionInFlight = false;
    if (button) button.disabled = false;
    form.setAttribute("aria-busy", "false");
  }
}

function configuredContactEmail() {
  return document.body?.dataset.contactEmail?.trim() || "";
}

function mailto(subject, body) {
  const contactEmail = configuredContactEmail();
  if (!contactEmail) {
    showNotice(
      "Contact email not configured",
      "This local prototype has no contact email configured yet. Set FLOODWATCH_CONTACT_EMAIL before using live contact or newsletter actions."
    );
    return false;
  }

  window.location.href = `mailto:${contactEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  return true;
}

document.addEventListener("DOMContentLoaded", function () {
  const contact = document.getElementById("contact-form");
  contact?.addEventListener("submit", submitContact);

  document.querySelectorAll("[data-newsletter-form]").forEach((form) => {
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      const email = form.querySelector('input[name="email"]').value;
      // Approval covered contact messages only. Newsletter requests retain the
      // email-draft flow and are not falsely reported as saved subscriptions.
      if (mailto("FloodWatch newsletter subscription", `Please add ${email} to the FloodWatch newsletter.`)) {
        showNotice("Email draft requested", "Review and send the request in your email application. No subscription has been saved by this website.");
      }
    });
  });
});
