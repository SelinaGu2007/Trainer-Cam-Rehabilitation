# Post-session results and voice feedback

## User experience

After an assessment starts, TrainerCam writes the technical `assessment.json` report and a separate user-facing `feedback_summary.json`. CustomerClient watches for the summary without blocking its interface, then opens a large, readable result window while the detailed motion visualisation remains available.

The result window contains:

- the overall score in large type and a colour-coded engineering rating;
- a short headline;
- up to three highest-priority body segments to review;
- a visible warning when tracking or joint data needs caution;
- an explicit statement that the result is not a diagnosis;
- a user-controlled voice option and replay button.

The voice preference is remembered with local Qt settings. `config/app.json` provides deployment defaults for locale, voice enabled state, speaking rate and volume. Supported summary locales are `en-US` and `zh-CN`.

## Separation of technical and user data

`assessment.json` remains the detailed engineering record with feature errors, alignment and data quality. `feedback_summary.json` is deliberately smaller and conforms to `schemas/feedback-summary-v1.schema.json`.

This separation prevents user interface wording from changing the underlying score and lets future interfaces present the same assessment differently. The summary contains no audio recording; it stores only the text to be spoken.

## Voice implementation and privacy

CustomerClient uses Qt TextToSpeech and the operating system's available speech engine. TrainerCam does not upload assessment text to a speech service itself. Deployment owners must still review the privacy behaviour of the speech engine configured on their operating system.

Users can disable automatic reading in the result window. Manual replay remains available. If no compatible system voice is installed, the visual result remains usable.

## Command line and preview

Generate the user summary together with an assessment:

```powershell
python test_exe\main.py `
  --folder_tutor "PATH_TO_TUTOR_SESSION" `
  --folder_customer "PATH_TO_CUSTOMER_SESSION" `
  --function report `
  --report-output assessment.json `
  --feedback-output feedback_summary.json `
  --feedback-locale en-US
```

Preview a generated summary without signing in:

```powershell
build-qt-cmake\CustomerClient\Release\CustomerClient.exe `
  --feedback-preview "PATH_TO_feedback_summary.json" `
  --no-voice
```

## Clinical boundary

The labels such as “good” or “review” are plain-language engineering categories derived from configurable score bands. They are not clinical outcome measures. Exercise profiles, thresholds, wording and spoken guidance require review by qualified rehabilitation professionals before patient deployment.
