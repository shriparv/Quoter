from __future__ import annotations

import glob
import json
import mimetypes
import os
import pickle
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

import config


class UploadError(RuntimeError):
    pass


class UploadConfigurationError(UploadError):
    pass


class Uploader:
    YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube"
    

    def __init__(self):
        if requests is None:
            raise UploadConfigurationError(
                "Uploads require the 'requests' package. Install dependencies from requirements.txt first."
            )
        self.session = requests.Session()
        self.timeout = int(os.getenv("UPLOAD_REQUEST_TIMEOUT_SECONDS", "120"))
        self.youtube_client_secret_glob = os.getenv(
            "YOUTUBE_CLIENT_SECRET_GLOB",
            config.YOUTUBE_CLIENT_SECRET_GLOB,
        )
        self.youtube_client_secret_fallback = os.getenv(
            "YOUTUBE_CLIENT_SECRET_FALLBACK",
            config.YOUTUBE_CLIENT_SECRET_FALLBACK,
        )
        self.youtube_token_file = self._resolve_path(
            os.getenv("YOUTUBE_TOKEN_FILE", config.YOUTUBE_TOKEN_FILE)
        )

    def upload_to_youtube(self, video_path: str | Path, title: str, description: str, tags: list = None, publish_at: str = None):
        video = self._ensure_video_file(video_path)
        print(f"\n  [YouTube] Starting upload for '{video.name}'...")

        (
            Request,
            InstalledAppFlow,
            build,
            HttpError,
            MediaFileUpload,
        ) = self._import_youtube_dependencies()

        credentials = self._load_youtube_credentials(Request, InstalledAppFlow)
        service = build("youtube", "v3", credentials=credentials, cache_discovery=False)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": os.getenv("YOUTUBE_CATEGORY_ID", config.YOUTUBE_CATEGORY_ID),
                "tags": tags or [],
            },
            "status": {
                "privacyStatus": os.getenv("YOUTUBE_PRIVACY_STATUS", config.YOUTUBE_PRIVACY_STATUS),
                "selfDeclaredMadeForKids": self._env_flag(
                    "YOUTUBE_MADE_FOR_KIDS",
                    config.YOUTUBE_MADE_FOR_KIDS,
                ),
            },
        }
        if publish_at:
            body["status"]["publishAt"] = publish_at
        if tags:
            body["snippet"]["tags"] = tags

        mime_type = mimetypes.guess_type(video.name)[0] or "video/mp4"
        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(str(video), mimetype=mime_type, resumable=True),
        )

        response = self._execute_youtube_upload(request, HttpError)
        video_id = response.get("id")
        if not video_id:
            raise UploadError("YouTube did not return a video ID.")

        print(f"  [YouTube] Upload complete. Video ID: {video_id}")
        print(f"  [YouTube] URL: https://www.youtube.com/watch?v={video_id}")

        # Add to Inspirational playlist (create if missing)
        try:
            playlist_id = self.get_or_create_playlist(service, title="Inspirational")
            if playlist_id:
                self.add_video_to_playlist(service, video_id, playlist_id)
        except Exception as e:
            print(f"  [YouTube] Failed to add to playlist: {e}")

        return response

    def get_or_create_playlist(self, service, title: str = "Quotes") -> str | None:
        try:
            request = service.playlists().list(part="snippet", mine=True, maxResults=50)
            response = request.execute()
            for item in response.get("items", []):
                if item["snippet"]["title"].lower() == title.lower():
                    return item["id"]

            request = service.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {"title": title, "description": "Auto-generated playlist."},
                    "status": {"privacyStatus": "public"},
                },
            )
            response = request.execute()
            return response.get("id")
        except Exception:
            return None

    def add_video_to_playlist(self, service, video_id: str, playlist_id: str):
        try:
            request = service.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            )
            request.execute()
            return True
        except Exception:
            return False

    def set_thumbnail(self, service, video_id: str, thumbnail_path: str) -> bool:
        if not os.path.exists(thumbnail_path):
            return False
        try:
            from googleapiclient.http import MediaFileUpload

            request = service.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path))
            request.execute()
            return True
        except Exception:
            return False

    def get_last_scheduled_publish_at(self, service):
        try:
            from dateutil import parser

            res = service.channels().list(mine=True, part="contentDetails").execute()
            uploads_id = res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            res = service.playlistItems().list(playlistId=uploads_id, part="contentDetails", maxResults=10).execute()
            video_ids = [item["contentDetails"]["videoId"] for item in res.get("items", [])]
            if not video_ids:
                return None
            res = service.videos().list(id=",".join(video_ids), part="status").execute()
            future_dates = []
            for item in res.get("items", []):
                publish_at = item.get("status", {}).get("publishAt")
                if publish_at:
                    future_dates.append(parser.parse(publish_at))
            if not future_dates:
                return None
            return max(future_dates)
        except Exception:
            return None

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = config.PROJECT_ROOT / path
        return path

    def _ensure_video_file(self, video_path: str | Path) -> Path:
        path = Path(video_path)
        if not path.exists():
            raise UploadError(f"Video file not found: {path}")
        if not path.is_file():
            raise UploadError(f"Video path is not a file: {path}")
        return path

    def _require_env(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise UploadConfigurationError(f"Missing required environment variable: {name}")
        return value

    def _env_flag(self, name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    def _import_youtube_dependencies(self):
        try:
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise UploadConfigurationError(
                "YouTube uploads require google-api-python-client, "
                "google-auth-oauthlib and google-auth-httplib2."
            ) from exc

        return Request, InstalledAppFlow, build, HttpError, MediaFileUpload

    def _load_youtube_credentials(self, request_cls, flow_cls):
        credentials = None
        if self.youtube_token_file.exists():
            try:
                with self.youtube_token_file.open("rb") as token_file:
                    credentials = pickle.load(token_file)
            except Exception as exc:
                raise UploadConfigurationError(
                    f"Error reading YouTube token file {self.youtube_token_file.name}. "
                    f"Delete it and authenticate again. ({exc})"
                ) from exc

        if credentials and credentials.valid:
            return credentials

        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(request_cls())
            except Exception as exc:
                raise UploadConfigurationError(
                    f"Error refreshing YouTube token. Delete {self.youtube_token_file.name} and re-authenticate. ({exc})"
                ) from exc
            with self.youtube_token_file.open("wb") as token_file:
                pickle.dump(credentials, token_file)
            return credentials

        client_secrets_file = self._find_youtube_client_secrets_file()
        if client_secrets_file is None:
            raise UploadConfigurationError(
                "Missing YouTube OAuth client secrets file. "
                f"Expected a file matching {self.youtube_client_secret_glob} or "
                f"{self.youtube_client_secret_fallback} in {config.PROJECT_ROOT}"
            )

        flow = flow_cls.from_client_secrets_file(
            str(client_secrets_file),
            scopes=[self.YOUTUBE_UPLOAD_SCOPE],
        )
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
        try:
            credentials = flow.run_local_server(port=0, open_browser=True)
        except OSError:
            if hasattr(flow, "run_console"):
                credentials = flow.run_console()
            else:
                credentials = flow.run_local_server(port=0, open_browser=False)

        with self.youtube_token_file.open("wb") as token_file:
            pickle.dump(credentials, token_file)
        return credentials

    def _find_youtube_client_secrets_file(self) -> Path | None:
        matched_files = sorted(
            Path(path)
            for path in glob.glob(str(config.PROJECT_ROOT / self.youtube_client_secret_glob))
        )
        if matched_files:
            return matched_files[0]

        fallback = config.PROJECT_ROOT / self.youtube_client_secret_fallback
        if fallback.exists():
            return fallback

        return None

    def _execute_youtube_upload(self, request, http_error_cls):
        max_retries = int(os.getenv("YOUTUBE_UPLOAD_MAX_RETRIES", "5"))
        retriable_statuses = {500, 502, 503, 504}
        response = None
        retry = 0

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"  [YouTube] Upload progress: {progress}%")
            except http_error_cls as exc:
                if exc.resp.status not in retriable_statuses or retry >= max_retries:
                    raise UploadError(f"YouTube upload failed: {exc}") from exc
                retry += 1
                sleep_seconds = 2 ** retry
                print(f"  [YouTube] Retrying after API error ({exc.resp.status}) in {sleep_seconds}s...")
                time.sleep(sleep_seconds)
            except Exception as exc:
                if retry >= max_retries:
                    raise UploadError(f"YouTube upload failed: {exc}") from exc
                retry += 1
                sleep_seconds = 2 ** retry
                print(f"  [YouTube] Retrying after upload error in {sleep_seconds}s...")
                time.sleep(sleep_seconds)

        return response

    def _request(self, method: str, url: str, **kwargs):
        timeout = kwargs.pop("timeout", self.timeout)
        response = self.session.request(method, url, timeout=timeout, **kwargs)
        if response.ok:
            return response

        details = self._safe_response_text(response)
        raise UploadError(f"HTTP {response.status_code} from {url}: {details}")

    def _post_json(self, url: str, **kwargs) -> dict:
        response = self._request("post", url, **kwargs)
        return self._decode_json(response)

    def _get_json(self, url: str, **kwargs) -> dict:
        response = self._request("get", url, **kwargs)
        return self._decode_json(response)

    def _decode_json(self, response: requests.Response) -> dict:
        try:
            return response.json()
        except ValueError as exc:
            raise UploadError(f"Invalid JSON response: {self._safe_response_text(response)}") from exc

    def _safe_response_text(self, response: requests.Response) -> str:
        text = response.text.strip()
        if not text:
            return "<empty response>"
        return text[:500]
