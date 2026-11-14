"use client";

import { useRef, useState, type DragEvent } from "react";
import { pdfSelectionError } from "@/lib/pdf-file";
import Icon from "./icon";

export default function PdfUpload({
  id,
  label,
  file,
  onChange,
}: {
  id: string;
  label: string;
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const sequence = useRef(0);
  async function select(candidate?: File) {
    const current = ++sequence.current;
    setError("");
    if (!candidate) return;
    try {
      const selectionError = await pdfSelectionError(candidate);
      if (current !== sequence.current) return;
      if (selectionError) {
        setError(selectionError);
        return;
      }
      onChange(candidate);
    } catch (cause) {
      if (current === sequence.current)
        setError(
          cause instanceof Error
            ? cause.message
            : "This file could not be read.",
        );
    }
  }
  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length > 1) {
      setError("Choose one PDF file at a time.");
      return;
    }
    void select(event.dataTransfer.files[0]);
  }
  return (
    <div className="pdf-upload">
      <div className="upload-heading">
        <label htmlFor={id}>{label}</label>
        <span>Optional</span>
      </div>
      <label
        className={`drop-zone ${dragging ? "is-dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
      >
        <input
          id={id}
          type="file"
          accept=".pdf,application/pdf"
          className="sr-only"
          aria-describedby={`${id}-hint`}
          onChange={(event) => {
            void select(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <Icon name={file ? "file" : "upload"} size={19} />
        <span>
          {file ? "Replace PDF" : "Drop PDF here or browse"}
          <small id={`${id}-hint`}>PDF · up to 10 MB · stays in this tab</small>
        </span>
      </label>
      {file && (
        <div className="selected-file">
          <span>
            <Icon name="file" size={15} />
            {file.name}
          </span>
          <button
            type="button"
            aria-label={`Remove ${label.toLowerCase()}`}
            onClick={() => {
              ++sequence.current;
              onChange(null);
              setError("");
            }}
          >
            <Icon name="close" size={15} />
          </button>
        </div>
      )}
      <p role="status" className="file-status">
        {error ||
          (file ? "Selected locally. PDF content has not been analysed." : "")}
      </p>
    </div>
  );
}
