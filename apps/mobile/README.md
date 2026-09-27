# Care 360 mobile

Native Android and iOS Care 360 client for the existing CareConnect Pro FastAPI service. The web app in `apps/web` remains independent and unchanged.

## Run locally

1. Start the existing FastAPI service on port `8000`.
2. Copy `.env.example` to `.env` and choose the correct API address:
   - Android emulator: `http://10.0.2.2:8000`
   - iOS simulator: `http://localhost:8000`
   - Physical device: `http://<computer-LAN-IP>:8000`
3. Run `npm start`, then press `a` for Android or `i` for iOS.

If Expo Go is already installed but the Expo version check/download is blocked,
launch the Android emulator from Android Studio and run:

```powershell
npm run android:offline
```

This project is Expo-managed and intentionally has no `android` Gradle folder,
so Android Studio provides the emulator rather than launching the app with its
Run button.

Local HTTP access is explicit: keep `EXPO_PUBLIC_APP_ENV=development` and set
`EXPO_PUBLIC_ALLOW_CLEARTEXT=true`. Store builds ignore that development choice
and fail configuration if the API or public policy URLs are not HTTPS.

For device testing, FastAPI must listen on `0.0.0.0`, and the phone and computer must share a network. Production builds must use an HTTPS API URL.

## Included mobile features

- Secure sign-in and session restoration
- Patient/clinician registration and password-reset initiation
- Required, versioned privacy/terms and AI-safety acknowledgements
- Role-aware dashboard metrics
- Appointment booking, clinician approval/rejection, and video-visit launch
- Medical records, mobile document upload, and clinical summary previews
- Notifications with mark-as-read
- Secure care connections and one-to-one messaging
- Prescription and medication-plan access
- Patient health assistant grounded in uploaded records
- Main-tab Care-aware Meal Planner with validated generation, recipe details, meal swapping, saved/scheduled plans, completion tracking, and meal chat
- Emergency SOS creation and false-alarm closure
- Consent-gated SOS with explicit emergency-services limitations
- Editable patient/clinician profiles
- Active-device session review and revocation
- Profile and secure sign-out
- Reauthenticated account-deletion requests and privacy/support controls
- Bounded API timeouts, safe GET retries, and `Retry-After` handling

### Clinician workspace

- Clinical command center with today’s consultations and work-queue metrics
- Pending appointment approval and care-connection requests
- Connected-patient roster and protected clinical profile access
- Dedicated Patients tab with name/email search and status/gender filters
- Pending connection requests embedded in the Patients tab
- Role-scoped Clinical Search tab across patients, records, appointments, and prescriptions
- Prescription creation for connected patients
- Consultation-hours and visit-duration management
- Connected-patient SOS monitoring, claiming, and acknowledgement

The mobile application focuses on patient and clinician workflows. Advanced operational administration—including user lifecycle management, audit analytics, RAG indexing, and bulk notification administration—remains in the web console because those dense workflows are better suited to a desktop workspace.

## Build binaries

After configuring an Expo account and final bundle identifiers:

```sh
npx eas-cli build --platform android
npx eas-cli build --platform ios
```

iOS and Play Store distribution require their respective developer credentials.
Set the production API, Privacy Policy, Terms of Use, and support URLs as EAS
environment secrets. The production profile rejects HTTP and always disables
Android cleartext traffic. Complete the repository-level
[`MARKET_READINESS.md`](../../MARKET_READINESS.md) gates before submission.
