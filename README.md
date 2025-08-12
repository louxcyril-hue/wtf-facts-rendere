# WTF Facts Renderer (Option B - Montage maison)

Un petit service web (FastAPI) qui assemble vos **images** (URLs ou base64) et une **voix off** (URL ou base64)
en une **vidéo verticale 1080x1920** de ~60s avec un léger effet de zoom et un watermark optionnel.

## 1) Prérequis

- Docker Desktop (recommandé) OU Python 3.11 + ffmpeg
- (Optionnel) Un bucket S3 si vous voulez que la vidéo soit envoyée automatiquement en ligne.

## 2) Installation (Docker recommandé)

```bash
docker build -t wtf-facts-renderer .
docker run --env-file .env -p 8080:8080 wtf-facts-renderer
```

Vérifiez que ça tourne : http://localhost:8080/health → `ok`

## 3) Tester l'API

- Préparez des **4 images** en base64 (ou des URLs), et un **MP3** en base64 (ou URL).
- Construisez le JSON comme dans `tests/sample_request_b64.json` (ou `tests/sample_request_urls.json`).

Exemple (renvoi en **binaire** MP4) :
```bash
curl -X POST http://localhost:8080/render   -H "Content-Type: application/json"   -d @tests/sample_request_urls.json   --output final.mp4
```

Exemple (renvoi en **base64** dans du JSON) :
```bash
curl -X POST "http://localhost:8080/render"   -H "Content-Type: application/json"   -d @tests/sample_request_b64.json
```

## 4) Champs acceptés

- `image_urls` **ou** `image_b64` (liste) — fournissez l'un des deux.
- `voice_url` **ou** `voice_b64` — fournissez l'un des deux.
- `music_url` (optionnel) — URL vers une musique de fond.
- `watermark_text` (optionnel) — texte en bas à droite.
- `return_b64` (bool) — si `true`, renvoie le MP4 encodé en base64 dans un JSON.

## 5) Intégration Make (ex-Integromat)
1. **Scheduler** quotidien.
2. **OpenAI – Chat Completions** : génère JSON (titre + script + 4 prompts d'image).
3. **Tools/Iterator** : itérer `image_prompts` →
4. **OpenAI – Images** : pour chaque prompt, `response_format=b64_json` → collecter `b64`.
5. **ElevenLabs – HTTP** : TTS (MP3 binaire) → Base64 encode.
6. **HTTP – Make a request (POST)** : vers `/render` avec `image_b64` (liste) + `voice_b64`.
7. **Google Drive – Upload file** : uploader la réponse binaire (ou décoder `mp4_b64`) dans un dossier "OUTBOX".
8. **Repurpose.io** : configurer un "workflow" qui publie automatiquement tout nouveau fichier du dossier sur TikTok/YouTube/IG.

## 6) Notes
- Le service ajuste la durée à 50–60s selon la longueur de l'audio.
- Les images sont recadrées pour le ratio 9:16.
- Si vous n'avez pas S3, laissez `.env` vide sur la partie AWS ; l'API renverra le MP4 directement.

Bonne création !
