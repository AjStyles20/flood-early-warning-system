# External news and messaging setup

Updated: 2026-09-10. Keep private keys out of chat, screenshots, templates and Git. Configure them locally in the service environment. News keys are sent server-side in `X-Api-Key` headers; API errors do not echo provider exceptions or credentials.

## NewsAPI or GNews

Create one provider account and obtain its key from its dashboard. [NewsAPI authentication](https://newsapi.org/docs/authentication) and [GNews authentication](https://docs.gnews.io/authentication) document their supported key headers. Check your plan's usage/delay limits before describing the feed as real-time or deploying it publicly.

For NewsAPI, run in the same PowerShell terminal that will start FastAPI:

```powershell
$env:FLOOD_EWS_NEWS_PROVIDER = 'newsapi'
$env:FLOOD_EWS_NEWSAPI_KEY = Read-Host 'Enter your NewsAPI key locally'
$env:FLOOD_EWS_NEWS_QUERY = 'flood OR rainfall Nigeria'
$env:FLOOD_EWS_NEWS_LANGUAGE = 'en'
```

Or choose GNews instead:

```powershell
$env:FLOOD_EWS_NEWS_PROVIDER = 'gnews'
$env:FLOOD_EWS_GNEWS_API_KEY = Read-Host 'Enter your GNews key locally'
$env:FLOOD_EWS_NEWS_QUERY = 'flood OR rainfall Nigeria'
$env:FLOOD_EWS_NEWS_LANGUAGE = 'en'
```

Change the query to another deployment country or region for portability. GNews optionally accepts `FLOOD_EWS_NEWS_COUNTRY`; this filter is not applied to NewsAPI's Everything endpoint. GNews requests are capped at 10 articles per call.

Then, from `files/api`:

```powershell
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8030
```

Open `/news` or `/api/news-feed`. Real articles require a working connection and a valid account/plan. Automated tests use representative provider responses and failures; they do not prove your key or provider subscription works.

Environment variables set in PowerShell last for that terminal session and its child processes. A new terminal needs the configuration again. The application does not automatically load a `.env` file. Docker Compose reads environment values and its project `.env` convention; private `.env` files are excluded from Git and container build context.

## Institutional RSS alternative

No API key is needed if an institution publishes an RSS feed. Obtain the exact feed URL from the institution; use that URL, not its normal website homepage.

```powershell
$env:FLOOD_EWS_NEWS_PROVIDER = 'rss'
$env:FLOOD_EWS_RSS_FEEDS = Read-Host 'Institutional RSS URL, or comma-separated RSS URLs'
```

The parser supports RSS channel/item feeds, RFC email-style dates and HTTP(S) article links. Atom feeds are not implemented. Five configured feeds at most are read. Articles are context for users; they do not modify the ML model, risk thresholds or official guidance.

Use `FLOOD_EWS_NEWS_PROVIDER=off` to disable external news. Default `auto` selects a configured NewsAPI key, then GNews key, then RSS. Normal responses are cached for five minutes; forced refresh has a 30-second minimum interval for the same request/configuration. An empty configured feed is shown differently from a feed with no configuration. This cache is not a production rate limiter.

## Weather context

The existing `/api/weather-forecast` adapter supplies rainfall context from Open-Meteo and reports provider failure separately from sensor risk. Weather is not a new input to the trained model. The current adapter uses Africa/Lagos forecast time; deployments outside the case study need to review that time-zone choice.

## EmailJS contact form

The user approved sending a visitor's name, email address, subject and message to EmailJS when the visitor submits the contact form. This approval supersedes the earlier blocked-change note. Implementation and automated local verification are complete; no live email has been sent or delivery confirmed during this work. The latest work-log entry records 16 passing frontend tests, 12 passing operational tests, the passing API regression suite and 13 successful HTTP smoke checks. Provider responses were mocked; complete the configuration and deliberate inbox check below before claiming live delivery.

### Configure the service and template

1. Create or sign in to your [EmailJS dashboard](https://dashboard.emailjs.com/). Under **Email Services**, connect the mailbox or email provider that will send contact messages. Record its Service ID. See [adding an email service](https://www.emailjs.com/docs/tutorial/adding-email-service/).
2. Under **Email Templates**, create a dedicated contact template and record its Template ID. Set **To Email** to a fixed project inbox you control. Leave **From Email** as the connected service's default sender, and set **Reply-To** to `{{reply_to}}`. Do not make the recipient address a form-controlled variable. See [creating an email template](https://www.emailjs.com/docs/tutorial/creating-email-template/).
3. Under **Account**, obtain the **Public Key**. It is the browser credential documented by [EmailJS installation](https://www.emailjs.com/docs/sdk/installation/). Do not copy a private key, mailbox password or other secret into these settings or into JavaScript.
4. In EmailJS's **Domains** settings, allow the exact origins you intend to use, such as `http://127.0.0.1:8030` for this local command and your HTTPS origin when deployed. Include the port when present; see [origin allowlisting](https://www.emailjs.com/docs/faq/can-i-add-my-domain-to-allowlist/).

Use these exact template variables to match the contact form:

| Template variable | Value supplied by FloodWatch | Suggested use |
|---|---|---|
| `{{from_name}}` | Visitor's name | From Name and message body |
| `{{from_email}}` | Visitor's email address | Message body |
| `{{reply_to}}` | Visitor's email address | Reply-To field |
| `{{subject}}` | Subject selected or entered in the form | Subject field |
| `{{message}}` | Visitor's message | Message body |

For example, use `FloodWatch contact: {{subject}}` as the subject and put the name, email and message variables in the body. Keep the destination inbox fixed in the provider template; the application does not send a recipient parameter.

### Set the local environment and start the app

Open a PowerShell terminal, copy only the commands below, and enter your actual public configuration values at the prompts. Use this same terminal to start FastAPI; the variables do not carry into a separate terminal. Stop any older development server before restarting it with the new configuration.

```powershell
Set-Location -LiteralPath 'C:\Users\User\Documents\Word_Document\Project\files\api'
$env:FLOOD_EWS_EMAILJS_PUBLIC_KEY = Read-Host 'EmailJS Public Key'
$env:FLOOD_EWS_EMAILJS_SERVICE_ID = Read-Host 'EmailJS Service ID'
$env:FLOOD_EWS_EMAILJS_CONTACT_TEMPLATE_ID = Read-Host 'EmailJS contact Template ID'
$env:FLOODWATCH_CONTACT_EMAIL = Read-Host 'Project inbox for the email-app fallback'
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8030
```

Open `http://127.0.0.1:8030/contact`. If you change the port, use the same port in the browser and the EmailJS origin allowlist. Enter configuration locally; there is no need to paste keys or mailbox credentials into chat.

The normal FastAPI startup does not automatically load `.env`. Docker Compose can receive the same environment values through its project `.env` convention or the calling shell. These three EmailJS IDs are deliberately public: FastAPI exposes them as safely serialized configuration on `/contact`, and the browser uses them to submit the form. A private EmailJS key must never be added to that configuration.

### Request flow and verification limits

After form submission, the browser sends JSON to `https://api.emailjs.com/api/v1.0/email/send`. It supplies `service_id`, `template_id`, the Public Key as `user_id`, and the five `template_params` above. These field names follow the [EmailJS REST send contract](https://www.emailjs.com/docs/rest-api/send/).

Local tests must check validation, unconfigured fallback, successful provider acknowledgement, duplicate-click protection, rejected requests and timeouts without contacting EmailJS. On a failed or timed-out request, the draft must remain available. A timeout does not prove the provider rejected the message; check the receiving inbox before retrying. Even a successful API response confirms provider acceptance, not final inbox delivery.

After configuration, a deliberate manual submission with a non-sensitive test message to the fixed inbox can establish live provider acceptance and receipt. Record the result separately from local mocked tests. No automated test here should send a live email.

`FLOODWATCH_CONTACT_EMAIL` configures the fallback destination in the user's email application. Opening that application does not send an email automatically. The newsletter form remains a mailto request; this integration does not persist subscriptions or send newsletter messages through EmailJS. Flood alerts, account-deletion notices and OTP codes retain their existing simulated behavior and need separate provider integration and verification.

## SMS, WhatsApp and account OTP preparation

The active notification implementation logs simulated web/email/SMS events. Account-deletion codes are demo codes shown locally, not out-of-band authentication. Adding a Twilio key alone does not activate sending in the current code.

For future setup, follow the [Twilio SMS quickstart](https://www.twilio.com/docs/messaging/quickstart): prepare an account, an appropriate SMS sender, server-side credentials and a test recipient you control. Keep the account SID/API credentials and sender details in a server secret store when the adapter is implemented; do not paste them here. Sender eligibility, international destinations, trial restrictions and consent need checking for the chosen deployment. Real WhatsApp delivery additionally needs its own sender/template setup.

Before live sending is implemented, supply only the provider choice and whether the account/sender is ready. Actual credentials should be entered locally. A separately authorized test should then verify provider acceptance, delivery status, recipient preferences and duplicate suppression. No messages were sent as part of the local tests documented here.
