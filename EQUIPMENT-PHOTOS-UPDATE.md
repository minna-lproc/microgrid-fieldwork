# Appliance photos and mobile business-equipment cards

This update includes the previous mobile appliance inventory update. Apply this newest package to your current Gridfield application, including if you have already installed the earlier appliance cards.

## For enumerators

1. Start an interview and record the separate photo consent. Photos are optional. If permission is No, continue without photos.
2. In Section C, tap **Add appliance**. Choose its type and fill in its details. Choose its time of use from the dropdown.
3. In each card, tap **Take photo** to use the phone's camera, or **Choose photo** to select an existing image. Depending on the phone/browser, the camera button may also show a file picker.
4. Wait for the image preview and **Photo saved on this device** message. You can replace or remove a photo without removing the equipment information. One photo is supported per card.
5. If the household runs a business, choose Yes in D1. In **Business equipment**, tap **Add equipment** for each machine. Enter its name, quantity, watts/hp (including the unit), hours/day, peak months, fuel use and output/capacity (including units). You can attach a photo here too.
6. Finish the interview normally. Photos and answers are stored together offline and sent together when the finished interview reconnects. Keep the app open until My interviews shows the queue is empty. Failed uploads retain the interview and photos for retry.

Tap card headings to expand or collapse them. Both inventories support up to 100 cards. Repeated appliance categories and multiple Other appliances are supported. Unknown quantities can stay blank; zero means zero. Photos are not required to finish an interview.

Photos require Yes for interview consent and photo consent. If you change photo consent to No after attaching images, a confirmation lets you remove all attached images from that draft. Declining business activity in D1 removes its business answers and associated photos, following the existing skip rule.

## Administrator dashboard

After sync: Survey responses -> open the interview -> scroll below Recorded answers. Photos are labelled with the appliance or equipment name. Click a photo to open it, or use Download photo.

Only the administrator and the submitting account can fetch an image. Image endpoints require an active sign-in and are excluded from service-worker caching. Ordinary JSON/CSV exports contain photo descriptors (ID, JPEG type, size and dimensions), not image bytes. Use the dashboard's Download photo link to save a photograph. An attachment is retrieved at /api/surveys/INTERVIEW_ID/photos/PHOTO_ID while signed in.

Deleting a submitted interview also deletes its associated photos from the server database. An administrator's deletion prevents a delayed device retry from recreating that interview or its images. Previously downloaded copies and database backups are unchanged.

## Apply on your Windows computer

1. Stop local Flask. Back up the existing database/instance folder as you normally do before an update.
2. Download **gridfield-equipment-photos-update.zip** and right-click -> Extract All.
3. Copy the contents of the extracted update into the existing **application folder containing app.py**. Replace matching files. This is an update package, not a folder to launch on its own. Keep your existing database, instance folder, environment and GitHub settings.
4. In that application folder, run:

    python scripts/generate_codebook.py --check
    python -m pytest -q
    python app.py

If pytest is missing: python -m pip install pytest

5. Open the local app and check Add appliance / Add equipment and the photo buttons. Business equipment is visible after D1 is Yes. Photo buttons are visible after separate photo consent is Yes.
6. Commit and push the included changes to GitHub:

    git add app.py static tests README.md UPDATE-FILES.txt EQUIPMENT-PHOTOS-UPDATE.md
    git commit -m "Add offline equipment photos and mobile business inventory"
    git push origin main

7. Wait for both GitHub Actions jobs (test and deploy) to succeed. This package does not itself update your GitHub or PythonAnywhere website.
8. On each phone, reconnect online, close Gridfield and reopen. If the old interface remains, close and reopen again after the update downloads. Verify the photo buttons and Add equipment button before leaving for fieldwork. Do not clear browser storage or reinstall to update.

Deploy app.py and all included static files together. There are no new Python dependencies. On first startup, the app automatically creates an additive survey_photos table in the existing SQLite database; existing records are retained. There is no database reset. The existing deployment cache handling updates installed phones after deployment and an online reopening.

For a fresh installation only, use gridfield-equipment-photos-full.zip, extract its gridfield-flask-pwa folder and follow README.md. Do not replace an existing production installation with a fresh demo database.

## Storage and compatibility

- A chosen image is decoded and re-encoded on the phone as JPEG, up to 1280 pixels on its longest side and 320 KiB. Original photo filenames and EXIF/GPS metadata are not retained in the app attachment. The original image may still remain in the phone's camera/gallery.
- Input images must be under 25 MiB and supported by the browser. If a format cannot open, choose JPEG or PNG. There is a 4 MiB combined compressed-photo limit per interview and a 6 MiB upload request limit. If reached, replace a photo with a smaller one or remove an optional photo.
- Unsynced photos are stored with the interview in browser IndexedDB. They are not encrypted by this app. Do not clear browser data or uninstall before syncing. Keep enough free device storage.
- Synced JPEG bytes are stored separately from scientific answers in the same SQLite database. Include that database in backups. Photos consume hosting disk quota, including on a free PythonAnywhere account.
- Photos become visible to the administrator only after the enumerator finishes and syncs the interview. The application must be open for the normal sync workflow.
- Existing submitted records are not migrated. Existing appliance arrays and time strings remain readable. Editing an older fixed-position appliance inventory converts its meaningful rows to named cards without discarding recorded values or zeroes.
- Business equipment retains its original seven fields and supports variable-length rows instead of three fixed slots. The public codebooks document both inventories and photo descriptors. Questionnaire IDs/version and questions outside C_loads and D_equipment are unchanged.
- Earlier pilot drafts can still be completed under their original questionnaire but cannot receive new photo attachments; use the current questionnaire for interviews with photos.

## Verification

71 API/unit tests passed, including consent, permissions, photo validation/limits, export separation, idempotent retries and photo deletion. JavaScript syntax and codebook consistency checks passed. Browser checks cover mobile cards, camera/gallery inputs, offline saves/reload, storage failure, replacement/removal, failed upload/retry, dashboard images and existing survey/reference workflows.
