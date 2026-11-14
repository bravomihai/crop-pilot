"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { locationSchema, type Location } from "@fieldshift/contracts";
import Icon from "./icon";

export default function LocationSearch({
  onSelect,
}: {
  onSelect: (location: Location) => void;
}) {
  const [query, setQuery] = useState("");
  const [locations, setLocations] = useState<Location[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [],
  );
  function clear() {
    ++sequence.current;
    controller.current?.abort();
    setLocations([]);
    setBusy(false);
    setMessage("");
  }
  async function search(event: FormEvent) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    clear();
    const current = sequence.current;
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    try {
      const response = await fetch(
        `/api/locations?q=${encodeURIComponent(query.trim())}`,
        { signal: request.signal },
      );
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.error || "Location search is unavailable.");
      if (!Array.isArray(data.locations))
        throw new Error("The location service returned an invalid response.");
      const found = data.locations.map((location: Location) =>
        locationSchema.parse({
          name: location.name,
          latitude: location.latitude,
          longitude: location.longitude,
        }),
      );
      if (current !== sequence.current) return;
      setLocations(found);
      setMessage(
        found.length
          ? `${found.length} places found. Choose one below.`
          : "No places found. Try another name or use the map.",
      );
    } catch (cause) {
      if (!request.signal.aborted && current === sequence.current)
        setMessage(
          cause instanceof Error
            ? cause.message
            : "Search failed. Use the map instead.",
        );
    } finally {
      if (current === sequence.current) setBusy(false);
    }
  }
  return (
    <div className="location-search-wrap">
      <form className="dashboard-search" onSubmit={search} role="search">
        <Icon name="search" size={19} />
        <label className="sr-only" htmlFor="dashboard-location">
          Search for a location
        </label>
        <input
          id="dashboard-location"
          value={query}
          maxLength={100}
          placeholder="Search for a town or location…"
          autoComplete="off"
          onChange={(event) => {
            clear();
            setQuery(event.target.value);
          }}
          aria-describedby="search-message"
          onKeyDown={(event) => {
            if (event.key === "Escape") clear();
          }}
        />
        <button
          type="submit"
          disabled={busy || query.trim().length < 2}
          aria-label="Search locations"
        >
          {busy ? <span className="spinner" /> : <span>Search</span>}
        </button>
      </form>
      <p id="search-message" className="sr-only" role="status">
        {busy ? "Searching for locations…" : message}
      </p>
      {(locations.length > 0 || message) && (
        <div className="search-popover">
          <p>{message}</p>
          {locations.length > 0 && (
            <ul>
              {locations.map((location, index) => (
                <li key={`${location.latitude}-${location.longitude}-${index}`}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(location);
                      setQuery(location.name ?? "Selected location");
                      clear();
                    }}
                  >
                    <Icon name="pin" size={17} />
                    <span>{location.name}</span>
                    <Icon name="arrow" size={15} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="search-dismiss" onClick={clear}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}
