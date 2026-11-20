# Recorded intro / outro voices

- `male/`   – Hasintha's clips: used on stories narrated by a male voice (am_*, bm_*)
- `female/` – the lady's clips: used on stories narrated by a female voice (af_*, bf_*)

Files are named `intro_NN.wav` / `outro_NN.wav` (cleaned, 24 kHz mono). Every file in the folder is used;
videos rotate through them so the morning and evening videos always differ.
Add a line of text for each new file to `voice/lines.json` (shown as captions under the intro).
If a folder has no clips, stories with that voice simply get no intro/outro.
