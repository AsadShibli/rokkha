"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { API_URL, refreshSession, tokens } from "./api";
import { type Incident, type IncidentDetail, incidentKeys } from "./incidents";

type FeedMessage =
  | { type: "snapshot"; incident: Incident }
  | { type: "status"; incident: Incident }
  | { type: "location"; incident_id: number; officer_id: number; lat: number; lng: number };

export type FeedState = "connecting" | "live" | "reconnecting" | "closed";

const WS_URL = API_URL.replace(/^http/, "ws");
const CLOSE_UNAUTHORIZED = 4401;
const CLOSE_NOT_FOUND = 4404;

/**
 * Live updates for one incident over WS /ws/incidents/{id}. Each message is merged into the
 * React Query cache, so every component showing the incident updates at once. Reconnects with
 * backoff; on 4401 (expired access token) it refreshes the session first. The timeline is
 * re-fetched on status changes, because the socket carries the incident, not its events.
 */
export function useIncidentFeed(id: number, enabled = true): FeedState {
  const queryClient = useQueryClient();
  const [state, setState] = useState<FeedState>("connecting");

  useEffect(() => {
    if (!enabled || !Number.isFinite(id)) return;
    let socket: WebSocket | null = null;
    let ping: ReturnType<typeof setInterval> | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let stopped = false;

    const merge = (patch: Partial<IncidentDetail>) =>
      queryClient.setQueryData<IncidentDetail>(incidentKeys.detail(id), (old) =>
        old ? { ...old, ...patch } : old,
      );

    const connect = async () => {
      if (!tokens.access && !(await refreshSession())) {
        setState("closed");
        return;
      }
      socket = new WebSocket(`${WS_URL}/ws/incidents/${id}?token=${tokens.access}`);

      socket.onopen = () => {
        attempts = 0;
        setState("live");
        ping = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send("ping"), 25_000);
      };

      socket.onmessage = (event) => {
        if (event.data === "pong") return;
        const message = JSON.parse(event.data) as FeedMessage;
        if (message.type === "location") {
          queryClient.setQueryData<IncidentDetail>(incidentKeys.detail(id), (old) =>
            old?.officer
              ? { ...old, officer: { ...old.officer, last_lat: message.lat, last_lng: message.lng } }
              : old,
          );
          return;
        }
        merge(message.incident);
        if (message.type === "status") {
          void queryClient.invalidateQueries({ queryKey: incidentKeys.detail(id) });
          void queryClient.invalidateQueries({ queryKey: ["incidents", "list"] });
        }
      };

      socket.onclose = async (event) => {
        clearInterval(ping);
        if (stopped) return;
        if (event.code === CLOSE_NOT_FOUND) {
          setState("closed");
          return;
        }
        if (event.code === CLOSE_UNAUTHORIZED && !(await refreshSession())) {
          setState("closed");
          return;
        }
        setState("reconnecting");
        attempts += 1;
        retry = setTimeout(connect, Math.min(1000 * 2 ** attempts, 15_000));
      };
    };

    void connect();
    return () => {
      stopped = true;
      clearInterval(ping);
      clearTimeout(retry);
      socket?.close();
    };
  }, [id, enabled, queryClient]);

  return state;
}
