"use client";

import { useId, useRef, useState } from "react";
import Icon from "../Icon";
import { formatFileSize } from "@/app/lib/formatters";

export interface FileRule {
  extensions: string[];
  label: string;
  maxBytes?: number;
}

export function validateFile(file: File, rule: FileRule): string | null {
  if (file.size === 0) return "File kosong. Pilih file yang memiliki isi.";
  const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
  if (!rule.extensions.includes(extension)) return `Format ${extension} tidak didukung. Gunakan ${rule.label}.`;
  if (rule.maxBytes && file.size > rule.maxBytes) return `Ukuran file melebihi ${formatFileSize(rule.maxBytes)}. Pilih file yang lebih kecil.`;
  return null;
}

export default function FileDropzone({
  files,
  rule,
  onFiles,
  onRemove,
  disabled = false,
  error,
  multiple = false,
}: {
  files: File[];
  rule: FileRule;
  onFiles: (files: File[]) => void;
  onRemove: (index: number) => void;
  disabled?: boolean;
  error?: string | null;
  multiple?: boolean;
}) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleFiles(fileList: FileList | null) {
    if (!fileList) return;
    const incoming = Array.from(fileList);
    if (!multiple) {
      const first = incoming[0];
      if (first) onFiles([first]);
    } else {
      onFiles(incoming);
    }
    // Reset input agar bisa memilih file yang sama lagi atau menambah file
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div>
      <div
        className={`file-dropzone${dragging ? " is-dragging" : ""}${files.length > 0 ? " has-file" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); if (!disabled) setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!disabled) handleFiles(event.dataTransfer.files);
        }}
      >
        {files.length > 0 ? (
          <div className="selected-files">
            {files.map((file, index) => (
              <div className="selected-file" key={`${file.name}-${index}`}>
                <span className="file-icon"><Icon name="file" size={22} /></span>
                <div className="min-w-0"><strong>{file.name}</strong><span>{formatFileSize(file.size)}</span></div>
                <button className="icon-button" type="button" onClick={() => onRemove(index)} disabled={disabled} aria-label={`Hapus ${file.name}`}><Icon name="trash" size={18} /></button>
              </div>
            ))}
            {multiple ? (
              <label className="dropzone-add-more" htmlFor={inputId}>
                <Icon name="upload" size={16} />
                <span>Tambah file</span>
              </label>
            ) : null}
          </div>
        ) : (
          <label className="dropzone-label" htmlFor={inputId}>
            <span className="dropzone-icon"><Icon name="upload" size={24} /></span>
            <span><strong>Tarik file ke sini atau pilih file</strong><small>{rule.label}{multiple ? " · Beberapa file diperbolehkan" : " · 1 file per proses"}</small></span>
          </label>
        )}
        <input
          ref={inputRef}
          className="visually-hidden"
          id={inputId}
          name="upload_file"
          type="file"
          accept={rule.extensions.join(",")}
          disabled={disabled}
          multiple={multiple}
          onChange={(event) => handleFiles(event.target.files)}
        />
      </div>
      {error ? <p className="field-error" role="alert"><Icon name="alert" size={16} /> {error}</p> : null}
    </div>
  );
}
