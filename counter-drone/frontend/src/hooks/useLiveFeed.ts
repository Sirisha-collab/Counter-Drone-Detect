import { useCallback, useEffect, useRef, useState } from "react";
import type { ConnectionState, DetectionEvent, LiveFrame } from "../types";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/live";
const MAX_EVENTS = 60;

/**
 * Holds the WebSocket to the backend and exposes the latest frame.
 *
 * Frames replace each other — the newest one is the whole current picture.
 * Events accumulate, because the log is a history rather than a snapshot.
 * If the socket drops, it retries with a backoff that tops out at 8 seconds.
 */
export function useLiveFeed() {
  const [frame, setFrame] = useState<LiveFrame | null>(null);
  const [events, setEvents] = useState<DetectionEvent[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connecting");

  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const closedByUs = useRef(false);

  const connect = useCallback(() => {
    if (closedByUs.current) return;
    setConnection((current) => (current === "live" ? current : "connecting"));

    const socket = new WebSocket(WS_URL);
    socketRef.current = socket;

    socket.onopen = () => {
      retryRef.current = 0;
      setConnection("live");
    };

    socket.onmessage = (message) => {
      try {
        const incoming = JSON.parse(message.data) as LiveFrame;
        setFrame(incoming);
        if (incoming.events?.length) {
          setEvents((previous) =>
            [...incoming.events].reverse().concat(previous).slice(0, MAX_EVENTS),
          );
        }
      } catch {
        // A malformed frame shouldn't take the dashboard down; skip it.
      }
    };

    socket.onclose = () => {
      setConnection("offline");
      if (closedByUs.current) return;
      const delay = Math.min(8000, 800 * 2 ** retryRef.current);
      retryRef.current += 1;
      timerRef.current = window.setTimeout(connect, delay);
    };

    socket.onerror = () => socket.close();
  }, []);

  useEffect(() => {
    closedByUs.current = false;
    connect();
    return () => {
      closedByUs.current = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      socketRef.current?.close();
    };
  }, [connect]);

  return { frame, events, connection };
}
