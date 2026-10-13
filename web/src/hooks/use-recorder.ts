import { useCallback, useEffect, useRef, useState } from "react";

const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus", "audio/aac"];
const MAX_SECONDS = 90;

export interface Recording {
  blob: Blob;
  mime: string;
  filename: string;
  seconds: number;
}

export type RecorderStatus = "idle" | "recording" | "unsupported";

function pickMime() {
  if (typeof MediaRecorder === "undefined") return null;
  return MIME_CANDIDATES.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? "";
}

function extensionFor(mime: string) {
  if (mime.includes("mp4") || mime.includes("aac")) return "m4a";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

export function useRecorder(onRecorded: (recording: Recording) => void, onError: (message: string) => void) {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [seconds, setSeconds] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const cancelledRef = useRef(false);
  const startedAtRef = useRef(0);
  const timerRef = useRef<number | null>(null);

  const cleanup = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    recorderRef.current = null;
    setSeconds(0);
  }, []);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }, []);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    stop();
  }, [stop]);

  const start = useCallback(async () => {
    const mime = pickMime();
    if (mime === null || !navigator.mediaDevices?.getUserMedia) {
      onError("Seu navegador não permite gravar áudio aqui. Use HTTPS ou localhost em um navegador atualizado.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("Não consegui acessar o microfone. Verifique a permissão do navegador e tente de novo.");
      return;
    }
    const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunksRef.current = [];
    cancelledRef.current = false;
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const type = recorder.mimeType || mime || "audio/webm";
      const elapsed = Math.round((Date.now() - startedAtRef.current) / 1000);
      const blob = new Blob(chunksRef.current, { type });
      cleanup();
      setStatus("idle");
      if (cancelledRef.current) return;
      if (blob.size < 1200 || elapsed < 1) {
        onError("O áudio ficou curtinho demais. Segure um pouco mais enquanto fala.");
        return;
      }
      onRecorded({ blob, mime: type, filename: `audio.${extensionFor(type)}`, seconds: elapsed });
    };
    recorderRef.current = recorder;
    startedAtRef.current = Date.now();
    recorder.start(250);
    setStatus("recording");
    timerRef.current = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAtRef.current) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_SECONDS) stop();
    }, 250);
  }, [cleanup, onError, onRecorded, stop]);

  useEffect(
    () => () => {
      cancelledRef.current = true;
      if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
      cleanup();
    },
    [cleanup],
  );

  return { status, seconds, start, stop, cancel };
}
